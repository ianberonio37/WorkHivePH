#!/usr/bin/env python3
"""validate_embed_retry_queue.py — T10's AI4 lock: a failed RAG-index write retries and queues,
never silently vanishes.

Walked live (T10): embed-entry returned 500 on a PM save's logbook echo and the entry was SILENTLY
missing from the RAG index — console-only, no retry (the write-only-index class: the assistant's
recall quietly loses exactly the entries saved during a bad minute). Fixed 2026-09-02: utils.js
ships whEmbedEntry — one 2s-delayed retry, then the payload persists to wh_embed_retry (capped 20)
and a loader drains the queue on a later page load (7-day expiry; embedding is idempotent
server-side). Verified live BOTH halves: against the down edge runtime a call double-failed and
queued (payload recovered intact); with transport mocked ok the drain sent and did not re-queue.
pm-scheduler's fault-mirror (the walked site) routes through the helper.

Lock: helper (retry + queue + drain) in utils.js; the walked call site uses it. Teeth: each
reddens.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK_NAMES = ["embed-retry-queue"]

HELPER_RE = re.compile(r"async function whEmbedEntry\([\s\S]{0,1600}?wh_embed_retry")
DRAIN_RE = re.compile(r"_whDrainEmbedQueue[\s\S]{0,900}?whEmbedEntry\(it\.payload\)")
WIRE_RE = re.compile(r"await whEmbedEntry\(\{\s*\n?\s*type: 'fault'")


def problems_for(utils_src: str, pm_src: str) -> list[str]:
    out = []
    if not HELPER_RE.search(utils_src):
        out.append("utils.js: whEmbedEntry (retry + wh_embed_retry queue) is gone — a failed index "
                   "write silently vanishes again (the T10 write-only-index class)")
    if not DRAIN_RE.search(utils_src):
        out.append("utils.js: the wh_embed_retry drain loop is gone — queued entries never re-send")
    if not WIRE_RE.search(pm_src):
        out.append("pm-scheduler.html: the fault-mirror embed no longer routes through whEmbedEntry")
    return out


def main() -> int:
    u = io.open(ROOT / "utils.js", encoding="utf-8", errors="replace").read()
    p = io.open(ROOT / "pm-scheduler.html", encoding="utf-8", errors="replace").read()
    bad = problems_for(u, p)
    if bad:
        print("FAIL embed-retry-queue:")
        for x in bad:
            print("    " + x)
        return 1
    print("PASS embed-retry-queue — a failed embed retries once, queues persistently, and drains on "
          "a later load; the walked call site routes through the helper.")
    return 0


def self_test() -> int:
    u = io.open(ROOT / "utils.js", encoding="utf-8", errors="replace").read()
    p = io.open(ROOT / "pm-scheduler.html", encoding="utf-8", errors="replace").read()
    fails = []
    if problems_for(u, p):
        fails.append("HEAD should PASS")
    if not any("silently vanishes" in x for x in problems_for(u.replace("whEmbedEntry", "whEmbedEntryX"), p)):
        fails.append("removing the helper must redden")
    if not any("fault-mirror" in x for x in problems_for(u, WIRE_RE.sub("await fetch({ type: 'fault'", p))):
        fails.append("unwiring the call site must redden")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_embed_retry_queue self-test (missing helper + unwired site both redden; HEAD clean)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
