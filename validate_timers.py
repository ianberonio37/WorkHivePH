"""
Timer and Scheduled Job Hygiene Validator — WorkHive Platform
=============================================================
Timer leaks accumulate silently. After an hour-long shift on the live
board, dozens of ghost intervals can be running simultaneously.

  Layer 1 — setInterval hygiene
    1.  Interval handle stored      — every setInterval() result assigned to variable
    2.  Interval handle cleared     — every stored handle has clearInterval()  [WARN]
    3.  No interval in event handler — setInterval inside repeated events = timer storm

  Layer 2 — setTimeout hygiene
    4.  No setTimeout in loops      — setInterval/setTimeout in forEach/map/for = storm

  Layer 3 — Long-running timer UX
    5.  Visibility pause on long timers — pages with >=60s intervals should pause
                                          when tab is hidden (saves CPU, battery)

  Layer 4 — Scheduled jobs (pg_cron)
    6.  Cron handlers exist         — every pg_cron report_type has an edge fn handler

  Layer 5 — Scope
    7.  All timer pages in scope    — analytics.html and new pages included

Usage:  python validate_timers.py
Output: timers_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

MIGRATIONS_DIR   = os.path.join("supabase", "migrations")
FUNCTIONS_DIR    = os.path.join("supabase", "functions")
SCHEDULED_AGENTS = os.path.join(FUNCTIONS_DIR, "scheduled-agents", "index.ts")

LIVE_PAGES = [
    "logbook.html",
    "inventory.html",
    "pm-scheduler.html",
    "hive.html",
    "assistant.html",
    "skillmatrix.html",
    "dayplanner.html",
    "engineering-design.html",
    "analytics.html",
    "platform-health.html",
    "nav-hub.html",
    "report-sender.html",
    "community.html",
]

# Event types where spawning intervals is dangerous (fires repeatedly)
REPEATED_EVENT_TYPES = ["message", "data", "storage", "visibilitychange"]
DEBOUNCE_SAFE_EVENTS = {"resize", "scroll", "input", "keydown", "keyup", "mousemove"}

# Minimum interval duration (ms) to require visibilitychange pause
LONG_INTERVAL_MS = 60000


# ── Layer 1: setInterval hygiene ──────────────────────────────────────────────

def check_interval_stored(pages):
    issues = []
    for page in pages:
        content = read_file(page)
        if not content:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if "setInterval(" not in line:
                continue
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            is_stored = bool(re.search(
                r"(?:const|let|var)\s+\w+\s*=\s*setInterval\s*\("
                r"|^\s*\w[\w.[\]]*\s*=\s*setInterval\s*\(",
                line
            ))
            if not is_stored:
                issues.append({"check": "interval_stored", "page": page, "line": i + 1,
                               "reason": f"{page}:{i+1} setInterval() not stored — cannot be cancelled, leaks until tab closes: `{stripped[:60]}`"})
    return issues


def check_interval_cleared(pages):
    issues = []
    for page in pages:
        content = read_file(page)
        if not content:
            continue
        handles = set()
        for m in re.finditer(
            r"(?:const|let|var)\s+(\w+)\s*=\s*setInterval\s*\("
            r"|(?<!=\s)(\w[\w.[\]]*)\s*=\s*setInterval\s*\(",
            content
        ):
            name = m.group(1) or m.group(2)
            if name and name not in {"null", "undefined", "false"}:
                handles.add(name.split(".")[0])
        for handle in handles:
            if not re.search(rf"clearInterval\s*\(\s*{re.escape(handle)}\s*\)", content):
                issues.append({"check": "interval_cleared", "page": page, "handle": handle,
                               "skip": True,   # WARN — not always critical (page-level timers stop on unload)
                               "reason": f"{page} interval handle '{handle}' has no clearInterval({handle}) — leaks for the browser session"})
    return issues


def check_interval_in_event_handler(pages):
    issues = []
    for page in pages:
        content = read_file(page)
        if not content:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if "setInterval(" not in line or line.strip().startswith("//"):
                continue
            window = "\n".join(lines[max(0, i - 10):i + 1])
            for evt in REPEATED_EVENT_TYPES:
                if (f"'{evt}'" in window or f'"{evt}"' in window) and \
                   re.search(r"addEventListener|\.on\s*\(|\.subscribe\s*\(", window):
                    issues.append({"check": "interval_in_event", "page": page,
                                   "line": i + 1, "event": evt,
                                   "reason": f"{page}:{i+1} setInterval() inside '{evt}' event handler — each event spawns a new interval (timer storm)"})
                    break
    return issues


# ── Layer 2: setTimeout hygiene ───────────────────────────────────────────────

def check_timeout_in_loop(pages):
    """
    setTimeout (or setInterval) inside a forEach, map, or for loop creates
    N timers simultaneously — one per iteration.
    Exception: loops that exit immediately after the timer (return/break on
    the next 2 lines) create at most one timer and are safe.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if not content:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if not re.search(r"\b(setInterval|setTimeout)\s*\(", line):
                continue
            if line.strip().startswith("//"):
                continue
            # Look back 4 lines for a loop opener
            window_back = "\n".join(lines[max(0, i - 4):i])
            if not re.search(r"\bforEach\s*\(|\bfor\s*\(|\bfor\s+(?:const|let|var)\b|\bmap\s*\(", window_back):
                continue
            # Safe exception: timer is immediately followed by return/break (at most 1 timer created)
            window_after = "\n".join(lines[i + 1:min(len(lines), i + 3)])
            if re.search(r"^\s*return\b|^\s*break\b", window_after, re.MULTILINE):
                continue
            fn = "setInterval" if "setInterval" in line else "setTimeout"
            issues.append({"check": "timeout_in_loop", "page": page, "line": i + 1,
                           "reason": f"{page}:{i+1} {fn}() inside a loop — creates N timers simultaneously: `{line.strip()[:70]}`"})
    return issues


# ── Layer 3: Long-running timer UX ───────────────────────────────────────────

def check_visibility_pause(pages):
    """
    Pages with long-running intervals (>=60s) should pause when the tab is
    hidden and resume when visible. Without this, a worker who multitasks
    keeps the timer firing in the background, wasting CPU and battery.

    Required pattern near the interval:
      document.addEventListener('visibilitychange', ...)
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if not content:
            continue
        # Find all setInterval calls with a timeout >= LONG_INTERVAL_MS
        for m in re.finditer(r"setInterval\s*\([^,]+,\s*(\d+)\s*\)", content):
            interval_ms = int(m.group(1))
            if interval_ms < LONG_INTERVAL_MS:
                continue
            # Does this page have a visibilitychange listener?
            if not re.search(r"['\"]visibilitychange['\"]", content):
                line = content[:m.start()].count("\n") + 1
                issues.append({"check": "visibility_pause", "page": page, "line": line,
                               "interval_ms": interval_ms,
                               "skip": True,   # WARN — UX improvement, not a bug
                               "reason": f"{page}:{line} {interval_ms}ms interval has no visibilitychange handler — wastes CPU/battery when tab is hidden"})
                break   # one report per page
    return issues


# ── Layer 4: Scheduled jobs ───────────────────────────────────────────────────

def check_cron_handlers():
    issues = []
    if not os.path.isdir(MIGRATIONS_DIR):
        return [{"check": "cron_handlers", "page": MIGRATIONS_DIR,
                 "reason": f"{MIGRATIONS_DIR} not found"}]

    scheduled_types = []
    for fname in sorted(os.listdir(MIGRATIONS_DIR)):
        if not fname.endswith(".sql"):
            continue
        content = read_file(os.path.join(MIGRATIONS_DIR, fname))
        if not content:
            continue
        no_comments = re.sub(r"/\*[\s\S]*?\*/", "", content)
        for m in re.finditer(r"cron\.schedule\s*\([^)]+\$\$([\s\S]+?)\$\$", no_comments):
            rt_m = re.search(r'"report_type"\s*:\s*"([^"]+)"', m.group(1))
            if rt_m:
                scheduled_types.append((fname, rt_m.group(1)))

    if not scheduled_types:
        return []

    agent_content = read_file(SCHEDULED_AGENTS)
    if not agent_content:
        return [{"check": "cron_handlers", "page": SCHEDULED_AGENTS,
                 "reason": f"{SCHEDULED_AGENTS} not found — cannot verify cron handlers"}]

    for migration, report_type in scheduled_types:
        if not re.search(rf"['\"]?{re.escape(report_type)}['\"]?\s*:", agent_content):
            issues.append({"check": "cron_handlers", "page": SCHEDULED_AGENTS,
                           "report_type": report_type, "migration": migration,
                           "reason": f"cron job in {migration} sends report_type='{report_type}' but no handler in scheduled-agents — fails silently in production"})
    return issues


# ── Layer 5: Scope ────────────────────────────────────────────────────────────

def check_pages_in_scope():
    import glob
    live_set = set(LIVE_PAGES)
    issues   = []
    for path in glob.glob("*.html") + glob.glob("*.js"):
        fname = os.path.basename(path)
        if fname in live_set:
            continue
        if any(s in fname for s in ["-test", ".backup", "platform-health", "guardian",
                                     "parts-tracker", "symbol-gallery", "architecture"]):
            continue
        content = read_file(fname)
        if content and "setInterval(" in content:
            issues.append({"check": "pages_in_scope", "page": fname,
                           "reason": f"{fname} uses setInterval but is not in validate_timers.py LIVE_PAGES"})
    return issues


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    # L1
    "interval_stored", "interval_cleared", "interval_in_event",
    # L2
    "timeout_in_loop",
    # L3
    "visibility_pause",
    # L4
    "cron_handlers",
    # L5
    "pages_in_scope",
]

CHECK_LABELS = {
    # L1
    "interval_stored":    "L1  setInterval() result stored in named variable",
    "interval_cleared":   "L1  Every interval handle has clearInterval()  [WARN]",
    "interval_in_event":  "L1  No setInterval() inside repeated event handlers",
    # L2
    "timeout_in_loop":    "L2  No setTimeout/setInterval inside loops",
    # L3
    "visibility_pause":   "L3  Long-running intervals pause on visibilitychange  [WARN]",
    # L4
    "cron_handlers":      "L4  pg_cron report_types have matching edge fn handlers",
    # L5
    "pages_in_scope":     "L5  All timer-using pages in LIVE_PAGES",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nTimer and Scheduled Job Hygiene Validator (4-layer)"))
    print("=" * 55)

    all_issues = []
    all_issues += check_interval_stored(LIVE_PAGES)
    all_issues += check_interval_cleared(LIVE_PAGES)
    all_issues += check_interval_in_event_handler(LIVE_PAGES)
    all_issues += check_timeout_in_loop(LIVE_PAGES)
    all_issues += check_visibility_pause(LIVE_PAGES)
    all_issues += check_cron_handlers()
    all_issues += check_pages_in_scope()

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL — warnings are UX improvements\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "timers",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("timers_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
