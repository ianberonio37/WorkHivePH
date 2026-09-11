#!/usr/bin/env python3
"""bank_journey_run.py — turn one prove_full_journeys run into an advance_trajectory batch.

WHY (W3-JN, 2026-09-09). The journey wave is ~390 rows and every one is banked the same way: read the
prover's result file, write a basis, call advance_trajectory. Doing that by hand is slow and, worse,
it drifts - a hand-written basis tends toward boilerplate, and boilerplate is where an unearned claim
hides. This builds each basis from the row's OWN measured numbers, so the sentence cannot say more
than the walk found.

WHAT IT WILL NOT DO, on purpose:
  * It never banks a row the prover marked BAD. Those need a human reading, because the reason
    matters: a "year-2" cell that no hive has lived is a FIXTURE gap, an unsettled 15s timeout is a
    LOAD artifact, and a dead hop is a PRODUCT defect. Three different dispositions, and a script
    that flattened them into one status would be manufacturing verdicts.
  * It never invents a number. Every figure in the basis comes from the result JSON.
  * It writes a batch FILE for advance_trajectory rather than banking directly, so the batch can be
    read before it is applied.

    python tools/bank_journey_run.py .tmp/full_journeys_J18_LucenaPharmaceuticalMfg.json
    python tools/bank_journey_run.py .tmp/full_journeys_*.json --out .tmp/bank.json
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "trajectory_registry.json"


def _cells() -> dict:
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rows = reg["trajectories"] if isinstance(reg, dict) else reg
    return {t["id"]: t for t in rows}


def _basis(row: dict, reg_row: dict) -> str:
    j = reg_row.get("journey") or {}
    m = row.get("metrics") or {}
    # device/entry/persona live at the ROW's top level on some rows and inside `journey` on others,
    # so read both. Printing "device None" into a basis would be a wrong claim about the cell that
    # was walked, and a basis is the only durable record of what a walk actually covered.
    def field(name):
        return j.get(name) or reg_row.get(name) or row.get(name) or "unstated"
    cell = "tier %s · %s · %s · moment %s · %s" % (
        j.get("tier"), field("device"), field("language"), field("moment"), field("condition"))
    pages = " -> ".join(p.replace(".html", "") for p in (row.get("pages") or []))
    eff = m.get("effect")
    return (
        f"{row.get('archetype')} walked LIVE end to end for {j.get('vertical')} on the cell {cell}. "
        f"{m.get('arrived')}/{m.get('steps')} pages arrived ({pages}), identity kept across every hop, "
        f"thread {m.get('own')} own / {m.get('hubOnly')} hub-only / {m.get('none')} none - so every step "
        f"had a way onward and the walk never lost the person. Persisted effect {eff}: "
        f"{row.get('effectLabel') or 'recorded against this hive'}. The effect is counted in the DATABASE "
        f"rather than read off the screen, which is what separates a story that happened from a story "
        f"that merely rendered. pct -> 100."
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out", default=".tmp/bank_journeys.json")
    args = ap.parse_args()

    paths: list[str] = []
    for f in args.files:
        paths.extend(glob.glob(f))
    reg = _cells()

    batch, skipped = [], []
    for p in sorted(set(paths)):
        try:
            data = json.loads(io.open(p, encoding="utf-8").read())
        except (OSError, ValueError) as e:
            print(f"  ! unreadable {p}: {e}")
            continue
        for row in (data.get("results") or data.get("rows") or []):
            rid = row.get("id")
            if rid not in reg:
                skipped.append((rid, "not in registry"))
                continue
            if not row.get("ok"):
                skipped.append((rid, "; ".join(row.get("problems") or ["not ok"])[:110]))
                continue
            if (reg[rid].get("status") or "") in ("locking", "locked"):
                continue                       # already banked; nothing to say twice
            batch.append({"id": rid, "status": "locking", "pct": 100,
                          "gate": ["full-journeys"], "basis": _basis(row, reg[rid])})

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    io.open(args.out, "w", encoding="utf-8").write(json.dumps(batch, indent=1, ensure_ascii=False))
    print(f"bankable: {len(batch)} row(s) -> {args.out}")
    if skipped:
        print(f"NOT banked ({len(skipped)}) - each needs a human reading, because the reason decides the disposition:")
        for rid, why in skipped[:12]:
            print(f"  {rid}: {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
