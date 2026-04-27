"""
Observability Validator — WorkHive Platform
============================================
Checks that failures are visible — to the worker AND to developers.
"Observability" means: when something goes wrong, someone knows.

Without it:
  - A worker saves a logbook entry, sees "Saved!" but the inventory
    transaction silently failed — their parts balance is now wrong.
  - A developer refreshes the page and has no idea why the board didn't load.
  - A Supabase Realtime channel leaks memory because no one cleaned it up.

Four things checked:

  1. Realtime channel cleanup  — every page that opens a db.channel() must
                                 close all channels on window beforeunload.
                                 Leaked channels = memory buildup + ghost
                                 subscriptions consuming Supabase quota.

  2. Silent DB write failures  — error handlers on DB inserts/upserts that
                                 only call console.error (no showToast nearby)
                                 mean the worker has no idea a save failed.
                                 Checks a 4-line window after each error catch.

  3. Top-level init catch      — async functions called at page startup
                                 (DOMContentLoaded, window.onload) must have
                                 .catch() so init errors don't silently
                                 leave the page in a broken state.

  4. Critical ops have success toast — logbook save, PM completion, and
                                 skill exam save must confirm success to the
                                 worker with a showToast call so they know
                                 the action was recorded.

Usage:  python validate_observability.py
Output: observability_report.json
"""
import re, json, sys

# Pages to scan
LIVE_PAGES = [
    "logbook.html",
    "inventory.html",
    "pm-scheduler.html",
    "hive.html",
    "skillmatrix.html",
    "assistant.html",
    "dayplanner.html",
    "engineering-design.html",
]

# Pages that use Supabase Realtime — must have beforeunload cleanup
REALTIME_PAGES = ["hive.html"]

# Critical save functions: each must have a showToast confirming success.
# Format: (page, function_pattern, description)
CRITICAL_SAVES = [
    (
        "logbook.html",
        r"async function saveEntry\b|async function saveNew\b",
        "logbook save must confirm success to the worker via showToast",
    ),
    (
        "pm-scheduler.html",
        r"async function completeTask\b|markComplete\b",
        "PM completion must confirm success to the worker via showToast",
    ),
    (
        "skillmatrix.html",
        r"async function submitExam\b|submitExam\s*=",
        "skill exam submit must confirm result to the worker via showToast",
    ),
]


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


# ── Check 1: Realtime channel beforeunload cleanup ────────────────────────────

def check_realtime_cleanup(pages):
    """
    Every page that opens a Supabase Realtime channel must close all its
    channels when the user navigates away (window beforeunload event).
    Unclosed channels keep running server-side, consuming Supabase quota
    and triggering memory leaks in long-running browser sessions.

    Safe pattern:
      window.addEventListener('beforeunload', () => {
        db.removeChannel(myChannel);
      });
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue

        # Count channels opened
        channels_opened = re.findall(r"db\.channel\s*\(", content)
        if not channels_opened:
            continue   # page doesn't use realtime

        # Count removeChannel calls inside a beforeunload handler
        unload_m = re.search(
            r"addEventListener\s*\(\s*['\"]beforeunload['\"][\s\S]{0,1000}?removeChannel",
            content
        )
        if not unload_m:
            issues.append({
                "page":     page,
                "channels": len(channels_opened),
                "reason": (
                    f"{page} opens {len(channels_opened)} Supabase Realtime channel(s) "
                    f"but has no beforeunload listener calling removeChannel — "
                    f"channels leak on page navigation"
                ),
            })
        else:
            # Also count removeChannel calls in the unload section
            unload_block = content[unload_m.start():unload_m.start() + 600]
            removes = re.findall(r"removeChannel", unload_block)
            if len(removes) < len(channels_opened):
                issues.append({
                    "page":     page,
                    "opened":   len(channels_opened),
                    "removed":  len(removes),
                    "reason": (
                        f"{page} opens {len(channels_opened)} channel(s) but beforeunload "
                        f"only removes {len(removes)} — "
                        f"{len(channels_opened) - len(removes)} channel(s) may leak"
                    ),
                })
    return issues


# ── Check 2: Silent DB write failures ─────────────────────────────────────────

def check_silent_failures(pages):
    """
    Error handlers on DB writes that call console.error but NOT showToast
    within the next 4 lines are silent failures — the worker has no idea
    the save failed.

    Silent (bad):
      if (txnErr) console.error('txn insert:', txnErr.message);
      showToast('Entry updated.');    ← this toast is for a DIFFERENT operation

    Visible (good):
      if (txnErr) {
        console.error('txn insert:', txnErr.message);
        showToast('Transaction record failed: ' + txnErr.message);
      }
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()

        for i, line in enumerate(lines):
            # Is this line an error check on a DB write result?
            if not re.search(r"if\s*\(\s*\w*[Ee]rr\w*\b", line):
                continue
            if "console.error" not in line:
                continue
            # Is it a standalone one-liner (no block)?  e.g. if (err) console.error(...)
            if "{" in line:
                continue   # block form — showToast likely on next line, handled

            # Check the surrounding 4 lines for showToast
            window_start = max(0, i - 1)
            window_end   = min(len(lines), i + 4)
            window_text  = "\n".join(lines[window_start:window_end])

            if "showToast" not in window_text:
                issues.append({
                    "page": page,
                    "line": i + 1,
                    "code": line.strip()[:80],
                    "reason": (
                        f"{page}:{i + 1} — DB write error silently logged "
                        f"(no showToast within 4 lines): `{line.strip()[:60]}`"
                    ),
                })
    return issues


# ── Check 3: Top-level async init calls have catch handlers ───────────────────

def check_init_catches(pages):
    """
    Async functions called at page startup must have .catch() so that if
    initialisation fails (e.g. Supabase is unreachable), the error is
    visible rather than leaving the page silently broken.

    Risky pattern:
      document.addEventListener('DOMContentLoaded', () => {
        initApp();    ← async, no .catch()
      });

    Safe pattern:
      initApp().catch(err => showToast('Could not load: ' + err.message));
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue

        # Find async top-level init calls that lack .catch
        # Pattern: standalone function call at the start of a line (not inside a function body)
        # inside a DOMContentLoaded or similar boot block
        boot_m = re.search(
            r"addEventListener\s*\(\s*['\"]DOMContentLoaded['\"][\s\S]{0,2000}?\}\s*\)",
            content
        )
        if not boot_m:
            continue

        boot_block = boot_m.group(0)

        # Find async calls without .catch() in the boot block
        bare_calls = re.findall(
            r"^\s{2,8}(\w+)\s*\(\s*\)\s*;",   # indented call with no chained .catch
            boot_block, re.MULTILINE
        )
        for call in bare_calls:
            # Skip known sync helpers
            if call.lower() in {"return", "if", "else", "for", "while", "const", "let", "var"}:
                continue
            # Check if this function is defined as async in the same file
            if not re.search(rf"async function {re.escape(call)}\b", content):
                continue
            # Check if .catch is chained or try/catch wraps it
            call_pat = re.search(
                rf"\b{re.escape(call)}\s*\(\s*\)\s*[;.]",
                boot_block
            )
            if call_pat:
                snippet = boot_block[call_pat.start():call_pat.start() + 60]
                if ".catch" not in snippet and "try" not in boot_block[max(0, call_pat.start()-20):call_pat.start()]:
                    issues.append({
                        "page": page,
                        "call": call,
                        "reason": (
                            f"{page} — async init function `{call}()` called in "
                            f"DOMContentLoaded without .catch() — "
                            f"init errors will leave the page silently broken"
                        ),
                    })
    return issues


# ── Check 4: Critical saves confirm success to the worker ────────────────────

def check_success_feedback(saves):
    """
    Critical save operations must tell the worker the action was recorded.
    Without a success toast, the worker has no confirmation — they may
    submit twice, or leave thinking the save worked when it didn't.
    """
    issues = []
    for page, func_pattern, description in saves:
        content = read_file(page)
        if content is None:
            continue

        # Find the function body
        m = re.search(func_pattern, content)
        if not m:
            continue   # function not found — different name, skip

        # Extract function body (next 60 lines after declaration)
        start = m.start()
        lines = content[start:start + 3000].splitlines()[:60]
        body  = "\n".join(lines)

        if "showToast" not in body:
            issues.append({
                "page":   page,
                "reason": (
                    f"{page} — {description} — "
                    f"no showToast found in first 60 lines of the save function"
                ),
            })
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("\n" + "=" * 70)
print("Observability Validator")
print("=" * 70)

fail_count = 0
warn_count = 0
report     = {}

checks = [
    (
        "[1] Realtime channel beforeunload cleanup",
        check_realtime_cleanup(LIVE_PAGES),
        "FAIL",
    ),
    (
        "[2] No silent DB write failures (console.error without showToast)",
        check_silent_failures(LIVE_PAGES),
        "FAIL",
    ),
    (
        "[3] Top-level async init calls have .catch() handlers",
        check_init_catches(LIVE_PAGES),
        "WARN",
    ),
    (
        "[4] Critical saves confirm success to the worker (showToast)",
        check_success_feedback(CRITICAL_SAVES),
        "FAIL",
    ),
]

for label, issues, severity in checks:
    print(f"\n{label}\n")
    if not issues:
        print("  PASS")
    else:
        for iss in issues:
            print(f"  {severity}  {iss.get('page', '?')}")
            print(f"        {iss['reason']}")
        if severity == "FAIL":
            fail_count += len(issues)
        else:
            warn_count += len(issues)
    report[label] = issues

print(f"\n{'=' * 70}")
print(f"Result: {fail_count} FAIL  {warn_count} WARN")

with open("observability_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved observability_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll observability checks PASS.")
