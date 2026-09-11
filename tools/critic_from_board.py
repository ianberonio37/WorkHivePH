#!/usr/bin/env python3
"""critic_from_board.py — turn the family rubric board into critic rows for the pending P program.

The CRITIC DEEPWALK (critic_registry.json) grades every trajectory against the UFAI rubric and
records per-dim verdicts + findings. The 500 P rows entered as `pending`. The family board
(family_rubric_scoreboard.json, written by tools/family_rubric_sweep.mjs) already IS that
critique for every page it grades: 90 measured dims per page, each with pass/total and a note.
Writing those verdicts onto the P critic rows is the same "critiqued from the row's own documented
receipt (retrieve-first)" move the first 657 critic rows used — not a shortcut, the instrument's
own output banked where the program can see it.

Rules honoured (validate_critic_registry.py):
  R2  status >= critiqued needs dims_graded non-empty (they are: the measured dims for the page),
      walked_at on every walked+ row, every finding carries dim/layer/severity/evidence/owner with
      severity 0-4 and layer floor|heuristic.
  R4  a graded dim must exist in ufai-rubric-spec.json — dims the board reports that the spec does
      not define are DROPPED from dims_graded (never invented), and counted in the summary.
  R5  rows without a UI page (edge-function rows carry no_ui_basis) are left pending untouched.
Only rows whose page is on the board move; a page the board never graded stays pending — that is
exactly the "a page outside the board is invisible" line this program drew today.

  (default)  update critic_registry.json in place (only pending rows; idempotent per board ranAt)
  --dry-run  print what would change
"""
from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CRITIC = ROOT / "critic_registry.json"
BOARD = ROOT / "family_rubric_scoreboard.json"
SPEC = ROOT / "ufai-rubric-spec.json"
TRAJ = ROOT / "trajectory_registry.json"

# board pct -> finding severity (0 = note, 4 = blocking). A dim at 0% on a page is a real defect
# class (severity 3); a partial is 2; a near-miss (>=90) is 1.
def _sev(pct: int) -> int:
    return 3 if pct == 0 else (2 if pct < 90 else 1)


def main() -> int:
    dry = "--dry-run" in sys.argv
    # opt-in, and deliberately not the default: see the note in the loop below
    INCLUDE_MULTIPAGE = "--include-multipage" in sys.argv
    # --board <file>: bank a `--page` run's board (family_rubric_scoreboard.page.json) instead of the
    # full one — the 14 subpath pages (calculators + learn index) joined PAGES on 2026-09-05 and their
    # 28 critic rows should not wait for the next full board when a page run has already graded them.
    board_path = BOARD
    if "--board" in sys.argv:
        board_path = ROOT / sys.argv[sys.argv.index("--board") + 1]
    critic = json.loads(CRITIC.read_text(encoding="utf-8"))
    board = json.loads(board_path.read_text(encoding="utf-8"))
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    dims_ok = {k for k in spec if k != "_meta"}
    pages = board["pages"]; ran = (board.get("summary") or {}).get("ranAt", "")
    day = ran[:10] or "2026-09-05"
    moved = dropped = skipped = skipped_multipage = 0
    for r in critic["rows"]:
        if r.get("status") != "pending" or not r.get("pages"):
            continue
        # ★A MULTI-PAGE ROW CANNOT BE CREDITED FROM ITS FIRST PAGE (2026-09-10). The line below takes
        # `pages[0]`, which is exactly right for a row whose subject IS one page - a learn article, a
        # calculator, a page x layer cell - and wrong for a JOURNEY. W31 crosses index, hive, asset-hub,
        # logbook, pm-scheduler and alert-hub; grading it from index.html alone, at rest, is precisely the
        # shallowness this extension was created to answer ("all you are sharing are so shallow, you have
        # to deepwalk live mcps each trajectories"). Every remaining multi-page pending row is a W3-JN
        # journey (724 of them, measured), and each one owes an IN-MOTION critique, so they are skipped by
        # default and counted separately rather than quietly banked at 70%. --include-multipage exists for
        # a caller who has decided otherwise, and has to say so out loud.
        if len(r["pages"]) > 1 and not INCLUDE_MULTIPAGE:
            skipped_multipage += 1
            continue
        pg = r["pages"][0]
        p = pages.get(pg)
        if not p or p.get("overall") is None or not p.get("dims"):
            skipped += 1
            continue
        graded, findings = [], []
        for d in p["dims"]:
            if d.get("kind") not in ("MEASURED", "JUDGED"):
                continue
            code = d["dim"]
            if code not in dims_ok:
                dropped += 1
                continue
            graded.append(code)
            if d.get("kind") == "MEASURED" and isinstance(d.get("pct"), (int, float)) and d["pct"] < 100:
                findings.append({
                    "dim": code, "layer": "heuristic", "severity": _sev(int(d["pct"])),
                    "evidence": f"{pg}: {code} {d['pct']}% — {(d.get('note') or '')[:160]}",
                    "owner": "P-program", "source": f"family_rubric_sweep {ran}",
                })
        if not graded:
            skipped += 1
            continue
        r["status"] = "critiqued"
        r["walked_at"] = day
        r["dims_graded"] = graded
        r["findings"] = findings
        r["clean_note"] = (f"Critiqued from the family rubric board ({ran}, 42-page run, role-first sign-in): "
                           f"{pg} overall {p.get('overall')}% across {len(graded)} measured dims; "
                           f"{len(findings)} sub-100 dim(s) recorded as findings.")
        r["target_source"] = "family-rubric-board"
        moved += 1
    print(f"critic rows moved pending -> critiqued: {moved} · skipped (no page on the board / edge fn): {skipped} "
          f"· skipped MULTI-PAGE journeys owing an in-motion critique: {skipped_multipage} "
          f"· board dims not in the rubric spec (dropped): {dropped}")
    if dry:
        return 0
    critic["updated"] = day
    tmp = CRITIC.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(critic, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, CRITIC)
    print("critic_registry.json written")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
