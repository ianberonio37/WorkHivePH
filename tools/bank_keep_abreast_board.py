"""bank_keep_abreast_board.py - bank KA354-366 from tools/prove_keep_abreast_board.py (2026-10-30).

A row is banked only when the report is fresh (3 h), the row's instrument AGREED with the independent live reading, and the
teeth report (--teeth, same day) caught every planted contradiction. The basis quotes both readings.

  python tools/bank_keep_abreast_board.py [--dry]
"""
from __future__ import annotations

import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import bank_sl_walk as bsw  # noqa: E402

REPORT, TEETH = ROOT / "keep_abreast_board_report.json", ROOT / "keep_abreast_board_teeth.json"
# the deployed origin is what these rows read; the three pipeline rows read the command that feeds each surface
PIPELINE = {"KA364", "KA365", "KA366"}


def _fresh(p: Path) -> dict | None:
    if not p.exists():
        return None
    d = json.load(io.open(p, encoding="utf-8"))
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(d["ran"])).total_seconds()
    return d if age <= 3 * 3600 else None


def main() -> int:
    dry = "--dry" in sys.argv
    rep, teeth = _fresh(REPORT), _fresh(TEETH)
    if not rep or not teeth or len(teeth.get("caught") or []) != len(teeth.get("planted") or [1]):
        print("need a fresh report and a fresh teeth run that caught every planted contradiction")
        return 1
    reg = bsw._load_registry()
    stamp = rep["ran"][:10]
    banked = []
    for rid, row in sorted(rep["rows"].items()):
        if not row["ok"]:
            print(f"  OPEN {rid}: {row['independent_reading'][:160]}")
            continue
        where = ("Measured live - tools/prove_keep_abreast_board.py ran the command that feeds this surface"
                 if rid in PIPELINE else
                 "Measured live - tools/prove_keep_abreast_board.py read the deployed origin (https://workhiveph.com) independently")
        basis = (f"[{stamp}] LOCKING pct -> {{pct}}. {where}: {row['independent_reading']}. The instrument's own answer: "
                 f"{row['instrument_says']}. The two agree. Teeth (--teeth, same run day): five planted contradictions "
                 f"({', '.join(teeth['planted'])}) all read FAIL. Gate keep-abreast-board.")
        if not dry:
            bsw._bank(reg, rid, basis, ["keep-abreast-board"])
        banked.append(rid)
    if banked and not dry:
        bsw._write_registry(reg)
    print(f"{'would bank' if dry else 'banked'} {len(banked)} KA-B row(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
