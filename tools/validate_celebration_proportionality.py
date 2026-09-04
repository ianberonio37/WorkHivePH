#!/usr/bin/env python3
"""celebration-proportionality - T182: two celebration ladders must not collide (2026-08-28).

WorkHive celebrates progression on TWO independent ladders that live in DIFFERENT FILES:

    utils.js          ACHIEVEMENT_TIERS   iron/bronze/silver/gold/platinum/legend, by `min` level
    achievements.html handleLevelUp()     a round-number milestone every Nth level

Both raise the same full-screen modal. Neither file can see the other's ladder, and that is
exactly how they drifted: the tiers began at 11/26/51/76/91 and the milestones fired on
25/50/75 - each milestone sitting EXACTLY ONE LEVEL BELOW a tier boundary. The three most
significant moments in the whole progression (bronze->silver, silver->gold, gold->platinum)
each delivered TWO full-screen modals on consecutive level-ups: "Level 25!" then "Tier Up!".

A celebration that fires twice in a row is not twice the celebration - it is an interruption,
and it devalues the bigger of the two events. The fix let the round number step aside when a
tier-up is one level away; this gate holds that resolution against the drift that caused it.

★WHY A GATE AND NOT A COMMENT: the collision is invisible from inside either file. Editing a
tier `min` in utils.js - a plausible, innocent balance change - can silently re-create a
back-to-back pair in a page the editor never opened. This is the cross-file invariant a
reviewer cannot hold in their head, which is the whole reason it is worth a prover.

THE ASSERTIONS, over the simulated ladder:
    1. no two CONSECUTIVE levels both raise the full-screen modal
    2. every tier boundary still raises one (the tier-up must never be suppressed)
    3. modals stay RARE - at most one level in eight over the simulated range

Both ladders are read from source, so the gate measures the shipped configuration rather than
a copy of it.

Usage: python tools/validate_celebration_proportionality.py
"""
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
MAX_LEVEL = 120
RARITY_FLOOR = 8  # at most one modal per this many levels


def read_tiers(src: str):
    """The `min` of every ACHIEVEMENT_TIERS entry, as shipped."""
    m = re.search(r"ACHIEVEMENT_TIERS\s*=\s*\[(.*?)\]\s*;", src, re.S)
    if not m:
        return None
    mins = [int(x) for x in re.findall(r"\bmin\s*:\s*(\d+)", m.group(1))]
    return sorted(set(mins)) or None


def read_milestone_divisor(src: str):
    """The N of the round-number ladder, from the crossing check in handleLevelUp."""
    m = re.search(r"Math\.floor\(\s*newLevel\s*/\s*(\d+)\s*\)\s*>\s*Math\.floor\(", src)
    if m:
        return int(m.group(1))
    # the pre-fix exact-landing form, still worth simulating so the gate can indict it
    m = re.search(r"newLevel\s*%\s*(\d+)\s*===\s*0", src)
    return int(m.group(1)) if m else None


def read_suppression(src: str):
    """Which adjacent tier-ups make the round number step aside - ahead, behind, or both.

    ★THE SIMULATION MUST MODEL WHAT THE PAGE ACTUALLY DOES. If this reader claimed a
    suppression the code does not implement, the gate would pass a ladder that ships
    back-to-back modals - an oracle describing a page other than the one deployed.
    """
    return {
        "ahead": bool(re.search(r"getWorkerTier\(\s*newLevel\s*\+\s*1\s*\)", src)),
        "behind": bool(re.search(r"getWorkerTier\(\s*newLevel\s*-\s*1\s*\)", src)
                       and re.search(r"getWorkerTier\(\s*newLevel\s*-\s*2\s*\)", src)),
    }


def main() -> int:
    utils = ROOT / "utils.js"
    page = ROOT / "achievements.html"
    for f in (utils, page):
        if not f.exists():
            print(f"SKIP celebration-proportionality - {f.name} not found")
            return 0

    usrc = io.open(utils, encoding="utf-8", errors="replace").read()
    psrc = io.open(page, encoding="utf-8", errors="replace").read()

    tier_mins = read_tiers(usrc)
    divisor = read_milestone_divisor(psrc)
    suppresses = read_suppression(psrc)

    # ★A GATE THAT CANNOT READ ITS SUBJECT MUST FAIL, NOT PASS. If either ladder stops parsing,
    # the simulation below would silently measure a ladder of nothing and report a clean board.
    if not tier_mins or not divisor:
        print("FAIL celebration-proportionality - could not read both ladders from source "
              f"(tiers={tier_mins}, milestone divisor={divisor}). The gate cannot measure what "
              "it cannot parse; fix the reader rather than trusting the silence.")
        return 1

    def tier_of(level: int) -> int:
        return max((m for m in tier_mins if level >= m), default=tier_mins[0])

    def is_modal(old: int, new: int) -> str:
        if tier_of(new) != tier_of(old):
            return "tier"
        crossed = (new // divisor) > (old // divisor)
        blocked = ((suppresses["ahead"] and tier_of(new + 1) != tier_of(new))
                   or (suppresses["behind"] and tier_of(new - 1) != tier_of(new - 2)))
        if crossed and not blocked:
            return "milestone"
        return ""

    modal_levels = [lv for lv in range(1, MAX_LEVEL + 1) if is_modal(lv - 1, lv)]
    kinds = {lv: is_modal(lv - 1, lv) for lv in modal_levels}

    adjacent = [(a, b) for a, b in zip(modal_levels, modal_levels[1:]) if b == a + 1]
    boundaries = [m for m in tier_mins if m > 0]
    missing_tier = [m for m in boundaries if kinds.get(m) != "tier"]

    directions = ", ".join(d for d, on in suppresses.items() if on) or "NONE"
    print(f"  tier boundaries: {boundaries} | milestone every {divisor} "
          f"| adjacent-suppression: {directions}")
    print(f"  full-screen modals over levels 1-{MAX_LEVEL}: {len(modal_levels)} "
          f"({', '.join(f'{lv}:{kinds[lv]}' for lv in modal_levels)})")

    if missing_tier:
        print(f"FAIL celebration-proportionality - {len(missing_tier)} tier boundary(ies) raise no "
              f"modal: {missing_tier}")
        print("    A tier-up is the biggest moment on the ladder and must always be celebrated.")
        return 1

    if adjacent:
        print(f"FAIL celebration-proportionality - {len(adjacent)} back-to-back full-screen "
              f"modal pair(s): {adjacent}")
        print("    Two celebrations on consecutive level-ups is one interruption, not two")
        print("    rewards - and it devalues the larger of the pair. The round-number ladder")
        print(f"    (every {divisor}) and the tier ladder ({boundaries}) have drifted into")
        print("    adjacency; let the round number step aside when a tier-up is one level away.")
        return 1

    rarity = MAX_LEVEL / max(1, len(modal_levels))
    if rarity < RARITY_FLOOR:
        print(f"FAIL celebration-proportionality - modals fire every {rarity:.1f} levels, under "
              f"the 1-in-{RARITY_FLOOR} floor. Routine progress should whisper via the toast.")
        return 1

    print(f"PASS celebration-proportionality - {len(modal_levels)} full-screen moments over "
          f"{MAX_LEVEL} levels (one per {rarity:.0f}), none consecutive, every tier boundary kept.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
