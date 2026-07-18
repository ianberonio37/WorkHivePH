#!/usr/bin/env python3
# DEEPWALK-CELL: * D17
# DEEPWALK-CELL: * D15
# DEEPWALK-CELL: * D5
"""validate_frontend_floor_cells.py — fix-to-ZERO ratchet over the live-mined frontend U/A/F lens.

`tools/mine_frontend_ufai_surfaces.py` live-walks every production page (headless, both viewports)
and records a per-page U/I/A/F lens in `frontend_ufai_results.json`. Several of its cells are
exactly the deep-walk's open EXPERIENCE-time dims — already measured live but never ratcheted on
their own. This gate binds them:

  • F1 Completeness    → `consoleErrors=N`                       ==  D17 SMOKE (loads clean)
  • F6 Degraded states → loading/empty/error present            ==  D15 empty/error/loading
  • U7 Mobile usability→ `360px scrollW==clientW overflow=false`==  D5 MOBILE (no h-scroll @360)
  • A1 Responsive      → `breakpoints 360/768/1280/1920 no overflow`  D5 MOBILE (responsive)

FAILs if any applicable page regresses any bound cell — a page that starts throwing a console
error, drops a degraded state, or overflows at 360px blocks CI. Fast HALF of the two-tool pattern
(the sweep is the slow live probe, this is the fast ratchet — same shape as cwv_probe→cwv_gate).
fix-to-ZERO: the floor is 0 non-pass bound cells.

DEEPWALK-CELL tags (top of file) bind it into the platform flywheel: D17 + D15 + D5 per page.

Usage:  python tools/validate_frontend_floor_cells.py [--json]
Exit 0 = clean (or artifact absent → SKIP), 1 = a page regressed a bound floor cell.
"""
import json
import os
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "frontend_ufai_results.json")
# lens cell id → the deep-walk dim it evidences (all live-mined, ratcheted fix-to-zero here).
CHECK_CELLS = {
    "F1": "D17 smoke (console-clean)",
    "F6": "D15 empty/error/loading states",
    "U7": "D5 mobile (no h-scroll @360px)",
    "A1": "D5 mobile (responsive breakpoints)",
}


def main():
    as_json = "--json" in sys.argv
    if not os.path.isfile(RESULTS):
        print("SKIP — frontend_ufai_results.json absent (run tools/mine_frontend_ufai_surfaces.py)")
        return 0
    try:
        data = json.load(open(RESULTS, encoding="utf-8"))
    except Exception as e:
        print(f"SKIP — could not read frontend_ufai_results.json ({e})")
        return 0

    pages = data.get("pages", {})
    violations = []
    checked = {c: 0 for c in CHECK_CELLS}
    for page, p in pages.items():
        cells = p.get("cells", {})
        for cid in CHECK_CELLS:
            c = cells.get(cid)
            if not c or c.get("status") == "n/a" or not c.get("applicable", True):
                continue
            checked[cid] += 1
            status = c.get("status")
            measured = c.get("measured", "")
            bad = status not in ("pass",)
            # F1 double-check: the consoleErrors count must be 0 even if status says pass.
            if cid == "F1":
                m = re.search(r"consoleErrors\s*=\s*(\d+)", measured)
                if m and int(m.group(1)) > 0:
                    bad = True
            # U7 double-check: no horizontal overflow at the 360px mobile viewport.
            if cid == "U7" and re.search(r"overflow\s*=\s*true", measured):
                bad = True
            if bad:
                violations.append({"page": page, "cell": cid, "dim": CHECK_CELLS[cid],
                                   "status": status, "measured": measured[:80]})

    result = {"generated_from": data.get("generated"), "pages_scored": len(pages),
              "cells_checked": checked, "violations": violations,
              "violation_count": len(violations)}
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        total = sum(checked.values())
        if violations:
            print(f"FAIL — {len(violations)} frontend floor regression(s) "
                  f"across {len(pages)} pages ({total} F1/F6/U7/A1 cells checked):")
            for v in violations[:20]:
                print(f"  {v['page']:32} {v['cell']} [{v['dim']}] status={v['status']}  {v['measured']}")
        else:
            print(f"PASS — {total} floor cells clean across {len(pages)} pages "
                  f"(D17 console-clean + D15 degraded-states + D5 mobile, fix-to-zero). "
                  f"source generated {data.get('generated', '?')}")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
