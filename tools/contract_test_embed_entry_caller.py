#!/usr/bin/env python3
"""contract_test_embed_entry_caller.py — C4 contract test for the saas→ai / utils.js→embed-entry seam.

WHY THIS SEAM (2026-09-03): utils.js gained whEmbedEntry — the shared fire-and-forget embed caller
with retry-once + a persisted localStorage queue + drain-on-load — and the seam miner rightly grew
the catalog by one. Rather than accept a higher uncovered floor, this pins the wire.

THE CONTRACT (both directions):
  caller SENDS   POST {SUPABASE_URL}/functions/v1/embed-entry
                 headers: Content-Type: application/json, apikey, Authorization: Bearer <token>
                 body: the payload object VERBATIM (whEmbedEntry(payload) forwards it untouched —
                 shaping belongs to the call sites, exactly like the pages that call the fn direct)
  caller READS   only response.ok / response.status (fire-and-forget: no body field is read, so
                 the fn's response SHAPE can evolve without breaking this caller)
  callee ACCEPTS a JSON body via req.json() and never requires a field the queue could not
                 replay (a queued payload is re-sent verbatim after a reload)
  durability     a failed send retries ONCE then lands in localStorage 'wh_embed_retry';
                 the drain re-calls whEmbedEntry(it.payload) — same wire, later.

USAGE:      python tools/contract_test_embed_entry_caller.py
Self-test:  python tools/contract_test_embed_entry_caller.py --selftest
Exit 0 = contract holds; 1 = the seam drifted.
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

if sys.platform == "win32" and (sys.stdout.encoding or "").lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")
G = "\033[92m"; R = "\033[91m"; X = "\033[0m"

ROOT = Path(__file__).resolve().parent.parent
UTILS = ROOT / "utils.js"
FN = ROOT / "supabase" / "functions" / "embed-entry" / "index.ts"


def check(utils_src: str, fn_src: str) -> list[str]:
    problems: list[str] = []
    m = re.search(r"function whEmbedEntry\b(.{0,2400})", utils_src, re.S)
    if not m:
        return ["utils.js no longer defines whEmbedEntry — the seam this pins is gone (update "
                "ai_seam_contracts.json if that is deliberate)"]
    body = m.group(1)
    if "/functions/v1/embed-entry" not in body:
        problems.append("whEmbedEntry no longer targets /functions/v1/embed-entry")
    if not re.search(r"Authorization.+Bearer", body):
        problems.append("whEmbedEntry dropped the Bearer Authorization header — verify_jwt callers break")
    if "apikey" not in body:
        problems.append("whEmbedEntry dropped the apikey header")
    if "JSON.stringify(payload)" not in body:
        problems.append("whEmbedEntry no longer forwards the payload VERBATIM — queued replays "
                        "and direct sends would diverge")
    if not re.search(r"\.ok\b|\.status\b", body):
        problems.append("whEmbedEntry no longer reads response.ok/status — failures become invisible "
                        "and the retry/queue path is dead code")
    if "wh_embed_retry" not in utils_src:
        problems.append("the wh_embed_retry persisted queue is gone from utils.js — a bad minute "
                        "silently loses exactly those entries (the write-only-index class)")
    if not re.search(r"req\.json\(\)", fn_src):
        problems.append("embed-entry/index.ts no longer reads a JSON body — every caller breaks")
    return problems


def main() -> int:
    utils_src = UTILS.read_text(encoding="utf-8", errors="replace")
    fn_src = FN.read_text(encoding="utf-8", errors="replace")
    problems = check(utils_src, fn_src)
    if problems:
        print(f"{R}FAIL{X} embed-entry caller seam drifted:")
        for p in problems:
            print("    " + p)
        return 1
    print(f"{G}PASS{X} embed-entry caller seam — whEmbedEntry sends the verbatim JSON payload with "
          "apikey+Bearer, reads only ok/status, and the wh_embed_retry queue replays the same wire.")
    return 0


def selftest() -> int:
    utils_src = UTILS.read_text(encoding="utf-8", errors="replace")
    fn_src = FN.read_text(encoding="utf-8", errors="replace")
    fails = []
    if check(utils_src, fn_src):
        fails.append("healthy tree should PASS")
    if not check(utils_src.replace("JSON.stringify(payload)", "JSON.stringify({wrapped: payload})"),
                 fn_src):
        fails.append("a re-shaped payload must FAIL")
    if not check(utils_src.replace("wh_embed_retry", "wh_gone_queue"), fn_src):
        fails.append("a removed queue must FAIL")
    if not check(utils_src, fn_src.replace("req.json()", "req.text()")):
        fails.append("a callee that stops reading JSON must FAIL")
    if fails:
        print(f"{R}SELF-TEST FAIL{X}: " + "; ".join(fails)); return 1
    print(f"{G}PASS{X} contract_test_embed_entry_caller self-test (re-shaped payload / removed queue "
          "/ non-JSON callee all redden)")
    return 0


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else main())
