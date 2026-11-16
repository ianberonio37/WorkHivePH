#!/usr/bin/env python3
"""bank_vx_walks.py - lift the Wave VX walk-family trajectory rows (VX-V widths, VX-J field conditions) from `specced`
to `walked` once their critic walk is banked (2026-11-17).

THE GAP THIS CLOSES. `critic_walk_batch.mjs --apply` banks a walk onto the CRITIC row (critic_registry_vx.json:
status critiqued, with the findings). The same id is a TRAJECTORY row (trajectory_registry_vx.json), and nothing
moved it: 2,287 VX-V and 464 VX-J rows had a banked walk and still read 5% `specced`, so the roadmap header said the
M14 walks had not happened.

WHAT `walked` MEANS HERE, and no more. The ladder is specced 5 / walked 25 / fixed 60 / locked 100. A banked walk is
exactly "walked": the page was read at that width (or the journey lived under that condition) and the findings are
recorded. It is NOT `fixed` (a finding may still stand) and NOT `locking` (no gate holds the width or the condition).
Those need their own evidence, so this tool never writes them.

THE WRITER. `advance_trajectory.py --batch` is the only writer of status and basis; it refuses a bad batch whole and
appends the basis newest-last. This tool only builds the batch.

    python tools/bank_vx_walks.py --dry     # how many rows would move, and a sample basis
    python tools/bank_vx_walks.py           # advance them
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
FAMILIES = ("VX-V", "VX-J")


def _basis(t: dict, c: dict) -> str:
    v = t.get("vx") or {}
    cell = v.get("cell") or {}
    fam = v.get("family")
    finds = c.get("findings") or []
    sev = sorted((f.get("severity") or 0) for f in finds)
    worst = [f for f in finds if (f.get("severity") or 0) >= (sev[-1] if sev else 0)][:2]
    saw = "; ".join(str(f.get("evidence", ""))[:90] for f in worst) if worst else "none"
    if fam == "VX-J":
        what = (f"the scenario lived under {cell.get('condition') or (t.get('journey') or {}).get('condition')} "
                f"({len(c.get('pages') or [])} pages)")
    else:
        what = f"the page read at {cell.get('device') or t.get('device')} ({len(c.get('pages') or [])} pages)"
    return (f"{fam} WALKED {c.get('walked_at')} through the Playwright browser (tools/critic_walk_batch.mjs, "
            f"the rubric survey run on every page): {what}; critic row banked {str(c.get('banked_at'))[:10]} "
            f"under lens {c.get('lens_sha')}; {len(finds)} finding(s), worst: {saw}. "
            f"Walked, not fixed or locked - no gate holds this {'condition' if fam == 'VX-J' else 'width'} yet")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    from registry_io import load_doc
    crit = {r["id"]: r for r in json.load(open(ROOT / "critic_registry_vx.json", encoding="utf-8"))["rows"]
            if r.get("status") == "critiqued" and r.get("wave") in FAMILIES}
    reg = load_doc()
    entries = []
    for t in reg["trajectories"]:
        v = t.get("vx") or {}
        if v.get("family") in FAMILIES and t.get("status") == "specced" and t["id"] in crit:
            entries.append({"id": t["id"], "status": "walked", "basis": _basis(t, crit[t["id"]])})
    print(f"{len(entries)} walk-family row(s) have a banked critic walk and are still specced")
    if entries:
        print("sample:", entries[0]["id"], "-", entries[0]["basis"][:330])
    if a.dry or not entries:
        return 0
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
        json.dump(entries, fh)
        path = fh.name
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "advance_trajectory.py"), "--batch", path],
                       cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
    print((r.stdout or "")[-600:], (r.stderr or "")[-400:])
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
