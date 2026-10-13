#!/usr/bin/env python3
"""slow-hint-reads-only - the page-wide "still loading" notice is for READS, and names no cause it cannot know.

Found 2026-10-06 walking shift-brain.html as an assistive-tech user (LXP153), with a HEALTHY stack: a polite live
region announced "The connection is slow - still loading. Nothing is lost." and held it past 93 seconds over a plan
that had finished rendering at ~20s. Two defects, both in shared code, and nothing guarded either:

  1. utils.js _timeoutFetch reference-counts every request through the supabase client and shows the notice until
     the LAST one settles - and an edge-function call went through the same counter. analytics-orchestrator, a
     background ENRICHMENT whose caller keeps the stored brief as "the instant fallback", ran to the 45s transport
     cap and held the page-wide notice the whole time. An AI compose is slow by design; it is not a read.
  2. offline-banner.js said "the connection is slow", but whSlowRead.show() returns early unless navigator.onLine
     is TRUE - so the cause was never measured, and on that walk the network was fine.

This gate holds both, on the SOURCE (comments stripped, so prose cannot satisfy it):
  A. _timeoutFetch derives a /functions/v1/ test from the request, skips the in-flight increment AND the slow timer
     for it, and _clearSlow returns early for it (an uncounted request must never be uncounted).
  B. the slow notice's English text does not assert a connection cause.

  python tools/validate_slow_hint_reads_only.py           # PASS / FAIL
  python tools/validate_slow_hint_reads_only.py --teeth   # proves each clause can FAIL on a reverted copy
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UTILS = ROOT / "utils.js"
BANNER = ROOT / "offline-banner.js"


def _strip_js_comments(src: str) -> str:
    """Remove /* */ blocks and WHOLE-LINE // comments. Deliberately not a full tokenizer: the first version was,
    and it was not regex-literal aware - in `/\\/functions\\/v1\\//` the escaped slash before the closing slash reads
    as `//`, so it deleted the very line this gate checks and failed on correct code. Trailing comments after code
    are kept; harmless, because every pattern below is code-shaped (an assignment, an `if`, a call), never prose."""
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join("" if re.match(r"\s*//", ln) else ln for ln in src.split("\n"))


def check(utils_src: str, banner_src: str) -> list[str]:
    problems = []
    u = _strip_js_comments(utils_src)
    m = re.search(r"const\s+SLOW_HINT_MS\s*=.*?const\s+_clearSlow\s*=\s*\(\)\s*=>\s*\{(.*?)\n\s*\};", u, re.S)
    if not m:
        return ["_timeoutFetch's slow-hint block (SLOW_HINT_MS ... _clearSlow) was not found in utils.js"]
    block = m.group(0)
    fn_test = re.search(r"const\s+(\w+)\s*=\s*/\\/functions\\/v1\\//\.test\(", block)
    if not fn_test:
        return ["A: _timeoutFetch no longer tells an edge-function call from a read (/functions/v1/ test missing)"]
    flag = fn_test.group(1)
    if not re.search(r"if\s*\(\s*!\s*%s\s*\)\s*window\.__whInFlight\s*=" % flag, block):
        problems.append("A: an edge-function call is still COUNTED as an in-flight read")
    if not re.search(r"const\s+slowT\s*=\s*%s\s*\?\s*0\s*:\s*setTimeout" % flag, block):
        problems.append("A: an edge-function call still arms the slow-notice timer")
    if not re.search(r"if\s*\(\s*%s\s*\)\s*return" % flag, m.group(1)):
        problems.append("A: _clearSlow uncounts an edge-function call it never counted")
    b = _strip_js_comments(banner_src)
    sm = re.search(r"show\(\s*'slow'\s*,\s*_tt\(\s*'([^']*)'", b)
    if not sm:
        problems.append("B: the slow notice's text was not found in offline-banner.js")
    elif re.search(r"connection", sm.group(1), re.I):
        problems.append(f"B: the slow notice names a cause it never measured: {sm.group(1)!r}")
    return problems


def main() -> int:
    u = UTILS.read_text(encoding="utf-8", errors="ignore")
    b = BANNER.read_text(encoding="utf-8", errors="ignore")
    if "--teeth" in sys.argv:
        fails = []
        reverted_a = re.sub(r"if\s*\(\s*!\s*_isFn\s*\)\s*(window\.__whInFlight)", r"\1", u, count=1)
        if not check(reverted_a, b):
            fails.append("clause A did not fail when the in-flight guard was removed")
        reverted_b = re.sub(r"(show\(\s*'slow'\s*,\s*_tt\(\s*')[^']*'", r"\1The connection is slow - still loading.'", b, count=1)
        if not check(u, reverted_b):
            fails.append("clause B did not fail when the connection wording came back")
        if fails:
            print("FAIL slow-hint-reads-only --teeth: " + "; ".join(fails))
            return 1
        print("PASS slow-hint-reads-only --teeth: each clause fails on a reverted copy")
        return 0
    problems = check(u, b)
    if problems:
        print("FAIL slow-hint-reads-only - " + "; ".join(problems))
        return 1
    print("PASS slow-hint-reads-only - edge-function calls neither raise nor hold the page-wide 'still loading' "
          "notice, and the notice names no cause it never measured")
    return 0


if __name__ == "__main__":
    sys.exit(main())
