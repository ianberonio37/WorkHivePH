"""
WorkHive Platform Guardian — Phase 6b: Scheduled Runs
======================================================
Runs the Platform Guardian on a schedule without needing cron or Task Scheduler.
Works on Windows, Mac, and Linux. Runs as a background process.

Usage:
  python schedule_guardian.py                   # default: every 6 hours
  python schedule_guardian.py --interval 2h     # every 2 hours
  python schedule_guardian.py --interval 30m    # every 30 minutes
  python schedule_guardian.py --interval 1d     # once per day
  python schedule_guardian.py --once            # run once immediately, then exit
  python schedule_guardian.py --on-change       # run when platform files change

What it does each cycle:
  1. python run_platform_checks.py --fast
  2. python learn.py                   (capture new lessons)
  3. python autofix.py --dry-run       (detect fixable patterns, report only)
  4. Updates platform_health.json with schedule metadata
  5. Logs to schedule_guardian.log

Stop: Ctrl+C  (or kill the process)

Tip — run in background on Windows:
  start /B python schedule_guardian.py
"""
import subprocess, sys, os, json, time, datetime, hashlib, re
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PYTHON     = sys.executable
LOG_FILE   = "schedule_guardian.log"
HEALTH     = "platform_health.json"

# ── Parse interval ────────────────────────────────────────────────────────────
def parse_interval(s):
    """Parse '30m', '2h', '1d' into seconds."""
    s = s.strip().lower()
    if s.endswith('m'): return int(s[:-1]) * 60
    if s.endswith('h'): return int(s[:-1]) * 3600
    if s.endswith('d'): return int(s[:-1]) * 86400
    return int(s)  # raw seconds


interval_str = "6h"
for a in sys.argv:
    if a.startswith("--interval="):
        interval_str = a.split("=")[1]
    elif a.startswith("--interval") and sys.argv.index(a) + 1 < len(sys.argv):
        interval_str = sys.argv[sys.argv.index(a) + 1]

INTERVAL    = parse_interval(interval_str)
RUN_ONCE    = "--once" in sys.argv
ON_CHANGE   = "--on-change" in sys.argv

# Files to watch when --on-change
WATCH_FILES = [
    "engineering-design.html", "floating-ai.js",
    "logbook.html", "pm-scheduler.html", "inventory.html",
    "hive.html", "skillmatrix.html", "assistant.html",
    "python-api/calcs",   # directory
]

# ── Logging ───────────────────────────────────────────────────────────────────
def log(msg):
    ts   = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Strip ANSI colour codes for clean log output
    clean = re.sub(r'\x1b\[[0-9;]*m', '', msg)
    line  = f"[{ts}] {clean}"
    print(line.encode("utf-8", errors="replace").decode("utf-8", errors="replace"))
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run_cmd(cmd, label):
    log(f"Running: {label}")
    result = subprocess.run(
        [PYTHON] + cmd,
        capture_output=True, text=True,
        encoding="utf-8", errors="replace"
    )
    status = "PASS" if result.returncode == 0 else "FAIL"
    # Extract key result line from output
    for line in (result.stdout + result.stderr).splitlines():
        if any(w in line for w in ["PASS", "FAIL", "fixed", "written", "Result:"]):
            log(f"  {status} {label}: {line.strip()[:80]}")
            break
    else:
        log(f"  {status} {label}")
    return result.returncode


# ── File change detection ─────────────────────────────────────────────────────
def file_hash(path):
    try:
        if os.path.isdir(path):
            content = "".join(
                os.path.getmtime(os.path.join(r, f))
                for r, _, files in os.walk(path)
                for f in files if f.endswith(".py")
            )
            return hashlib.md5(str(content).encode()).hexdigest()
        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception:
        return ""


def platform_hash():
    return hashlib.md5(
        "".join(file_hash(f) for f in WATCH_FILES).encode()
    ).hexdigest()


# ── Update platform_health.json with schedule metadata ───────────────────────
def update_health_schedule(cycle, next_run_ts):
    try:
        with open(HEALTH) as f:
            health = json.load(f)
        health["schedule"] = {
            "interval":   interval_str,
            "cycle":      cycle,
            "last_run":   datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "next_run":   next_run_ts,
            "mode":       "on-change" if ON_CHANGE else "timer",
        }
        with open(HEALTH, "w") as f:
            json.dump(health, f, indent=2)
    except Exception:
        pass


# ── One run cycle ─────────────────────────────────────────────────────────────
def run_cycle(cycle_n):
    log(f"=== Cycle {cycle_n} starting ===")

    # 1. Validate
    rc1 = run_cmd(["run_platform_checks.py", "--fast"], "Guardian (fast)")

    # 2. Learn (only if there were changes)
    rc2 = run_cmd(["learn.py"], "Self-learn")

    # 3. Auto-fix detection (dry-run — report only, no writes)
    rc3 = run_cmd(["autofix.py", "--dry-run"], "Auto-fix scan")

    # 4. Improve (only every 10 cycles to avoid rate limits)
    if cycle_n % 10 == 0:
        log("Running improvement scan (every 10 cycles)...")
        run_cmd(["improve.py", "--fast"], "Improve")

    log(f"=== Cycle {cycle_n} complete  validator={'PASS' if rc1==0 else 'FAIL'} ===\n")
    return rc1


# ── Main loop ─────────────────────────────────────────────────────────────────
def main():
    print("\n" + "=" * 70)
    print("  WorkHive Platform Guardian — Scheduler")
    if RUN_ONCE:
        print("  Mode: single run, then exit")
    elif ON_CHANGE:
        print(f"  Mode: run on file change (polling every 30s)")
    else:
        print(f"  Mode: every {interval_str} ({INTERVAL}s)")
    print("  Stop with Ctrl+C")
    print("=" * 70 + "\n")

    log(f"Guardian scheduler started. Interval={interval_str}")

    cycle     = 0
    last_hash = platform_hash() if ON_CHANGE else None

    try:
        while True:
            if ON_CHANGE:
                # Poll for file changes
                current_hash = platform_hash()
                if current_hash != last_hash:
                    log("File change detected — running cycle")
                    last_hash = current_hash
                    cycle += 1
                    run_cycle(cycle)
                else:
                    time.sleep(30)
                    continue

                if RUN_ONCE:
                    break
                continue

            # Timer mode
            cycle += 1
            next_ts = (datetime.datetime.now() + datetime.timedelta(seconds=INTERVAL)).strftime("%Y-%m-%d %H:%M")
            run_cycle(cycle)
            update_health_schedule(cycle, next_ts)

            if RUN_ONCE:
                log("Single run complete. Exiting.")
                break

            log(f"Next run at {next_ts}. Sleeping {interval_str}...")
            time.sleep(INTERVAL)

    except KeyboardInterrupt:
        log("Guardian scheduler stopped by user.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
