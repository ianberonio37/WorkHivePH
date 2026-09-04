#!/usr/bin/env python3
"""validate_draft_age_visible.py — T55's lock: a seller's pending-review draft states how long it
has waited.

Walked live (T55): listings sat 'Draft: Pending Review' for 43 and 71 days (P23,474 parked) with
no age indicator, no expectation, no reassurance — review latency was invisible to the seller.
Fixed (verified live 2026-09-02 on the exact walked listings: '43d waiting' / '71d waiting'):
the draft chip carries the wait ('Draft: Pending Review · Nd waiting'), deliberately with NO
invented SLA — only what is true. Lock: _draftChip computes the age from created_at and the
draft branch of the renderer uses it. Teeth: unwiring either shape reddens.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK_NAMES = ["draft-age-visible"]

CHIP_RE = re.compile(r"_draftChip[\s\S]{0,400}?d waiting")
WIRE_RE = re.compile(r"item\.status === 'draft' \? _draftChip\(item\)")


def problems_for(src: str) -> list[str]:
    out = []
    if not CHIP_RE.search(src):
        out.append("marketplace-seller.html: the draft age chip (_draftChip with 'Nd waiting') is gone — "
                   "review latency is invisible to the seller again (the T55 43/71-day silence)")
    if not WIRE_RE.search(src):
        out.append("marketplace-seller.html: the renderer's draft branch no longer uses _draftChip")
    return out


def main() -> int:
    src = io.open(ROOT / "marketplace-seller.html", encoding="utf-8", errors="replace").read()
    bad = problems_for(src)
    if bad:
        print("FAIL draft-age-visible:")
        for p in bad:
            print("    " + p)
        return 1
    print("PASS draft-age-visible — a pending-review draft states its wait ('Nd waiting'), no invented SLA.")
    return 0


def self_test() -> int:
    src = io.open(ROOT / "marketplace-seller.html", encoding="utf-8", errors="replace").read()
    fails = []
    if problems_for(src):
        fails.append("HEAD should PASS")
    if not any("gone" in p for p in problems_for(src.replace("d waiting", "d__X"))):
        fails.append("removing the age suffix must redden")
    if not any("draft branch" in p for p in problems_for(WIRE_RE.sub("item.status === 'draft' ? statusChip.draft", src))):
        fails.append("unwiring the draft branch must redden")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_draft_age_visible self-test (missing suffix + unwired branch both redden; HEAD clean)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
