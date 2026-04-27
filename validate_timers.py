"""
Timer and Scheduled Job Hygiene Validator — WorkHive Platform
=============================================================
WorkHive has timer-heavy pages (loading spinners, cooldown countdowns,
live board polling) and 6 pg_cron scheduled jobs running in Supabase.
A leaked timer costs nothing immediately — but after an hour-long shift
on the live board, dozens of ghost intervals accumulate in the browser.
A mis-wired cron job silently no-ops in production with no visible error.

Four things checked:

  1. setInterval return value stored
     — Every setInterval() call must assign the return value to a named
       variable. A bare setInterval(...) with no assignment cannot be
       cancelled. When the page component re-initialises (e.g. a hive
       board reload), a new interval spawns while the old one keeps firing.

  2. Every interval handle has a matching clearInterval
     — For every variable that holds a setInterval return value, confirm
       that clearInterval(that_variable) appears somewhere in the same
       file. If not, the interval runs until the browser tab closes.
       This matters most on single-page-style pages like hive.html where
       workers stay for an entire shift.

  3. No setInterval or setInterval inside a repeated event handler
     — Spawning a new timer on every click / every message / every
       Supabase Realtime event creates a "timer storm" — each interaction
       adds another background interval, all running simultaneously.
       Debounce timeouts (setTimeout inside resize/scroll handlers) are
       a known valid pattern and are excluded from this check.

  4. pg_cron scheduled jobs have matching edge function handlers
     — Every report_type sent by a cron.schedule() call in a migration
       file must have a handler registered in the scheduled-agents
       edge function. A cron job that calls a non-existent handler
       fails silently in Supabase — no error, no retry, no log entry
       (unless automation_log is checked manually).

Usage:  python validate_timers.py
Output: timers_report.json
"""
import re, json, sys, os

MIGRATIONS_DIR    = os.path.join("supabase", "migrations")
FUNCTIONS_DIR     = os.path.join("supabase", "functions")
SCHEDULED_AGENTS  = os.path.join(FUNCTIONS_DIR, "scheduled-agents", "index.ts")

# Pages to scan for browser timer issues
LIVE_PAGES = [
    "logbook.html",
    "inventory.html",
    "pm-scheduler.html",
    "hive.html",
    "assistant.html",
    "skillmatrix.html",
    "dayplanner.html",
    "engineering-design.html",
    "platform-health.html",   # Guardian dashboard — timer polling
    "nav-hub.html",
]

# Event listener types where spawning a new interval is dangerous
REPEATED_EVENT_TYPES = [
    "message", "data", "storage",
    "visibilitychange",
]

# Event types where setTimeout is a valid debounce/deferral (not a storm risk)
DEBOUNCE_SAFE_EVENTS = {
    "resize", "scroll", "input", "keydown", "keyup", "mousemove",
}


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


# ── Check 1: setInterval return value stored in a variable ───────────────────

def check_interval_stored(pages):
    """
    Every setInterval() call must store its return value so it can be
    cancelled later with clearInterval(). A bare setInterval() creates
    a timer that cannot be stopped — it runs until the browser tab closes.

    Safe pattern:   let timerId = setInterval(...);
    Unsafe pattern: setInterval(...);
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if "setInterval(" not in line:
                continue
            stripped = line.strip()
            # Skip comments
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            # Check if the return value is captured
            # Safe patterns: const/let/var X = setInterval, X = setInterval
            is_stored = bool(re.search(
                r"(?:const|let|var)\s+\w+\s*=\s*setInterval\s*\("
                r"|^\s*\w[\w.[\]]*\s*=\s*setInterval\s*\(",
                line
            ))
            if not is_stored:
                issues.append({
                    "page": page,
                    "line": i + 1,
                    "code": stripped[:80],
                    "reason": (
                        f"{page}:{i + 1} — setInterval() return value not stored "
                        f"— cannot be cancelled, timer leaks until tab closes: "
                        f"`{stripped[:60]}`"
                    ),
                })
    return issues


# ── Check 2: Every interval handle has a matching clearInterval ───────────────

def check_interval_cleared(pages):
    """
    Every variable that holds a setInterval handle must have a
    corresponding clearInterval(variable) call somewhere in the same file.

    If there is no clearInterval, the timer runs for the entire browser
    session — harmless for a 5-minute visit, costly on a full shift.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue

        # Find all stored interval handles
        handles = set()
        for m in re.finditer(
            r"(?:const|let|var)\s+(\w+)\s*=\s*setInterval\s*\("
            r"|(?<!=\s)(\w[\w.[\]]*)\s*=\s*setInterval\s*\(",
            content
        ):
            name = m.group(1) or m.group(2)
            if name and name not in {"null", "undefined", "false"}:
                handles.add(name.split(".")[0])  # strip property access

        for handle in handles:
            # Check if clearInterval is called with this handle anywhere in file
            if not re.search(
                rf"clearInterval\s*\(\s*{re.escape(handle)}\s*\)",
                content
            ):
                issues.append({
                    "page":   page,
                    "handle": handle,
                    "reason": (
                        f"{page} — interval handle '{handle}' has no matching "
                        f"clearInterval({handle}) — timer leaks for the entire "
                        f"browser session"
                    ),
                })
    return issues


# ── Check 3: No setInterval inside a repeated event handler ──────────────────

def check_timer_in_event_handler(pages):
    """
    Spawning a new setInterval inside an event handler that fires repeatedly
    creates a timer storm — each event adds another interval, all firing
    simultaneously. This is different from setTimeout which fires once.

    Dangerous example:
      db.channel('feed').on('INSERT', payload => {
        setInterval(refreshCard, 1000);  // new timer on every INSERT!
      });

    Safe: setTimeout inside resize/scroll is a valid debounce pattern.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()

        for i, line in enumerate(lines):
            if "setInterval(" not in line:
                continue
            stripped = line.strip()
            if stripped.startswith("//"):
                continue

            # Look back up to 10 lines for an event listener that fires repeatedly
            window = "\n".join(lines[max(0, i - 10):i + 1])
            for evt in REPEATED_EVENT_TYPES:
                if f"'{evt}'" in window or f'"{evt}"' in window:
                    # Verify it's an addEventListener pattern
                    if re.search(r"addEventListener|\.on\s*\(|\.subscribe\s*\(", window):
                        issues.append({
                            "page":  page,
                            "line":  i + 1,
                            "event": evt,
                            "reason": (
                                f"{page}:{i + 1} — setInterval() inside a "
                                f"'{evt}' event handler — each event fires "
                                f"spawns a new interval, creating a timer storm"
                            ),
                        })
                        break
    return issues


# ── Check 4: pg_cron report_types have matching edge function handlers ────────

def check_cron_handlers():
    """
    Every report_type sent by a cron.schedule() call must have a registered
    handler in the scheduled-agents edge function. A missing handler causes
    the cron job to fail silently — no error surface, no retry.

    Detection:
    1. Parse all migration files for active (non-commented) cron.schedule() calls
    2. Extract the report_type JSON field from each call body
    3. Confirm that string appears as a key in the runners dict in index.ts
    """
    issues = []

    # Step 1: collect all active cron schedule calls from migrations
    scheduled_types = []
    if not os.path.isdir(MIGRATIONS_DIR):
        return [{"page": MIGRATIONS_DIR, "reason": f"{MIGRATIONS_DIR} not found"}]

    for fname in sorted(os.listdir(MIGRATIONS_DIR)):
        if not fname.endswith(".sql"):
            continue
        content = read_file(os.path.join(MIGRATIONS_DIR, fname))
        if not content:
            continue

        # Strip block comments /* ... */ before searching
        no_comments = re.sub(r"/\*[\s\S]*?\*/", "", content)

        for m in re.finditer(
            r"cron\.schedule\s*\([^)]+\$\$([\s\S]+?)\$\$",
            no_comments
        ):
            body = m.group(1)
            # Extract report_type value from JSON body
            rt_m = re.search(r'"report_type"\s*:\s*"([^"]+)"', body)
            if rt_m:
                scheduled_types.append((fname, rt_m.group(1)))

    if not scheduled_types:
        return []   # No active cron jobs found — nothing to check

    # Step 2: read edge function handler registrations
    agent_content = read_file(SCHEDULED_AGENTS)
    if agent_content is None:
        return [{
            "page": SCHEDULED_AGENTS,
            "reason": f"{SCHEDULED_AGENTS} not found — cannot verify cron handlers"
        }]

    # Step 3: check each scheduled type has a handler
    for migration, report_type in scheduled_types:
        # Look for the type as a key in the runners dict
        if not re.search(
            rf"['\"]?{re.escape(report_type)}['\"]?\s*:",
            agent_content
        ):
            issues.append({
                "page":        SCHEDULED_AGENTS,
                "report_type": report_type,
                "migration":   migration,
                "reason": (
                    f"cron job in {migration} sends report_type='{report_type}' "
                    f"but no handler found in {SCHEDULED_AGENTS} — "
                    f"this job will fail silently in production"
                ),
            })
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("\n" + "=" * 70)
print("Timer and Scheduled Job Hygiene Validator")
print("=" * 70)

fail_count = 0
warn_count = 0
report     = {}

checks = [
    (
        "[1] setInterval return value stored in a named variable",
        check_interval_stored(LIVE_PAGES),
        "FAIL",
    ),
    (
        "[2] Every interval handle has a matching clearInterval",
        check_interval_cleared(LIVE_PAGES),
        "WARN",
    ),
    (
        "[3] No setInterval inside a repeated event handler",
        check_timer_in_event_handler(LIVE_PAGES),
        "FAIL",
    ),
    (
        "[4] pg_cron report_types have matching edge function handlers",
        check_cron_handlers(),
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

with open("timers_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved timers_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll timer hygiene checks PASS.")
