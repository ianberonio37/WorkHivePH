#!/usr/bin/env python3
"""validate_lowstock_marketplace_handoff.py — T30's lock instrument: the low-stock -> marketplace buy hop
CARRIES CONTEXT — 'Find on Marketplace' navigates to the parts section with the part number prefilled, so
a supervisor lands on the search already run, not an empty marketplace they must re-type into.

T30 verified the buy hop exists and carries context: the inventory low-stock card's 'Find on Marketplace'
goes to marketplace.html?section=parts&q=<part> with the part number seeded (encodeURIComponent). This gate
locks that the handoff keeps its query, so a future edit cannot degrade it to a context-less link that
drops the reader into an empty search — the 'a handoff must carry the full context' class.

Assertions on inventory.html (each refutable — see the self-test):
  1. THE AFFORDANCE EXISTS — a 'Find on Marketplace' control.
  2. THE HANDOFF CARRIES THE PART — navigation to marketplace.html with section=parts AND a q= built from
     encodeURIComponent (the part number seeded), not a bare marketplace link.

Read-only; no browser; no DB. Registered in run_platform_checks (Platform).
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "inventory.html"

CHECK_NAMES = ["lowstock-marketplace-handoff"]

_AFFORDANCE = re.compile(r"Find on Marketplace", re.I)
_HANDOFF = re.compile(r"""marketplace\.html\?section=parts&q=['"]?\s*\+\s*encodeURIComponent""", re.I)


def check(src: str) -> list[str]:
    problems: list[str] = []
    if not _AFFORDANCE.search(src):
        problems.append("no 'Find on Marketplace' affordance — the buy hop from a low-stock part is gone.")
    if not _HANDOFF.search(src):
        problems.append("the handoff does not carry the part: no marketplace.html?section=parts&q= built "
                        "with encodeURIComponent — the reader would land on an empty marketplace search.")
    return problems


def main() -> int:
    if not PAGE.exists():
        print("FAIL lowstock-marketplace-handoff: inventory.html not found"); return 1
    problems = check(PAGE.read_text(encoding="utf-8", errors="replace"))
    if problems:
        print("FAIL lowstock-marketplace-handoff — the low-stock->marketplace buy hop lost its context:")
        for p in problems:
            print(f"    {p}")
        return 1
    print("PASS lowstock-marketplace-handoff — 'Find on Marketplace' hands off to "
          "marketplace.html?section=parts&q=<part> with the part number seeded (encodeURIComponent).")
    return 0


def self_test() -> int:
    fails = []
    good = "<span>Find on Marketplace</span> ... location.href='marketplace.html?section=parts&q='+encodeURIComponent(q);"
    if check(good):
        fails.append("the real context-carrying handoff should PASS")
    if not any("affordance" in p for p in check("location.href='marketplace.html?section=parts&q='+encodeURIComponent(q);")):
        fails.append("missing the affordance should FAIL")
    if not any("carry the part" in p for p in check("<span>Find on Marketplace</span> location.href='marketplace.html';")):
        fails.append("a bare marketplace link (no q=) should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_lowstock_marketplace_handoff self-test (missing affordance / context-less link redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
