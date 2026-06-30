"""
Auth Idle-Timeout LIVE proof — guardian wrapper (Arc I I2/A)
============================================================
session-timeout.js protects a shared tablet: idle → soft prompt → hard-clear +
sign-in redirect. The Arc I sweep scored I2/A as `proof` (the file exists) — this
wrapper upgrades it to `live` by actually DRIVING the sequence in a real browser
(tests/idle-timeout.spec.ts, via the production-safe window.WH_IDLE_TIMEOUT_OVERRIDE
clock-seam) against the live Flask seeder origin. No DB/model.

Mirrors validate_voice_router_oracle.py: runs ONLY the idle-timeout spec via a
relative `node` invocation (the repo path's '&' breaks npx), parses the JSON
reporter, exits 0/1. Skips gracefully if the seeder or the JS toolchain is absent
(so it never blocks CI when the env can't run a browser test).

Exit 0 = idle→prompt→hard-clear proven live (or skipped, env absent). Exit 1 = a
real regression in the shared-device timeout.

Usage:  python validate_auth_idle_timeout_live.py
Output: auth_idle_timeout_live_report.json

Skills: qa (timer-UI integration test), security + mobile-maestro (shared-tablet
hand-off), platform-guardian (parseable, graceful skip).
"""
import json
import os
import subprocess
import sys
import urllib.request

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SPEC = "idle-timeout"
SPEC_FILE = os.path.join("tests", "idle-timeout.spec.ts")
SEAM_FILE = "session-timeout.js"
PW_CLI = os.path.join("node_modules", "@playwright", "test", "cli.js")
SEEDER = "http://127.0.0.1:5000/"
REPORT = "auth_idle_timeout_live_report.json"
RUN_TIMEOUT = 180


def _skip(reason: str) -> int:
    print(f"\033[93m  SKIP  {reason}\033[0m")
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump({"validator": "auth_idle_timeout_live", "skipped": True,
                   "reason": reason, "passed": 0, "failed": 0}, f, indent=2)
    return 0


def _seeder_up() -> bool:
    try:
        urllib.request.urlopen(SEEDER, timeout=4)
        return True
    except Exception:
        return False


def main() -> int:
    print("\033[1m\nAuth Idle-Timeout LIVE proof (Arc I I2/A)\033[0m")
    print("=" * 55)

    if not os.path.exists(SEAM_FILE) or not os.path.exists(SPEC_FILE):
        print(f"\033[91m  FAIL  {SEAM_FILE} or {SPEC_FILE} missing\033[0m")
        with open(REPORT, "w", encoding="utf-8") as f:
            json.dump({"validator": "auth_idle_timeout_live", "passed": 0, "failed": 1,
                       "reason": "seam/spec missing"}, f, indent=2)
        return 1
    if not os.path.exists(PW_CLI):
        return _skip(f"{PW_CLI} not found — run `npm install`")
    if not _seeder_up():
        return _skip("Flask seeder (127.0.0.1:5000) down — idle-timeout needs a real origin")

    cmd = ["node", PW_CLI, "test", SPEC, "--reporter=json"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=RUN_TIMEOUT)
    except subprocess.TimeoutExpired:
        print("\033[91m  FAIL  idle-timeout run timed out\033[0m")
        with open(REPORT, "w", encoding="utf-8") as f:
            json.dump({"validator": "auth_idle_timeout_live", "passed": 0, "failed": 1,
                       "reason": "timeout"}, f, indent=2)
        return 1
    except FileNotFoundError:
        return _skip("node not on PATH")

    passed = failed = 0
    try:
        out = proc.stdout
        brace = out.find("{")
        if brace >= 0:
            data = json.loads(out[brace:])
            stats = data.get("stats", {})
            passed = stats.get("expected", 0)
            failed = stats.get("unexpected", 0) + stats.get("flaky", 0)
    except (json.JSONDecodeError, ValueError):
        failed = 0 if proc.returncode == 0 else 1

    total = passed + failed
    if failed == 0 and passed > 0:
        print(f"\033[92m  PASS  {passed}/{total} idle-timeout sequence proofs (live)\033[0m")
    elif failed == 0 and proc.returncode == 0:
        print("\033[92m  PASS  idle-timeout ran clean\033[0m")
    else:
        print(f"\033[91m  FAIL  {passed} pass / {failed} fail — shared-device timeout broke\033[0m")
        print((proc.stdout or "")[-500:])

    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump({"validator": "auth_idle_timeout_live", "passed": passed,
                   "failed": failed, "total": total, "returncode": proc.returncode}, f, indent=2)
    return 1 if (failed > 0 or proc.returncode != 0) else 0


if __name__ == "__main__":
    sys.exit(main())
