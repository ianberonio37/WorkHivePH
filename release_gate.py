"""WorkHive Release Gate.

Runs the full 3-layer test suite before allowing a deploy.

Phases:
  Pre-flight  - Docker, local Supabase, Flask dashboard reachable?
  Phase 1     - Reset + reseed local DB (clean baseline)
  Phase 2     - Static validators (run_platform_checks.py --fast)
  Phase 3     - Data tests (test-data-seeder/run_tests.py)
  Phase 4     - UI tests (test-data-seeder/run_flows.py)

PASS  -> writes .last-gate-pass with current commit SHA. Safe to push.
FAIL  -> exits 1. The git pre-push hook aborts the push.

Usage:
  python release_gate.py            # full gate
  python release_gate.py --skip-ui  # skip Playwright (e.g., on a server without Chromium)
  python release_gate.py --no-seed  # use existing seeded data (faster iteration)
"""
import io
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SEEDER = ROOT / "test-data-seeder"
SEEDER_PY = SEEDER / "venv" / "Scripts" / "python.exe"

# If we're not running inside the seeder venv, re-launch ourselves with it.
# This makes `python release_gate.py` work from a plain shell — no manual
# venv activation needed. The venv has supabase, playwright, etc.
# Using subprocess (not os.execv) because Windows execv doesn't quote args
# correctly when the script path contains spaces.
if SEEDER_PY.exists() and Path(sys.executable).resolve() != SEEDER_PY.resolve():
    rc = subprocess.run([str(SEEDER_PY), str(Path(__file__).resolve())] + sys.argv[1:]).returncode
    sys.exit(rc)

# Force UTF-8 console output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
LAST_PASS_FILE = ROOT / ".last-gate-pass"
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# CLI flags
SKIP_UI = "--skip-ui" in sys.argv
NO_SESEED = "--no-seed" in sys.argv


def py_for(path: Path) -> str:
    """Return the python interpreter to use for a script (venv if available)."""
    if SEEDER_PY.exists():
        return str(SEEDER_PY)
    return sys.executable


def banner(text, color="cyan"):
    bar = "=" * 64
    codes = {"cyan": "\033[96m", "green": "\033[92m", "red": "\033[91m", "yellow": "\033[93m"}
    c = codes.get(color, "")
    r = "\033[0m" if c else ""
    print(f"\n{c}{bar}{r}")
    print(f"{c}  {text}{r}")
    print(f"{c}{bar}{r}\n")


def step(text):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {text}")


def ok(text): print(f"  \033[92m✓\033[0m {text}")
def fail(text): print(f"  \033[91m✗\033[0m {text}")
def warn(text): print(f"  \033[93m⚠\033[0m {text}")


def can_reach(host_port: str, timeout=2) -> bool:
    host, port = host_port.split(":")
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except OSError:
        return False


def run_subprocess(args, cwd=None) -> tuple[int, str, list[str]]:
    """Run a subprocess; return (rc, summary_line, all_lines)."""
    proc = subprocess.Popen(
        args, cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
    )
    summary = ""
    lines = []
    SUMMARY_PATTERNS = ("Summary", "BLOCKED", "READY", "PASS", "FAIL", "pass ·", "PASS  ", "REGRESSIONS")
    for line in proc.stdout:
        clean = ANSI_RE.sub("", line.rstrip())
        if clean:
            print(f"    {clean}")
            lines.append(clean)
            # Capture the last line that looks like a summary
            stripped = clean.strip()
            if any(p in stripped for p in SUMMARY_PATTERNS) and len(stripped) < 120:
                summary = stripped
    proc.wait()
    return proc.returncode, summary, lines


# ── Pre-flight ────────────────────────────────────────────────────────────

def preflight() -> bool:
    step("Pre-flight checks")
    all_good = True

    # Docker
    try:
        r = subprocess.run(["docker", "ps"], capture_output=True, timeout=5)
        if r.returncode == 0:
            ok("Docker running")
        else:
            fail("Docker is not running. Open Docker Desktop, wait for whale to be solid, retry.")
            all_good = False
    except (FileNotFoundError, subprocess.TimeoutExpired):
        fail("Docker not found / not running")
        all_good = False

    # Local Supabase
    if can_reach("127.0.0.1:54321"):
        ok("Local Supabase reachable on 127.0.0.1:54321")
    else:
        fail("Local Supabase not running. Run: supabase start")
        all_good = False

    # Flask seeder (only needed for UI phase)
    if not SKIP_UI:
        if can_reach("127.0.0.1:5000"):
            ok("Flask seeder dashboard reachable on 127.0.0.1:5000")
        else:
            warn("Flask seeder not running on :5000 — UI phase will be skipped")
            warn("To include UI tests, double-click the WorkHive Tester desktop shortcut and re-run")

    return all_good


# ── Phases ────────────────────────────────────────────────────────────────

def phase_reseed() -> bool:
    if NO_SESEED:
        step("Phase 1: skipping reseed (--no-seed)")
        return True
    step("Phase 1: Reset + reseed (clean baseline)")

    # Import seeder modules directly — bypasses Flask's job lock when the gate
    # is launched from the dashboard button (since the gate IS the running job).
    sys.path.insert(0, str(SEEDER))
    try:
        from lib.supabase_client import get_client
        from seeders.reset import reset_all
        from seeders.orchestrator import seed_everything
    except ImportError as e:
        fail(f"Could not import seeder modules: {e}")
        fail("Run from inside test-data-seeder/venv (or via the dashboard button).")
        return False

    def log_msg(m: str):
        # Indent so it nests under the phase header
        print(f"    {m}")

    try:
        client = get_client()
        reset_all(client, log_msg)
        seed_everything(client, log_msg)
        ok("Database reset + reseeded cleanly")
        return True
    except Exception as e:
        fail(f"reseed failed: {type(e).__name__}: {e}")
        return False


def phase_static() -> tuple[bool, dict]:
    step("Phase 2: Static validators (Platform Guardian)")
    rc, summary, lines = run_subprocess([sys.executable, "run_platform_checks.py", "--fast"], cwd=ROOT)
    return (rc == 0, {"summary": summary, "lines": lines})


def phase_data() -> tuple[bool, dict]:
    step("Phase 3: Data tests (DB integrity)")
    rc, summary, lines = run_subprocess([py_for(SEEDER), "run_tests.py"], cwd=SEEDER)
    return (rc == 0, {"summary": summary, "lines": lines})


def phase_ui() -> tuple[bool, dict]:
    if SKIP_UI:
        step("Phase 4: UI tests (skipped, --skip-ui)")
        return (True, {"summary": "skipped", "lines": []})
    if not can_reach("127.0.0.1:5000"):
        warn("Skipping UI tests: Flask not running on :5000")
        return (True, {"summary": "skipped (no Flask)", "lines": []})
    step("Phase 4: UI tests (Playwright)")
    rc, summary, lines = run_subprocess([py_for(SEEDER), "run_flows.py"], cwd=SEEDER)
    return (rc == 0, {"summary": summary, "lines": lines})


# ── Verdict ───────────────────────────────────────────────────────────────

def get_head_sha() -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT, timeout=5)
        return r.stdout.strip() if r.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def write_pass_marker(results: dict):
    sha = get_head_sha()
    LAST_PASS_FILE.write_text(json.dumps({
        "passed_at": datetime.now(timezone.utc).isoformat(),
        "commit": sha,
        "results": results,
    }, indent=2), encoding="utf-8")
    print(f"\nWrote .last-gate-pass for HEAD = {sha[:8]}")


def main() -> int:
    banner("WORKHIVE RELEASE GATE", "cyan")

    if not preflight():
        banner("GATE BLOCK — pre-flight failed", "red")
        print("Fix the pre-flight issues above, then re-run.")
        return 1

    print()
    if not phase_reseed():
        banner("GATE BLOCK — reseed failed", "red")
        return 1

    print()
    static_ok, static_res = phase_static()
    print()
    data_ok, data_res = phase_data()
    print()
    ui_ok, ui_res = phase_ui()

    results = {"static": static_res, "data": data_res, "ui": ui_res}
    all_pass = static_ok and data_ok and ui_ok

    if all_pass:
        banner("GATE PASS — safe to deploy", "green")
        for label, res in [("static", static_res), ("data", data_res), ("ui", ui_res)]:
            print(f"  {label}: {res['summary'] or 'ok'}")
        write_pass_marker(results)
        return 0
    else:
        banner("GATE BLOCK — push aborted", "red")
        for label, res, passed in [
            ("static", static_res, static_ok),
            ("data", data_res, data_ok),
            ("ui", ui_res, ui_ok),
        ]:
            mark = "PASS" if passed else "FAIL"
            print(f"  {label}: {mark} — {res['summary'] or '(no summary)'}")
        print("\nFix the failures above, then re-run.")
        print("To bypass (NOT recommended): git push --no-verify")
        return 1


if __name__ == "__main__":
    sys.exit(main())
