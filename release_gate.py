"""WorkHive Release Gate.

Runs the full 3-layer test suite before allowing a deploy.

Phases:
  Pre-flight  - Docker, local Supabase, Flask dashboard reachable?
  Phase 1     - Reset + reseed local DB (clean baseline)
  Phase 2     - Static validators (run_platform_checks.py --fast)
  Phase 3     - Data tests (test-data-seeder/run_tests.py)
  Phase 4     - UI tests (test-data-seeder/run_flows.py)
  Phase 4b    - AI Self-Improvement Loop (Playwright-driven, optional: --with-ai-deep)

PASS  -> writes .last-gate-pass with current commit SHA. Safe to push.
FAIL  -> exits 1. The git pre-push hook aborts the push.

Usage:
  python release_gate.py                  # full gate
  python release_gate.py --skip-ui        # skip Playwright (e.g., on a server without Chromium)
  python release_gate.py --no-seed        # use existing seeded data (faster iteration)
  python release_gate.py --with-ai-deep   # include AI self-improvement loop (all surfaces)
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

# ── Durable observability (close-the-loop fix, 2026-06-09) ──────────────────
# The Tester only kept a 200-line rolling in-memory buffer that was wiped on any
# Flask restart, and persist_run() silently no-op'd when its seeder-lib import
# failed — so a full Mega Gate run could finish (or get interrupted) leaving NO
# durable trace of what surfaced. These artefacts make every run inspectable
# regardless of Flask state. Asserted by validate_gate_observability.py (G0).
TMP_DIR = ROOT / ".tmp"
RUN_TS = datetime.now().strftime("%Y%m%d_%H%M%S")
GATE_LOG = TMP_DIR / f"mega_gate_{RUN_TS}.log"
VERDICT_FILE = TMP_DIR / "last_mega_gate_verdict.json"   # stable pointer to the latest run

# CLI flags
SKIP_UI = "--skip-ui" in sys.argv
NO_SESEED = "--no-seed" in sys.argv
WITH_AI = "--with-ai" in sys.argv
WITH_VISUAL = "--with-visual" in sys.argv
WITH_PERF = "--with-perf" in sys.argv
WITH_AI_DEEP = "--with-ai-deep" in sys.argv
WITH_BATTERY = "--with-battery" in sys.argv   # G3 UFAI battery ratchet (Mega Gate)


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
    # 2026-05-19: bumped timeout 5s → 15s. On a loaded Windows box with
    # many running containers, `docker ps` can take 6-10s — the old 5s
    # ceiling produced false-negative pre-flight FAILs even when Docker
    # was healthy (Supabase containers reachable in the very next check).
    try:
        r = subprocess.run(["docker", "ps"], capture_output=True, timeout=15)
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
    extras = []
    if WITH_AI: extras.append("AI Full")
    if WITH_VISUAL: extras.append("Visual")
    if WITH_PERF: extras.append("Perf")
    step("Phase 4: UI tests (Playwright)" + (f" + {' + '.join(extras)}" if extras else ""))
    cmd = [py_for(SEEDER), "run_flows.py"]
    if WITH_AI: cmd.append("--with-ai")
    if WITH_VISUAL: cmd.append("--with-visual")
    if WITH_PERF: cmd.append("--with-perf")
    rc, summary, lines = run_subprocess(cmd, cwd=SEEDER)
    return (rc == 0, {"summary": summary, "lines": lines})


def phase_ai_deep() -> tuple[bool, dict]:
    """Phase 4b: AI Self-Improvement Loop (Playwright-driven)."""
    if not WITH_AI_DEEP:
        return (True, {"summary": "skipped (no --with-ai-deep)", "lines": []})
    if not can_reach("127.0.0.1:5000"):
        warn("Skipping AI loop: Flask not running on :5000")
        return (True, {"summary": "skipped (no Flask)", "lines": []})

    # Pre-flight check: groq must be importable for the loop's analyze layer
    try:
        check = subprocess.run(
            [sys.executable, "-c", "from groq import Groq"],
            capture_output=True, timeout=10
        )
        if check.returncode != 0:
            warn("Skipping AI loop: groq not importable in {}".format(sys.executable))
            warn("Install with: {} -m pip install groq".format(sys.executable))
            return (True, {"summary": "skipped (no groq)", "lines": []})
    except Exception as e:
        warn(f"Skipping AI loop: groq preflight error: {e}")
        return (True, {"summary": "skipped (preflight failed)", "lines": []})

    step("Phase 4b: AI Self-Improvement Loop (Playwright + Groq)")
    rc, summary, lines = run_subprocess([sys.executable, "tools/ai_self_improvement_loop.py", "--fast"], cwd=ROOT)
    return (rc == 0, {"summary": summary, "lines": lines})


def phase_battery() -> tuple[bool, dict]:
    """Phase 5: G3 UFAI Battery family — forward-only ratchet (Mega Gate Rule B).

    Headless (~5s); compares against battery_family_baseline.json and exits 1
    only on a real regression (new undisposed candidate or a lost required
    component sub-part). Gated behind --with-battery so it runs in the Mega
    Gate but not the lighter Release Gate.
    """
    if not WITH_BATTERY:
        return (True, {"summary": "skipped (no --with-battery)", "lines": []})
    step("Phase 5: G3 UFAI Battery (run_battery_family.py --gate)")
    rc, summary, lines = run_subprocess(
        [sys.executable, "tools/run_battery_family.py", "--gate"], cwd=ROOT)
    return (rc == 0, {"summary": summary, "lines": lines})


# ── Verdict ───────────────────────────────────────────────────────────────

def get_head_sha() -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT, timeout=5)
        return r.stdout.strip() if r.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def parse_layer_summary(text: str) -> dict:
    """Extract pass/fail/warn from a summary line like 'Summary  62 pass · 0 warn · 0 fail'
    or platform_guardian's '54 PASS  0 FAIL  0 WARN  2 SKIP'."""
    if not text:
        return {"pass": 0, "fail": 0, "warn": 0}
    s = text.strip()
    # Pattern A: "62 pass · 0 warn · 0 fail" (test-data-seeder format)
    m = re.search(r"(\d+)\s*pass[^\d]+(\d+)\s*warn[^\d]+(\d+)\s*fail", s, re.IGNORECASE)
    if m:
        return {"pass": int(m.group(1)), "warn": int(m.group(2)), "fail": int(m.group(3))}
    # Pattern B: "54 PASS  0 FAIL  0 WARN  2 SKIP" (platform_guardian format)
    m = re.search(r"(\d+)\s*PASS[^\d]+(\d+)\s*FAIL[^\d]+(\d+)\s*WARN", s)
    if m:
        return {"pass": int(m.group(1)), "fail": int(m.group(2)), "warn": int(m.group(3))}
    return {"pass": 0, "fail": 0, "warn": 0}


class _Tee:
    """Mirror everything written to stdout into a durable log file too.

    Strips ANSI so the on-disk log is clean. Best-effort: a file error never
    breaks the gate (the console still works)."""
    def __init__(self, console, fh):
        self._console = console
        self._fh = fh

    def write(self, s):
        self._console.write(s)
        try:
            self._fh.write(ANSI_RE.sub("", s))
        except Exception:
            pass
        return len(s)

    def flush(self):
        self._console.flush()
        try:
            self._fh.flush()
        except Exception:
            pass


def install_durable_log():
    """Point stdout at a Tee writing to GATE_LOG. Returns the file handle."""
    try:
        TMP_DIR.mkdir(parents=True, exist_ok=True)
        fh = open(GATE_LOG, "w", encoding="utf-8", errors="replace")
        sys.stdout = _Tee(sys.stdout, fh)
        return fh
    except Exception as e:
        print(f"  WARN: could not open durable gate log ({e}); console-only this run")
        return None


def write_durable_verdict(verdict: str, layer_oks: dict, layer_results: dict):
    """Write a dependency-free verdict JSON that survives Flask restarts.

    This is the authoritative record the Tester's rolling buffer could not be.
    Independent of persist_run()'s fragile seeder-lib import (which silently
    no-op'd before) — so the verdict is ALWAYS persisted, PASS or BLOCK."""
    try:
        TMP_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "verdict": verdict,                      # "PASS" | "BLOCK"
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "commit": get_head_sha(),
            "flags": [a for a in sys.argv[1:] if a.startswith("--")],
            "layers": {
                name: {
                    "ok": bool(layer_oks.get(name)),
                    "summary": (layer_results.get(name) or {}).get("summary", ""),
                }
                for name in layer_results
            },
            "log": str(GATE_LOG),
        }
        VERDICT_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        ts_copy = TMP_DIR / f"mega_gate_verdict_{RUN_TS}.json"
        ts_copy.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nDurable verdict -> {VERDICT_FILE}")
        print(f"Durable log     -> {GATE_LOG}")
    except Exception as e:
        print(f"  WARN: could not write durable verdict ({e})")


def write_pass_marker(results: dict):
    sha = get_head_sha()
    LAST_PASS_FILE.write_text(json.dumps({
        "passed_at": datetime.now(timezone.utc).isoformat(),
        "commit": sha,
        "results": results,
    }, indent=2), encoding="utf-8")
    print(f"\nWrote .last-gate-pass for HEAD = {sha[:8]}")


def persist_run(verdict: str, layer_results: dict):
    """Compute health score, append to run_history.json, update streak.json."""
    sys.path.insert(0, str(SEEDER))
    try:
        from lib.health_score import compute_score, update_streak
        from lib.run_history import append_run, load_streak, save_streak
    except ImportError as e:
        print(f"  WARN: could not persist run history: {e}")
        return

    layers = {
        name: parse_layer_summary(layer_results.get(name, {}).get("summary", ""))
        for name in ("static", "data", "ui")
    }

    score_info = compute_score(layers)  # not stale on a fresh run
    sha = get_head_sha()
    now = datetime.now(timezone.utc)
    run_record = {
        "timestamp": now.isoformat(),
        "commit": sha,
        "commit_short": sha[:8],
        "verdict": verdict,
        "score": score_info["score"],
        "tier": score_info["tier"],
        "layers": layers,
        "flags": [a for a in sys.argv[1:] if a.startswith("--")],
    }
    append_run(run_record)

    streak = load_streak()
    streak = update_streak(streak, verdict, now.date().isoformat(),
                           commit=sha if verdict == "PASS" else None)
    save_streak(streak)

    print(f"  Score: {score_info['score']}/100 ({score_info['tier']})")
    if streak["current_streak"]:
        print(f"  Streak: {streak['current_streak']} day(s) (best: {streak['best_streak']})")
    elif streak.get("broken_at"):
        print(f"  Streak: broken (was {streak.get('broken_after_days', 0)} days)")


def main() -> int:
    _log_fh = install_durable_log()
    banner("WORKHIVE RELEASE GATE", "cyan")

    if not preflight():
        banner("GATE BLOCK — pre-flight failed", "red")
        print("Fix the pre-flight issues above, then re-run.")
        write_durable_verdict("BLOCK", {"preflight": False}, {"preflight": {"summary": "pre-flight failed"}})
        return 1

    print()
    if not phase_reseed():
        banner("GATE BLOCK — reseed failed", "red")
        write_durable_verdict("BLOCK", {"reseed": False}, {"reseed": {"summary": "reseed failed"}})
        return 1

    print()
    static_ok, static_res = phase_static()
    print()
    data_ok, data_res = phase_data()
    print()
    ui_ok, ui_res = phase_ui()
    print()
    ai_deep_ok, ai_deep_res = phase_ai_deep()
    print()
    battery_ok, battery_res = phase_battery()

    results = {"static": static_res, "data": data_res, "ui": ui_res, "ai_deep": ai_deep_res, "battery": battery_res}
    layer_oks = {"static": static_ok, "data": data_ok, "ui": ui_ok, "ai_deep": ai_deep_ok, "battery": battery_ok}
    all_pass = static_ok and data_ok and ui_ok and ai_deep_ok and battery_ok

    layer_results = {"static": static_res, "data": data_res, "ui": ui_res, "ai_deep": ai_deep_res, "battery": battery_res}

    if all_pass:
        banner("GATE PASS — safe to deploy", "green")
        for label, res in layer_results.items():
            print(f"  {label}: {res['summary'] or 'ok'}")
        write_pass_marker(results)
        # Durable record FIRST (dependency-free) so the verdict survives even if
        # persist_run's seeder-lib import fails — the gap this run exposed.
        write_durable_verdict("PASS", layer_oks, layer_results)
        persist_run("PASS", layer_results)
        return 0
    else:
        banner("GATE BLOCK — push aborted", "red")
        for label, res, passed in [
            ("static", static_res, static_ok),
            ("data", data_res, data_ok),
            ("ui", ui_res, ui_ok),
            ("ai_deep", ai_deep_res, ai_deep_ok),
            ("battery", battery_res, battery_ok),
        ]:
            mark = "PASS" if passed else "FAIL"
            print(f"  {label}: {mark} — {res['summary'] or '(no summary)'}")
        write_durable_verdict("BLOCK", layer_oks, layer_results)
        persist_run("BLOCK", layer_results)
        print("\nFix the failures above, then re-run.")
        print("To bypass (NOT recommended): git push --no-verify")
        return 1


if __name__ == "__main__":
    sys.exit(main())
