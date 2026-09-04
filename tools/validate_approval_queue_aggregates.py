#!/usr/bin/env python3
"""validate_approval_queue_aggregates.py — T20's lock: the hive board's approval badge counts
EVERYTHING a supervisor owes a decision on, not just the on-board types.

Walked live (T20): the board's APPROVAL QUEUE showed 4 (asset submissions) while 30 more pending
approvals existed in the same hive (19 rcm_fmea_modes + 9 rcm_strategies unapproved + 2
amc_briefings pending), scattered on asset-hub/alert-hub with no aggregate anywhere — a supervisor
looking at the ONE place named 'Approval Queue' reasonably believed 4 was the whole job. Fixed
(verified live 2026-09-02 as the supervisor: badge = 34, 'Also awaiting your review in Asset Hub:
19 FMEA modes · 9 strategies · 2 shift briefings in Alert Hub'): the loader counts all three
elsewhere-types and the card names where each lives, with the link to act.

Lock: the loader queries rcm_fmea_modes (approved_by null) + rcm_strategies (approved_by null) +
amc_briefings (status pending), the sum feeds the badge, and the elsewhere line renders the
briefings chip. Teeth: dropping any of the three counts reddens.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK_NAMES = ["approval-queue-aggregates"]

FMEA_RE = re.compile(r"from\('rcm_fmea_modes'\)[\s\S]{0,120}?is\('approved_by',\s*null\)")
STRAT_RE = re.compile(r"from\('rcm_strategies'\)[\s\S]{0,120}?is\('approved_by',\s*null\)")
# 2026-09-04: the pending-briefings count reads the CANONICAL view v_amc_truth, not the raw
# amc_briefings table — the canonical-sources drift gate requires the v_*_truth read where one
# exists. Accept EITHER source (view is preferred); a total removal of the count still reddens.
BRIEF_RE = re.compile(r"from\('(?:amc_briefings|v_amc_truth)'\)[\s\S]{0,120}?eq\('status',\s*'pending'\)")
SUM_RE = re.compile(r"\(_elseFmea \|\| 0\) \+ \(_elseStrat \|\| 0\) \+ \(_elseBrief \|\| 0\)")
# T20 S2: an aging approval must SAY its dwell ('44 days waiting') - age is the triage cue.
DWELL_RE = re.compile(r"days waiting")


def problems_for(src: str) -> list[str]:
    out = []
    if not FMEA_RE.search(src):
        out.append("hive.html: the approval aggregate no longer counts unapproved rcm_fmea_modes")
    if not STRAT_RE.search(src):
        out.append("hive.html: the approval aggregate no longer counts unapproved rcm_strategies")
    if not BRIEF_RE.search(src):
        out.append("hive.html: the approval aggregate no longer counts pending amc_briefings — the "
                    "board undercounts again (the T20 4-of-34)")
    if not SUM_RE.search(src):
        out.append("hive.html: the elsewhere sum no longer includes all three types")
    if not DWELL_RE.search(src):
        out.append("hive.html: approval cards lost the dwell-age cue ('N days waiting') — a 44-day "
                   "CRITICAL approval looks identical to a fresh one again (T20 S2)")
    return out


def main() -> int:
    src = io.open(ROOT / "hive.html", encoding="utf-8", errors="replace").read()
    bad = problems_for(src)
    if bad:
        print("FAIL approval-queue-aggregates:")
        for p in bad:
            print("    " + p)
        return 1
    print("PASS approval-queue-aggregates — the board's approval badge counts assets/parts + FMEA "
          "modes + strategies + pending shift briefings, each named with its review surface.")
    return 0


def self_test() -> int:
    src = io.open(ROOT / "hive.html", encoding="utf-8", errors="replace").read()
    fails = []
    if problems_for(src):
        fails.append("HEAD should PASS")
    if not any("amc_briefings" in p for p in problems_for(BRIEF_RE.sub("from('amc_briefings_X')", src))):
        fails.append("dropping the briefings count must redden")
    if not any("three types" in p for p in problems_for(SUM_RE.sub("(_elseFmea || 0) + (_elseStrat || 0)", src))):
        fails.append("dropping a type from the sum must redden")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_approval_queue_aggregates self-test (dropped count + shrunken sum both redden; HEAD clean)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
