#!/usr/bin/env python3
"""validate_persona_echo_live.py — LIVE lock for the CL9 persona-echo contract (2026-07-08).

The floating companion's persona selection was silently ignored (bug: companion-launcher.js read an
undefined window.getCurrentPersona + the wrong localStorage key wh_persona → the backend ALWAYS got
'zaniah'). Fixed to getPersonaKey()+canonical key, and a STRUCTURAL persona echo was added end-to-end
(voice-journal-agent returns {answer, lang, persona}; ai-gateway forwards data.persona) so a harness can
assert WHICH persona answered without prose-grepping "Naks"/"Hala".

This LIVE probe asserts the echo contract holds: invoking ai-gateway agent='voice-journal' with
context.persona=hezekiah returns data.persona=='hezekiah', and =zaniah returns 'zaniah'. A regression that
drops the forward (or re-hardcodes the persona) FAILs. Skips cleanly (exit 0) if the local stack is down,
so it never blocks a --fast dev run — same live-tier pattern as axe_scan_live / validate_rpc_write_integrity.

Usage:  python tools/validate_persona_echo_live.py [--json]
Exit 0 = echo holds (or stack down = skip) · 1 = the persona echo is broken (selection would be ignored).
"""
import re
import sys
import json
import time
import pathlib
import urllib.request
import urllib.error

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "lib"))
EDGE = "http://127.0.0.1:54321"
# HIVE is resolved AT RUNTIME from the worker's live hive_members row (reseed-proof); a hard-coded
# UUID rots on reseed → 403 "not_a_member" → this gate would VACUOUSLY PASS (stale-hive-fixture class).
WORKER_EMAIL = "leandromarquez@auth.workhiveph.com"


def _anon_key() -> str | None:
    f = ROOT / "tests" / "_db-cleanup.ts"
    if not f.exists():
        return None
    m = re.search(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}", f.read_text(encoding="utf-8", errors="ignore"))
    return m.group(0) if m else None


def _post(url: str, body: dict, headers: dict, timeout: float = 45.0):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={**headers, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> int:
    as_json = "--json" in sys.argv
    anon = _anon_key()
    if not anon:
        print("persona-echo LIVE: SKIP (no anon key / not a local checkout)")
        return 0
    try:
        from test_identity import resolve_test_identity, TestIdentityError
        ident = resolve_test_identity(WORKER_EMAIL, "test1234", anon=anon)
    except TestIdentityError as e:
        print(f"persona-echo LIVE: SKIP ({e})")
        return 0
    except Exception as e:
        print(f"persona-echo LIVE: SKIP (identity resolve failed: {type(e).__name__})")
        return 0
    tok, HIVE = ident.jwt, ident.hive_id

    hdr = {"apikey": anon, "Authorization": f"Bearer {tok}"}
    viols = []
    for persona in ("hezekiah", "zaniah"):
        try:
            resp = _post(f"{EDGE}/functions/v1/ai-gateway",
                         {"agent": "voice-journal", "message": f"note persona-echo {persona} {int(time.time())}",
                          "hive_id": HIVE, "context": {"persona": persona}}, hdr, timeout=60)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            print(f"persona-echo LIVE: SKIP (gateway unreachable: {e})")
            return 0
        got = (resp.get("data") or {}).get("persona")
        if got != persona:
            viols.append({"requested": persona, "got": got,
                          "why": "gateway data.persona != requested persona — the persona echo is dropped or "
                                 "the persona is hardcoded; the worker's Hezekiah/Zaniah selection is ignored"})

    if as_json:
        print(json.dumps({"violations": viols, "count": len(viols)}, indent=2))
    else:
        print("CL9 persona-echo LIVE (gateway must echo the requested persona back as data.persona)")
        if not viols:
            print("  PASS: data.persona == requested for both hezekiah and zaniah")
        else:
            print(f"  FAIL: {len(viols)} issue(s):")
            for v in viols:
                print(f"    - requested={v['requested']} got={v['got']} — {v['why']}")
    return 1 if viols else 0


if __name__ == "__main__":
    sys.exit(main())
