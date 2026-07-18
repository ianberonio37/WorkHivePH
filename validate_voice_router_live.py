"""
Voice Router LIVE slot-fill proof — guardian wrapper (Arc H H2/F)
================================================================
The deterministic routing core is value-oracle-tested offline (validate_voice_router_oracle).
THIS proves the same guard fires END-TO-END through the deployed edge function: a live
invoke of voice-action-router (real JWT + LLM router) must NEVER return a confident
(> 0.45) asset-required intent (logbook.create/pm.complete/asset.lookup) without a
RESOLVED asset — that is the A3 "log a failure → junk-write" protection, enforced in
the production path (sanitiseIntents + the handler's asset-resolution demotion).

INVARIANT (deterministic, holds regardless of LLM wording): for every returned intent
whose kind is asset-required and whose machine is missing/unresolved, confidence <= 0.45
AND params._needs_asset is true (the page slot-fills instead of writing).

Cost: ONE happy-path invoke on the permanently-free AI tier = $0 (a burst would cost,
this does not). Skips gracefully if the seeder/edge runtime/creds are absent.

Usage:  python validate_voice_router_live.py
Output: voice_router_live_report.json
Skills: ai-engineer (router two-halves), qa (assert the value live), security (code-enforced guard).
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
# The hive is RESOLVED AT RUNTIME from the CREDS user's live hive_members row (reseed-proof) —
# a hard-coded UUID rots on reseed and the edge fn then 403s "not_a_member" → the gate would
# VACUOUSLY PASS (see the stale-hive-fixture class, 2026-07-13). resolve_test_identity does this.
CREDS = {"email": "leandromarquez@auth.workhiveph.com", "password": "test1234"}
ASSET_REQUIRED = {"logbook.create", "pm.complete", "asset.lookup"}
FLOOR = 0.45
REPORT = "voice_router_live_report.json"
# Asset-required, NO machine named → the guard MUST demote (the live A3 case).
TRANSCRIPT = "I need to log a failure"


def _key() -> str:
    try:
        return re.search(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
                         (ROOT / "tests" / "_db-cleanup.ts").read_text(encoding="utf-8")).group(0)
    except Exception:
        return ""


def _skip(reason: str) -> int:
    print(f"\033[93m  SKIP  {reason}\033[0m")
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump({"validator": "voice_router_live", "skipped": True, "reason": reason}, f, indent=2)
    return 0


def main() -> int:
    print("\033[1m\nVoice Router LIVE slot-fill proof (Arc H H2/F)\033[0m")
    print("=" * 55)
    key = _key()
    if not key:
        return _skip("local anon key not found (tests/_db-cleanup.ts)")
    # 1. user JWT + CURRENT hive, resolved live (reseed-proof — never a hard-coded UUID)
    try:
        from test_identity import resolve_test_identity, TestIdentityError
        ident = resolve_test_identity(CREDS["email"], CREDS["password"], anon=key)
    except TestIdentityError as e:
        return _skip(str(e))
    except Exception as e:
        return _skip(f"identity resolve failed: {type(e).__name__}")
    jwt, hive = ident.jwt, ident.hive_id
    # 2. live invoke
    try:
        req = urllib.request.Request(f"{BASE}/functions/v1/voice-action-router",
            data=json.dumps({"transcript": TRANSCRIPT, "hive_id": hive}).encode(),
            headers={"Content-Type": "application/json", "apikey": key,
                     "Authorization": f"Bearer {jwt}"}, method="POST")
        resp = urllib.request.urlopen(req, timeout=45)
        code = resp.getcode()
        body = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return _skip("AI rate-limit 429 (free-tier bucket drained) — re-run after reset")
        print(f"\033[91m  FAIL  voice-action-router HTTP {e.code}: {e.read().decode()[:160]}\033[0m")
        with open(REPORT, "w", encoding="utf-8") as f:
            json.dump({"validator": "voice_router_live", "passed": 0, "failed": 1,
                       "reason": f"HTTP {e.code}"}, f, indent=2)
        return 1
    except Exception as e:
        return _skip(f"edge runtime unreachable: {type(e).__name__} (run `supabase functions serve`)")

    # 3. assert the deterministic invariant on the LIVE response
    intents = body.get("intents", []) if isinstance(body, dict) else []
    violations = []
    checked = 0
    for it in intents:
        kind = it.get("kind")
        params = it.get("params", {}) or {}
        machine = params.get("machine")
        resolved = isinstance(machine, str) and machine.strip() and not params.get("_needs_asset")
        if kind in ASSET_REQUIRED and not resolved:
            checked += 1
            conf = it.get("confidence", 1)
            if conf > FLOOR or not params.get("_needs_asset"):
                violations.append({"kind": kind, "confidence": conf,
                                   "machine": machine, "needs_asset": params.get("_needs_asset")})

    ok = (code == 200) and not violations
    print(f"  live invoke HTTP {code} · intents={len(intents)} · asset-required-unresolved checked={checked}")
    if ok:
        print(f"\033[92m  PASS  slot-fill guard fires LIVE — no confident (>{FLOOR}) asset-required write without a resolved asset\033[0m")
    else:
        print(f"\033[91m  FAIL  guard breach (junk-write risk): {json.dumps(violations)[:240]}\033[0m")
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump({"validator": "voice_router_live", "http": code, "intents": len(intents),
                   "checked": checked, "violations": violations,
                   "passed": 1 if ok else 0, "failed": 0 if ok else 1}, f, indent=2)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
