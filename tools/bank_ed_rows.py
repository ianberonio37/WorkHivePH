"""bank_ed_rows.py - bank Wave ED rows (engineering design, one calculator at a time) on the walk their lens names
(2026-10-31).

An ED row closes "walked on <the calculator> with a receipt, the fix landed, a gate holds it". The Guide lenses (G1, GR1-GR3)
are walked by tools/prove_engineering_guides.mjs (gate engineering-guides): every built calculator selected, its form's
own field labels read, its Guide opened and read back at phone-390 and desktop-1280. Its receipt is
engineering_guides_report.json.

A row is banked only when ALL hold:
  1. the receipt is the walk's own (not a --teeth run) and under 3 hours old, and the gate is green when re-run (--run);
  2. GR rows: the receipt's renderer verdict for that site holds on every calculator at both widths;
  3. G1 rows: the calculator passes in the receipt (a guide, its field names exactly the form's, its renderer clean) AND it
     is in ENGINE_CHECKED - a guide whose formulas and constants were read against python-api/calcs/<name>.py. Matching
     field names is necessary, never sufficient: G1 also asks that the guide's formulas are the engine's.
A failing or missing row is left as it is and printed with the reason.

    python tools/bank_ed_rows.py [--run] [--dry]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import bank_sl_walk as bsw  # noqa: E402

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

REPORT = ROOT / "engineering_guides_report.json"
PROVER = "tools/prove_engineering_guides.mjs"
GATE = "engineering-guides"
MAX_AGE_H = 3

# a guide read against its engine, and how - the second half of G1 that a field-name match cannot prove
ENGINE_CHECKED = {
    "Transformer Sizing": "FOUND AND FIXED: the Guide said 'No guide available yet ... check back after it is built' for a "
                          "built calculator. Written from python-api/calcs/transformer_sizing.py: the STD_KVA ladder, the "
                          "spare-capacity sizing, I = kVA x 1000 / (√3 V), Isc = I2 x 100 / Z%, the LOSS_TABLE fractions, "
                          "the 0.75² copper loss at 75% load, and VR = εr·PF + εx·sinφ - each line the engine's own.",
    "Harmonic Distortion": "FOUND AND FIXED: no guide for a built calculator. Written from python-api/calcs/harmonic_distortion.py: "
                           "THD_I and TDD over Σ I_h², the IEEE 519-2022 TDD_LIMITS and the full INDIVIDUAL_LIMITS matrix "
                           "(bands h<11, 11-16, 17-22, 23-34, 35+), K = 1 + Σ (I_h/I₁)² h², and the ISC/IL = 20 assumption "
                           "the engine makes when I_SC is 0. The five harmonic inputs had all been named 'System Voltage (%)' "
                           "by labelizeInputs - each now names its order (data-wh-own-label), and the group heading is the "
                           "form's field label the guide names.",
    "Clean Agent Suppression": "FOUND AND FIXED: no guide for a built calculator. Written from "
                               "python-api/calcs/clean_agent_suppression.py: the altitude factor, S = s1 + s2·T per agent, the "
                               "halocarbon C/(100-C) and the inert-gas 2.303·log10[100/(100-C)] relations, the default "
                               "concentrations and the NOAEL table. The form note and the drawing's general notes had stated "
                               "only the halocarbon formula and '(halocarbon)' for every agent - both now follow the agent class.",
}
GR_FIXED = {
    "GR1": "FOUND AND FIXED: every tip, note, standard and the subtitle were rgba(255,255,255,0.55) and the tips 12.5px - now "
           "0.80 (the page's measured Lc 79.8 value) at 14px, the formulas 14px.",
    "GR2": "FOUND AND FIXED: formulas were joined with <br> at line-height 2.1, so each of 134 empty entries opened a "
           "three-line hole - an empty entry is now a 0.6rem gap. Three guides (Expansion Tank, FCU Selection, Refrigerant "
           "Pipe) printed '[object Object]' for each of their five formulas - their {label, eq} entries now render.",
    "GR3": "FOUND AND FIXED: 398 formula lines wrap at 390 and the continuation sat at the same indent as the next formula - "
           "each formula is now its own line with a hanging indent, and an indented sub-line keeps its indent.",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", help="re-run the gate first; a red gate banks nothing")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    if a.run:
        ok, last = bsw._run_gate(str(ROOT / PROVER), "--gate")
        if not ok:
            print(f"gate {GATE} is red ({last}) - nothing banked")
            return 1
    if not REPORT.exists():
        print(f"no receipt at {REPORT.name} - run {PROVER}")
        return 1
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    if rep.get("teeth"):
        print("the receipt is a --teeth run - nothing banked")
        return 1
    age_h = (datetime.now(timezone.utc) - datetime.fromisoformat(rep["generated"].replace("Z", "+00:00"))).total_seconds() / 3600
    if age_h > MAX_AGE_H:
        print(f"the receipt is {age_h:.1f} h old (limit {MAX_AGE_H}) - re-run {PROVER}")
        return 1
    calcs = {c["calc"]: c for c in rep.get("calcs") or []}
    gr = rep.get("gr") or {}
    today = date.today().isoformat()
    reg = bsw._load_registry()
    banked, held = [], []
    for t in reg["trajectories"]:
        ed = t.get("ed") or {}
        if ed.get("kind") != "engineering-design" or t.get("status") in ("locking", "locked", "descoped"):
            continue
        key, unit = ed.get("key", ""), ed.get("unit", "")
        why = None
        if key.startswith("GR"):
            if not gr.get(key):
                held.append((t["id"], f"{key} does not hold in the receipt"))
                continue
            why = GR_FIXED.get(key, "")
            what = f"the Guide renderer's {ed.get('lens')} - held on all {rep.get('calculators')} calculators at phone-390 and desktop-1280"
        elif key == "G1":
            c = calcs.get(unit)
            if not c or not c.get("g1") or not c.get("renderer"):
                continue                                  # open: the walk names its drift in the receipt
            if unit not in ENGINE_CHECKED:
                held.append((t["id"], f"{unit}: field names match its form, but its formulas are not yet read against the engine"))
                continue
            why = ENGINE_CHECKED[unit]
            what = f"{unit}'s Guide - present, its field names exactly the form's, its text and formulas clean at both widths"
        else:
            continue
        basis = (f"[{today}] {why} WALKED: {what}, read through {PROVER} (receipt {REPORT.name}, {rep['generated'][:19]}Z) "
                 f"after selecting the calculator inside engineering-design.html. HELD BY: gate {GATE} (ratchet "
                 f"engineering_guides_baseline.json; teeth plant a ghost field, faint and small text, a hole and a flat line). "
                 f"pct -> {{pct}}")
        banked.append(t["id"])
        if not a.dry:
            bsw._bank(reg, t["id"], basis, [GATE])
    for rid, reason in held:
        print(f"  held   {rid}: {reason}")
    print(f"{'would bank' if a.dry else 'banked'} {len(banked)} ED row(s): {', '.join(banked)}")
    if banked and not a.dry:
        bsw._write_registry(reg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
