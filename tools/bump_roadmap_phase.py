#!/usr/bin/env python3
"""bump_roadmap_phase.py — auditable, evidence-gated ratchet of ONE phase column in the
PER_PAGE_BUGHUNT_ROADMAP scoreboard, recomputing each Page% (mean of 8) it changes.

Usage:  python tools/bump_roadmap_phase.py --phase P2 --from 75 --to 80 [--apply]
Only rows whose phase cell EXACTLY equals --from are bumped to --to (so it can't silently
inflate an already-higher cell). Dry-run by default: prints every change for review.
This is a SCORING tool — the caller is responsible for the evidence justifying --to
(here: the live page_battery verified P2's load rubric per-page). It does NOT invent evidence.
"""
import argparse
import re
import sys

ROADMAP = "PER_PAGE_BUGHUNT_ROADMAP.md"
PHASES = ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", required=True, choices=PHASES)
    ap.add_argument("--from", dest="frm", type=int, required=True)
    ap.add_argument("--to", type=int, required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    idx = PHASES.index(a.phase)

    with open(ROADMAP, encoding="utf-8") as f:
        lines = f.readlines()

    changed = []
    for i, line in enumerate(lines):
        if not line.startswith("| ") or "P1 Smoke" in line or "---" in line:
            continue
        if "RETIRED" in line or "n/a" in line:
            continue
        # cells: ['', ' name ', ' P1 ', ... ' P8 ', ' **NN** ', '']  (leading+trailing from split)
        parts = line.rstrip("\n").split("|")
        nums = [p for p in parts if p.strip().isdigit()]
        m = re.search(r"\*\*(\d+)\*\*", line)
        if len(nums) < 8 or not m:
            continue
        vals = [int(n.strip()) for n in nums[:8]]
        if vals[idx] != a.frm:
            continue
        vals[idx] = a.to
        newpct = round(sum(vals) / 8)
        # rebuild: replace the 8 numeric cells (in order) + the **pct**
        # find the positions of the 8 numeric cells in parts and overwrite
        cnt = 0
        for j, p in enumerate(parts):
            if p.strip().isdigit() and cnt < 8:
                width = len(p)
                parts[j] = f" {vals[cnt]} " if width >= 3 else f"{vals[cnt]}"
                cnt += 1
        newline = "|".join(parts)
        newline = re.sub(r"\*\*\d+\*\*", f"**{newpct}**", newline) + "\n"
        name = parts[1].strip()
        changed.append((name, a.frm, a.to, m.group(1), newpct))
        lines[i] = newline

    for name, frm, to, oldp, newp in changed:
        print(f"  {name}: {a.phase} {frm}->{to}  Page% {oldp}->{newp}")
    print(f"\n{len(changed)} row(s) {'APPLIED' if a.apply else 'would change (dry-run)'}")

    if a.apply and changed:
        with open(ROADMAP, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print("written.")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
