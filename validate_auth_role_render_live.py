"""
Auth Role-Render LIVE proof — guardian wrapper (Arc I I4/U)
===========================================================
Role-gated UI (RBAC at the render layer) is proven LIVE by tests/journey-permissions.spec.ts:
a supervisor sees supervisor-only blocks (Plain-Read summary, Engagement card, Audit-Log link,
SUPERVISOR badge), a worker/unauthenticated visitor is gated/redirected. This upgrades the Arc I
I4/U cell from `proof` (the page references a membership check) to `live` (the gate actually
renders-or-hides per role against the real stack).

Mirrors validate_auth_idle_timeout_live.py: runs ONLY journey-permissions via a relative `node`
invocation, parses the JSON reporter, exits 0/1, skips gracefully if the seeder/JS toolchain is absent.

Usage:  python validate_auth_role_render_live.py
Output: auth_role_render_live_report.json
Skills: qa (role matrix, escalation-direction), multitenant-engineer (RBAC render), security.
"""
import json
import os
import subprocess
import sys
import urllib.request

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SPEC = "journey-permissions"
SPEC_FILE = os.path.join("tests", "journey-permissions.spec.ts")
PW_CLI = os.path.join("node_modules", "@playwright", "test", "cli.js")
SEEDER = "http://127.0.0.1:5000/"
REPORT = "auth_role_render_live_report.json"
RUN_TIMEOUT = 300  # role specs hit the live stack + JS init; generous ceiling


def _skip(reason: str) -> int:
    print(f"\033[93m  SKIP  {reason}\033[0m")
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump({"validator": "auth_role_render_live", "skipped": True, "reason": reason,
                   "passed": 0, "failed": 0}, f, indent=2)
    return 0


def main() -> int:
    print("\033[1m\nAuth Role-Render LIVE proof (Arc I I4/U)\033[0m")
    print("=" * 55)
    if not os.path.exists(SPEC_FILE):
        print(f"\033[91m  FAIL  {SPEC_FILE} missing\033[0m")
        with open(REPORT, "w", encoding="utf-8") as f:
            json.dump({"validator": "auth_role_render_live", "passed": 0, "failed": 1,
                       "reason": "spec missing"}, f, indent=2)
        return 1
    if not os.path.exists(PW_CLI):
        return _skip(f"{PW_CLI} not found — run `npm install`")
    try:
        urllib.request.urlopen(SEEDER, timeout=4)
    except Exception:
        return _skip("Flask seeder (127.0.0.1:5000) down — role-render needs the live stack")

    cmd = ["node", PW_CLI, "test", SPEC, "--reporter=json"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=RUN_TIMEOUT)
    except subprocess.TimeoutExpired:
        print("\033[91m  FAIL  role-render run timed out\033[0m")
        with open(REPORT, "w", encoding="utf-8") as f:
            json.dump({"validator": "auth_role_render_live", "passed": 0, "failed": 1,
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
        print(f"\033[92m  PASS  {passed}/{total} role-gated render proofs (live)\033[0m")
    elif failed == 0 and proc.returncode == 0:
        print("\033[92m  PASS  role-render ran clean\033[0m")
    else:
        print(f"\033[91m  FAIL  {passed} pass / {failed} fail — a role gate broke\033[0m")
        print((proc.stdout or "")[-500:])

    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump({"validator": "auth_role_render_live", "passed": passed,
                   "failed": failed, "total": total, "returncode": proc.returncode}, f, indent=2)
    return 1 if (failed > 0 or proc.returncode != 0) else 0


if __name__ == "__main__":
    sys.exit(main())
