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
ENGINE_CHECKED["Duct Sizing (Equal Friction)"] = (
    "FOUND AND FIXED, read against the ported segment method in python-api/calcs/duct_sizing.py (_form_segments): the "
    "guide said 'System Total dP = sum of every segment' (branches run in parallel - the fan sees the mains plus the worst "
    "branch on each side, ASHRAE Ch.21 index run), gave the smooth-duct closed form as the method (the engine solves "
    "dp/L = fr with Colebrook at the material's roughness - now stated, the closed form kept as its smooth case), told "
    "the reader not to size flexible duct with a tool that offers it (the material is read now), and said '1 kW at 10 C "
    "dT = 24 L/s supply air' - 1000 x kW / (1.2 x dT) = 83 L/s, so a branch flow taken from a cooling load came out 3.5x "
    "too small. Its field names are the form's: 'Friction Rate', and one 'Duct Segment Schedule' tip in place of two "
    "for fields the form does not have.")
ENGINE_CHECKED["Short Circuit"] = (
    "FOUND AND FIXED, read against python-api/calcs/short_circuit.py: the guide gave the infinite-bus transformer formula "
    "and 'Z_total = Z_transformer + Z_cable' (the engine adds the 250 MVA utility source and sums R and X separately, with "
    "IEC 60909's c = 1.05), and 'Peak = 1.8 x Isc' (ip = kappa x sqrt2 x Isc - 1.8 is a typical kappa, so the guide's peak was "
    "sqrt2 too low). Reading the copper resistivity found an ENGINE defect: the maximum fault was computed with the cable at "
    "75 C while IEC 60909-0 takes 20 C for the maximum - 1000 kVA / 4.5% / 30 m of 100 mm2 gave 19.14 kA and recommended a "
    "20 kA breaker; at 20 C it is 20.18 kA and needs 25 kA. The report's steps (0.0175 'at 75 C', V/(sqrt3 Z) without c, "
    "1.8 x Isc, Z_xfmr + Z_cable) could not reproduce the engine's own figures - each step now shows the engine's value. "
    "Field names are the form's. Two oracle vectors fail on the old engine; the door page's three figures restamped "
    "(21.35 kA / 41.04 kA / 14.79 MVA); walked on the served page at 390 (1000 kVA, 100 mm2, 25 kA): source python, every "
    "step reproduces - 'Isc = c x V_LL / (sqrt3 x Z_total) = 1.05 x 400 / (1.7321 x 0.012014) = 20.184 kA'.")
ENGINE_CHECKED["Shaft Design"] = (
    "FOUND AND FIXED, read against python-api/calcs/shaft_design.py: the guide described the ASME elliptic method with "
    "Ss = 0.30/0.18 Sut and M = F x L, while the engine sizes by Shigley DE-Goodman with M = F x L / 4. Reading the engine's "
    "von Mises term found an ENGINE defect: sigma' was (16/pi d3)sqrt(M2 + 3/4 T2) - HALF the real stress (bending is "
    "32M/pi d3) - in the sizing, the fatigue check and the yield check, so every shaft came out at 0.794 of its minimum and "
    "every safety factor doubled: the form's default was given 32 mm at a reported n_f 2.21, real 1.10; it needs 40 mm "
    "(d_min 39.28, kb now iterated on d - Shigley Ex. 7-2 - and the size steps up until n_f >= 2). The yield check took Sy "
    "as 0.6 Sut instead of the material's Sy. The report applied Kb/Kt to a moment the engine had already factored (shock "
    "counted twice; 'M = F x L / 4' printed 225 for 150) - the engine returns the raw loads beside the design ones, and the "
    "summary card shows the governing minimum. The guide's overhung-load tip (enter the overhang as the span) gave a "
    "quarter of the moment - an undersized shaft; it now says enter 4 x the overhang. Materials are the engine's (4340: "
    "1170, not 1035). Two oracle vectors fail on the old engine (the I1 vector's 38.70 re-derived by hand: 49.88); door "
    "page restamped (45 mm / 177.39 MPa); walked on the served page at 390: source python, 'M = 2000 N x 300 mm / 4 = "
    "150.0', 'Combined load = sqrt[(1.5 x 150.0)2 + (1 x 49.4)2] = 230.4', Goodman 39.3 governs, 40 mm selected.")
ENGINE_CHECKED["V-Belt Drive Design"] = (
    "FOUND AND FIXED, read against python-api/calcs/gear_belt_drive.py: the guide's 'Rated Power per Belt' had no basis "
    "stated, and the engine's was Pd_max x sqrt(n/3000) - commented 'simplified for demonstration' - independent of the "
    "sheave: a B belt rated 5.2 kW on 100 mm and on 200 mm alike, above even a premium catalog's figure. The form's "
    "default (7.5 kW x 1.2, B, 125 mm, 1450 rpm) was given 2 belts. Classical belts are now rated by the ANSI/RMA equation "
    "(Machinery's Handbook 30th, constants via Engineers Edge; cross-checked against the Dayton/Grainger 1750 rpm table, "
    "which runs 1.35-1.4x above the standard as premium catalogs do): 3.412 kW per belt -> 3 belts; on a 100 mm sheave "
    "5 belts. Guide states the equation and names the form's 'Driver Sheave Pitch Dia.'. Two oracle vectors fail on the "
    "old engine; walked on the served page at 390: source python, 'Corrected power per belt = 3.414 x 0.959 x 1.004 = "
    "3.287 kW/belt ... 2.74 -> 3 belts'. Open: the AI narrative called 7.5 kW the design power (it is 9.0); the door page's "
    "SPB example is a narrow ISO section the classical equation does not cover (still the old estimate).")
ENGINE_CHECKED["Hoist Capacity"] = (
    "FOUND AND FIXED, read against python-api/calcs/hoist_capacity.py: the guide still stated the reeving error fixed in the "
    "engine on 2026-09-16 ('Power = rope pull x lifting speed' - the rope runs n_parts times faster), a drum-flange formula "
    "the engine does not compute, and 'MBF = GL x Safety Factor'. Reading the MBF found an ENGINE defect: the rope's "
    "breaking force ignored the parts of line (ASME B30.2: the load on EACH part <= 1/5 of the MBF), so a 4-part hoist for "
    "2045 kg was told to fit the 1-part 14 mm rope (>= 100 kN) where 8 mm (>= 25.08 kN) meets 5:1 - rope, drum and "
    "sheaves all oversize; the report's spec item judged the factor against the gross load. And the lift speed was "
    "rounded to 0.13 m/s before the power, cutting it 2.5% (2835 W for 2907). Guide names the form's 'Parts of Line' and "
    "explains its Safety Factor field; the report's MBF and power lines reproduce. Oracle vector fails on the old engine; "
    "reeving invariant holds (2729 -> 3006 W, 1 -> 6 parts, sheave loss only); walked on the served page at 390, 4 parts: "
    "source python, 'MBF = (2045 kg / 4) x 5 = 2556.25 kg (25.08 kN)', '5451 N x 0.5333 m/s = 2907 W'.")
ENGINE_CHECKED["Refrigerant Pipe Sizing"] = (
    "FOUND AND FIXED, read against python-api/calcs/refrigerant_pipe.py and checked with CoolProp 8.0.0 (installed locally "
    "for the purpose; the engine ships static tables): the mass flow was Q / h_fg - the liquid reaches the valve at "
    "condensing enthalpy, so the refrigerating effect is h(suction) - h(liquid at T_cond): 158.2 kJ/kg for R-410A at 5/45, "
    "not 213; mass flow 1.3-1.85x low across the table. The static table claimed '<= 3% vs REFPROP': suction densities up "
    "to 40% low, evaporating dP/dT up to 33% low, liquid densities up to 9% low. The discharge and liquid lines took dP/dT "
    "at the EVAPORATING temperature (discharge 0.6x of it - the curve steepens: R-410A 64.4 kPa/K at 45 C vs 28.6 at 5), "
    "so the form's default discharge line read 2.12 K against its 2 K budget (now 0.73). The form's 'Low-Temp "
    "Refrigeration' never matched 'Low-Temperature Refrigeration' - every low-temp system was sized at +5 C. The copper "
    "roughness was 1.5e-9 m, 1000x too small (drawn tubing 0.0015 mm). Tables regenerated from CoolProp (suction +10 K "
    "superheat, discharge at the compressor outlet with eta_is 0.70, liquid at T_cond, 40/45/50 C), guide and report "
    "state the method. Two vectors fail on the old engine; two earlier vectors that had pinned engine numbers (Q/h_fg; "
    "0.94 K) re-derived by hand. Walked on the served page at 390 (Low-Temp): source python, '-10 C', 'm = Q / RE, RE = "
    "152.3 kJ/kg'.")
ENGINE_CHECKED["Compressed Air"] = (
    "FOUND AND FIXED, read against python-api/calcs/compressed_air.py: the guide says the main is 'sized at 8 m/s (6 m/s "
    "over 50 m)'; the engine never checked velocity - it took the smallest pipe whose drop stayed under 10% of the working "
    "pressure (0.7 bar at 7 bar g): 5 m3/min on a 30 m main got 25 mm at 19 m/s and 0.43 bar (each bar of drop costs ~7% "
    "compressor power). Now the Design FAD (FAD x safety factor - the guide's own term) inside the guide's velocity and a "
    "0.1 bar network drop: 50 mm at 6.08 m/s; 65 mm over 100 m. The guide's receiver labels were reversed (P1 'cut-in', "
    "P2 'working' - the engine uses P1 = working = cut-out, P2 = 0.5 bar lower) and the engine's comment claimed a +/-0.5 "
    "bar band it never used; the guide never stated the motor's duty-cycle up-size (/0.70) or the ISO 1217 power. The "
    "report's pipe card claimed '@ 8 m/s' - it shows the velocity, the drop and their limits. Field name is the form's. "
    "Two vectors fail on the old engine; walked on the served page at 390 (30 m main): source python, '15 mm 1.392 m/s "
    "(limit 8), drop 0.0058 bar (limit 0.1)'.")
ENGINE_CHECKED["Drainage Pipe Sizing"] = (
    "FOUND AND FIXED, read against python-api/calcs/drainage_pipe_sizing.py: the engine and guide said 'UPC Table 7-5' "
    "but the tables were IPC - the stack table was IPC 710.1(2) exactly, the '2%' horizontal row spliced IPC's 1/4-in "
    "building-drain column (up to 75 mm: 42) onto its 1/8-in column (100 mm: 180), and a horizontal fixture BRANCH was "
    "rated like a building drain (75 mm: 42 DFU; UPC gives 35). The water-closet rule forced 100 mm for a single water "
    "closet and called it a UPC hard rule; UPC Table 703.2 note d allows 3 on a 75 mm horizontal (4 on a stack), none on "
    "50/65 mm. Now UPC Table 703.2 (verified against the King County and CPC 2022 reproductions): horizontal at 1/4 in per "
    "ft, x 0.8 at 1/8 in (note 5), vertical for stacks; 38 lavatories -> 100 mm (was 75), 2 WC + 4 lavatories -> 75 mm "
    "(was 100). Guide states the table and the WC limits; the report's override names its reason. Two vectors fail on the "
    "old engine; walked on the served page at 390: source python, 'upsized to 100 mm: 4 water closets, and UPC Table "
    "703.2 allows a 75 mm pipe at most 3 on a horizontal branch or drain'.")
ENGINE_CHECKED["Grease Trap Sizing"] = (
    "FOUND AND FIXED, read against python-api/calcs/grease_trap.py: the engine took grease retention as 1 lb per GPM "
    "('PDI G-101 §4.4') - the PDI-G101 rating is twice the flow rating (a maker's 10 GPM unit is rated 20 lb; IPC/UPC "
    "'double the flow-through rating'), so every trap's grease capacity was reported at half (15 GPM: 6.8 kg, rated 13.6) "
    "and the oracle vector had pinned the engine's half. The page and guide cited 'PDI BH-201' 24 times - no such PDI "
    "standard (G101 rates grease interceptors; WH-201 is water hammer arresters); the engine always said G-101. The guide "
    "said the facility type sets a grease rate per meal (15/20/10 g) - the engine uses ~60 g FOG per meal for all, now "
    "stated as the estimate it is; its cleaning note described 25% of the liquid capacity where the engine uses 25% of "
    "the rated grease capacity. Field name is the form's. Vector re-derived by hand (13.61 kg) fails on the old engine; "
    "walked on the served page at 390: source python, 'Grease retention capacity 3.63 kg (8.00 lbs)' for 4 GPM, no "
    "BH-201 left in the report.")
ENGINE_CHECKED["Septic Tank Sizing"] = (
    "READ AGAINST python-api/calcs/septic_tank.py: the guide's method is the engine's - flow = occupants x rate, liquid = "
    "flow x retention, sludge 40 and scum 15 L/person/yr x desludging years, 1,000 L minimum, 0.30 m freeboard, 2/3 : 1/3 "
    "compartments (hand-checked on the form's default: 3,000 + 2,400 + 900 = 6,300 L). FIXED: the guide had no tip for "
    "the form's Wastewater Rate (the value that sets the liquid capacity), and the drawing printed 'Effluent to leach "
    "field: X m2 required' computed from a sandy-loam soil the form never asks for, while the guide says to size the field "
    "from a percolation test - the drawing now states the assumed soil and the test. Walked on the served page at 390: "
    "source python, 6300 L, 'Leach field about 187.5 m2 if the soil is Sandy Loam; confirm by percolation test'.")
ENGINE_CHECKED["Storm Drain / Stormwater"] = (
    "READ AGAINST python-api/calcs/storm_drain.py: the guide's method is the engine's - Rational Q = C·i·A/360 (A in ha), "
    "composite C = Σ(Ci·Ai)/ΣAi over the form's z1..z3 zones, full-pipe Manning D = [Q·n/(0.3117·√S)]^(3/8) (0.3117 = "
    "(π/4)·4^(-2/3), checked), DPWH 300 mm minimum, 0.6 m/s floor and 3.0 / 5.0 m/s ceilings by material; the form's "
    "'single' / 'composite' values are the engine's own. FIXED: the guide had no tip for the form's Area Input Method - "
    "how the zones are weighted. Read in the page by the guide prover at 390 and 1280.")
ENGINE_CHECKED["Power Factor Correction"] = (
    "READ AGAINST python-api/calcs/power_factor_correction.py: Qc = kW·(tanφ1 − tanφ2), kVA before/after, the next "
    "standard bank and the surcharge % = (0.85 − PF)/0.85 are the engine's (Qc oracle-pinned: 100 kW, 0.75 → 0.95 = "
    "55.32 kVAR → 60). FIXED: the form's Monthly kWh and Meralco Rate had no tip - the guide now says they only feed the "
    "savings estimate, only below PF 0.85, and that the engine takes 18% of the all-in rate as the distribution charge "
    "(an assumption, stated). Read in the page by the guide prover at 390 and 1280.")
ENGINE_CHECKED["Bolt Torque & Preload"] = (
    "FOUND AND FIXED, read against python-api/calcs/bolt_torque.py: the separation minimum was written as a ceiling, "
    "-(-int(x)), but int() truncates first - it was a FLOOR. 100 kN x 1.5 / 68.3 kN = 2.196 gave 2 bolts (2 clamp 136.6 kN "
    "against the 150 kN asked: PASS), and 73 kN on 1 bolt (clamping 68.3 kN, less than the load) passed. Now math.ceil. "
    "The guide divided by the margin (n_min = F_ext / (Fi x SF) - fewer bolts the bigger the margin) and gave grade 8.8 "
    "as 600 MPa where the engine and ISO 898-1 use 580 MPa for d <= 16 mm. Field names are the form's (Preload Target, "
    "Number of Bolts in Joint). The vector fails on the old engine; walked on the served page at 390 (100 kN, 2 bolts): "
    "source python, 'Minimum bolts required (SF >= 1.5) = ceil(100 x 1.5 / 68.3) = 3 bolts ... 2: Status: FAIL'.")
ENGINE_CHECKED["Bearing Life (L10)"] = (
    "FOUND AND FIXED, read against python-api/calcs/bearing_life.py: the guide said X, Y come from the ISO 281 table by "
    "Fa/C0; the engine keyed a made-up table on Fa/Fr (thresholds 0.44, 0.72, 1.02 ... match no ISO column), so any axial "
    "load up to 0.44 Fr was dropped - ISO's e is 0.19-0.44 by f0 Fa/C0 - and a roller took P = 0.4 Fr + 1.5 Fa for ANY "
    "axial load: at Fa = 0.1 Fr, P = 0.55 Fr, below the radial load, life overstated 7.3x. Now ISO 281 Table 3 (deep-groove, "
    "normal clearance, interpolated) with the catalog C0 when given, else C0 = 0.55 C and f0 = 14, stated in the report; "
    "rollers e = 0.40. The guide's a1 values are ISO 281:1990's (labelled as such - conservative against 2007's 0.64 / "
    "0.25); field names are the form's, with a tip for Bearing Number (report only). Two vectors fail on the old engine; "
    "walked on the served page at 390 (Fa 2 kN): source python, 'P = 0.56 x 5 + 1.325 x 2 = 5.45 kN', 'L10h = ... = 1,178 "
    "hours' (old 1,525).")
ENGINE_CHECKED["Pressure Vessel"] = (
    "FOUND AND FIXED, read against python-api/calcs/pressure_vessel.py: the guide wrote the UG-34 flat head as "
    "t = d x C x sqrt(P/SE) and the ENGINE implemented it so - the code is t = d x sqrt(C P / (S E)): C = 0.33 where the "
    "code has sqrt(0.33) = 0.574, so every flat head was 42% thin (800 mm at 10 bar in SA-516-70: 22.5 mm, needs 39.1 -> a "
    "45 mm plate, not 25). The UG-37 nozzle check computed tr at the NOZZLE's radius (0.36 mm against the shell's 2.91) and "
    "counted the shell excess twice, so a pad was essentially never required - the form's default needs 300.4 mm2, has "
    "50.4, and was told 'no pad'. Now tr at the shell radius (seamless E = 1), d = bore + 2 CA, A1 = d (t_net - tr), neck "
    "area not counted (stated). The report's steps reproduce; field names are the form's, with tips for Shell Length and "
    "No. Nozzles. The vector fails on the old engine; walked on the served page at 390 (Flat): source python, "
    "'t = d x sqrt(C x P / (S x E)) ... 39.121 mm ... 45 mm', 'A_required = 103.2 x 2.911 = 300.4 mm2 ... A_available = 50.4'.")
ENGINE_CHECKED["Roof Drain Sizing"] = (
    "FOUND AND FIXED, read against python-api/calcs/roof_drain.py: the engine and guide cited 'IPC 2018 Table 1106.2' "
    "for drain capacities of 0.76 / 1.51 / 2.65 / 4.16 / 8.83 L/s (75-200 mm); the table gives 92 / 192 / 360 / 563 / "
    "1208 gpm = 5.80 / 12.11 / 22.71 / 35.52 / 76.21 L/s (cross-checked: the Engineering Toolbox reproduction, a 4-in = "
    "18,400 ft2 at 1 in/h worked example), so every drain and leader was oversized 2-8x; the horizontal row matched "
    "neither Table 1106.3 nor Manning. Now IPC 1106.2 / 1106.3 (1/8 in per ft base, sqrt S). The report hard-coded the "
    "old table and printed '125 mm <- SELECTED 2.65 x' beside the engine's 22.71 - it carries the IPC values. The oracle "
    "vector had pinned the engine's 200 mm (re-derived: 100 mm); the door page's 200 / 200 mm restamped 75 / 75. Field "
    "names are the form's. Walked on the served page at 390 (1000 m2): source python, '125 mm <- SELECTED 22.71 ✓'.")
ENGINE_CHECKED["Fire Alarm Battery"] = (
    "READ AGAINST python-api/calcs/fire_alarm_battery.py: Ah = I_standby x hours + I_alarm x minutes / 60, x 1.25, next "
    "standard size - the engine's (hand-checked: panel 50/200 mA + 20 addressable + 10 horn/strobe + 4 pull stations = "
    "56.4 / 1262 mA -> 1.354 + 0.105 = 1.459 Ah x 1.25 = 1.823 -> 2.6 Ah). FIXED: the guide described three device "
    "'fields' the form does not have (the device counts are rows of one table, with their currents in their labels) and "
    "named only three of the seven device types; it now lists all seven currents the engine uses. Read in the page by "
    "the guide prover at 390 and 1280.")
ENGINE_CHECKED["Voltage Drop"] = (
    "READ AGAINST python-api/calcs/voltage_drop.py: VD = (2 or sqrt3) x I x R x L, resistance only, at the 75 C operating "
    "temperature, and the maximum run for the limit - the engine's. FIXED: the guide's resistivity note said copper "
    "'approx 0.0220' and aluminium 0.0354 ohm.mm2/m at 75 C; the engine computes 0.01724 x (1 + 0.00393 x 55) = 0.0210 and "
    "0.0283 x (1 + 0.00403 x 55) = 0.0346 - now stated so. The form's Phase Configuration, VD Limit and Conductor Material "
    "had no tip. Read in the page by the guide prover at 390 and 1280.")
ENGINE_CHECKED["Cable Tray Sizing"] = (
    "FOUND AND FIXED, read against python-api/calcs/cable_tray_sizing.py: the guide said 'NEC 392.22: <= 40% mixed power "
    "+ control, <= 50% control only', and the engine took 50% of width x depth as the 'NEC limit'. For multiconductor power "
    "cable below 4/0, NEC 392.22(A) is Table 392.22(A) Column 1 = width x 7/6 in2 per in (7.0 in2 for 6 in, 28.0 for 24 in "
    "- two secondary sources; one notes calculators misdescribing it as 50%), i.e. 29.6 mm2 per mm of width WHATEVER the "
    "depth - so deep trays were sized on the % alone: 20 x 30 mm power cables in a 150 mm deep ladder tray at 40% got "
    "300 mm, 59% over the code's area; Column 1 needs 600 mm. Now width = max(design fill, NEC Column 1 / 3 for power, 50% "
    "for control only); a cable is power unless its type says control/signal/instrument/data. The report called the "
    "design fill 'Fill Ratio Limit (NEC 392.22)' - relabelled, with the NEC allowable area and its basis. Guide fields are "
    "the form's (Tray Run Length, Cable Schedule). The vector fails on the old engine; walked on the served page at 390: "
    "source python, '2a NEC 392.22 allowable 2963.3 mm2 (Column 1: 100 mm x 29.6 mm2/mm)'.")
ENGINE_CHECKED["Water Softener Sizing"] = (
    "READ AGAINST python-api/calcs/water_softener.py: gpg = mg/L / 17.1, daily load = demand x removal, load per cycle x "
    "regen days x 1.20, resin = load / exchange capacity (35-55 g/L by salt dose; 45 g/L at 80 g/L is consistent with "
    "resin data, ~19 kgr/ft3 at 5 lb/ft3 x 2.288), salt per regen and monthly - the engine's. FIXED: the guide named the "
    "form's Demand Input Method 'Demand Source' and had no tip for Number of People or Per Capita Use (used only By "
    "Occupancy). Read in the page by the guide prover at 390 and 1280.")
ENGINE_CHECKED["Water Treatment System"] = (
    "READ AGAINST python-api/calcs/water_treatment.py: peak = demand x factor / 24, filter area at 10 m/h (8 for iron), "
    "backwash 25 m/h, chlorine by source, NaOCl 12% at 8.3 L per kg Cl2 (120 g/L available chlorine), contact tank on the "
    "peak flow - the engine's. FIXED: the guide named fields the form does not have (Daily Demand (L/day), Turbidity "
    "(NTU), Peak Factor) and omitted the form's Demand Input Method, Number of People and Per Capita Use; it now names the "
    "form's six. Read in the page by the guide prover at 390 and 1280.")
ENGINE_CHECKED["Lightning Protection System (LPS)"] = (
    "FOUND AND FIXED, read against python-api/calcs/lightning_protection.py (the engine was corrected earlier the same day "
    "for the Type A/B earthing - ED352): the guide's Nd dropped Cd (IEC 62305-2: N_D = N_G x A_D x C_D x 10^-6, as the "
    "engine computes), quoted LPL efficiencies 99/97/91% where the engine and IEC use 98/95/90/80%, cited 'IEC 62305-3 "
    "Table 7' (the report: 'Annex E') for an electrode length max(5, 0.5 H) that is the engine's own simplification of "
    "Figure 3 - now said so, in the guide and the report - and its earthing tip predated the Type A/B behaviour. Field "
    "names are the form's (Building Length / Width / Height, Lightning Protection Level, Custom Ng). Read in the page by "
    "the guide prover at 390 and 1280; the earthing walk is ED352's.")
ENGINE_CHECKED["Generator Sizing"] = (
    "FOUND AND FIXED, read against python-api/calcs/generator_sizing.py: the guide said 'Design kVA = max(running, "
    "starting) x safety factor'; the engine sized on the larger of steady and running-plus-start kVA and only CHECKED the "
    "motor-start dip X''d x start kVA / gen kVA - so the set it recommended failed its own check: a 10 hp DOL motor got "
    "62.5 kVA dipping 23.4%, a 40 hp one 250 kVA dipping 23.5%. Now the set is also sized so the dip holds the class: gen "
    ">= X''d x start / limit; and G2 is ISO 8528-5's -20% (Cummins / Avtron tables; the engine had 15%, stricter than the "
    "standard). 10 hp -> 75 kVA at 19.5%. The guide states the three-way sizing; field names are the form's (Connected "
    "Load Schedule, Largest Motor (DOL Start), System Configuration, Overall Power Factor), and the starting-method field "
    "the form never had is gone. The vector fails on the old engine; walked on the served page at 390 (10 hp): source "
    "python, 'Next standard size >= 73.14 kVA -> 75 kVA'.")
ENGINE_CHECKED["UPS Sizing"] = (
    "READ AGAINST python-api/calcs/ups_sizing.py (its load schedule, backup, growth and efficiency were wired earlier "
    "the same day - ED-I1): kVA = design VA / 0.80, kW_design = load / eta, Ah = kW_design x t / (V_dc x 0.80 x 0.98), "
    "DC bus by kVA. FIXED: the guide divided by eta_UPS a second time in the Ah formula (the engine applies it once, in "
    "kW_design), called the 0.80 a depth of discharge without saying it is the IEEE 1184 aging margin, and named a "
    "'Load VA and PF' field the form does not have (it is the Load Schedule) with no tip for UPS Efficiency. It now says "
    "the Ah is a 20-hour-rate LOWER BOUND - a VRLA battery delivers well below that at a 5-30 min discharge; select from "
    "the maker's W/cell table (IEEE 1184). OPEN: the engine has no rate-capacity correction (no verified table encoded). "
    "Read in the page by the guide prover at 390 and 1280.")
ENGINE_CHECKED["Cooling Tower Sizing"] = (
    "READ AGAINST python-api/calcs/cooling_tower.py (chiller source, temperatures and cells wired earlier the same day - "
    "ED-I1): Q_rej = TR x 3.517 x (1 + 1/COP), range, approach, flow = Q / (cp x range), evaporation 0.75% per 5.6 C of "
    "range (~0.13%/C - consistent with the latent-heat ceiling cp dT / h_fg), drift 0.02%, blowdown = evap / (CoC - 1). "
    "FIXED: the guide wrote evaporation as 0.085% x Range with the range in C (that rule is per F - half the water), and "
    "its note put a 1,000 TR plant's makeup at 25-35 m3/day at CoC 4 - the engine gives ~160 m3/day (evaporating ~120), "
    "about 7x more; CoC 3 adds ~12%, not 25%. Field names are the form's (EWT / LWT / WBT). Read in the page by the guide "
    "prover at 390 and 1280; the figures stated were run on the engine (4,220 kW: 117 / 160 / 179 m3/day).")
ENGINE_CHECKED["FCU Selection"] = (
    "FOUND AND FIXED, read against python-api/calcs/fcu_selection.py: the guide's 'Q_design = sum(room load x qty) x "
    "diversity' with the load 'per FCU unit' - the engine selected each FCU for the row load and multiplied flow and "
    "connected kW by qty, but summed the REQUIRED total without qty: four 3.5 kW units read 3.5 kW required and 2.98 kW "
    "design against 16.8 kW connected - the plant load handed on was a quarter of the room's. Now load x qty: 14.0 / 11.9 "
    "kW. The form's room header said only 'Load (kW)' - now 'Load per FCU (kW)'. Guide field names are the form's (CHW "
    "Supply Temp, CHW Return Temp, Room / Zone Schedule). The vector fails on the old engine; walked on the served page "
    "at 390 (one room, 3.5 kW x 4): source python, 'DESIGN LOAD (DF=0.85) 11.90 kW 3.38 TR', header 'Load per FCU (kW)'.")
ENGINE_CHECKED["Elevator Traffic Analysis"] = (
    "FOUND AND FIXED, read against python-api/calcs/elevator_traffic.py and CIBSE Guide D (Peters 2000 Eq. 9, RTT = "
    "2.H.tv + (S+1).ts + 2.P.tp): the engine ran the full rise at rated speed, charged each stop only its door times (no "
    "slow-down/speed-up loss ts = tf1 + tc + to - tv), skipped the main-floor stop (S, not S+1), and moved each passenger in "
    "0.8 s one way (CIBSE 1.2 s each way). The default 12-floor, 3-car office read RTT 110.3 s / interval 36.8 s / HC 16.3%; "
    "by CIBSE it is 147.4 s / 49.1 s / 12.7% - capacity overstated by about a third. Now the probable stops and highest "
    "reversal floor, tf1 from the CIBSE flight-time table plus the extra floor height, P = 10.4 not rounded, and the dwell "
    "as a floor under the transfer time. The guide said S was ~2/3 of floors and listed a Total Rise field the form lacks; "
    "names are now the form's (Number of Floors Served, Number of Elevators, Door Open/Close Time, Dwell Time / Stop). Two "
    "hand-derived vectors fail on the old engine; walked on the served page at 390: 'RTT = 48.8 + 73.6 + 25 = 147.4 "
    "seconds', interval 49.1 s Adequate, no sideways scroll. Door page restamped (66.8 s / 15.6% / 133.6 s).")
ENGINE_CHECKED["Expansion Tank Sizing"] = (
    "FOUND AND FIXED, read against python-api/calcs/expansion_tank.py: a chilled-water loop was sized for the swing fill "
    "-> operating only (20 -> 7 C, E_w 0.0017), but a stopped loop warms to the plant room (ASHRAE: size between the lowest "
    "operating and the highest ambient the system sees) - 7 -> 35 C, E_w 0.0059. A 20,000 L loop was given a 60 L tank "
    "where it needs 300 L (207.6 L required). Chilled water now also takes the idle ambient (35 C default, returned as "
    "idle_ambient_c with v_low / v_high and the swing). The report's E_w working was built from v_fill and v_max, which no "
    "longer bound the swing - it now prints the engine's own v_low / v_high and an Idle Ambient row. Guide names are the "
    "form's (System Volume Method, System Water Volume, System Capacity, Min Operating Temperature). The vector (800 L, "
    "hand-derived from IAPWS v(7) = 1.000097, v(35) = 1.005998) fails on the old engine (8 L tank, should be 12); walked "
    "on the served page at 390: 'E_w (7 C -> 35 C) = 0.00590', '118.01 L / 0.5690 = 207.58 L', no sideways scroll. The "
    "door page already entered 7 -> 35 C, so its figures stand.")
ENGINE_CHECKED["Chiller System — Air Cooled"] = (
    "FOUND AND FIXED, read against python-api/calcs/chiller.py: the guide's 'units share the design load equally' - the "
    "engine picked each unit's nominal size for the WHOLE design load and installed n x that: two units for a 550 kW "
    "design printed 'per unit 275 kW' then 'selected each 180 TR (633 kW)', 360 TR installed for a 156 TR plant, and the "
    "recommendation said to procure them. Each unit is now the smallest standard size >= its share (281 kW, 159.8 TR "
    "installed). The ASHRAE 90.1 tier was taken from the building load, not the chiller's rated size - now the unit's. Two "
    "airflow figures for one fan duty (450 m3/h per kW, a 6.9 K rise, vs the report's 10 K) - one now, and the report's "
    "working printed the 8 K condensing approach as the air rise while its number used 10 - it prints the 10 K rise now. "
    "The guide's ASHRAE minimum was 90.1-2010's COP 2.84 / EER 9.7 - now 2019's 2.96 full load, IPLV 4.02 / 4.10. Guide "
    "names are the form's. The vector fails on the old engine; walked on the served page at 390: '79.9 TR (281 kW) per "
    "unit', '159.8 TR = 562.0 kW', 'dT air = 10 C', '<528 kW unit', no sideways scroll.")
ENGINE_CHECKED["Chiller System — Water Cooled"] = (
    "FOUND AND FIXED, read against python-api/calcs/chiller.py: the form offers Centrifugal / Screw / Scroll / "
    "Reciprocating, but every type was held to ASHRAE 90.1's centrifugal rows - a 100 TR screw chiller at COP 5.0 (Path A "
    "minimum 4.88) was reported failing at 5.77. Water-cooled positive displacement now has its own 90.1-2019 Table "
    "6.8.1-3 Path A rows (0.750/0.600, 0.720/0.560, 0.660/0.540, 0.610/0.520, 0.560/0.500 kW/ton; the first two "
    "confirmed against the California Energy Commission tables). The per-unit sizing fix (ED13) applies here too. The "
    "guide and the report's standards row printed older minimums (Centrifugal 5.00/5.55/6.10, Screw 4.45/4.90, "
    "Scroll/Recip 3.80; IPLV 6.28/7.19/8.27...) matching neither the engine nor 2019 - both now print the 2019 rows, and "
    "the minimum's label names the tier and the unit's rated size, not the design load. Guide names are the form's (CHW "
    "Supply/Return Temperature, CW Supply/Return Temp, IPLV / NPLV). The vector fails on the old engine; walked on the "
    "served page at 390 (300 kW screw, COP 5.0): '4.88 (75-<150 TR positive displacement: each 352 kW unit)', 'COP 5 vs "
    "min 4.88', no sideways scroll.")
ENGINE_CHECKED["AHU Sizing"] = (
    "FOUND AND FIXED, read against python-api/calcs/ahu_sizing.py: (1) the guide's 'Q_design = Cooling Load x Safety "
    "Factor' - the margin enlarged the fan and coil face, but the coil capacity, its chilled water, the dehumidification "
    "and the AHU's rated airflow ran on the load airflow without it (a 1.10 factor left the coil ~9% short of its air); all "
    "now at the design airflow. (2) The form's eta is the COMBINED fan + motor efficiency; the engine divided by a further "
    "0.92 (+8.7% fan power). (3) The motor was picked for the whole airflow and printed 'per unit' (2 AHUs: a 3.0 kW motor "
    "each where 1.1 kW serves). (4) The '90.1' limit was 1.2 W/(L/s) citing Table 10.8 (motor efficiency), the guide said "
    "0.82 (0.0011 hp/cfm read as W/cfm): now 90.1-2019 6.5.3.1.1 Option 1, nameplate <= 1.7 W per L/s, N/A at or below 5 "
    "hp. (5) The default outdoor air was 35 C at 80% RH (31 C dew point, 108 kJ/kg) - no Manila design condition; now 35 C "
    "DB / 28 C WB (89.4 kJ/kg). (6) OA per person printed a fixed 10. The report's working now reproduces its numbers "
    "(load airflow x SF; coil = m x (h_mix - h_sup); nameplate W/(L/s)); guide names are the form's. The vector (hand "
    "psychrometrics from ASHRAE Fundamentals Ch.1) fails on the old engine (coil 89.69 vs 82.22, OA 10 vs 17.8); walked on "
    "the served page at 390: 'Q_coil = 4.1004 x (58.05 - 38) kJ/kg = 82.23 kW', '1.1 kW per unit, 2.2 kW nameplate total', "
    "no sideways scroll. Door page restamped on the design airflow (9157.6 CFM / 29.18 TR / 7.5 kW).")
ENGINE_CHECKED["HVAC Cooling Load"] = (
    "FOUND AND FIXED, read against python-api/calcs/hvac_cooling_load.py: (1) glass conduction used the WALL U-value "
    "(0.45) - single clear glass is 5.9 W/m2K (ASHRAE Ch.15), 13x low (24 m2 at 11 K: 119 W for 1,558); U_glass is now by "
    "glass type (5.9 / 5.9 / 2.8 / 1.8). (2) Walls were the gross area, the windows counted as wall too; now net of glass. "
    "(3) The default outdoor air was 35 C at 80% RH (31 C dew point) - infiltration latent ~70% high; now 35 C DB / 28 C "
    "WB. The guide and the report's working described a different method from the engine: walls/roof U x A x DT (x1.15) "
    "where the engine uses CLTD, glass 0.57 x A x DT, equipment x0.85 diversity the engine never applied, infiltration "
    "0.35 x V x DT sensible only, Mixed irradiance 200 against the engine's 350 (and the form label's '3.5x'), and a "
    "latent row labelled occupants-only that held infiltration too - all now the engine's method with its own numbers. "
    "Guide names are the form's. The vector (hand psychrometrics) fails on the old engine and the old gross-wall vector "
    "(630, re-derived to 504); walked on the served page at 390: 'Q_walls = 0.45 x 96 x 9 = 388.8 W', 'Q_glass = (5.9 x "
    "24 x 11) + (24 x 0.87 x 350) = 1,557.6 + 7,308', 'design 18,883.5', no sideways scroll. Door page restamped "
    "(38.87 kW / 11.05 TR).")
ENGINE_CHECKED["Wire Sizing"] = (
    "FOUND AND FIXED, read against python-api/calcs/wire_sizing.py and walked: (1) the report NEVER RENDERED on this "
    "engine - size_comparison was a sentence the report maps as rows ('TypeError: .map is not a function', 'Could not "
    "generate the report' on every calculation since the engine began serving the form; it would have reached production "
    "at M5); now rows with a status each. (2) The ampacity table rated each metric size at the next-LARGER AWG conductor "
    "(30 mm2 115 A = 2 AWG 33.6 mm2; 100 mm2 230 A = 4/0 107 mm2; 125 mm2 270 A above 250 kcmil's 255) - now the guide's "
    "PEC rows to 100 mm2, above that the rating of the largest NEC conductor not bigger. (3) Every breaker at 125%: a "
    "motor's trips on starting - now 250% for motors (PEC 4.30.52), 175% compressors (4.40.22). (4) No PEC 2.40.4(D) "
    "small-conductor limit (2.0 mm2 left on a 20 A breaker). (5) A hidden 30 m voltage-drop check upsized wires the form "
    "never asked about - now only with a length, and the report says it is unchecked. (6) 'Corrected Ampacity' printed the "
    "table value; 'Phase' printed 3; the 'with multiplier' current was without it. Guide: no motor FLA table exists (the "
    "tip said so), 40 C factor 0.88 not 0.87, names are the form's. Three hand vectors fail on the old engine (2.0 mm2 on "
    "20 A, a 20 A motor breaker, 80 mm2 for 176 A); walked on the served page at 390 (7.5 kW motor): renders, 'Sizing "
    "Current 15.92 A', '40 A PEC 4.30.52', no sideways scroll. Door page restamped (38 mm2 / 0.75%).")
ENGINE_CHECKED["Solar PV System"] = (
    "FOUND AND FIXED, read against python-api/calcs/solar_pv.py: (1) the heat was counted twice - the array kWp already "
    "divides by the derating (which holds the 5-15% heat loss), then the panels were counted on a hot-cell Pmax (450 Wp "
    "-> 385 W): every array ~17% over; now STC Wp as the guide says. (2) Strings were filled to the cold-Voc maximum (33 "
    "panels -> 2 x 19 = 38); now equal strings as short as the count allows (2 x 17), the maximum kept as "
    "max_panels_per_string. The door page's '100 kWp' example had been sold as 121.6 kWp; now 100.8. (3) CO2 used 0.522, "
    "no DOE figure (the guide said 0.72) - now DOE NGEF 2015-2017 combined margin for solar, Luzon-Visayas 0.6836 / "
    "Mindanao 0.7859. (4) The off-grid battery NEVER reached the report: battery_kwh / battery_ah read keys the bank never "
    "had - every off-grid report printed 0 kWh and 0 Ah. (5) 'Inverter Capacity' printed the kVA x 0.9; 'Voc_max' was the "
    "whole string's voltage beside a per-panel formula. (6) The fallback PSH table differed from the page's. The guide's "
    "string rule used STC Voc, its battery omitted the 0.85 round trip, and its names are now the form's. Hand vectors fail "
    "on the old engine; walked on the served page at 390 (off-grid Davao): '94.12 kWh', '1960.8 Ah @ 48 V', '0.7859 (DOE "
    "NGEF ... Mindanao)', no sideways scroll. Door page restamped (252 panels / 100.8 kWp / 629 m2).")
ENGINE_CHECKED["Earthing / Grounding System"] = (
    "FOUND AND FIXED, read against python-api/calcs/earthing_grounding.py and IEEE 142 Table 4-5: (1) the rod formula put "
    "the DIAMETER where Dwight's ln(4L/a) takes the radius - 11% optimistic (3 m x 16 mm in 100 Ohm-m: 29.8 for 33.5 "
    "Ohm); the oracle vector had pinned the 29.8. (2) The ring 'Sunde' formula ln(8D/d) - 2 gave a 10 m ring 3.54 Ohm, "
    "below a solid 10 m surface disc (rho/2D = 5) - impossible; now IEEE 142's [ln(8D/d) + ln(4D/s)] at the 0.75 m "
    "minimum burial: 6.22 Ohm. (3) The GEC table gave 6 mm2 for a 35 mm2 service and 16 mm2 up to 95 mm2 - NEC 250.66 by "
    "the service conductor's area, as PEC sizes: 35 -> 14 mm2, 95 -> 38 mm2. The guide carried the same formulas and a "
    "third GEC table; it and the report now print the engine's, and its names are the form's. Vectors fail on the old "
    "engine; walked on the served page at 390 (ring, 95 mm2 service): '6.216 Ohm', 'IEEE 142 Table 4-5', '38 mm2 (2 "
    "AWG)', no sideways scroll. Door page restamped (4.19 Ohm).")
ENGINE_CHECKED["Lighting Design"] = (
    "FOUND AND FIXED, read against python-api/calcs/lighting_design.py: the lumen method itself matches the guide (N = "
    "E.A/(F.CU.LLF), RCR from the mounting height above the 0.85 m work plane, CU interpolated, rows x columns layout). "
    "But the form's space types ('Office', 'Conference Room', 'Corridor', ...) matched none of the LPD table's keys "
    "('Office - general', ...), so every form calculation was checked against the 15 W/m2 fallback - and that table, "
    "labelled 90.1-2019, is an older edition (office 11.0 W/m2 = 1.02 W/ft2). The form's spaces now take ASHRAE 90.1-2019 "
    "Table 9.6.1 (search-confirmed: open office 0.61, enclosed office > 250 ft2 0.66, corridor 0.41; the others from the "
    "same table, = IECC 2021 C405.3.2(2)). The report printed the LPD and never its limit or verdict - it does now. The "
    "guide's CU list (0.72/0.62/...) was not the engine's (0.70/0.63/...); its names are the form's. The vector fails on "
    "the old engine (15 W/m2, PASS); walked on the served page at 390 (form defaults): 'Limit: 7.1 W/m2 ... FAIL' for 36 "
    "W / 3,200 lm panels, no sideways scroll.")
ENGINE_CHECKED["Water Supply Pipe Sizing"] = (
    "FOUND AND FIXED, read against python-api/calcs/water_supply_pipe.py: the guide's 'Hunter's Curve' - the engine's "
    "'PPC Table A-3' curve was about a THIRD of Hunter's (10 WFU 0.32 L/s, 100 WFU 1.22, 1000 WFU 4.20, where IPC Table "
    "E103.3(3)'s flush-tank branch is 0.92 / 2.74 / 13.1 L/s) and had no flush-valve branch at all: every main was sized "
    "for about a third of its probable demand. The door page's 10 flush-valve WCs drew 76.1 L/min - less than ONE "
    "flushometer - on 32 mm; now 263.8 L/min on 50 mm. Both of Hunter's branches now (the flush-valve column is the one "
    "calcs/domestic_water.py carries, oracle-verified; any flush-valve fixture selects it). The oracle vector had pinned "
    "1.34 L/s from the old curve; re-derived to 4.606. The guide's pressures were in metres where the form takes kPa; its "
    "names are the form's; the report names the branch. Vectors fail on the old engine; walked on the served page at 390 "
    "(form defaults, 20 WFU): '1.237 L/s (flush tank branch, IPC E103.3(3))', 32 mm, no sideways scroll. Door page "
    "restamped. Seen in passing, queued: calcs/domestic_water.py's flush-TANK power fit overshoots Hunter above ~50 WSFU "
    "(82.6 gpm at 100 against 43.5) and crosses above its own flush-valve curve.")
ENGINE_CHECKED["Hot Water Demand"] = (
    "FOUND AND FIXED, read against python-api/calcs/hot_water_demand.py: the form's Recovery Time is 'hours available "
    "for the heater to reheat the TANK from cold', but the guide's formula and the engine heated the whole DAY's demand "
    "in it - 100 hotel rooms (14,850 L/day) got a 277 kW heater where reheating the selected 5,000 L tank in 2 h takes "
    "92.9 kW (the storage, peak hour x 1.25, already carries the peak hour). The heater now recovers the tank; the day's "
    "heat is still reported, as running cost. The report's working named the daily demand as the mass and hard-coded Cp "
    "4.186 beside the engine's IAPWS 4.1787 - both now the engine's. Guide names are the form's. The vector fails on the "
    "old engine (275.8 kW); walked on the served page at 390 (form defaults): '1500 L tank in 2 h', '200577 kJ', "
    "'27.86 kW', no sideways scroll. Same commit: calcs/domestic_water.py's flush-TANK power fit overshot Hunter above "
    "~20 WSFU (100 WSFU 312.8 L/min, above its own flush-valve 255.5) - now IPC Table E103.3(3)'s tank column, with a "
    "vector that fails on the fit (163.6 vs 110.1 L/min at 50 WSFU).")
ENGINE_CHECKED["Wastewater Treatment (STP)"] = (
    "FOUND AND FIXED, read against python-api/calcs/wastewater_stp.py (Metcalf & Eddy): the aeration volume (SRT method), "
    "oxygen demand (a.BOD + b.MLVSS.V) and blower air (O2 / (0.232 x 1.2 x 0.08 x 1440)) are right. The sludge was not: "
    "Y_obs x BOD removed is biomass as VSS, and the engine took it as the dry solids - mass, volume at 1% DS and the "
    "desludging interval all 20% short (default plant: 2.3 kg/day, every 87 days; it is 2.9 kg/day, every 69). Now VSS / "
    "0.80 (the engine's own VSS/TSS). The guide's blower formula divided kg O2/DAY by a per-MINUTE factor (x 60 for x "
    "1440) and its sludge formula was a different empirical one - both now the engine's; names are the form's. The "
    "vector fails on the old engine; walked on the served page at 390: '2.9 kg dry solids/day', 'Every 69.0 days'. The "
    "walk caught the page at 513 px: 18 report renderers set the signature block grid-template-columns:1fr 1fr 1fr "
    "INLINE, which beat the stylesheet's 640 px single-column rule - the rule is !important now (engineering-design.html), "
    "390 px again.")
ENGINE_CHECKED["Boiler System"] = (
    "READ AGAINST python-api/calcs/boiler_system.py: blowdown % = TDS_makeup / (TDS_max - TDS_makeup) is already blowdown "
    "per kg of steam - the guide divided again by (1 - BD%); the engine takes no condensate return (all feedwater is "
    "makeup, the conservative case) while the guide subtracted one the form never asks for (its Condensate Return field "
    "does not exist); each boiler is sized for the FULL design output (one carries the plant), which the guide now says. "
    "Field names are the form's (Load Input Mode, Steam Pressure (gauge), Boiler Efficiency, Makeup Water TDS, plus the "
    "hot-water fields). Walked on the served page at 390 (2,000 kg/h steam): blowdown 177.5 kg/h, makeup 2,677.5 kg/h = "
    "steam + blowdown, no sideways scroll.")
ENGINE_CHECKED["Fire Sprinkler Hydraulic"] = (
    "FOUND AND FIXED, read against python-api/calcs/fire_sprinkler.py and NFPA 13: the density/area method itself is right "
    "(per-head flow = max(density x coverage, K sqrt(P_min))). Three defects around it: (1) the water supply was 60 min for "
    "every hazard - NFPA 13 Table 19.3.3.1.2 is Light 30, Ordinary 60-90, Extra 90-120 (the guide's 30/60/60/90/120): an "
    "Extra Hazard tank 1/3 to 1/2 short of water, Light doubled; (2) the form's hazard labels ('Ordinary Group 1', 'Extra "
    "Hazard Grp 1') matched none of the engine's keys, so every one fell to the Light row; (3) the FORM pre-filled hose "
    "streams of 250 / 500 / 950 L/min where NFPA 13 requires 100 / 250 / 500 gpm (379 / 946 / 1,893 L/min) - every Ordinary "
    "and Extra system's demand, tank and pump short by about half the allowance (input default and fallback 500 too). The "
    "guide carried the same wrong hose figures and a K.sqrt(P)-only flow; now the engine's method and NFPA's numbers; names "
    "are the form's. The vector fails on the old engine; walked on the served page at 390 (Extra Hazard 1 from its "
    "pre-fill): hose 1893, '2836.5 + 1893 = 4729.5 L/min', 'Duration ... 90 minutes', '425.65 m3', no sideways scroll.")
ENGINE_CHECKED["Fire Pump Sizing"] = (
    "FOUND AND FIXED, read against python-api/calcs/fire_pump.py: the guide's 'rated power >= Shaft Power x 1.15' - the "
    "engine took Q.dP / (pump eff x MOTOR eff), the electrical INPUT, as the shaft power, then x 1.15: every driver ~9% "
    "over the rule, and the report printed that input as 'Shaft power'. Now shaft = Q.dP / pump eff at the larger of the "
    "rated and 150% points, rating = that x 1.15, input = shaft / motor eff. The report's aliases did not reproduce its "
    "lines ('Required = shaft HP x nfpa_factor' where the factor was the churn 140%; 'P_motor = shaft / eff' printing the "
    "1.15 figure; diesel labelled 120% where the engine applies 1.15; jockey '+10%' where the engine adds 0.35 bar). All now "
    "the engine's. Door page 'Motor' now the selected 75 kW (it printed the input 56.96). The vector fails on the old "
    "engine; walked on the served page at 390 (1900 L/min, 7.0 bar): 'P_shaft = 51.35 kW', '68.8 HP x 1.15 = 79.2 HP', "
    "'75.0 kW', 'P_jockey = 7.594 + 0.35', no sideways scroll.")
ENGINE_CHECKED["Stairwell Pressurization"] = (
    "FOUND AND FIXED, read against python-api/calcs/stairwell_pressurization.py: the NFPA 92 method matches the guide "
    "(Q = Cd.A.sqrt(2.dP/rho), door leakage per Table B.1, the door-force lever arm). But the guide says 'each stairwell is "
    "pressurized independently by its own fan', and the report says 'N fans, each rated at Q per stairwell with a "
    "selected-HP motor' - the motor was picked for the TOTAL design flow of all stairwells (and the 'each fan' airflow "
    "carried no safety factor): two stairwells got 7.5 HP each where 5 HP serves. Each fan now carries one stairwell x 1.20 "
    "and its motor is picked for that (the total stays reported). Guide names are the form's; its formulas now state the "
    "wall leakage, site density and per-fan margin. The vector (hand ISA density) fails on the old engine; walked on the "
    "served page at 390 (2 stairwells, 10 floors): 'Q_fan = 3.044 x 1.2 = 3.653 m3/s; P = 2.44 kW', '5 HP per fan (2 "
    "fans)', no sideways scroll.")
ENGINE_CHECKED["Fluid Power"] = (
    "READ AGAINST python-api/calcs/fluid_power.py: the engine is right - delivered flow Q = Vg.n.eta_vol, hydraulic "
    "power Q.dP/600, shaft = P_hyd / (eta_vol x eta_mech), bore from sqrt(4F/(pi.P)), Boyle accumulator with P0 = 0.9 "
    "P-min. The guide was not: it put both efficiencies into the HYDRAULIC power and divided by them again for the motor. "
    "The report's working printed shaft = P_hyd / 0.92 (the engine divides by 0.95 x 0.92) and a fixed 0.92 motor "
    "efficiency whatever the form sent - it now prints the engine's eta_vol, eta_mech and eta_motor. Guide names are the "
    "form's (System Flow, Cylinder Stroke, Bore, Acc. P-min / P-max, Fluid Vol.). Walked on the served page at 390 (form "
    "defaults): '16.53 / (0.95 x 0.92) = 18.913 kW', '18.913 / 0.92 = 20.558 kW', no sideways scroll.")
ENGINE_CHECKED["Heat Exchanger"] = (
    "FOUND AND FIXED, read against python-api/calcs/heat_exchanger.py: the guide's chain A = Q/(U.F.dTlm), n_tubes = A / "
    "(pi.do.L) - but both film coefficients (and the shell diameter) were computed for an ASSUMED 100-tube bundle, and "
    "only the printed Re was redone at the resulting tube count, never U or the area: a 3 MW water/water exchanger was "
    "sized at 423 tubes / 75.78 m2 on a U of 1,312 W/m2K taken at 100 tubes' velocity, where its own geometry gives U "
    "779.5 and needs 711 tubes / 127.56 m2 - 40% short. The tube count, h_i, h_o, U and the area now converge together "
    "(damped fixed point). The tube Re in the transition zone (4,000-10,000) is now labelled so, not 'turbulent'. The "
    "guide said F came from the shell type (the engine computes it from P and R since Arc Q); its names are the form's. "
    "The vector is a CONSISTENCY lock (tube count holds the area; Re is at that tube count), stated as such - U itself "
    "rests on the fluid table and the Kern j-fit; it fails on the old engine. Walked on the served page at 390 (3 MW): "
    "'U_design = 779.5', 'A_required = 127.56 m2', 'n_tubes = 711', no sideways scroll.")
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
I1_FIXED["Hoist Capacity"] = (
    "FOUND AND FIXED: the form sends hoist_type (Wire Rope Electric / Electric Chain / Manual Chain); "
    "python-api/calcs/hoist_capacity.py recommended a 6x19 wire rope and sized a motor for all three - its own guide says a "
    "manual chain hoist needs no motor sizing. The type now decides the lifting medium (load chain, ASME B30.16) and whether "
    "a motor is sized, and the report's heading, specification items 1, 2 and 4 and its motor tile follow it. Oracle vector "
    "'Hoist Capacity - the form's hoist type decides the lifting medium and the motor' fails on the old engine. WALKED in "
    "the page through the Playwright MCP (signed in, Manual Chain): 'Lifting medium: load chain rated for a working load of "
    "at least 2045 kg', 'Manual chain hoist: hand-operated, no motor to size', '4. Load chain inspection schedule per ASME B30.16'.")
for _calc in ("Chiller System — Air Cooled", "Chiller System — Water Cooled"):
    I1_FIXED[_calc] = (
        "FOUND AND FIXED: both chiller forms take the manufacturer's rated IPLV / NPLV (optional); python-api/calcs/chiller.py "
        "always checked ASHRAE 90.1 against its own estimate from the full-load COP, so a chiller whose datasheet IPLV failed "
        "the minimum could pass on the estimate (and the reverse). An entered IPLV is the one checked now and the result says "
        "which it was (iplv_source). Oracle vectors '<chiller>: the form's rated IPLV is the one checked' fail on the old "
        "engine; walked through the served path (engineering-calc-agent, by curl).")
for _calc in ("Earthing / Grounding System", "Grease Trap Sizing", "FCU Selection"):
    I1_FIXED[_calc] = ("DECIDED, recorded on the report only: the value is descriptive and the result does not depend on it "
                       "(tools/census_calc_input_reach.py RECORDED states each reason - for FCU Selection the guide now says "
                       "a 4-pipe unit's heating coil is sized separately).")
for _calc in ("Bearing Life (L10)", "HVAC Cooling Load"):
    I1_FIXED[_calc] = ("DECIDED, recorded on the report only: the form's own label says so (tools/census_calc_input_reach.py "
                       "RECORDED names the label as the reason) - the value it sends is a reference printed on the report, "
                       "and every value the result depends on is read by the engine.")
# E1 - the engine a person is served is the oracle-verified one: closed when tools/census_calc_served_engine.py finds Python
# answering the form's own payload, with the report's reads covered and an oracle vector on the form's keys
E1_FIXED: dict[str, str] = {
    "Wire Sizing": (
        "FOUND AND FIXED: python-api/calcs/wire_sizing.py raised 'Provide load_kw, load_kva, or load_amps.' on every "
        "calculation the form sent (power_w, phase, ambient_temp, conduit_fill, load_type), so the edge function fell through "
        "silently to its TypeScript and the oracle-verified engine never sized a wire for a person - recorded as an "
        "'input-contract drift' residual in COMPREHENSIVE_STUDY_FULLSTACK_GATE.md and never closed. The form's keys are read "
        "now (a fill range at its top count; motors, HVAC, lighting and continuous loads at 125%, a general load at 100% - "
        "the form's own rule). The report's 21 reads are all in the Python result. Oracle vector 'Wire Sizing - the form's "
        "payload is sized by the verified engine' raises on the old engine; walked through the served path (curl): source python."),
    "Duct Sizing (Equal Friction)": (
        "FOUND AND FIXED: python-api/calcs/duct_sizing.py read only sections / flow_m3s, so it raised 'Duct flow rate must "
        "be greater than 0' on the page's segments[] schedule; Python was reached through main.py's alias and the edge "
        "function fell through to its TypeScript, which sized every duct a person drew (walked before the fix: source "
        "typescript). The page's segment method is ported with the TypeScript's result keys, and three of its defects fixed: "
        "the duct material changed nothing (roughness fixed at 0.09 mm, smooth Blasius below Re 1e5) - Colebrook at the "
        "material's roughness now, a flexible supply main 500 -> 550 mm; the fan's duct loss summed parallel branches - now "
        "the index run, 38.49 Pa against a 44.26 Pa sum for the form's defaults; and the drawing read single-duct keys the "
        "TypeScript never returned ('O0mm or 0x0mm, v = 0.00 m/s') - it is given the fan-side main. Three oracle vectors "
        "fail on the old engine. Walked on the served page at 390 (Run Calculation): source python, the schedule marks the "
        "index run, 'INDEX-RUN PRESSURE DROP ... 38.49 Pa'; the drawing reads 'O500mm or 650x350mm | v=6.11 m/s'. The "
        "TypeScript fallback keeps the old method - it answers only when Python is down."),
    "Lightning Protection System (LPS)": "MEASURED AGAIN - the E1 premise was the census's false reading: main.py already maps the page's name, handlers[\"Lightning Protection System (LPS)\"] = handlers[\"Lightning Protection (LPS)\"] (commit 84fbae35), and the census's first parser followed only `= <name>_calc`, so it reported no handler. Python has answered every LPS a person ran. Reading the engine under the right name found a real defect: the form's Type A / Type B earthing choice was never read - the engine forced a ring for LPL I/II or any building 20 m long. The arrangement is now the person's (IEC 62305-3 §5.4.2): Type A an electrode at each down conductor, min two, vertical >= 0.5 l1; Type B a ring ~1 m outside the walls, re = sqrt(A/pi) checked against l1, supplementary electrodes when short. Three oracle vectors fail on the old engine; walked on the served page (Type B (Ring) -> Run Calculation): source python, 'Ring 108 m ... re = 14.97 m >= l1 = 6.0 m'. The census follows aliases now. Open on ED149: l1 is max(5 m, 0.5 H), not Figure 3.",
    "V-Belt Drive Design": "MEASURED AGAIN - the row was the census's false reading: main.py already maps handlers[\"V-Belt Drive Design\"] = handlers[\"Gear / Belt Drive\"] (commit 84fbae35); the census's first parser could not follow the alias and reported no handler. Python has answered every belt drive. Read against the engine, it takes the form's driver_rpm / driven_rpm / center_dist_mm / service_factor (varied, every result moved); power_input / power_unit are echoes of the HP-to-kW conversion the form does, recorded. Oracle vector on the form's own names (Lp = 1600 mm, 9.0 kW design power); walked through the served path (curl): source python. The census follows aliases now.",
}
I1_FIXED["Wire Sizing"] = E1_FIXED["Wire Sizing"]
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
        elif key == "E1":
            if unit not in E1_FIXED:
                continue                                  # open: TypeScript still answers this calculator
            import census_calc_served_engine as cse
            served = next((r for r in cse.census()["rows"] if r["calc"] == unit), {})
            if served.get("served") != "python":
                held.append((t["id"], f"{unit}: still answered by {served.get('served')} - {served.get('why')}"))
                continue
            why = E1_FIXED[unit]
            what = f"{unit}: the form's own default payload is answered by the Python engine (tools/census_calc_served_engine.py)"
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
        if key in ("I1", "E1"):
            basis = (f"[{today}] {why} MEASURED: {what} (how each row was walked is in its sentence above). HELD BY: gate "
                     f"calc-input-reach (ratchet calc_input_reach_baseline.json; teeth plant an unread key) and gate "
                     f"calc_formula_accuracy (the oracle vector named above). pct -> {{pct}}")
            gates = ["calc-served-engine", "calc_formula_accuracy"] if key == "E1" else ["calc-input-reach", "calc_formula_accuracy"]
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
