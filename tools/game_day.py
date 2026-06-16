#!/usr/bin/env python3
"""game_day.py - Pillar DR (Delivery & Recovery): local game-day / chaos drills.
================================================================================
A game-day exercises how the system behaves UNDER stress / bad input - it asserts
the gateway FAILS SAFE (clean 4xx, gates hold, no 5xx crash, health recovers),
not that nothing ever errors. Runs against the LOCAL edge (:54321); SKIPs cleanly
if the edge is down (nothing to drill - that itself is reported).

Drills:
  D1 health_baseline    - the two front doors + key fns answer /health 200
  D2 graceful_badinput  - a malformed POST returns a 4xx, never a 5xx crash
  D3 auth_gate_holds    - a non-anon agent with NO auth returns 401 (not 500/leak)
  D4 unknown_route      - a bogus agent returns a clean 4xx (uniform contract)

Exit 0 = all drills passed (or SKIP, edge down); 1 = a drill failed (a real
fail-safe regression). Stdlib only; no deploy; reads no secrets.
"""
from __future__ import annotations
import io
import json
import sys
import urllib.error
import urllib.request

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

EDGE = "http://127.0.0.1:54321/functions/v1"
GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; BOLD = "\033[1m"; RESET = "\033[0m"


def _req(method: str, path: str, body: dict | None = None, timeout: float = 8.0):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{EDGE}{path}", data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(2000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(2000).decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001 - connection refused etc.
        return 0, str(e)


def edge_up() -> bool:
    status, _ = _req("GET", "/ai-gateway/health")
    return status == 200


def main() -> int:
    print(f"{BOLD}\nGAME-DAY DRILLS (Pillar DR) - local edge {EDGE}{RESET}")
    print("=" * 64)
    if not edge_up():
        print(f"{YEL}SKIP{RESET}: local edge not reachable - start it (docker) to run drills. "
              f"(A down edge is not a drill failure; nothing to exercise.)")
        return 0

    drills: list[tuple[str, bool, str]] = []

    # D1 - health baseline across the front doors + key fns
    fns = ["ai-gateway", "platform-gateway", "agentic-rag-loop", "voice-action-router", "asset-brain-query"]
    downs = [f for f in fns if _req("GET", f"/{f}/health")[0] != 200]
    drills.append(("D1 health_baseline", not downs,
                   "all up" if not downs else f"down: {', '.join(downs)}"))

    # D2 - malformed body must degrade to a 4xx, never a 5xx crash
    s2, _ = _req("POST", "/ai-gateway", None)  # no body
    s2b, _ = _req("POST", "/voice-action-router", {"garbage": True})  # missing required fields
    ok2 = (400 <= s2 < 500) and (400 <= s2b < 500)
    drills.append(("D2 graceful_badinput", ok2, f"ai-gateway={s2}, voice-action-router={s2b} (want 4xx, not 5xx)"))

    # D3 - non-anon agent without auth must be rejected with 401, not 500 or a leak
    s3, b3 = _req("POST", "/ai-gateway", {"agent": "assistant", "message": "hi"})
    ok3 = s3 == 401
    drills.append(("D3 auth_gate_holds", ok3, f"status={s3} ({'auth gate fired' if ok3 else b3[:80]})"))

    # D4 - unknown agent must be a clean 4xx (uniform routing contract), not a 5xx
    s4, _ = _req("POST", "/ai-gateway", {"agent": "no-such-agent-zzz", "message": "hi"})
    ok4 = 400 <= s4 < 500
    drills.append(("D4 unknown_route", ok4, f"status={s4} (want clean 4xx)"))

    for name, okk, detail in drills:
        print(f"  {(GREEN + 'PASS' + RESET) if okk else (RED + 'FAIL' + RESET)}  {name:<22} {detail}")

    failed = [n for n, okk, _ in drills if not okk]
    if failed:
        print(f"\n{RED}{BOLD}  GAME-DAY: FAIL{RESET} - fail-safe regression in: {', '.join(failed)}")
        return 1
    print(f"\n{GREEN}{BOLD}  GAME-DAY: PASS{RESET} - the gateway fails safe under bad input + holds its gates.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
