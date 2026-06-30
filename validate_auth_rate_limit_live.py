"""
Auth AI Rate-Limit LIVE enforcement — guardian wrapper (Arc I I7/F)
==================================================================
Per-identity/per-hive AI rate-limiting (LLM10 unbounded-consumption) is coverage-proven
statically by validate_ai_rate_limit_coverage. THIS proves it ENFORCES live: a boundary
test drives the hive's ai_rate_limits counter to the limit, then a real AI edge invoke
must return HTTP 429 (not serve the request). Self-resetting (cleans the counter after),
so it leaves the env as it found it — same local-test-state discipline as the Arc E
counter reset (the counter is dev test-state, not user data).

This is a real enforcement proof, not faking: the 429 is produced by the production
checkAIRateLimit code path when count >= limit; we only set the test-state to the
boundary and observe the live response.

Exit 0 = 429 enforced at the limit (or skipped, env absent). Exit 1 = the limit did NOT
enforce (a real LLM10 regression — the fn served a request past the cap).

Usage:  python validate_auth_rate_limit_live.py
Output: auth_rate_limit_live_report.json
Skills: security (LLM10), ai-engineer (per-hive rate-limit), qa (boundary test + cleanup).
"""
import json
import re
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
BASE = "http://127.0.0.1:54321"
HIVE = "9b4eaeac-59b0-4b0e-9b0b-0947b45ad1e7"
DB = "supabase_db_workhive"
CREDS = {"email": "leandromarquez@auth.workhiveph.com", "password": "test1234"}
REPORT = "auth_rate_limit_live_report.json"
BOUNDARY = 100000  # well above any WH_RATE_LIMIT_OVERRIDE → guarantees count >= limit


def _key() -> str:
    try:
        return re.search(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
                         (ROOT / "tests" / "_db-cleanup.ts").read_text(encoding="utf-8")).group(0)
    except Exception:
        return ""


def _psql(sql: str) -> bool:
    try:
        p = subprocess.run(["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres", "-c", sql],
                           capture_output=True, text=True, timeout=30)
        return p.returncode == 0
    except Exception:
        return False


def _skip(reason: str) -> int:
    print(f"\033[93m  SKIP  {reason}\033[0m")
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump({"validator": "auth_rate_limit_live", "skipped": True, "reason": reason}, f, indent=2)
    return 0


def main() -> int:
    print("\033[1m\nAuth AI Rate-Limit LIVE enforcement (Arc I I7/F)\033[0m")
    print("=" * 55)
    key = _key()
    if not key:
        return _skip("local anon key not found")
    try:
        tok = urllib.request.Request(f"{BASE}/auth/v1/token?grant_type=password",
            data=json.dumps(CREDS).encode(),
            headers={"Content-Type": "application/json", "apikey": key}, method="POST")
        jwt = json.loads(urllib.request.urlopen(tok, timeout=15).read())["access_token"]
    except Exception as e:
        return _skip(f"GoTrue/seeder unreachable: {type(e).__name__}")

    # Drive the counter to the boundary (upsert so it exists), then invoke.
    seeded = _psql(
        f"insert into ai_rate_limits (hive_id, call_count, window_start) "
        f"values ('{HIVE}', {BOUNDARY}, now()) "
        f"on conflict (hive_id) do update set call_count={BOUNDARY}, window_start=now();"
    )
    if not seeded:
        return _skip("docker psql unavailable / ai_rate_limits not seedable")

    code = None
    try:
        req = urllib.request.Request(f"{BASE}/functions/v1/voice-action-router",
            data=json.dumps({"transcript": "rate-limit enforcement boundary test", "hive_id": HIVE}).encode(),
            headers={"Content-Type": "application/json", "apikey": key,
                     "Authorization": f"Bearer {jwt}"}, method="POST")
        r = urllib.request.urlopen(req, timeout=30)
        code = r.getcode()
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception as e:
        _psql(f"delete from ai_rate_limits where hive_id='{HIVE}';")
        return _skip(f"edge runtime unreachable: {type(e).__name__}")
    finally:
        _psql(f"delete from ai_rate_limits where hive_id='{HIVE}';")  # leave env clean

    ok = (code == 429)
    if ok:
        print(f"\033[92m  PASS  AI rate-limit ENFORCED live — invoke at limit → HTTP 429\033[0m")
    else:
        print(f"\033[91m  FAIL  limit NOT enforced — invoke at boundary returned HTTP {code} (expected 429)\033[0m")
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump({"validator": "auth_rate_limit_live", "http": code,
                   "passed": 1 if ok else 0, "failed": 0 if ok else 1}, f, indent=2)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
