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
ENGINE_CHECKED["Load Estimation"] = (
    "FOUND AND FIXED: the guide said Connected Load = Qty x W x PF (VA is W / PF - python-api/calcs/load_estimation.py "
    "divides), '125% of the largest motor + 100% of the rest' (the engine's LOAD_DEMAND_FACTOR applies 1.25 to every Motor, "
    "Fire Pump and Elevator row and 0.50 to welding), told the reader to add the 125% to motor rows (it would count twice), "
    "used US 120 V branch-circuit figures, and described four fields the form does not have. Rewritten from the engine: "
    "the demand-factor table, the 1.25 spare, the STANDARD_BREAKER_A ladder, and the form's two fields. The schedule's "
    "controls had all been named 'Load Schedule (qty)/(W)/(PF)' - each now names its row, its load type and its column.")
ENGINE_CHECKED["Ventilation / ACH"] = (
    "READ AGAINST python-api/calcs/ventilation_ach.py: Vbz, the ACH conversion, max(ASHRAE, minimum ACH), the 1.15 margin "
    "and the fan ladder were the engine's. FIXED: the guide said only toilets and kitchens use the minimum-ACH method - the "
    "engine uses it for every space with no Rp and no Ra, Server Room included; the per-space minimum ACH table and the "
    "ACH line were missing; and Ventilation Type, which changes nothing in the engine, did not say so.")
ENGINE_CHECKED["Pipe Sizing"] = (
    "FOUND AND FIXED: the guide described Hazen-Williams with a temperature-corrected C per material; "
    "python-api/calcs/pipe_sizing.py is Darcy-Weisbach with Colebrook-White, absolute roughness per material and IAPWS-IF97 "
    "water properties - the method, the material tip and the temperature tip are rewritten from it, and fire protection's "
    "floor is 1.2 m/s, not 1.5. Reading it found an ENGINE defect: the form sends 'Chilled Water Supply', 'Hot Water "
    "Supply', 'Cold Water Supply', 'General Water', and the engine knew none of them, so five of seven services were sized "
    "on the General range (a domestic cold-water pipe up to 3.0 m/s against its 2.5 limit). SERVICE_ALIASES maps each; "
    "oracle vector 'Pipe Sizing (the form's service name)' in validate_calc_formula_accuracy.py fails on the old engine.")
ENGINE_CHECKED["Pump Sizing (TDH)"] = (
    "FOUND AND FIXED: the guide described Hazen-Williams; python-api/calcs/pump_tdh.py is Darcy-Weisbach / Colebrook-White. "
    "Reading the two side by side found four ENGINE defects: the form's pressure_head never reached TDH (and the result "
    "carried a hard-coded 0.0), fittings_allowance was never read (always 20%), fluid_density was never read (seawater and "
    "glycol sized as water), and the form's default diameter 0 = Auto was refused by Python (the edge function then fell through silently to its TypeScript fallback). All "
    "four fixed in the engine; two oracle vectors fail on the old engine; walked live in the page - Auto chose 80 mm and "
    "TDH carried the 20 m back-pressure. The guide is rewritten from the engine, and names the form's Fluid field.")
# I1 - a value the form sends that its engine never reads: closed when tools/census_calc_input_reach.py finds none left for
# the calculator (gate calc-input-reach green), with the fix and its oracle named here
I1_FIXED = {
    "AHU Sizing": "FOUND AND FIXED: python-api/calcs/ahu_sizing.py read none of ten values the form sends. It took the whole "
                  "load as sensible (airflow from the TOTAL load - SHR was ignored), fixed the room and supply temperatures at "
                  "24 / 13 °C, the fan static and efficiency at a budget table and 0.65, the CHW flow at a 7/12 °C ΔT of 5 K, "
                  "one unit, and the 62.1 OA check at office rates for every space. All ten read now; oracle vector 'AHU Sizing "
                  "- the form's values reach the result' fails on the old engine on every assert. Walked live: 2 units halved "
                  "the per-unit airflow (11669 -> 5835 m³/h). The unit toggle said '2 units (N+1)' on the AHU and both chiller "
                  "forms while every engine shares the load (each unit half) - relabelled 'sharing the load', and the guides "
                  "now say how to get N+1 (a standby of the same size, not counted).",
}
I1_FIXED["Short Circuit"] = (
    "FOUND AND FIXED (a safety defect): the form sends xfmr_kva, z_pct, voltage_ll, cable_len_m and breaker_ic_kA; "
    "python-api/calcs/short_circuit.py read transformer_kva, transformer_z_pct, voltage, cable_length_m and "
    "ocpd_interrupting_ka. Every fault current came from a 500 kVA default transformer, and the breaker verdict judged a "
    "25 kA default breaker: a 10 kA breaker on a 1000 kVA transformer (22 kA available) was reported ADEQUATE. The form's "
    "names are read now; oracle vector 'Short Circuit - the form's transformer and breaker reach the verdict' fails on the "
    "old engine on all three asserts (25 / 11.16 kA / True). Walked live: 1000 kVA + 10 kA -> 22.03 kA, '10 kA installed vs "
    "22.034 kA required', 'the current 10 kA breaker is inadequate'.")
I1_FIXED["Cooling Tower Sizing"] = (
    "FOUND AND FIXED: with Load Source 'From Chiller (TR + COP)' the form sends chiller_cap_tr and chiller_cop with "
    "q_rejection_kw 0; python-api/calcs/cooling_tower.py read neither and fell through to its 100 kW 'safe default', so "
    "EVERY chiller-sourced tower was sized for 100 kW. It also read ewt_c/lwt_c/wbt_c, cycles_of_concentration and "
    "l_over_g where the form sends ewt/lwt/wbt, coc and lg_ratio, and reported one cell whatever was chosen. Now Q_rej = "
    "TR x 3.517 x (1 + 1/COP), the form's temperatures, cycles and L/G are read, and cells share the duty. Oracle vector "
    "'Cooling Tower Sizing - the form's chiller source, temperatures and cells' fails on the old engine on all five "
    "asserts. Walked live: 200 TR at COP 5.5, 2 cells -> 831.3 kW (415.6 per cell).")
I1_FIXED["Fire Sprinkler Hydraulic"] = (
    "FOUND AND FIXED (fire safety): the form sends operating_pressure ('Min. Operating Pressure at Remote Head'); "
    "python-api/calcs/fire_sprinkler.py never read it, and when the design density needed LESS pressure than the minimum "
    "(a large-K head) it only flagged min_pressure_ok False and carried the low pressure into the total flow and the pump "
    "pressure. The remote head now runs at max(P_density, P_min) and discharges q = K·√P there (NFPA 13 hydraulic method): "
    "a K115 Ordinary-1 design went 1385.7 -> 1654.6 L/min. The Light Hazard oracle that had asserted the head RUNNING at "
    "0.437 bar (below the engine's own 0.52 bar floor) now pins the density figures under their own names and the floor's "
    "flow; a new vector fails on the old engine. The public tools/fire-sprinkler-calculator worked example moved 881.3 -> "
    "923 L/min - patched in place (promoting staging would revert the live page's later fixes) and restamped.")
I1_FIXED["Fire Pump Sizing"] = (
    "FOUND AND FIXED (fire safety): python-api/calcs/fire_pump.py rated the pump at the system pressure + 10% and never "
    "added the form's static rise (pump to highest outlet), the pump piping's friction or the suction - a 30 m riser's 2.9 "
    "bar was left out of the pump's rated pressure and motor; the efficiencies were fixed at 0.70 / 0.92; the report printed "
    "a fixed 100 mm pipe and a 'friction head' of 30% of TDH; NPSH subtracted the rise as a suction lift. Now P_pump = P_req "
    "+ rise + Hazen-Williams friction (auto pipe <= 2.5 m/s) - flooded head (+ lift), each when the caller describes it (the "
    "sprinkler hand-off sends its total demand alone; no suction credit assumed). Reading the method's source found the "
    "Hazen-Williams constant at 6.05e4 in the edge function's TypeScript sprinkler and pump fallbacks and in both guides - "
    "NFPA 13's SI form is 6.05e5, ten times more: all four fixed (the Python sprinkler and domestic-water engines already "
    "had 6.05e5). Oracle vector 'Fire Pump Sizing - the form's rise, piping, suction and efficiencies reach the rating' "
    "fails on the old engine; the public fire-pump page's example moved 7.58 -> 7.75 bar, 55.74 -> 56.96 kW (patched, "
    "restamped). Walked through the served path (engineering-calc-agent): source python, rated 10.831 bar, 150 mm.")
I1_FIXED["Solar PV System"] = (
    "FOUND AND FIXED: the form - and the off-grid planner that hands its plan into the form - sends dod_pct and "
    "battery_voltage; python-api/calcs/solar_pv.py fixed the DoD at 0.80 and chose a 48 / 96 V bus itself. A person who set "
    "50% DoD for lead-acid life got a bank sized for 80% (58.82 kWh where 94.12 kWh was needed, 1.6x too small), and the "
    "voltage they chose was ignored. Both read now; the bank reports its DoD. Oracle vector 'Solar PV System - the form's "
    "depth of discharge and battery voltage size the bank' fails on the old engine. Walked through the served path "
    "(engineering-calc-agent): source python, 94.12 kWh at 50% DoD on a 24 V bus, 2 in series x 16 strings of 250 Ah.")
I1_FIXED["UPS Sizing"] = (
    "FOUND AND FIXED: the form sends its loads as a schedule (loads: [{description, va_per_unit, power_factor, qty}]); "
    "python-api/calcs/ups_sizing.py read only load_kw / load_kva, so EVERY UPS sized from the form was sized for its 10 kW "
    "default - 60 kVA of servers got the same 20 kVA UPS as the default room. backup_min, growth_factor and ups_eff were "
    "read under other names, and two of three topologies under other spellings. The schedule now sets kVA and kW; the "
    "form's backup, growth, efficiency and topology are read; phase is recorded-only (UPS kVA and Ah do not depend on it). "
    "Oracle vector 'UPS Sizing - the form's load schedule sizes the UPS' fails on the old engine on all six asserts; walked "
    "through the served path (engineering-calc-agent).")
I1_FIXED["Generator Sizing"] = (
    "FOUND AND FIXED: the form sends safety_factor (1.25) and application (Standby ESP / Prime PRP / Continuous COP); "
    "python-api/calcs/generator_sizing.py used its own 20% margin and gave a kVA without saying which ISO 8528-1 rating it "
    "is. The margin is the form's now (1.25 -> 8 kVA where 20% gave 6.25 for the default schedule) and the result names "
    "its rating basis with a note to compare like with like; phase is recorded-only (the engine computes in kVA). Oracle "
    "vector 'Generator Sizing - the form's safety factor sets the margin and the result names its rating' fails on the old "
    "engine; walked through the served path (engineering-calc-agent).")
I1_FIXED["Compressed Air"] = (
    "FOUND AND FIXED: the form sends tools: [{tool_type, quantity, custom_cfm}], diversity_factor and leakage_allowance; "
    "python-api/calcs/compressed_air.py read none of them for the sizing and fell to one default impact wrench, so 20 tools "
    "sized the same 2.2 kW compressor as the default three (now 5.5 kW), and the report's connected / diversity / leakage "
    "CFM were back-computed from a default leakage key. The tool table (the edge function's TOOL_DEMAND, keyed by the form's "
    "own names) now sets demand = Σ CFM x qty x duty, x diversity, + leakage. Found only after the census learned the "
    "shorthand `tools,` - its first parser counted `name:` alone. Oracle vector 'Compressed Air - the form's tool list "
    "sizes the demand' fails on the old engine; walked through the served path (engineering-calc-agent).")
I1_FIXED["Refrigerant Pipe Sizing"] = (
    "FOUND AND FIXED: the form sends lines: [{name, line_type, equiv_length_m}]; python-api/calcs/refrigerant_pipe.py read "
    "only suction/discharge/liquid_length_m (default 10 m), so every line was sized as 10 m - 60 m lines gave the same "
    "answer as 15 m. Once the lengths reached the engine they exposed a second defect: _select_tube returned the first tube "
    "inside the velocity limits whatever its ΔT_eq - the budget its docstring names was computed and never used - so a 60 m "
    "suction line kept 19.05 mm at 2.04 K against 1 K. Each line now sets its type's length (the longest run of a type "
    "governs; a riser line turns the riser check on) and the selector honours the budget (60 m suction -> 22.22 mm, 0.94 K). "
    "Oracle vector 'Refrigerant Pipe Sizing - the form's line lengths size the suction line within its budget' fails on the "
    "old engine; walked through the served path. Still flagged, for its R1 walk: the discharge line misses its ΔT budget "
    "even at 15 m because only one tube fits its velocity window.")
I1_FIXED["Storm Drain / Stormwater"] = (
    "MEASURED AGAIN - the row was the census's false reading: it reported the form's three catchment zones (z1..z3 area "
    "and C) unread because its first parser could not see python-api/calcs/storm_drain.py's f-string reads "
    "(inputs.get(f\"z{zi}_area\")). Read against the engine, the zones are read: composite C = Σ A·C / Σ A = 0.62 for the "
    "form's defaults, matching the hand figure. The census now reads f-string keys (read_patterns), and oracle vector "
    "'Storm Drain - the form's catchment zones set the composite runoff coefficient' pins it.")
I1_FIXED["Shaft Design"] = (
    "FOUND AND FIXED: the form sends shock_type (its labels give the ASME shock factors: Minor Kb 1.5, Moderate 2.0 / Kt "
    "1.5, Heavy 3.0 / 2.0) and keyway (Yes / No); python-api/calcs/shaft_design.py applied no shock factor and chose the "
    "shoulder-fillet stress concentration whatever the form said - the form's own default (a keyed shaft under minor shock) "
    "was sized as a steady filleted one. M and T now carry the form's Kb / Kt, and a keyway selects the end-mill keyseat "
    "(Kf 2.2 / Kfs 3.0): a keyed shaft under heavy shock went 26.38 -> 38.70 mm. power_input / power_unit are echoes (the "
    "form converts HP to power_kW before sending) - recorded-only. Oracle vector 'Shaft Design - the form's keyway and shock "
    "type reach the diameter' fails on the old engine; walked through the served path (engineering-calc-agent, by curl).")
for _calc in ("Bearing Life (L10)", "HVAC Cooling Load"):
    I1_FIXED[_calc] = ("DECIDED, recorded on the report only: the form's own label says so (tools/census_calc_input_reach.py "
                       "RECORDED names the label as the reason) - the value it sends is a reference printed on the report, "
                       "and every value the result depends on is read by the engine.")
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
    # the guide receipt is what a G1 / GR row closes on; an I1 row closes on the reach census and its oracle vector, so a
    # stale or missing guide receipt holds the guide rows only (2026-11-01: a 12.8 h receipt had refused an I1 row)
    rep, receipt_problem = {}, None
    if not REPORT.exists():
        receipt_problem = f"no receipt at {REPORT.name} - run {PROVER}"
    else:
        rep = json.loads(REPORT.read_text(encoding="utf-8"))
        age_h = (datetime.now(timezone.utc) - datetime.fromisoformat(rep["generated"].replace("Z", "+00:00"))).total_seconds() / 3600
        if rep.get("teeth"):
            receipt_problem = "the guide receipt is a --teeth run"
        elif age_h > MAX_AGE_H:
            receipt_problem = f"the guide receipt is {age_h:.1f} h old (limit {MAX_AGE_H}) - re-run {PROVER}"
    calcs = {c["calc"]: c for c in rep.get("calcs") or []} if not receipt_problem else {}
    gr = (rep.get("gr") or {}) if not receipt_problem else {}
    if receipt_problem:
        print(f"  guide rows held: {receipt_problem}")
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
        elif key == "I1":
            if unit not in I1_FIXED:
                continue                                  # open: the census still names its unread values
            import census_calc_input_reach as cir
            left = [r for r in cir.census()["rows"] if r["calc"] == unit and
                    set(r.get("unread", [])) - set(cir.RECORDED.get(unit, {}))]
            if left:
                held.append((t["id"], f"{unit}: still sends {', '.join(left[0]['unread'])} its engine never reads"))
                continue
            why = I1_FIXED[unit]
            what = f"{unit}: every value its form sends now reaches its engine (tools/census_calc_input_reach.py)"
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
        if key == "I1":
            basis = (f"[{today}] {why} MEASURED: {what} (how each row was walked is in its sentence above). HELD BY: gate "
                     f"calc-input-reach (ratchet calc_input_reach_baseline.json; teeth plant an unread key) and gate "
                     f"calc_formula_accuracy (the oracle vector named above). pct -> {{pct}}")
            gates = ["calc-input-reach", "calc_formula_accuracy"]
        else:
            basis = (f"[{today}] {why} WALKED: {what}, read through {PROVER} (receipt {REPORT.name}, {rep['generated'][:19]}Z) "
                     f"after selecting the calculator inside engineering-design.html. HELD BY: gate {GATE} (ratchet "
                     f"engineering_guides_baseline.json; teeth plant a ghost field, faint and small text, a hole and a flat line). "
                     f"pct -> {{pct}}")
            gates = [GATE]
        banked.append(t["id"])
        if not a.dry:
            bsw._bank(reg, t["id"], basis, gates)
    for rid, reason in held:
        print(f"  held   {rid}: {reason}")
    print(f"{'would bank' if a.dry else 'banked'} {len(banked)} ED row(s): {', '.join(banked)}")
    if banked and not a.dry:
        bsw._write_registry(reg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
