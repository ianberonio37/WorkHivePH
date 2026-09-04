"""
Auth Function-Level Role-Guard LIVE — guardian wrapper (Arc I I4/A)
==================================================================
Function-level RBAC (not just UI-gating) is proven LIVE: a WORKER-role JWT invoking a
SUPERVISOR-ONLY edge function must be rejected 403. export-hive-data documents "Caller
MUST be an active SUPERVISOR ... Anonymous OR worker-role calls are rejected 403" — this
exercises that path with a real seeded worker (bryangarcia) against the live edge runtime.

Exit 0 = worker got 403 (role guard enforced) or skipped (env absent). Exit 1 = a worker
reached a supervisor-only function (a real privilege-escalation regression).

Usage:  python validate_auth_role_guard_live.py
Output: auth_role_guard_live_report.json
Skills: security (privilege escalation / function-level authz), multitenant-engineer (role gate).
"""
import json
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools" / "lib"))
BASE = "http://127.0.0.1:54321"
# ★NO PINNED HIVE UUID (2026-08-27). The id that sat here was reseeded away - and so was the id a
# previous session repointed it to, which is the whole argument: a hardcoded fixture hive rots at
# every reseed, and this gate would keep exiting 0 while posting a hive_id that no longer exists,
# so a 403 could be earned by the missing hive rather than by the ROLE GUARD it claims to prove.
# The worker's CURRENT hive comes from live hive_members via resolve_test_identity, which raises
# rather than let the gate pass vacuously.
WORKERS = ["bryangarcia", "wilfredomalabanan"]  # seeded worker-role members of the test hive
SUPERVISOR_ONLY_FN = "export-hive-data"
REPORT = "auth_role_guard_live_report.json"


def _key() -> str:
    try:
        return re.search(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
                         (ROOT / "tests" / "_db-cleanup.ts").read_text(encoding="utf-8")).group(0)
    except Exception:
        return ""


def _skip(reason: str) -> int:
    print(f"\033[93m  SKIP  {reason}\033[0m")
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump({"validator": "auth_role_guard_live", "skipped": True, "reason": reason}, f, indent=2)
    return 0


def _synth(u: str) -> str:
    return u.lower().replace(" ", "") + "@auth.workhiveph.com"


def main() -> int:
    print("\033[1m\nAuth Function-Level Role-Guard LIVE (Arc I I4/A)\033[0m")
    print("=" * 55)
    key = _key()
    if not key:
        return _skip("local anon key not found")

    try:
        from test_identity import resolve_test_identity, TestIdentityError
    except ImportError as e:
        return _skip(f"tools/lib/test_identity.py unavailable: {e}")

    jwt = used = hive = None
    why = "no seeded worker-role login available (test1234)"
    for w in WORKERS:
        try:
            ident = resolve_test_identity(_synth(w), "test1234", anon=key)
            jwt, used, hive = ident.jwt, w, ident.hive_id
            break
        except TestIdentityError as e:
            why = str(e)          # carries the real reason: bad login, or no ACTIVE membership
            continue
    if not jwt:
        return _skip(why)

    # Worker invokes the supervisor-only fn → must be 403.
    code = None
    try:
        req = urllib.request.Request(f"{BASE}/functions/v1/{SUPERVISOR_ONLY_FN}",
            data=json.dumps({"hive_id": hive}).encode(),
            headers={"Content-Type": "application/json", "apikey": key,
                     "Authorization": f"Bearer {jwt}"}, method="POST")
        r = urllib.request.urlopen(req, timeout=20)
        code = r.getcode()
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception as e:
        return _skip(f"edge runtime unreachable: {type(e).__name__}")

    ok = (code == 403)
    if ok:
        print(f"\033[92m  PASS  function-level role guard ENFORCED live — worker '{used}' -> HTTP 403 on {SUPERVISOR_ONLY_FN}\033[0m")
    else:
        print(f"\033[91m  FAIL  privilege escalation — worker '{used}' reached {SUPERVISOR_ONLY_FN}: HTTP {code} (expected 403)\033[0m")
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump({"validator": "auth_role_guard_live", "worker": used, "fn": SUPERVISOR_ONLY_FN,
                   "http": code, "passed": 1 if ok else 0, "failed": 0 if ok else 1}, f, indent=2)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
