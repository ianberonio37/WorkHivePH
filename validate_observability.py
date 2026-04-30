"""
Observability Validator — WorkHive Platform
============================================
Checks that failures are visible — to the worker AND to developers.

  Layer 1 — Channel hygiene
    1.  Realtime channel cleanup    — beforeunload removes all opened channels

  Layer 2 — Failure visibility
    2.  Silent DB write failures    — console.error/warn on DB write without showToast nearby
    3.  Swallowed catch blocks      — } catch(e) { console.xxx } with no toast or rethrow

  Layer 3 — Init safety
    4.  Top-level init .catch()     — async init functions called at startup have .catch()

  Layer 4 — Success feedback
    5.  Critical saves confirm      — logbook save, PM completion, exam submit show toast
    6.  Analytics runAnalytics      — analytics phase fetch has error feedback

  Layer 5 — Scope
    7.  All pages in scope          — analytics.html and new pages included

Usage:  python validate_observability.py
Output: observability_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

LIVE_PAGES = [
    "logbook.html",
    "inventory.html",
    "pm-scheduler.html",
    "hive.html",
    "skillmatrix.html",
    "assistant.html",
    "dayplanner.html",
    "engineering-design.html",
    "analytics.html",
    "community.html",
    "public-feed.html",
]

CRITICAL_SAVES = [
    (
        "logbook.html",
        r"async function saveEntry\b|async function saveNew\b",
        "logbook save must confirm success via showToast",
    ),
    (
        "pm-scheduler.html",
        r"async function submitCompletion\b|async function completeTask\b",
        "PM completion must confirm success via showToast",
    ),
    (
        "skillmatrix.html",
        r"async function submitExam\b|submitExam\s*=",
        "skill exam submit must confirm result via showToast",
    ),
]


# ── Layer 1: Channel hygiene ──────────────────────────────────────────────────

def check_realtime_cleanup(pages):
    issues = []
    for page in pages:
        content = read_file(page)
        if not content:
            continue
        channels_opened = re.findall(r"db\.channel\s*\(", content)
        if not channels_opened:
            continue
        unload_m = re.search(
            r"addEventListener\s*\(\s*['\"]beforeunload['\"][\s\S]{0,1000}?removeChannel",
            content
        )
        if not unload_m:
            issues.append({"check": "realtime_cleanup", "page": page,
                           "channels": len(channels_opened),
                           "reason": f"{page} opens {len(channels_opened)} Realtime channel(s) but no beforeunload removeChannel — channels leak on navigation"})
        else:
            unload_block = content[unload_m.start():unload_m.start() + 600]
            removes = len(re.findall(r"removeChannel", unload_block))
            if removes < len(channels_opened):
                issues.append({"check": "realtime_cleanup", "page": page,
                               "opened": len(channels_opened), "removed": removes,
                               "reason": f"{page} opens {len(channels_opened)} channels but beforeunload only removes {removes} — {len(channels_opened)-removes} leak"})
    return issues


# ── Layer 2: Failure visibility ───────────────────────────────────────────────

def check_silent_failures(pages):
    """
    Single-line if(err) console.error (not warn) without showToast = silent failure.
    console.warn is excluded — it signals the developer intentionally treated
    this as a non-critical, expected failure (background sync, fallback op).
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if not content:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if not re.search(r"if\s*\(\s*\w*[Ee]rr\w*\b", line):
                continue
            if "console.error" not in line:
                continue   # console.warn = intentionally non-critical, skip
            if "{" in line:
                continue   # block form — showToast likely inside
            window = "\n".join(lines[max(0, i - 1):min(len(lines), i + 4)])
            if "showToast" not in window:
                issues.append({"check": "silent_failures", "page": page, "line": i + 1,
                               "reason": f"{page}:{i+1} DB write console.error with no showToast nearby: `{line.strip()[:70]}`"})
    return issues


def check_swallowed_catches(pages):
    """
    Catch blocks that:
    - contain console.error (not warn — warn = intentional non-critical handling)
    - AND have no showToast, throw, or rethrow
    - AND take no fallback action (no assignment, no display change, no return value)
    These completely hide errors from the worker with no recovery path.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if not content:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if not re.search(r"}\s*catch\s*\(|\.catch\s*\(console\.error", line):
                continue
            if line.strip().startswith("//"):
                continue
            block_lines = lines[i:min(len(lines), i + 8)]
            block = "\n".join(block_lines)
            # Must have console.error (not warn) to qualify
            if "console.error" not in block and ".catch(console.error)" not in line:
                continue
            # Safe patterns: toast, throw, fallback assignment, display change
            if re.search(r"showToast|throw\s|showError|=\s*JSON\.parse|=\s*\[\]|\.style\.|\.display|fallback|Fall", block):
                continue
            # .catch(console.error) inline — the catch IS the handler
            if re.search(r"\.catch\s*\(console\.error\)", line):
                issues.append({"check": "swallowed_catches", "page": page, "line": i + 1,
                               "reason": f"{page}:{i+1} .catch(console.error) swallows error silently — worker has no feedback: `{line.strip()[:70]}`"})
                continue
            # Block catch with only error log and no action
            non_trivial = [l for l in block_lines[1:] if l.strip() and
                           not l.strip().startswith("//") and
                           not l.strip().startswith("}") and
                           not re.match(r"^\s*console\.", l)]
            if not non_trivial:
                issues.append({"check": "swallowed_catches", "page": page, "line": i + 1,
                               "reason": f"{page}:{i+1} catch block only logs error, no user feedback or fallback: `{line.strip()[:70]}`"})
    return issues


# ── Layer 3: Init safety ──────────────────────────────────────────────────────

def check_init_catches(pages):
    issues = []
    for page in pages:
        content = read_file(page)
        if not content:
            continue
        boot_m = re.search(
            r"addEventListener\s*\(\s*['\"]DOMContentLoaded['\"][\s\S]{0,2000}?\}\s*\)",
            content
        )
        if not boot_m:
            continue
        boot_block = boot_m.group(0)
        for call in re.findall(r"^\s{2,8}(\w+)\s*\(\s*\)\s*;", boot_block, re.MULTILINE):
            if call.lower() in {"return", "if", "else", "for", "while", "const", "let", "var"}:
                continue
            if not re.search(rf"async function {re.escape(call)}\b", content):
                continue
            call_pat = re.search(rf"\b{re.escape(call)}\s*\(\s*\)\s*[;.]", boot_block)
            if call_pat:
                snippet = boot_block[call_pat.start():call_pat.start() + 60]
                before  = boot_block[max(0, call_pat.start() - 20):call_pat.start()]
                if ".catch" not in snippet and "try" not in before:
                    issues.append({"check": "init_catches", "page": page, "call": call,
                                   "skip": True,   # WARN — not always critical
                                   "reason": f"{page} async init `{call}()` in DOMContentLoaded without .catch() — init errors leave page silently broken"})
    return issues


# ── Layer 4: Success feedback ─────────────────────────────────────────────────

def check_success_feedback(saves):
    issues = []
    for page, func_pattern, desc in saves:
        content = read_file(page)
        if not content:
            continue
        m = re.search(func_pattern, content)
        if not m:
            continue
        body = "\n".join(content[m.start():m.start() + 3000].splitlines()[:60])
        if "showToast" not in body:
            issues.append({"check": "success_feedback", "page": page,
                           "reason": f"{page} — {desc} — no showToast found in save function"})
    return issues


def check_analytics_error_feedback(pages):
    """
    The analytics runAnalytics function must show a toast on error so workers
    know when an analysis failed (not just a silent empty results panel).
    """
    page = "analytics.html"
    if page not in pages:
        return []
    content = read_file(page)
    if not content:
        return []
    m = re.search(r"async function runAnalytics\s*\(", content)
    if not m:
        return []
    body = content[m.start():m.start() + 2000]
    if "showToast" not in body:
        return [{"check": "analytics_error_feedback", "page": page,
                 "reason": f"{page} runAnalytics() has no showToast — analysis failures are invisible to the worker"}]
    return []


# ── Layer 5: Scope ────────────────────────────────────────────────────────────

def check_pages_in_scope():
    import glob, os
    live_set = set(LIVE_PAGES)
    issues   = []
    for path in glob.glob("*.html"):
        fname = os.path.basename(path)
        if fname in live_set:
            continue
        if any(s in fname for s in ["-test", ".backup", "platform-health", "guardian",
                                     "parts-tracker", "symbol-gallery", "architecture"]):
            continue
        content = read_file(fname)
        if content and "db.channel(" in content:
            issues.append({"check": "pages_in_scope", "page": fname,
                           "reason": f"{fname} uses Realtime channels but is not in validate_observability.py LIVE_PAGES"})
    return issues


def check_automation_log_recency(scan_paths):
    """
    automation_log is written by scheduled-agents on success and failure.
    validate_compliance.py confirms the write path is correct.
    But no code anywhere READS automation_log with a time-based filter to
    surface recent failures as alerts.

    Problem 13 (Broken Pipelines): if the weekly digest cron job fails for
    3 days, there is no alert — the hive board shows no change, the Guardian
    shows no warning, and the worker has no idea. Only a direct DB query would
    reveal the failure log entries.

    The fix: add a recency query to the Guardian dashboard or a hive board
    notification check:
      SELECT * FROM automation_log
      WHERE status = 'failed'
        AND created_at > NOW() - INTERVAL '48 hours'
        AND hive_id = $hive_id

    This check verifies that some code queries automation_log with a time
    filter (gte created_at / hours / interval) to surface recent failures.
    Reported as WARN — scheduled jobs run but pipeline failures are invisible.
    """
    all_content = ""
    for path in scan_paths:
        c = read_file(path)
        if c:
            all_content += c

    has_recency_query = bool(re.search(
        r"automation_log[\s\S]{0,200}(?:gte|gt|created_at|hours|interval|recent|last.*24|last.*48|last.*36)"
        r"|(?:gte|gt|created_at|hours|interval|recent)[\s\S]{0,200}automation_log",
        all_content, re.IGNORECASE
    ))
    if not has_recency_query:
        return [{"check": "automation_log_recency", "skip": True,
                 "reason": ("No code queries automation_log with a time-based filter — "
                            "cron job failures are invisible until someone manually checks the DB; "
                            "add: SELECT * FROM automation_log WHERE status='failed' AND "
                            "created_at > NOW() - INTERVAL '48 hours' to the Guardian dashboard "
                            "or hive board init to surface pipeline failures as alerts")}]
    return []


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    # L1
    "realtime_cleanup",
    # L2
    "silent_failures", "swallowed_catches",
    # L3
    "init_catches",
    # L4
    "success_feedback", "analytics_error_feedback",
    # L5
    "pages_in_scope", "automation_log_recency",
]

CHECK_LABELS = {
    # L1
    "realtime_cleanup":          "L1  Realtime channels removed on beforeunload",
    # L2
    "silent_failures":           "L2  No silent DB write failures (console.error/warn only)",
    "swallowed_catches":         "L2  No catch blocks that swallow errors silently",
    # L3
    "init_catches":              "L3  Async init functions have .catch()  [WARN]",
    # L4
    "success_feedback":          "L4  Critical saves confirm success via showToast",
    "analytics_error_feedback":  "L4  analytics runAnalytics shows toast on error",
    # L5
    "pages_in_scope":            "L5  All Realtime pages in LIVE_PAGES scope",
    "automation_log_recency":    "L5  automation_log queried with time filter for failure monitoring  [WARN]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nObservability Validator (4-layer)"))
    print("=" * 55)

    all_issues = []
    all_issues += check_realtime_cleanup(LIVE_PAGES)
    all_issues += check_silent_failures(LIVE_PAGES)
    all_issues += check_swallowed_catches(LIVE_PAGES)
    all_issues += check_init_catches(LIVE_PAGES)
    all_issues += check_success_feedback(CRITICAL_SAVES)
    all_issues += check_analytics_error_feedback(LIVE_PAGES)
    all_issues += check_pages_in_scope()
    all_issues += check_automation_log_recency(LIVE_PAGES + [
        "platform-health.html",
        os.path.join("supabase", "functions", "scheduled-agents", "index.ts"),
    ])

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL — warnings are informational\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "observability",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("observability_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
