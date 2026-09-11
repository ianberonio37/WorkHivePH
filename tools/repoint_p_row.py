#!/usr/bin/env python3
"""repoint_p_row.py — aim a still-specced P row at a RECEIPTED finding (Phase 4: issue-driven).

The P catalog is generated as (real surface) x (named lens) under a row budget, so it names only a
fraction of each wave's cells (P-A: 72 rows for 292 cells). The deepwalk then finds real pain on
cells the catalog never named — logbook's 0.606 CLS, seller-profile's 4.44:1 badge, hive's dead-end
empty state. The plan's answer is explicit: "the FOUND issues + improvements shape the 500, not a
pre-allocated rigid grid." This tool is that mechanism, kept surgical:

  · only a row still at `specced` with an empty basis may be re-pointed (a row that has walked
    something is history — its receipts are not overwritten to make room);
  · the target lens must belong to the row's wave, the page must exist on disk, and the lens must
    be able to APPLY to that page (the seeder's LENS_SIGNALS anti-vacuity rule) — a re-point cannot
    create the vacuous row the generator refuses to;
  · the row's title / pages / layers / cells are rewritten to the new cell, and the basis is stamped
    "[<date> repointed …]" so the seeder preserves it verbatim on every future re-run
    (seed_p_program_catalog.py keeps any moved row) and the audit trail says why.

After writing it regenerates the header, the catalog block and the coverage matrix, and runs the
registry gate — the same three generated surfaces every registry change must leave current.

  repoint_p_row.py --id P7 --page logbook.html --lens "CSS contract" --why "CLS 0.606 isolated: boot-wait prepended above the header"
  repoint_p_row.py --find P-A          list still-specced rows in a wave (candidates to re-point)
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "trajectory_registry.json"
TODAY = "2026-09-05"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from seed_p_program_catalog import THEMES, CELLS, _lens_layers, _applies, _label  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id")
    ap.add_argument("--page")
    ap.add_argument("--lens")
    ap.add_argument("--why", default="")
    ap.add_argument("--find", help="wave id: list still-specced candidate rows")
    a = ap.parse_args()

    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rows = {t["id"]: t for t in reg["trajectories"]}

    if a.find:
        cands = [t for t in reg["trajectories"] if t.get("wave") == a.find
                 and t.get("status") == "specced" and not (t.get("basis") or "").strip()]
        print(f"{len(cands)} still-specced row(s) in {a.find}:")
        for t in cands:
            print(f"  {t['id']:6} {t['title']}")
        return 0

    if not (a.id and a.page and a.lens):
        print("need --id, --page, --lens (and --why)")
        return 1
    t = rows.get(a.id)
    if not t:
        print(f"no such row {a.id}")
        return 1
    if t.get("status") != "specced" or (t.get("basis") or "").strip():
        print(f"{a.id} is {t.get('status')} with a basis — it has walked something; re-point a "
              "still-specced row instead (its receipts are not overwritten)")
        return 1
    wave = t["wave"]
    lenses = {l: probe for l, probe in THEMES.get(wave, [])}
    if a.lens not in lenses:
        print(f"lens {a.lens!r} is not one of {wave}'s lenses: {sorted(lenses)}")
        return 1
    if not (ROOT / a.page).exists():
        print(f"page {a.page} does not exist on disk (no phantom surfaces)")
        return 1
    if not _applies(wave, a.lens, a.page):
        print(f"lens {a.lens!r} cannot apply to {a.page} (its signal is absent) — that row would "
              "only ever pass vacuously; pick a lens the page can exhibit")
        return 1
    if not a.why.strip():
        print("give --why: the receipted finding this row is being aimed at")
        return 1

    old_title = t["title"]
    t["title"] = f"{a.lens} - {_label(a.page)}"
    t["pages"] = [a.page]
    t["functions"] = []
    t["layers"] = _lens_layers(wave, a.lens)
    t["cells"] = [CELLS[wave]]
    t["story"] = (f"Walk {a.page} with the '{a.lens}' lens: {lenses[a.lens]}. Record every pain "
                  "with a file:line receipt (A7), fix central-first, close with an instrument the "
                  "walk itself discovered, then lock.")
    t["basis"] = f"[{TODAY} repointed from '{old_title}' -> '{t['title']}': {a.why.strip()}]"
    reg["updated"] = TODAY
    tmp = REGISTRY.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(reg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, REGISTRY)
    print(f"{a.id}: '{old_title}' -> '{t['title']}'  layers={t['layers']}")

    for script in ("update_trajectory_scoreboard.py", "emit_expansion_catalog_md.py",
                   "build_coverage_matrix.py"):
        subprocess.run([sys.executable, str(ROOT / "tools" / script)], capture_output=True, text=True)
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "validate_trajectory_registry.py")],
                       capture_output=True, text=True)
    print((r.stdout or r.stderr).strip().splitlines()[-1] if (r.stdout or r.stderr) else "")
    return r.returncode


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
