#!/usr/bin/env python3
"""validate_board_covers_roster.py — every root page in the roster must be on the family rubric board.

Why this gate exists (2026-09-05, the P-program's biggest single finding): the family board graded
32 pages at mean 99 while TEN root pages sat outside its PAGES list — and their first rubric run
ever read mean 82 (validator-catalog 58): Poppins never loaded on four, a 1519px table scrolling
the whole page sideways, a 2.04:1 label, a 38x20 switch. Nothing was wrong with the ruler; the
pages simply were not under it. "A page outside the board is a page whose regressions are
invisible" — and the ★×16 shape applies: when the page roster grows, the board's page list must
grow in the same change, or coverage silently shrinks while the headline stays green.

The check is mechanical: substrate/reference/page_roster.json (kind == root) minus the PAGES array
in tools/family_rubric_sweep.mjs must be empty, except for an EXPLICIT, reasoned allowlist below.
A page can be excused only by name and with a reason — never by omission.

  (default)   run the check
  --self-test each rule must redden on a mutated input
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROSTER = ROOT / "substrate" / "reference" / "page_roster.json"
SWEEP = ROOT / "tools" / "family_rubric_sweep.mjs"

# Pages that the rubric board deliberately does NOT grade. Each needs a reason a reader can check.
ALLOWLIST = {
    # (none yet) — e.g. "some-page.html": "print-only artifact: the rubric grades it as a print doc elsewhere",
}


def board_pages(src: str) -> list[str]:
    m = re.search(r"const PAGES\s*=\s*\[(.*?)\];", src, re.S)
    if not m:
        return []
    return re.findall(r"'([^']+\.html)'", m.group(1))


def check(roster: dict, sweep_src: str) -> list[str]:
    root = [p["path"] for p in roster["pages"] if p.get("kind") == "root"]
    board = set(board_pages(sweep_src))
    if not board:
        return ["could not parse PAGES from tools/family_rubric_sweep.mjs"]
    problems = []
    for p in root:
        if p not in board and p not in ALLOWLIST:
            problems.append(f"{p}: in page_roster.json (root) but NOT on the family rubric board — "
                            "add it to PAGES in tools/family_rubric_sweep.mjs (or allowlist it here WITH a reason)")
    for p in ALLOWLIST:
        if p in board:
            problems.append(f"{p}: allowlisted as not-graded but IS on the board — drop the allowlist entry")
    return problems


def main() -> int:
    roster = json.loads(ROSTER.read_text(encoding="utf-8"))
    src = SWEEP.read_text(encoding="utf-8")
    problems = check(roster, src)
    root_n = sum(1 for p in roster["pages"] if p.get("kind") == "root")
    print(f"board-covers-roster: {root_n} root pages in the roster · {len(board_pages(src))} on the board · "
          f"{len(ALLOWLIST)} allowlisted")
    if problems:
        for p in problems[:12]:
            print(f"  FAIL {p}")
        return 1
    print("PASS board-covers-roster — every root page in the roster is graded by the family rubric board.")
    return 0


def self_test() -> int:
    roster = json.loads(ROSTER.read_text(encoding="utf-8"))
    src = SWEEP.read_text(encoding="utf-8")
    fails = []
    if check(roster, src):
        fails.append("live inputs should PASS (fix the board first)")
    # a new root page appears in the roster and nobody adds it to the board -> must redden
    m = json.loads(json.dumps(roster)); m["pages"].append({"path": "brand-new-console.html", "kind": "root"})
    if not any("brand-new-console.html" in p for p in check(m, src)):
        fails.append("a roster page missing from the board should FAIL")
    # a page removed from the board list -> must redden. Mutate INSIDE the PAGES block: the same
    # filename also appears earlier in PAGE_SETTLE/PAGE_QUERY, and a whole-file first-occurrence
    # replace hit that map instead and left the board entry standing (the self-test's own false green).
    victim = board_pages(src)[0]
    m = re.search(r"const PAGES\s*=\s*\[(.*?)\];", src, re.S)
    src2 = src[:m.start(1)] + m.group(1).replace(f"'{victim}',", "", 1) + src[m.end(1):]
    if not any(victim in p for p in check(roster, src2)):
        fails.append("a board page dropped from PAGES should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_board_covers_roster self-test (new roster page / dropped board page both redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
