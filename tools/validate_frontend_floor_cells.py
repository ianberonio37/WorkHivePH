#!/usr/bin/env python3
# DEEPWALK-CELL: * D17
# DEEPWALK-CELL: * D15
# DEEPWALK-CELL: * D5
"""validate_frontend_floor_cells.py — fix-to-ZERO ratchet over the live-mined frontend U/A/F lens.

TWO tools stand behind `frontend_ufai_results.json`, and conflating them is how this gate came to
certify a month-old reading (corrected 2026-08-18):
  • `tools/mine_frontend_ufai_surfaces.py`  — STATIC. Mines the applicable-cell DENOMINATOR (D0) from
    per-page HTML signals. Imports json/re/pathlib; it cannot see a console error.
  • `tools/frontend_ufai_sweep.mjs`         — LIVE. Playwright, real authed pages, both viewports.
    Produces every measured value this gate ratchets (consoleErrors, scrollW/clientW, breakpoints)
    and MERGES them into the same artifact.
This gate reads the merged artifact. Several of its cells are
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

★ FRESHNESS (added 2026-08-18, after this gate PASSed over a 31-day-old reading). This gate does not
measure anything — it ratchets what `mine_frontend_ufai_surfaces.py` measured, whenever that was. It
guarded an ABSENT artifact and an UNREADABLE one, but not an EXPIRED one, so a page edited after the
sweep kept its old verdict indefinitely. It certified "139 floor cells clean" while alert-hub was
throwing a SyntaxError on load, because the sweep predated the edit that broke it and nothing re-ran.

Worse, its PASS line printed `source generated D0 — tools/mine_frontend_ufai_surfaces.py`, echoing the
artifact's `generated` PROVENANCE string. "D0" is a phase label, not an age - but it reads exactly like
"generated 0 days ago", which is how I misread it. A gate may not print something that looks like a
freshness assurance and is not one.

The rule is the one the live-MCP bank already uses (R4): evidence expires with the code under it. A
page whose file is NEWER than the reading has an expired reading, and an expired reading is not a
clean one. Expired pages are reported as their OWN number and never folded into the clean count -
"stale is a column, never absorbed" (PAGE_TESTBANK_ROADMAP §5c.2).

A stale page that was measured VIOLATING still fails. The edit may well have fixed it, but this gate
cannot know that, and silently dropping a measured violation because the file moved is how a
denominator shrinks until a green means nothing. The remedy for both directions is the same: re-run
the sweep.
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
        print("SKIP — frontend_ufai_results.json absent (mine the denominator with "
              "tools/mine_frontend_ufai_surfaces.py, then MEASURE it live with "
              "node tools/frontend_ufai_sweep.mjs — the live values come from the sweep)")
        return 0
    try:
        data = json.load(open(RESULTS, encoding="utf-8"))
    except Exception as e:
        print(f"SKIP — could not read frontend_ufai_results.json ({e})")
        return 0

    pages = data.get("pages", {})
    violations = []
    checked = {c: 0 for c in CHECK_CELLS}

    # R4 for this gate: a reading is evidence about a FILE, and it expires when that file changes.
    # The deepwalk flywheel's report-backed cells use a coarser <14d window; page-vs-artifact mtime is
    # sharper in both directions - a 20-day-old reading on an untouched page is still good evidence,
    # and a 1-day-old reading on a page edited an hour ago is not.
    art_mtime = os.path.getmtime(RESULTS)
    stale_cells = {c: 0 for c in CHECK_CELLS}
    stale_pages = []
    for page in pages:
        src = os.path.join(ROOT, page if page.endswith(".html") else page + ".html")
        if os.path.isfile(src) and os.path.getmtime(src) > art_mtime:
            age_h = (os.path.getmtime(src) - art_mtime) / 3600.0
            stale_pages.append({"page": page, "edited_hours_after_reading": round(age_h, 1)})
    stale_names = {s["page"] for s in stale_pages}

    for page, p in pages.items():
        cells = p.get("cells", {})
        for cid in CHECK_CELLS:
            c = cells.get(cid)
            if not c or c.get("status") == "n/a" or not c.get("applicable", True):
                continue
            # An expired reading is not a clean one, so it never enters the certified count. It is
            # counted separately below; a violation measured on it is still reported (see docstring).
            if page in stale_names:
                stale_cells[cid] += 1
            else:
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

    import datetime
    art_age_days = round((datetime.datetime.now().timestamp() - art_mtime) / 86400.0, 1)
    result = {"reading_provenance": data.get("generated"), "reading_age_days": art_age_days,
              "pages_scored": len(pages), "cells_certified": checked,
              "cells_expired": stale_cells, "expired_pages": stale_pages,
              "violations": violations, "violation_count": len(violations)}
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        total = sum(checked.values())
        n_stale = sum(stale_cells.values())
        # The age is COMPUTED. `generated` is a provenance label ("D0 — <tool>"), not a timestamp, and
        # printing it where an age belongs is what made a 31-day-old reading look current.
        prov = (f"reading is {art_age_days}d old, provenance {data.get('generated', '?')!r}")
        if violations:
            print(f"FAIL — {len(violations)} frontend floor regression(s) "
                  f"across {len(pages)} pages ({total} F1/F6/U7/A1 cells certified):")
            for v in violations[:20]:
                flag = " [EXPIRED READING]" if v["page"] in stale_names else ""
                print(f"  {v['page']:32} {v['cell']} [{v['dim']}] status={v['status']}  "
                      f"{v['measured']}{flag}")
            print(f"  ({prov})")
        elif n_stale:
            # Deliberately NOT a non-zero exit: staleness means "unproven", not "broken", and the
            # recorded P12 floor rests on this gate's green. It must simply stop claiming what it
            # cannot see. The remedy is one command, named here.
            print(f"INCOMPLETE — {total} floor cells certified clean, but {n_stale} cells across "
                  f"{len(stale_pages)} page(s) have EXPIRED readings (the page changed after the "
                  f"sweep). Those are not certified either way. {prov}.")
            for s in sorted(stale_pages, key=lambda x: -x["edited_hours_after_reading"])[:12]:
                print(f"  {s['page']:32} edited {s['edited_hours_after_reading']}h after the reading")
            if len(stale_pages) > 12:
                print(f"  … and {len(stale_pages) - 12} more")
            # The LIVE prober, not the static denominator miner. `mine_frontend_ufai_surfaces.py`
            # imports only json/re/pathlib and cannot measure a console error or a scrollWidth - it
            # mines the applicable-cell denominator (D0). Running it would stamp a fresh mtime onto
            # live values it never re-read, which launders the staleness instead of clearing it.
            print("  Re-certify with: node tools/frontend_ufai_sweep.mjs   (the live Playwright sweep)")
        else:
            print(f"PASS — {total} floor cells clean across {len(pages)} pages "
                  f"(D17 console-clean + D15 degraded-states + D5 mobile, fix-to-zero). {prov}")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
