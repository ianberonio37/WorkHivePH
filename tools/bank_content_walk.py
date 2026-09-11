#!/usr/bin/env python3
"""bank_content_walk.py — turn a content walk into per-row bank entries (W3-LN and W3-CL).

`tools/prove_content_ufai.mjs` opens each learn article and calculator page ONCE and asks it three questions
that page never carried a row for: does it do the job it promises (F), does it hold up away from a desk (A),
and does it say where its numbers came from (I). Each answer belongs to a specific seeded row - the wave was
seeded as one row per missing dimension per page - so this matches the walk's verdicts back to those rows by
(page, dimension) and writes each into its own basis through `advance_trajectory.py`, the only writer.

★A LENS THAT DID NOT HOLD IS NOT BANKED. A page whose F failed keeps its finding and stays open; its A and I
may still bank, because they are different rows about different claims. Banking a page wholesale would hide
exactly the per-dimension detail the wave was seeded to expose.

  python tools/bank_content_walk.py .tmp/content_ufai_calc.json --dry-run
  python tools/bank_content_walk.py .tmp/content_ufai_calc.json --status locking --pct 60
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "trajectory_registry.json"

# the seeded lens text, per wave and dimension, is how a row is recognised without re-typing its title
LENS_KEY = {
    ("W3-LN", "F"): "the tool this article sends you to opens",
    ("W3-LN", "A"): "reads on a phone, survives being opened offline",
    ("W3-LN", "I"): "every claim here is sourced and dated",
    ("W3-CL", "F"): "must reproduce this calculator's reference answer",
    ("W3-CL", "A"): "must let this calculation be done on a phone",
    ("W3-CL", "I"): "must name the standard and clause behind every constant",
}


def rows_by_page_dim() -> dict:
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    out = {}
    for t in reg["trajectories"]:
        if t.get("wave") not in ("W3-LN", "W3-CL"):
            continue
        page = (t.get("pages") or [None])[0]
        dim = (t.get("ufai") or [None])[0]
        if not page or not dim:
            continue
        key = (t["wave"], dim)
        if key in LENS_KEY and LENS_KEY[key] in (t.get("title") or "").lower():
            out[(page, dim)] = t["id"]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--status", default="locking")
    ap.add_argument("--pct", default="60")
    ap.add_argument("--gate", default="content-ufai")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    doc = json.loads(Path(a.results).read_text(encoding="utf-8"))
    index = rows_by_page_dim()
    banked = held = unmatched = 0
    batch = []
    for r in doc.get("results", []):
        page = r.get("file")
        for dim in ("F", "A", "I"):
            v = r.get(dim)
            if not v:
                continue
            rid = index.get((page, dim))
            if not rid:
                unmatched += 1
                continue
            if v.get("verdict") != "ok":
                held += 1
                print(f"    hold {rid:<8} {dim} {page[:44]:46} {v.get('line', '')[:78]}")
                continue
            basis = (f"pct -> {a.pct}. WALKED LIVE {date.today().isoformat()} via tools/prove_content_ufai.mjs — "
                     f"{dim} on {page}: {v.get('line', '')}")
            if a.dry_run:
                print(f"    bank {rid:<8} {dim} {page[:44]:46} {v.get('line', '')[:70]}")
                banked += 1
                continue
            batch.append({"id": rid, "status": a.status, "pct": a.pct,
                          "gate": [a.gate], "basis": basis})
    # ★ONE PASS, NOT ONE PER ROW. advance_trajectory.py re-runs the scoreboard generator AND
    # the whole registry validator on every call - measured at 30 SECONDS per banked row against
    # a 7.7 MB registry, so this wave's 176 rows regenerated the roadmap 176 times to answer one
    # question each, and the rows still owed tonight would have cost about four hours of that
    # alone. --batch applies them together under the same rules, one regeneration at the end.
    if batch:
        Path(".tmp").mkdir(exist_ok=True)
        bf = Path(".tmp/bank_content_batch.json")
        bf.write_text(json.dumps(batch, ensure_ascii=False, indent=1), encoding="utf-8")
        p = subprocess.run([sys.executable, str(ROOT / "tools" / "advance_trajectory.py"),
                            "--batch", str(bf)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        print((p.stdout or p.stderr).strip()[-400:])
        banked = len(batch) if p.returncode == 0 else 0
        if p.returncode:
            print("    the batch was REFUSED, so nothing was written - fix it and re-run")
    print(f"\n  {banked} bankable · {held} held (each keeps its finding) · {unmatched} verdict(s) matched no seeded row")
    return 0


if __name__ == "__main__":
    sys.exit(main())
