#!/usr/bin/env python3
"""bank_brh_db.py - bank BRH rows that close by probe, not page walk (P..Y, §BRH.8; Z..AE, §BRH.9) once their fix
is in and gated (2026-10-21).

A P..Y row is an API probe made as the person the defect exposes, not a page walk: it closes when the exposure was shown
on demand, the fix landed as a migration, and a registered gate reddens on revert. This banks a set of such rows to
locking (pct 60, the BRH convention) with one basis per row: what production showed, how it was reproduced, the fix, the
live witness, and the gate. The gate is RUN first and must pass - a row is never banked on a gate that is red.

    python tools/bank_brh_db.py --spec .tmp/brh_db/<batch>.json [--dry]

The spec: {"gates": ["definer-doors"], "gate_scripts": ["tools/validate_definer_doors.py"],
           "rows": {"BRH336": "<the row's own evidence sentence>", ...}, "common": "<the fix, witness and gate text>"}
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import bank_sl_walk as bsw  # noqa: E402

# P..Y: the database classes (§BRH.8). Z..AE: the free-plan classes (§BRH.9) - what Vercel stores, what the database
# keeps, the AI's production corpus, a refused function, the plan's gaps - each closed by a read, a fix and a gate.
PROBE_CLASSES = set("PQRSTUVWXY") | {"Z", "AA", "AB", "AC", "AD", "AE"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    spec = json.loads(Path(a.spec).read_text(encoding="utf-8"))
    for script in spec.get("gate_scripts", []):
        exe, *args = script.split()     # "tools/deploy_payload.py --check": a gate that takes its mode as an argument
        ok, last = bsw._run_gate(str(ROOT / exe), *args)
        print(f"  gate {script}: {'PASS' if ok else 'FAIL'} - {last}")
        if not ok:
            print("  refused: a row is never banked on a red gate")
            return 1
    reg = bsw._load_registry()
    ids = {t["id"]: t for t in reg["trajectories"]}
    banked = 0
    for rid, own in spec["rows"].items():
        t = ids.get(rid)
        if not t or (t.get("brh") or {}).get("cls") not in PROBE_CLASSES:
            print(f"  skip {rid}: not a BRH P..Y or Z..AE row")
            continue
        basis = f"[{spec.get('date', '2026-10-21')}] pct -> {{pct}}. {own} {spec['common']}"
        if a.dry:
            print(f"  would bank {rid} ({t['brh']['cls']} {t['brh']['key'][:50]}): {basis[:180]}")
        else:
            bsw._bank(reg, rid, basis, spec["gates"])
        banked += 1
    if not a.dry:
        bsw._write_registry(reg)
    print(f"{'would bank' if a.dry else 'banked'} {banked} row(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
