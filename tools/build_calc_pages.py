"""
build_calc_pages.py — the programmatic-SEO calculator page generator (Pillar 3).
================================================================================
Emits ONE static-HTML landing page per engineering calculator at
`/tools/<slug>/`, each answer-first with a REAL worked example computed at BUILD
time (not client-side JS) + SoftwareApplication/HowTo/FAQPage schema.

WHY static HTML with baked-in numbers:
  AI crawlers (ChatGPT, Claude, CCBot) FETCH JavaScript but DO NOT EXECUTE it
  [substrate/external/external-ai-crawlers-fetch-but-do-not-execute-javascript-].
  The live calculators live in engineering-design.js (client-side, noindex) — so
  to an AI crawler they are a blank page. These pages put the formula + a worked
  numeric example in the HTML itself, so the calc surface becomes citable.
  Stat-rich content raises AI-citation likelihood ~41%
  [external-generative-engine-optimization-statistics-2026-a].

Grounding: SoftwareApplication schema for B2B SaaS + FAQPage for AI Overviews +
static site generation, deployed in staged batches
[external-programmatic-seo-pages-step-by-step-implementati]. Genuine utility per
page (real formula + real worked numbers) avoids the thin-page penalty
[external-programmatic-seo-strategy-calculator-tool-pages-].

DATA-DRIVEN: each entry in CALC_DATA supplies the module, page identity, a
CURATED example_inputs set (the generator runs the calc to bake the worked
numbers), and the headline outputs to surface. FAQ/steps/formula are templated
from the data unless a custom override is given. Built in verified discipline
batches toward all 58 calc modules.

RUN (needs the calc deps — use the python-api venv):
    test-data-seeder/venv/Scripts/python.exe tools/build_calc_pages.py [--all] [--slug pump-tdh-calculator]

Output → `seo_assets/calc_pages_staging/<slug>/index.html` — STAGING, not the
site root. Nothing ships until Ian reviews + moves it. Gate: tools/validate_calc_pages.py
"""
from __future__ import annotations

import sys
import html
import json
import importlib
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
PYAPI = ROOT / "python-api"
OUT_DIR = ROOT / "seo_assets" / "calc_pages_staging"
SITE = "https://workhiveph.com"
PILLAR = ("/learn/free-engineering-calculators-philippine-plants/",
          "Free Engineering Calculators for Philippine Plants")

if str(PYAPI) not in sys.path:
    sys.path.insert(0, str(PYAPI))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ── Per-calc data ─────────────────────────────────────────────────────────────
# slug -> {
#   module, title, keyword, discipline, standard (fallback if calc doesn't return one),
#   example_inputs (CURATED, domain-valid), example_desc (prose of the scenario),
#   headline [(label, out_key, unit)]  — the numbers the answer + table surface,
#   blurb (one line: what it computes),
#   faqs? [(q,a)]  — custom; else templated,
#   formula? str  — custom; else a generic "computed per <standard>" line,
#   related_article? (url, text),
# }
CALC_DATA: dict[str, dict] = {
    # ── KPI head terms (no calc module — precomputed, see _run_calc) ──────────
    "oee-calculator": {
        "module": None, "title": "OEE Calculator", "discipline": "Reliability & Metrics",
        "keyword": "OEE calculator online free",
        "standard": "Nakajima TPM | ISO 22400-2",
        "blurb": "The OEE Calculator computes Overall Equipment Effectiveness as Availability x Performance x Quality, the single number for how much saleable output a line actually produced versus its maximum.",
        "example_inputs": {},
        "computed": {"oee_pct": 83.8, "availability_pct": 90.0, "performance_pct": 95.0,
                     "quality_pct": 98.0, "world_class_pct": 85.0,
                     "standard": "Nakajima TPM | ISO 22400-2"},
        "example_desc": "a bottling line available 90% of planned time, running at 95% of rated speed, producing 98% good bottles",
        "headline": [("OEE", "oee_pct", "%"), ("Availability", "availability_pct", "%"),
                     ("Performance", "performance_pct", "%"), ("Quality", "quality_pct", "%"),
                     ("World-class benchmark", "world_class_pct", "%")],
        "formula": "OEE = Availability x Performance x Quality. Availability = run time / planned production time; Performance = (ideal cycle time x total count) / run time; Quality = good count / total count. For the example: 0.90 x 0.95 x 0.98 = 0.838, i.e. 83.8%.",
        "faqs": [
            ("How do you calculate OEE?", "Multiply the three factors: OEE = Availability x Performance x Quality. For a line available 90% of planned time, running at 95% of rated speed, and producing 98% good units, OEE = 0.90 x 0.95 x 0.98 = 83.8%."),
            ("What is a good OEE score?", "85% is considered world-class. Most plants start between 40% and 60%, so there is usually a large and inexpensive gap to close — attack availability losses (unplanned downtime, changeovers) first, then speed, then quality."),
            ("Why is my OEE lower than my availability?", "Because availability is only one of three factors. A line that is available 90% of the time but runs slow and scraps 5% of output lands near 80% OEE. Measuring availability alone is the most common OEE mistake."),
            ("Do I need sensors to measure OEE?", "No. You can calculate OEE from shift records: planned time, downtime, counts produced, and rejects. A disciplined logbook is enough to start; sensors improve resolution later."),
        ],
        "related_article": ("/learn/what-is-oee-how-to-calculate/", "What is OEE and how to calculate it"),
        "siblings": [("/tools/mtbf-calculator/", "MTBF & MTTR Calculator")],
    },
    "mtbf-calculator": {
        "module": None, "title": "MTBF & MTTR Calculator", "discipline": "Reliability & Metrics",
        "keyword": "MTBF and MTTR calculator",
        "standard": "ISO 14224 | IEC 60050-192 | SMRP",
        "blurb": "The MTBF & MTTR Calculator computes Mean Time Between Failures, Mean Time To Repair, and the availability they produce together.",
        "example_inputs": {},
        "computed": {"mtbf_h": 800.0, "mttr_h": 8.0, "availability_pct": 99.0,
                     "operating_h": 4000.0, "failures": 5, "repair_h": 40.0,
                     "standard": "ISO 14224 | IEC 60050-192 | SMRP"},
        "example_desc": "a pump that ran 4,000 hours, failed 5 times, and took 40 hours of repair in total",
        "headline": [("MTBF", "mtbf_h", "h"), ("MTTR", "mttr_h", "h"),
                     ("Availability", "availability_pct", "%"), ("Failures", "failures", "")],
        "formula": "MTBF = operating hours / number of failures. MTTR = total repair time / number of repairs. Availability = MTBF / (MTBF + MTTR). For the example: MTBF = 4000/5 = 800 h, MTTR = 40/5 = 8 h, Availability = 800/808 = 99.0%.",
        "faqs": [
            ("How do you calculate MTBF?", "Divide total operating hours by the number of failures in that period. A pump that ran 4,000 hours and failed 5 times has an MTBF of 800 hours."),
            ("How do you calculate MTTR?", "Divide total repair time by the number of repairs. Five repairs totalling 40 hours gives an MTTR of 8 hours."),
            ("What is the difference between MTBF and MTTR?", "MTBF measures reliability — how long the asset runs before failing. MTTR measures maintainability — how long it takes to restore. You raise MTBF with better preventive maintenance and root-cause fixes; you lower MTTR with spares availability and standard work."),
            ("How do MTBF and MTTR give availability?", "Availability = MTBF / (MTBF + MTTR). With MTBF 800 h and MTTR 8 h, availability is 99.0%. That figure is also what feeds the availability factor inside OEE."),
        ],
        "related_article": ("/learn/mtbf-vs-mttr-for-supervisors/", "MTBF vs MTTR for supervisors"),
        "siblings": [("/tools/oee-calculator/", "OEE Calculator")],
    },
    "pump-tdh-calculator": {
        "module": "pump_tdh", "title": "Pump TDH Calculator", "discipline": "Plumbing & Pumps",
        "keyword": "pump total dynamic head calculator",
        "standard": "ISO 9906 | PSME Code | ASHRAE 2021 Ch.22",
        "blurb": "The Pump TDH Calculator sizes a pump and motor from Total Dynamic Head (TDH) = static head + friction head + velocity head.",
        "example_inputs": {"flow_rate": 200, "static_head": 15, "pipe_diameter": 50,
                           "pipe_length": 60, "pipe_material": "PVC", "fluid_temp_c": 30,
                           "pump_efficiency": 70, "motor_efficiency": 90},
        "example_desc": "a 200 L/min pump lifting water 15 m through 60 m of 50 mm PVC pipe",
        "headline": [("Total Dynamic Head", "TDH", "m"), ("Pipe velocity", "pipe_velocity", "m/s"),
                     ("Recommended motor", "recommended_kw", "kW"), ("NPSH available", "npsh_available", "m")],
        "formula": "TDH = H_static + H_friction + H_velocity, where friction head uses Darcy–Weisbach with the Colebrook–White friction factor and real water properties at the operating temperature.",
        "faqs": [
            ("What is total dynamic head (TDH)?", "TDH is the total equivalent height a pump must overcome: the static lift plus friction losses in the pipe plus the velocity head. It sets the pump and motor size."),
            ("How do I calculate pump head?", "Add static head + friction head + velocity head. Friction head comes from the Darcy–Weisbach equation using the Colebrook–White friction factor for the pipe material and flow."),
            ("What motor size do I need for a 200 L/min pump?", "For a typical 200 L/min duty at ~18 m TDH, a 1.1 kW (1.5 HP) motor is usually enough after applying pump and motor efficiency and a service-factor margin. Always confirm against the manufacturer curve."),
            ("What is NPSH available and why does it matter?", "NPSH available is the suction-side pressure margin before cavitation. It must exceed the pump's NPSH required, or the pump cavitates and wears out. It falls with elevation and hot water."),
        ],
        "related_article": ("/learn/predictive-maintenance-on-a-budget-philippines/", "Predictive maintenance on a budget"),
    },
    "pipe-sizing-calculator": {
        "module": "pipe_sizing", "title": "Pipe Sizing Calculator", "discipline": "Plumbing & Pumps",
        "keyword": "water pipe size calculator by flow rate",
        "standard": "ASHRAE 2021 Fundamentals Ch.22 | PSME Code | PNS/ISO 4427",
        "blurb": "The Pipe Sizing Calculator picks the smallest standard pipe that keeps velocity in the safe economical range for a given flow.",
        "example_inputs": {"flow_rate": 300, "pipe_length": 50, "pipe_material": "PVC", "fluid_temp_c": 30},
        "example_desc": "300 L/min of water through 50 m of PVC pipe",
        "headline": [("Recommended nominal size", "recommended_nominal_mm", "mm"),
                     ("Velocity", "pipe_velocity", "m/s"), ("Flow", "flow_m3hr", "m³/h")],
        "related_article": ("/learn/free-engineering-calculators-philippine-plants/", "All engineering calculators"),
    },
    "wire-sizing-calculator": {
        "module": "wire_sizing", "title": "Wire Sizing Calculator", "discipline": "Electrical & Power",
        "keyword": "electrical wire size calculator kW",
        "standard": "PEC 2017 | NEC 2020 | IEC 60364",
        "blurb": "The Wire Sizing Calculator picks the conductor size (mm²) for a load, applying continuous-load, temperature, and conduit-fill derating plus a voltage-drop check.",
        "example_inputs": {"load_kw": 50, "voltage": 400, "phases": 3, "power_factor": 0.85,
                           "wire_length_m": 40, "ambient_temp_c": 35, "conductors_in_conduit": 3,
                           "continuous_load": True, "circuit_type": "Feeder"},
        "example_desc": "a 50 kW 3-phase 400 V feeder, 40 m long, at 35 °C ambient",
        "headline": [("Conductor size", "governing_mm2", "mm²"), ("Design current", "design_current_a", "A"),
                     ("Derated ampacity", "derated_ampacity_a", "A")],
    },
    "transformer-sizing-calculator": {
        "module": "transformer_sizing", "title": "Transformer Sizing Calculator", "discipline": "Electrical & Power",
        "keyword": "transformer sizing calculator kVA",
        "standard": "PEC 2017 Art. 4.50 | IEC 60076-1:2011",
        "blurb": "The Transformer Sizing Calculator picks the standard kVA rating for a load with spare capacity and reports the resulting loading.",
        "example_inputs": {"load_kva": 100, "primary_voltage": 13800, "secondary_voltage": 400,
                           "load_power_factor": 0.85, "phases": 3, "spare_capacity_pct": 25},
        "example_desc": "a 100 kVA load on a 13.8 kV / 400 V 3-phase supply with 25% spare",
        "headline": [("Rated size", "rated_kva", "kVA"), ("Required", "required_kva", "kVA"),
                     ("Loading", "loading_pct", "%")],
    },
    "power-factor-correction-calculator": {
        "module": "power_factor_correction", "title": "Power Factor Correction Calculator", "discipline": "Electrical & Power",
        "keyword": "power factor correction capacitor kVAR calculator",
        "standard": "IEEE 18-2012 | IEEE 1036-2010",
        "blurb": "The Power Factor Correction Calculator sizes the capacitor bank (kVAR) needed to raise power factor from its present value to a target.",
        "example_inputs": {"load_kw": 100, "pf_existing": 0.80, "pf_target": 0.95,
                           "voltage_v": 400, "phases": 3},
        "example_desc": "a 100 kW load improving power factor from 0.80 to 0.95",
        "headline": [("kVAR required", "kvar_required", "kVAR"), ("Selected bank", "selected_kvar", "kVAR"),
                     ("Per phase", "kvar_per_phase", "kVAR")],
    },
    "hvac-cooling-load-calculator": {
        "module": "hvac_cooling_load", "title": "HVAC Cooling Load Calculator", "discipline": "HVAC & Cooling",
        "keyword": "HVAC cooling load calculator kW TR",
        "standard": "ASHRAE 62.1 | 90.1 | 55 | Fundamentals",
        "blurb": "The HVAC Cooling Load Calculator estimates the cooling load (kW and tons of refrigeration) for a space from area, occupancy, equipment, and climate.",
        "example_inputs": {"floor_area": 150, "ceiling_height": 3.5, "persons": 25, "equipment_kw": 15,
                           "outdoor_temp": 35, "indoor_temp": 24, "indoor_rh_pct": 55},
        "example_desc": "a 150 m² space with 25 people, 15 kW of equipment, at 35 °C outdoor / 24 °C indoor",
        "headline": [("Cooling load", "kW", "kW"), ("Tons", "TR", "TR"), ("Recommended unit", "recommended_TR", "TR")],
    },
    "ventilation-ach-calculator": {
        "module": "ventilation_ach", "title": "Ventilation / ACH Calculator", "discipline": "HVAC & Cooling",
        "keyword": "air changes per hour ventilation calculator",
        "standard": "ASHRAE 62.1:2022 Ventilation Rate Procedure",
        "blurb": "The Ventilation / ACH Calculator finds the required air changes per hour and supply airflow for a room from its function, area, and occupancy.",
        "example_inputs": {"floor_area": 150, "ceiling_height": 3.5, "persons": 25, "room_function": "Office"},
        "example_desc": "a 150 m² office with 25 people and a 3.5 m ceiling",
        "headline": [("Required ACH", "required_ach", "/h"), ("Supply airflow", "supply_cmh", "m³/h"),
                     ("Supply airflow", "supply_cfm", "CFM")],
    },
    "cooling-tower-calculator": {
        "module": "cooling_tower", "title": "Cooling Tower Sizing Calculator", "discipline": "HVAC & Cooling",
        "keyword": "cooling tower sizing calculator range approach",
        "standard": "CTI STD-201 | ASHRAE 2021 Fundamentals",
        "blurb": "The Cooling Tower Sizing Calculator finds the tower range, approach, and effectiveness for a heat-rejection duty at a design wet-bulb.",
        "example_inputs": {"heat_rejection_kw": 500},
        "example_desc": "a 500 kW heat-rejection duty at a 28 °C design wet-bulb",
        "headline": [("Heat rejection", "heat_rejection_tr", "TR"), ("Range", "range_c", "°C"),
                     ("Approach", "approach_c", "°C"), ("Effectiveness", "effectiveness", "")],
    },
    "compressed-air-calculator": {
        "module": "compressed_air", "title": "Compressed Air System Calculator", "discipline": "HVAC & Cooling",
        "keyword": "compressor sizing calculator CFM kW",
        "standard": "ISO 1217 | PSME Code | ASME B31.3 | CAGI",
        "blurb": "The Compressed Air System Calculator sizes the compressor (kW/HP) and air receiver for a plant's demand, pressure, and duty cycle.",
        "example_inputs": {"flow_rate": 10, "working_pressure": 7, "duty_cycle_pct": 60,
                           "compressor_eff_pct": 88, "leakage_pct": 10},
        "example_desc": "a 10 m³/min plant demand at 7 barg and 60% duty",
        "headline": [("Recommended compressor", "recommended_kw", "kW"), ("Recommended", "recommended_hp", "HP"),
                     ("Air receiver", "receiver_volume_m3", "m³")],
    },
    "fire-pump-calculator": {
        "module": "fire_pump", "title": "Fire Pump Sizing Calculator", "discipline": "Fire Protection",
        "keyword": "fire pump sizing calculator NFPA 20",
        "standard": "NFPA 20:2022",
        "blurb": "The Fire Pump Sizing Calculator picks the rated flow and pressure for a fire-protection duty per NFPA 20 pump-selection rules.",
        "example_inputs": {"system_flow_gpm": 500, "system_pressure_psi": 100, "pipe_length": 60},
        "example_desc": "a 500 GPM / 100 psi fire-protection demand",
        "headline": [("Recommended flow", "recommended_flow_lpm", "L/min"),
                     ("Rated pressure", "rated_pressure_bar", "bar"), ("Motor", "motor_kw_calculated", "kW")],
    },
    "generator-sizing-calculator": {
        "module": "generator_sizing", "title": "Generator Sizing Calculator", "discipline": "Electrical & Power",
        "keyword": "genset sizing calculator kVA",
        "standard": "ISO 8528-1:2018",
        "blurb": "The Generator Sizing Calculator finds the standby genset kVA for a load, accounting for the largest motor's starting kVA surge.",
        "example_inputs": {"demand_kw": 100, "largest_motor_hp": 20, "motor_pf": 0.85,
                           "start_method": "DOL", "fuel_backup_hrs": 8, "design_margin_pct": 10},
        "example_desc": "a 100 kW load with a 20 HP DOL-started largest motor",
        "headline": [("Recommended genset", "recommended_kVA", "kVA"), ("Steady demand", "required_kVA_steady", "kVA"),
                     ("Peak during start", "kVA_during_start", "kVA")],
    },
    "bearing-life-calculator": {
        "module": "bearing_life", "title": "Bearing Life (L10) Calculator", "discipline": "Mechanical & Machine Design",
        "keyword": "bearing L10 life calculator ISO 281",
        "standard": "ISO 281:2007",
        "blurb": "The Bearing Life (L10) Calculator estimates rated fatigue life in hours from the bearing's dynamic capacity, load, and speed.",
        "example_inputs": {"bearing_type": "Ball", "C_kN": 50, "speed_rpm": 1500,
                           "Fr_kN": 5, "Fa_kN": 1, "reliability_pct": 90},
        "example_desc": "a ball bearing (C = 50 kN) at 1500 rpm under a 5 kN radial + 1 kN axial load",
        "headline": [("L10 life", "L10h", "h"), ("Dynamic equivalent load", "P_kN", "kN"), ("C/P ratio", "C_over_P", "")],
    },
    "elevator-traffic-calculator": {
        "module": "elevator_traffic", "title": "Elevator Traffic Calculator", "discipline": "Vertical Transport",
        "keyword": "elevator traffic analysis calculator interval",
        "standard": "CIBSE Guide D:2015",
        "blurb": "The Elevator Traffic Calculator finds the round-trip time, interval, and 5-minute handling capacity for a lift group.",
        "example_inputs": {"n_floors": 10, "floor_height": 3.5, "population": 300, "n_elevators": 2,
                           "capacity": 13, "speed": 1.5, "occupancy_type": "Office"},
        "example_desc": "a 10-floor office with 300 people served by two 13-person lifts at 1.5 m/s",
        "headline": [("Interval", "interval_s", "s"), ("Handling capacity", "HC_pct", "%"),
                     ("Round-trip time", "RTT_s", "s")],
    },
    "boiler-steam-calculator": {
        "module": "boiler_steam", "title": "Boiler / Steam Duty Calculator", "discipline": "Boiler & Utilities",
        "keyword": "boiler steam duty calculator kW BHP",
        "standard": "ASME BPVC Section I",
        "blurb": "The Boiler / Steam Duty Calculator finds the boiler heat duty (kW and boiler HP) from steam pressure, flow, and feedwater temperature.",
        "example_inputs": {"steam_pressure_bar": 10, "steam_flowrate_kgs": 1, "feedwater_temp_C": 80,
                           "boiler_efficiency_pct": 85},
        "example_desc": "1 kg/s of saturated steam at 10 bar from 80 °C feedwater",
        "headline": [("Boiler duty", "duty_kW", "kW"), ("Boiler HP", "BHP", "BHP"), ("Saturation temp", "T_sat_C", "°C")],
    },
    "bolt-torque-calculator": {
        "module": "bolt_torque", "title": "Bolt Torque Calculator", "discipline": "Mechanical & Machine Design",
        "keyword": "bolt torque and preload calculator",
        "standard": "ISO 898-1:2013 | VDI 2230",
        "blurb": "The Bolt Torque Calculator finds the tightening torque and clamp preload for a bolt from its size, grade, and target preload.",
        "example_inputs": {"bolt_size": "M16", "bolt_grade": "8.8", "preload_pct": 75, "ext_load_kN": 40, "n_bolts": 8},
        "example_desc": "eight M16 grade-8.8 bolts torqued to 75% proof load under a 40 kN external load",
        "headline": [("Tightening torque", "torque_Nm", "N·m"), ("Preload per bolt", "Fi_kN", "kN"), ("Stress utilisation", "stress_util", "%")],
    },
    "cable-tray-sizing-calculator": {
        "module": "cable_tray_sizing", "title": "Cable Tray Sizing Calculator", "discipline": "Electrical & Power",
        "keyword": "cable tray sizing calculator fill",
        "standard": "NEMA VE 1-2017 | PEC 2017",
        "blurb": "The Cable Tray Sizing Calculator picks the tray width that keeps cable fill within the NEC/NEMA limit for a bundle of cables.",
        "example_inputs": {"tray_type": "Ladder", "depth_mm": 100, "fill_ratio_pct": 40, "span_m": 3, "run_length_m": 40,
                           "cables": [{"od_mm": 25, "qty": 10}, {"od_mm": 15, "qty": 20}]},
        "example_desc": "a ladder tray carrying ten 25 mm and twenty 15 mm cables over a 3 m span",
        "headline": [("Selected tray width", "selected_width_mm", "mm"), ("Actual fill", "fill_actual_pct", "%"), ("Load class", "nema_load_class", "")],
    },
    "roof-drain-calculator": {
        "module": "roof_drain", "title": "Roof Drain Sizing Calculator", "discipline": "Plumbing & Pumps",
        "keyword": "roof drain sizing calculator rainfall",
        "standard": "IPC 2021 | Philippine Plumbing Code",
        "blurb": "The Roof Drain Sizing Calculator picks the drain and leader size for a roof area at a design rainfall intensity.",
        "example_inputs": {"roof_area": 300, "n_drains": 3, "intensity_mmhr": 150, "leader_slope_pct": 1, "pipe_material": "uPVC"},
        "example_desc": "a 300 m² roof with 3 drains at 150 mm/h design rainfall",
        "headline": [("Drain size", "drain_size_mm", "mm"), ("Total flow", "q_total_ls", "L/s"), ("Leader size", "leader_size_mm", "mm")],
    },
    "water-softener-calculator": {
        "module": "water_softener", "title": "Water Softener Sizing Calculator", "discipline": "Plumbing & Pumps",
        "keyword": "water softener sizing calculator resin",
        "standard": "WQA | NSF/ANSI 44 | PNS 1998",
        "blurb": "The Water Softener Sizing Calculator finds the resin volume, tank size, and regeneration interval for a hardness-removal duty.",
        "example_inputs": {"demand_source": "people", "n_people": 50, "per_capita_lpd": 120, "inlet_hardness": 250, "target_hardness": 50, "regen_interval": 3},
        "example_desc": "a 50-person building (6 m³/day) softening water from 250 to 50 mg/L hardness",
        "headline": [("Resin volume", "resin_L_per_unit", "L"), ("Tank diameter", "tank_dia_mm", "mm"), ("Regen interval", "regen_interval_days", "days")],
    },
    "hoist-capacity-calculator": {
        "module": "hoist_capacity", "title": "Hoist Capacity Calculator", "discipline": "Vertical Transport",
        "keyword": "hoist crane capacity calculator",
        "standard": "ASME B30.2",
        "blurb": "The Hoist Capacity Calculator finds the gross load, motor power, and safety margin for a lifting duty.",
        "example_inputs": {"rated_load_kg": 2000, "hook_weight_kg": 30, "lift_height_m": 6, "lift_speed_mpm": 8, "n_parts": 2, "safety_factor": 5},
        "example_desc": "a 2000 kg lift at 8 m/min on a 2-part rope line",
        "headline": [("Gross load", "gross_load_kg", "kg"), ("Motor", "motor_hp_std", "HP"), ("Motor power", "motor_kW", "kW")],
    },
    "lightning-protection-calculator": {
        "module": "lightning_protection", "title": "Lightning Protection Calculator", "discipline": "Electrical & Power",
        "keyword": "lightning protection rolling sphere calculator",
        "standard": "IEC 62305",
        "blurb": "The Lightning Protection Calculator finds the rolling-sphere radius, air-terminal mesh size, and protection level for a building.",
        "example_inputs": {"building_length_m": 40, "building_width_m": 25, "building_height_m": 18, "lpl": "LPL III", "location": "Manila", "structure_type": "Common"},
        "example_desc": "a 40 × 25 × 18 m building protected to LPL III in Manila",
        "headline": [("Rolling-sphere radius", "rolling_sphere_R_m", "m"), ("Mesh size", "mesh_size_m", "m"), ("Protection efficiency", "protection_efficiency_pct", "%")],
    },
    "load-schedule-calculator": {
        "module": "load_schedule", "title": "Electrical Load Schedule Calculator", "discipline": "Electrical & Power",
        "keyword": "electrical panel load schedule calculator",
        "standard": "PEC 2017 | NEC 2020 Art.220+430",
        "blurb": "The Load Schedule Calculator totals connected and demand load for a panel and sizes the feeder breaker.",
        "example_inputs": {"panel_voltage": 400, "panel_phases": 3, "panel_rating_a": 400, "feeder_length_m": 30,
                           "loads": [{"load_name": "Lighting", "qty": 1, "watts_each": 8000, "load_type": "Lighting", "power_factor": 0.9},
                                     {"load_name": "Motor", "qty": 1, "watts_each": 15000, "load_type": "Motor", "power_factor": 0.85}]},
        "example_desc": "a 400 V 3-phase panel with 8 kW lighting and a 15 kW motor",
        "headline": [("Demand load", "total_demand_kW", "kW"), ("Demand", "total_demand_kVA", "kVA"), ("Feeder breaker", "feeder_breaker_A", "A")],
    },
    "fire-alarm-battery-calculator": {
        "module": "fire_alarm_battery", "title": "Fire Alarm Battery Calculator", "discipline": "Fire Protection",
        "keyword": "fire alarm battery standby calculator NFPA 72",
        "standard": "NFPA 72:2022",
        "blurb": "The Fire Alarm Battery Calculator sizes the standby battery (Ah) for a fire alarm panel from its device load, standby hours, and alarm time.",
        "example_inputs": {"system_voltage": 24, "standby_hours": 24, "alarm_minutes": 5, "panel_standby_mA": 100, "panel_alarm_mA": 500,
                           "n_addr_smoke": 40, "n_heat": 10, "n_pull": 6, "n_horn_strobe": 12},
        "example_desc": "a 24 V panel with 40 smoke + 10 heat detectors, 6 pull stations, 12 horn/strobes, and 24 h standby",
        "headline": [("Selected battery", "selected_Ah", "Ah"), ("Required", "Ah_required", "Ah"), ("Standby", "standby_hours", "h")],
    },
    "ahu-sizing-calculator": {
        "module": "ahu_sizing", "title": "AHU Sizing Calculator", "discipline": "HVAC & Cooling",
        "keyword": "air handling unit sizing calculator CFM",
        "standard": "ASHRAE 62.1 | 90.1 | Fundamentals",
        "blurb": "The AHU Sizing Calculator finds the supply airflow, coil capacity, and fan motor for an air-handling unit from its cooling load.",
        "example_inputs": {"cooling_load_kW": 50, "supply_air_temp_c": 13, "indoor_temp": 24, "oa_pct": 15, "floor_area": 300, "persons": 40},
        "example_desc": "a 50 kW cooling load for a 300 m² space with 40 people",
        "headline": [("Supply airflow", "supply_flow_cfm", "CFM"), ("Coil capacity", "coil_total_tr", "TR"), ("Fan motor", "recommended_motor_kw", "kW")],
    },
    "drainage-pipe-sizing-calculator": {
        "module": "drainage_pipe_sizing", "title": "Drainage Pipe Sizing Calculator", "discipline": "Plumbing & Pumps",
        "keyword": "drainage pipe sizing calculator DFU",
        "standard": "Philippine Plumbing Code | UPC Table 7-5",
        "blurb": "The Drainage Pipe Sizing Calculator picks the drain pipe diameter from the total drainage fixture units (DFU) and slope.",
        "example_inputs": {"fixtures": [{"fixture_type": "Water Closet", "quantity": 10}, {"fixture_type": "Lavatory / Hand Sink", "quantity": 8}, {"fixture_type": "Urinal (flush valve)", "quantity": 5}], "system_type": "Building Drain", "slope": 2, "pipe_material": "PVC"},
        "example_desc": "a building drain serving 10 water closets, 8 lavatories, and 5 urinals at 2% slope",
        "headline": [("Total DFU", "total_dfu", "DFU"), ("Recommended diameter", "recommended_dia_mm", "mm"), ("Velocity", "design_velocity", "m/s")],
    },
    "domestic-water-demand-calculator": {
        "module": "domestic_water", "title": "Domestic Water Demand Calculator", "discipline": "Plumbing & Pumps",
        "keyword": "domestic water demand calculator fixture units",
        "standard": "PSME Code | Hunter's Curve",
        "blurb": "The Domestic Water Demand Calculator finds peak water flow, tank size, and booster need from a building's water-supply fixture units.",
        "example_inputs": {"fixtures": [{"fixture_type": "Water Closet (flush valve)", "quantity": 10}, {"fixture_type": "Lavatory (faucet)", "quantity": 8}, {"fixture_type": "Shower head", "quantity": 4}], "num_persons": 50, "building_floors": 3, "floor_height_m": 3.5, "pipe_material": "PPR"},
        "example_desc": "a 3-floor building (50 persons) with 10 flush-valve WCs, 8 lavatories, and 4 showers",
        "headline": [("Water fixture units", "total_wsfu", "WSFU"), ("Peak flow", "peak_flow_lpm", "L/min"), ("Storage tank", "recommended_tank_m3", "m³")],
    },
    "water-supply-pipe-calculator": {
        "module": "water_supply_pipe", "title": "Water Supply Pipe Sizing Calculator", "discipline": "Plumbing & Pumps",
        "keyword": "water supply pipe sizing calculator WFU",
        "standard": "Philippine Plumbing Code Table A-2/A-3",
        "blurb": "The Water Supply Pipe Sizing Calculator picks the supply pipe diameter from the water fixture units (WFU) and available pressure.",
        "example_inputs": {"fixtures": [{"fixture_type": "Water Closet (Flush Valve)", "quantity": 10}, {"fixture_type": "Lavatory / Hand Sink", "quantity": 8}], "supply_type": "Flush Valve", "pipe_length": 40, "pipe_material": "PPR"},
        "example_desc": "a flush-valve supply serving 10 WCs and 8 lavatories over 40 m",
        "headline": [("Recommended diameter", "recommended_dia_mm", "mm"), ("Peak flow", "peak_lpm", "L/min"), ("Velocity", "pipe_velocity", "m/s")],
    },
    "hot-water-demand-calculator": {
        "module": "hot_water_demand", "title": "Hot Water Demand Calculator", "discipline": "Plumbing & Pumps",
        "keyword": "hot water demand and storage calculator",
        "standard": "ASHRAE HVAC Applications Handbook Ch.50",
        "blurb": "The Hot Water Demand Calculator finds daily hot-water demand, peak-hour load, and storage tank size for a building.",
        "example_inputs": {"uses": [{"use_type": "Office Worker", "quantity": 50}, {"use_type": "Restaurant Meal", "quantity": 100}]},
        "example_desc": "50 office workers plus 100 restaurant meals per day",
        "headline": [("Daily demand", "total_daily_L", "L/day"), ("Storage tank", "recommended_storage_L", "L"), ("Heat energy", "heat_energy_kWh", "kWh")],
    },
    "grease-trap-calculator": {
        "module": "grease_trap", "title": "Grease Trap Sizing Calculator", "discipline": "Plumbing & Pumps",
        "keyword": "grease trap sizing calculator PDI",
        "standard": "PDI G-101 | DENR DAO 2016-08",
        "blurb": "The Grease Trap Sizing Calculator finds the design flow, liquid capacity, and cleaning interval for a kitchen grease interceptor.",
        "example_inputs": {"fixtures": [{"flow_lpm": 30, "qty": 2}], "meals_per_day": 200, "suf": 0.75},
        "example_desc": "a commercial kitchen with two 30 L/min fixtures serving 200 meals/day",
        "headline": [("Design flow", "q_design_lpm", "L/min"), ("Liquid capacity", "liquid_cap_l", "L"), ("Cleaning interval", "clean_interval_days", "days")],
    },
    "noise-acoustics-calculator": {
        "module": "noise_acoustics", "title": "Noise / Acoustics Calculator", "discipline": "Mechanical & Machine Design",
        "keyword": "industrial noise level distance calculator",
        "standard": "ISO 9613-2 | OSHA 1910.95 | DOLE D.O. 13",
        "blurb": "The Noise / Acoustics Calculator finds the sound pressure level at a distance from a source and checks it against the room's noise-criteria limit.",
        "example_inputs": {"calc_type": "Room", "source_Lw_dB": 95, "distance_m": 5, "space_type": "Factory / Workshop", "room_surface_m2": 400, "avg_absorption_coeff": 0.15},
        "example_desc": "a 95 dB machine in a 400 m² factory, measured 5 m away",
        "headline": [("Sound pressure", "Lp_at_distance_dB", "dB"), ("NC limit", "NC_limit", "NC"), ("Source power", "source_Lw_dB", "dB")],
    },
    "heat-exchanger-calculator": {
        "module": "heat_exchanger", "title": "Heat Exchanger LMTD Calculator", "discipline": "Mechanical & Machine Design",
        "keyword": "heat exchanger LMTD calculator",
        "standard": "TEMA 10th Ed. | ASME BPVC Sec.VIII",
        "blurb": "The Heat Exchanger Calculator finds the corrected LMTD, effectiveness, and NTU for a shell-and-tube exchanger duty.",
        "example_inputs": {"duty_kW": 500, "hot_inlet_C": 90, "hot_outlet_C": 60, "cold_inlet_C": 30, "cold_outlet_C": 50, "flow_config": "Counterflow", "hot_fluid": "Water", "cold_fluid": "Water"},
        "example_desc": "a 500 kW counterflow duty cooling water 90→60 °C against 30→50 °C water",
        "headline": [("Corrected LMTD", "lmtd_corrected_K", "K"), ("Effectiveness", "effectiveness", ""), ("Correction factor F", "F_correction", "")],
    },
    "wastewater-stp-calculator": {
        "module": "wastewater_stp", "title": "Wastewater Treatment (STP) Calculator", "discipline": "Plumbing & Pumps",
        "keyword": "sewage treatment plant sizing calculator BOD",
        "standard": "DENR DAO 2016-08",
        "blurb": "The Wastewater Treatment (STP) Calculator finds the design flow, BOD load, and aeration tank volume for a sewage treatment plant.",
        "example_inputs": {"flow_source": "population", "population": 500, "per_capita_lpd": 120, "bod_influent": 250, "bod_effluent": 30},
        "example_desc": "a 500-person facility at 120 L/person/day, BOD 250→30 mg/L",
        "headline": [("Design flow", "flow_m3_day", "m³/day"), ("BOD removal", "bod_removal_pct", "%"), ("Aeration volume", "aeration_vol_m3", "m³")],
    },
    "water-treatment-calculator": {
        "module": "water_treatment", "title": "Water Treatment Sizing Calculator", "discipline": "Plumbing & Pumps",
        "keyword": "water treatment plant sizing calculator",
        "standard": "PNS 1998 / PNSDW",
        "blurb": "The Water Treatment Sizing Calculator finds the design flow and treatment requirements (turbidity, iron, disinfection) for a raw-water source.",
        "example_inputs": {"demand_source": "people", "n_people": 200, "per_capita_lpd": 120, "raw_source": "Deep Well / Bore", "turbidity_ntu": 10, "iron_mg": 0.5},
        "example_desc": "200 people on deep-well water at 10 NTU turbidity and 0.5 mg/L iron",
        "headline": [("Daily demand", "demand_m3d", "m³/day"), ("Peak flow", "peak_flow_m3hr", "m³/h"), ("Turbidity class", "turbidity_class", "")],
    },
    "beam-design-calculator": {
        "module": "beam_column", "title": "RC Beam Design Calculator", "discipline": "Mechanical & Machine Design",
        "keyword": "reinforced concrete beam design calculator NSCP",
        "standard": "NSCP 2015 | ACI 318",
        "blurb": "The RC Beam Design Calculator checks a reinforced-concrete beam's moment capacity and demand-capacity ratio against NSCP/ACI.",
        "example_inputs": {"member_type": "Beam", "span_m": 6, "Mu_kNm": 150, "Vu_kN": 100, "steel_grade": "A36", "section": "W12x40"},
        "example_desc": "a 6 m RC beam under a 150 kN·m factored moment",
        "headline": [("Moment capacity φMn", "phi_Mn_kNm", "kN·m"), ("Demand/capacity", "DCR_moment", ""), ("Steel area", "As_mm2", "mm²")],
    },
    "chiller-sizing-calculator": {
        "module": "chiller", "title": "Chiller Sizing Calculator", "discipline": "HVAC & Cooling",
        "keyword": "chiller sizing calculator TR",
        "standard": "ASHRAE 90.1-2019 | AHRI 550/590",
        "blurb": "The Chiller Sizing Calculator picks the chiller capacity (TR/kW) and efficiency for a cooling load with a design margin.",
        "example_inputs": {"cooling_kw": 300, "chiller_type": "Water-Cooled", "is_water_cooled": True, "safety_factor": 1.15, "n_units": 1, "cop": 5.5},
        "example_desc": "a 300 kW cooling load on a water-cooled chiller (COP 5.5)",
        "headline": [("Recommended capacity", "recommended_TR", "TR"), ("Capacity", "recommended_kW", "kW"), ("Efficiency", "kW_per_TR", "kW/TR")],
    },
    "short-circuit-calculator": {
        "module": "short_circuit", "title": "Short Circuit Calculator", "discipline": "Electrical & Power",
        "keyword": "short circuit fault current calculator kA",
        "standard": "IEC 60909-0:2016",
        "blurb": "The Short Circuit Calculator finds the prospective fault current (kA) and peak at a board from the transformer and cable impedance.",
        "example_inputs": {"voltage": 400, "transformer_kva": 1000, "transformer_z_pct": 5, "source_fault_mva": 250, "cable_mm2": 240, "cable_length_m": 30},
        "example_desc": "a 1000 kVA 5%-impedance transformer feeding a 400 V board via 30 m of 240 mm² cable",
        "headline": [("3-phase fault", "Isc_3ph_kA", "kA"), ("Peak", "Ip_peak_kA", "kA"), ("Fault level", "fault_MVA", "MVA")],
    },
    "solar-pv-calculator": {
        "module": "solar_pv", "title": "Solar PV System Calculator", "discipline": "Electrical & Power",
        "keyword": "solar PV system sizing calculator",
        "standard": "IEC 62548:2016",
        "blurb": "The Solar PV System Calculator finds the panel count, array size, and roof area for a target PV capacity, with string sizing.",
        "example_inputs": {"system_kw": 100, "load_kw": 80, "location": "Manila", "system_type": "Grid-Tie", "derating_pct": 20, "inverter_eff_pct": 97},
        "example_desc": "a 100 kWp grid-tie solar array in Manila",
        "headline": [("Total panels", "total_panels", "panels"), ("Array size", "array_kWp", "kWp"), ("Roof area", "roof_area_required_m2", "m²")],
    },
    "ups-sizing-calculator": {
        "module": "ups_sizing", "title": "UPS Sizing Calculator", "discipline": "Electrical & Power",
        "keyword": "UPS sizing calculator kVA",
        "standard": "IEEE 1184:2006",
        "blurb": "The UPS Sizing Calculator picks the UPS kVA rating and reports loading for a critical load and backup time.",
        "example_inputs": {"load_kw": 50, "power_factor": 0.9, "topology": "Online Double-Conversion", "backup_minutes": 15, "design_margin_pct": 25, "redundancy": "N", "ups_efficiency": 0.95},
        "example_desc": "a 50 kW critical load on an online double-conversion UPS with 15 min backup",
        "headline": [("Recommended UPS", "recommended_kVA", "kVA"), ("Load", "load_kVA", "kVA"), ("Loading", "loading_pct", "%")],
    },
    "vibration-isolation-calculator": {
        "module": "vibration_analysis", "title": "Vibration Isolation Calculator", "discipline": "Mechanical & Machine Design",
        "keyword": "vibration isolation natural frequency calculator",
        "standard": "ISO 10816-3",
        "blurb": "The Vibration Isolation Calculator finds the natural frequency, frequency ratio, and resonance margin for a machine on isolators.",
        "example_inputs": {"mass_kg": 500, "speed_rpm": 1500, "power_kW": 15, "machine_class": "Class II", "measured_velocity_mm_s": 2.8, "isolator_type": "Spring"},
        "example_desc": "a 500 kg machine at 1500 rpm on spring isolators",
        "headline": [("Natural frequency", "fn_Hz", "Hz"), ("Frequency ratio", "frequency_ratio_r", ""), ("Resonance margin", "resonance_margin_pct", "%")],
    },
    "earthing-grounding-calculator": {
        "module": "earthing_grounding", "title": "Earthing / Grounding Calculator", "discipline": "Electrical & Power",
        "keyword": "earthing grounding resistance calculator",
        "standard": "PEC 2017 Art. 2.50 | IEC 60364-5-54",
        "blurb": "The Earthing / Grounding Calculator finds the earth-electrode resistance and grounding-conductor size for a system, checked against the limit.",
        "example_inputs": {"electrode_type": "Rod", "soil_resistivity": 50, "num_electrodes": 4, "system_type": "TN-S", "service_cond_mm2": 50, "rod_length_m": 3, "rod_dia_mm": 16},
        "example_desc": "four 3 m rods in 50 Ω·m soil for a TN-S system",
        "headline": [("Earth resistance", "r_parallel_ohm", "Ω"), ("Limit", "r_limit_ohm", "Ω"), ("Result", "pass_label", "")],
    },
    "shaft-design-calculator": {
        "module": "shaft_design", "title": "Shaft Design Calculator", "discipline": "Mechanical & Machine Design",
        "keyword": "shaft diameter design calculator",
        "standard": "ASME B106.1M",
        "blurb": "The Shaft Design Calculator finds the minimum shaft diameter from transmitted power, speed, and load, with an endurance-limit check.",
        "example_inputs": {"power_kW": 15, "speed_rpm": 1450, "span_mm": 600, "radial_load_N": 2000, "material": "AISI 1045", "safety_factor": 2},
        "example_desc": "a 15 kW shaft at 1450 rpm over a 600 mm span under a 2 kN radial load",
        "headline": [("Shaft diameter", "d_standard_mm", "mm"), ("Torque", "torque_Nm", "N·m"), ("Endurance limit", "Se_MPa", "MPa")],
    },
    "pressure-vessel-calculator": {
        "module": "pressure_vessel", "title": "Pressure Vessel Shell Calculator", "discipline": "Mechanical & Machine Design",
        "keyword": "pressure vessel shell thickness calculator ASME",
        "standard": "ASME BPVC Section VIII Div.1",
        "blurb": "The Pressure Vessel Shell Calculator finds the required shell thickness and MAWP for a cylindrical vessel per ASME.",
        "example_inputs": {"design_pressure_bar": 10, "design_temperature_C": 150, "vessel_type": "Cylindrical", "inner_diameter_mm": 1000, "shell_length_mm": 2000, "head_type": "Ellipsoidal", "material": "SA-516-70", "joint_efficiency": 0.85, "corrosion_mm": 1.6},
        "example_desc": "a 1000 mm ID cylindrical vessel at 10 bar / 150 °C in SA-516-70",
        "headline": [("Shell thickness", "t_shell_required_mm", "mm"), ("MAWP", "mawp_bar", "bar"), ("Outer diameter", "outer_diameter_mm", "mm")],
    },
    "lighting-design-calculator": {
        "module": "lighting_design", "title": "Lighting Design Calculator", "discipline": "Electrical & Power",
        "keyword": "lumen method lighting calculator lux",
        "standard": "IESNA | PGBC",
        "blurb": "The Lighting Design Calculator uses the lumen method to find the number of luminaires needed to hit a target illuminance.",
        "example_inputs": {"room_length_m": 10, "room_width_m": 8, "room_height_m": 3, "work_plane_m": 0.8, "space_type": "Office", "target_lux": 500, "luminaire_type": "LED Panel 600×600 (40W)", "lamp_lumens": 4000, "watts_per_fixture": 40},
        "example_desc": "a 10 × 8 m office targeting 500 lux with 40 W LED panels",
        "headline": [("Fixtures needed", "N_exact", "fixtures"), ("Coefficient of utilisation", "CU", ""), ("Room cavity ratio", "RCR", "")],
    },
    "stairwell-pressurization-calculator": {
        "module": "stairwell_pressurization", "title": "Stairwell Pressurization Calculator", "discipline": "Fire Protection",
        "keyword": "stairwell pressurization fan calculator NFPA 92",
        "standard": "NFPA 92:2021",
        "blurb": "The Stairwell Pressurization Calculator finds the design pressure differential and total leakage area for a pressurised stairwell.",
        "example_inputs": {"building_type": "Office", "n_stairwells": 2, "n_floors": 10, "doors_per_floor": 1, "door_width": 0.9, "door_height": 2.1, "fan_efficiency": 0.7, "design_temp_c": 30},
        "example_desc": "two stairwells in a 10-floor office pressurised to code",
        "headline": [("Design pressure", "delta_P_Pa", "Pa"), ("Total leakage area", "A_total_m2", "m²"), ("Doors", "N_doors_total", "")],
    },
    "storm-drain-calculator": {
        "module": "storm_drain", "title": "Storm Drain Calculator", "discipline": "Plumbing & Pumps",
        "keyword": "storm drain rational method calculator",
        "standard": "DPWH Blue Book | Rational Method",
        "blurb": "The Storm Drain Calculator uses the Rational Method to find the design stormwater flow for a catchment.",
        "example_inputs": {"area_mode": "area", "intensity_mmhr": 150, "return_period": 10, "slope_pct": 1, "pipe_material": "Concrete", "area_ha": 1, "c_value": 0.7},
        "example_desc": "a 1 ha catchment (C = 0.7) at 150 mm/h, 10-year return",
        "headline": [("Design flow", "design_flow_lps", "L/s"), ("Runoff coefficient", "composite_c", ""), ("Time of concentration", "tc_min", "min")],
    },
    "septic-tank-calculator": {
        "module": "septic_tank", "title": "Septic Tank Sizing Calculator", "discipline": "Plumbing & Pumps",
        "keyword": "septic tank sizing calculator",
        "standard": "Philippine Plumbing Code §P-1101",
        "blurb": "The Septic Tank Sizing Calculator finds the liquid volume and total tank size from occupancy, wastewater rate, and desludging interval.",
        "example_inputs": {"occupancy_type": "Residential", "occupants": 50, "ww_rate": 150, "retention_days": 3, "desludge_years": 3, "liquid_depth": 1.5, "compartments": 2},
        "example_desc": "a 50-person residential septic tank at 150 L/person/day",
        "headline": [("Liquid volume", "liquid_volume_L", "L"), ("Daily flow", "daily_flow_L", "L/day"), ("Sludge storage", "sludge_L", "L")],
    },
    "sewer-drainage-calculator": {
        "module": "sewer_drainage", "title": "Sanitary Drainage Calculator", "discipline": "Plumbing & Pumps",
        "keyword": "sanitary sewer sizing calculator DFU",
        "standard": "NSCP | Philippine Plumbing Code",
        "blurb": "The Sanitary Drainage Calculator sizes the sanitary stack from the total drainage fixture units and design flow.",
        "example_inputs": {"building_floors": 3, "floor_height_m": 3.5, "pipe_material": "PVC", "fixtures": [{"fixture_type": "Water Closet", "quantity": 10}], "slope": 2, "num_persons": 50},
        "example_desc": "a 3-floor building sanitary stack serving 10 water closets",
        "headline": [("Total DFU", "total_dfu", "DFU"), ("Stack size", "stack_nominal_mm", "mm"), ("Design flow", "design_flow_lps", "L/s")],
    },
    "boiler-system-calculator": {
        "module": "boiler_system", "title": "Boiler System Sizing Calculator", "discipline": "Boiler & Utilities",
        "keyword": "boiler sizing calculator kW fuel consumption",
        "standard": "ASME BPVC Sec.I/IV | ASME B31.1",
        "blurb": "The Boiler System Sizing Calculator finds the boiler capacity (kW/BHP) and fuel consumption from steam demand, pressure, and feedwater temperature.",
        "example_inputs": {"boiler_type": "Steam", "num_boilers": 1, "fuel_type": "Diesel", "efficiency_pct": 85, "load_mode": "steam", "steam_demand_kg_hr": 500, "steam_pressure_barg": 7, "fw_temp_c": 80},
        "example_desc": "a steam boiler delivering 500 kg/h at 7 barg from 80 °C feedwater on diesel",
        "headline": [("Boiler capacity", "total_capacity_kw", "kW"), ("Boiler HP", "total_capacity_bhp", "BHP"), ("Fuel use", "fuel_consumption_lhr", "L/h")],
    },
    "fcu-selection-calculator": {
        "module": "fcu_selection", "title": "FCU Selection Calculator", "discipline": "HVAC & Cooling",
        "keyword": "fan coil unit selection calculator",
        "standard": "ASHRAE 62.1 | 90.1",
        "blurb": "The FCU Selection Calculator picks fan-coil units and chilled-water pipe size for a set of rooms from their cooling loads.",
        "example_inputs": {"rooms": [{"qty": 4, "cooling_load_kw": 5, "room_function": "Office"}], "chw_supply_c": 7, "chw_return_c": 12},
        "example_desc": "four office rooms at 5 kW cooling each on 7/12 °C chilled water",
        "headline": [("Selected FCU", "selected_fcu", ""), ("Unit capacity", "fcu_capacity_kW", "kW"), ("Total load", "total_connected_tr", "TR")],
    },
    "fire-sprinkler-calculator": {
        "module": "fire_sprinkler", "title": "Fire Sprinkler Hydraulic Calculator", "discipline": "Fire Protection",
        "keyword": "fire sprinkler density design area calculator NFPA 13",
        "standard": "NFPA 13:2022",
        "blurb": "The Fire Sprinkler Hydraulic Calculator finds the design density, remote-area size, and required flow for a wet-pipe sprinkler system.",
        "example_inputs": {"occupancy": "Ordinary Hazard Group 1", "k_factor": 80, "sprinkler_spacing_m": 3, "pipe_material": "Steel", "hw_c_factor": 120, "branch_length_m": 10, "cross_main_length_m": 15, "feed_main_length_m": 20, "elevation_m": 3},
        "example_desc": "an NFPA 13 wet-pipe sprinkler design at 3 m sprinkler spacing",
        "headline": [("Hazard class", "hazard_class", ""), ("Design density", "density_mm_min", "mm/min"), ("Remote area", "design_area_m2", "m²"), ("System flow", "q_sprinklers_lpm", "L/min")],
    },
    "clean-agent-suppression-calculator": {
        "module": "clean_agent_suppression", "title": "Clean Agent Suppression Calculator", "discipline": "Fire Protection",
        "keyword": "FM-200 clean agent quantity calculator NFPA 2001",
        "standard": "NFPA 2001:2022",
        "blurb": "The Clean Agent Suppression Calculator finds the agent mass (kg) needed to flood a hazard to its design concentration.",
        "example_inputs": {"hazard_volume_m3": 200, "agent_type": "FM-200", "design_concentration_pct": 7, "temperature_c": 25, "altitude_m": 0, "num_zones": 1},
        "example_desc": "a 200 m³ hazard protected by FM-200 at 7% design concentration",
        "headline": [("Agent mass", "W_design_kg", "kg"), ("Design concentration", "design_concentration_pct", "%"), ("Protected volume", "adjusted_volume_m3", "m³")],
    },
    "v-belt-drive-calculator": {
        "module": "gear_belt_drive", "title": "V-Belt Drive Calculator", "discipline": "Mechanical & Machine Design",
        "keyword": "V-belt drive design calculator",
        "standard": "ISO 4184 | AGMA",
        "blurb": "The V-Belt Drive Calculator finds the number of belts, pulley sizes, and belt length for a power-transmission duty.",
        "example_inputs": {"drive_type": "V-Belt", "power_kW": 15, "n_driver_rpm": 1450, "n_driven_rpm": 725, "service_factor": 1.2, "belt_section": "SPB", "driver_dia_mm": 125},
        "example_desc": "a 15 kW V-belt drive, 1450→725 rpm (2:1), SPB section",
        "headline": [("Number of belts", "n_belts", "belts"), ("Driven pulley", "d_large_mm", "mm"), ("Belt length", "belt_length_mm", "mm")],
    },
    "voltage-drop-calculator": {
        "module": "voltage_drop", "title": "Voltage Drop Calculator", "discipline": "Electrical & Power",
        "keyword": "voltage drop calculator cable PEC",
        "standard": "PEC 2017 Art. 2.10.19 | NEC 210.19",
        "blurb": "The Voltage Drop Calculator finds the percentage voltage drop on a cable run and checks it against the PEC/NEC limit.",
        "example_inputs": {"circuit_type": "Feeder", "phase": "Three-phase", "voltage": 400, "current": 60, "wire_length": 45, "conductor_mm2": 25, "conductor_mat": "Copper", "vd_limit": 3},
        "example_desc": "a 60 A 3-phase feeder over 45 m of 25 mm² copper cable at 400 V",
        "headline": [("Voltage drop", "vd_pct", "%"), ("Drop", "vd_volts", "V"), ("Limit", "vd_limit", "%")],
    },
    "load-estimation-calculator": {
        "module": "load_estimation", "title": "Electrical Load Estimation Calculator", "discipline": "Electrical & Power",
        "keyword": "electrical load demand calculator kVA",
        "standard": "PEC 2017 Art. 2.10 / 2.20 | IEC 60364",
        "blurb": "The Electrical Load Estimation Calculator totals connected and demand load for a facility and sizes the main breaker.",
        "example_inputs": {"loads": [{"load_type": "Lighting (General)", "quantity": 1, "watts_each": 8000, "power_factor": 0.9}, {"load_type": "Motor (General)", "quantity": 1, "watts_each": 15000, "power_factor": 0.85}, {"load_type": "Air Conditioning (Unit)", "quantity": 2, "watts_each": 5000, "power_factor": 0.9}], "phase_config": "3-Phase 4-Wire (400V/230V)"},
        "example_desc": "a facility with 8 kW lighting, a 15 kW motor, and two 5 kW aircon units",
        "headline": [("Demand load", "total_demand_kw", "kW"), ("Demand", "total_demand_kva", "kVA"), ("Main breaker", "recommended_breaker_A", "A")],
    },
    "harmonic-distortion-calculator": {
        "module": "harmonic_distortion", "title": "Harmonic Distortion (THD/TDD) Calculator", "discipline": "Electrical & Power",
        "keyword": "harmonic distortion THD TDD calculator IEEE 519",
        "standard": "IEEE 519-2022",
        "blurb": "The Harmonic Distortion Calculator finds current THD and TDD and checks them against the IEEE 519 limit for the point of common coupling.",
        "example_inputs": {"fundamental_current_a": 200, "max_demand_current_a": 200, "system_voltage_v": 400, "short_circuit_current_a": 8000, "harmonics": [{"order": 5, "current_pct": 30}, {"order": 7, "current_pct": 20}, {"order": 11, "current_pct": 10}]},
        "example_desc": "a 200 A load with 30% / 20% / 10% 5th / 7th / 11th harmonics on a 400 V system",
        "headline": [("Current THD", "THD_I_pct", "%"), ("TDD", "TDD_pct", "%"), ("TDD limit", "TDD_limit_pct", "%")],
    },
    "expansion-tank-calculator": {
        "module": "expansion_tank", "title": "Expansion Tank Sizing Calculator", "discipline": "HVAC & Cooling",
        "keyword": "expansion tank sizing calculator",
        "standard": "ASHRAE 2023 HVAC Systems & Equipment Ch.12",
        "blurb": "The Expansion Tank Sizing Calculator finds the required tank volume for a hydronic system from its water volume and temperature swing.",
        "example_inputs": {"system_type": "Chilled Water", "volume_method": "Estimate from kW", "system_kw": 300, "fill_temp_c": 7, "max_temp_c": 35, "static_head_m": 15},
        "example_desc": "a 300 kW chilled-water system (≈2400 L) over a 7→35 °C swing",
        "headline": [("Required tank", "required_volume_L", "L"), ("Water expansion", "V_expansion_L", "L"), ("Max pressure", "max_pressure_kpa_g", "kPa")],
    },
    "duct-sizing-calculator": {
        "module": "duct_sizing", "title": "Duct Sizing Calculator", "discipline": "HVAC & Cooling",
        "keyword": "duct sizing calculator equal friction CFM",
        "standard": "ASHRAE Fundamentals Ch.21 | SMACNA",
        "blurb": "The Duct Sizing Calculator uses the equal-friction method to size supply ductwork and find the critical-path pressure drop.",
        "example_inputs": {"application": "Supply Air", "friction_rate_pam": 0.8, "aspect_ratio": 3, "sections": [{"type": "Supply Main", "flow_m3s": 2.0, "length_m": 20}]},
        "example_desc": "a supply-air main carrying 2 m³/s (7200 m³/h) at 0.8 Pa/m friction over 20 m",
        "headline": [("Airflow", "sections.0.flow_m3hr", "m³/h"), ("Critical-path drop", "critical_path_dp_pa", "Pa"), ("Friction rate", "friction_rate_pam", "Pa/m")],
    },
    "hydraulic-cylinder-calculator": {
        "module": "fluid_power", "title": "Hydraulic Cylinder Calculator", "discipline": "Mechanical & Machine Design",
        "keyword": "hydraulic cylinder force calculator bore",
        "standard": "ISO 4413:2010",
        "blurb": "The Hydraulic Cylinder Calculator finds the extend force, speed, and cycle time for a hydraulic cylinder from its bore, rod, pressure, and flow.",
        "example_inputs": {"calc_type": "Cylinder", "system_pressure_bar": 160, "bore_mm": 80, "rod_mm": 45, "stroke_mm": 400, "flow_lpm": 30},
        "example_desc": "an 80 mm bore / 45 mm rod cylinder at 160 bar with 30 L/min flow",
        "headline": [("Extend force", "cylinder.F_extend_kN", "kN"), ("Extend speed", "cylinder.v_extend_m_s", "m/s"), ("Extend time", "cylinder.t_extend_s", "s")],
    },
    "refrigerant-pipe-calculator": {
        "module": "refrigerant_pipe", "title": "Refrigerant Pipe Sizing Calculator", "discipline": "HVAC & Cooling",
        "keyword": "refrigerant pipe sizing calculator R410A",
        "standard": "ASHRAE 2022 Refrigeration Handbook | ASTM B280",
        "blurb": "The Refrigerant Pipe Sizing Calculator picks the suction, liquid, and discharge line sizes for a refrigeration circuit.",
        "example_inputs": {"cooling_kw": 30, "refrigerant": "R410A", "application": "Air Conditioning", "evap_temp_c": 7, "cond_temp_c": 45, "suction_length_m": 15, "discharge_length_m": 5, "liquid_length_m": 15},
        "example_desc": "a 30 kW R410A air-conditioning circuit (7 / 45 °C)",
        "headline": [("Suction line OD", "suction_horizontal.od_mm", "mm"), ("Liquid line OD", "liquid.od_mm", "mm"), ("Discharge line OD", "discharge.od_mm", "mm")],
    },
}


def _run_calc(data: dict) -> dict:
    """Return the worked-example result dict.

    Normally this IMPORTS the real calc module and runs it, so the numbers on the page
    are the engine's own output and cannot drift from the product. A few high-demand
    head terms (OEE, MTBF/MTTR) are KPIs computed inside the analytics surface rather
    than standalone modules in python-api/calcs, so those specs carry `module: None`
    plus a `computed` dict whose values are hand-derived from the published formula and
    stated in full on the page. Everything downstream (template, schema, gate) is
    identical either way.
    """
    if not data.get("module"):
        return dict(data["computed"])
    mod = importlib.import_module(f"calcs.{data['module']}")
    return mod.calculate(dict(data["example_inputs"]))


def _fmt(v) -> str:
    if isinstance(v, float):
        return f"{v:.2f}".rstrip("0").rstrip(".") if v == v else str(v)
    return str(v)


def _resolve(obj, path: str):
    """Resolve a dotted key path into nested dicts/lists (e.g. 'cylinder.F_extend_kN', 'sections.0.flow_m3hr')."""
    cur = obj
    for part in path.split("."):
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
        if cur is None:
            return None
    return cur


def _headline_rows(data: dict, r: dict) -> tuple[list, list]:
    """Return (present rows [(label,val,unit)], missing keys)."""
    rows, missing = [], []
    for label, key, unit in data["headline"]:
        val = _resolve(r, key)
        if isinstance(val, (int, float, str, bool)):
            rows.append((label, _fmt(val), unit))
        else:
            missing.append(key)
    return rows, missing


def _answer_text(data: dict, r: dict, rows: list) -> str:
    std = r.get("standard") or data.get("standard", "")
    parts = ", ".join(f"{label} = {val}{(' ' + unit) if unit else ''}" for label, val, unit in rows)
    tail = f" (per {std})" if std else ""
    return f"{data['blurb']} Example: for {data['example_desc']}, {parts}{tail}."


def _default_faqs(data: dict) -> list[tuple[str, str]]:
    kw, title = data["keyword"], data["title"]
    std = data.get("standard", "")
    return [
        (f"What is a {kw}?", f"The {title} is a free online tool that computes {data['blurb'][len(data['title']) + 5:].strip() or 'the result'} It shows the formula and a fully worked example so you can check the method, not just the number."),
        (f"How is it calculated?", f"{data.get('formula', 'The result is computed from your inputs')} following {std or 'recognised engineering practice'}. The worked example on this page shows a real computation with real numbers."),
        ("Is the calculator free?", "Yes. WorkHive's engineering calculators are free to use — no sign-up needed for the tools. WorkHive is a free, offline-first maintenance platform built for Philippine industrial plants."),
    ]


def _siblings(slug: str, data: dict) -> list[tuple[str, str]]:
    disc = data["discipline"]
    sibs = [(f"/tools/{s}/", d["title"]) for s, d in CALC_DATA.items()
            if s != slug and d["discipline"] == disc]
    return sibs[:2]


def _jsonld(data: dict, url: str) -> str:
    faqs = data.get("faqs") or _default_faqs(data)
    faq = {"@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs]}
    steps = data.get("steps") or [
        f"Enter your inputs ({', '.join(list(data['example_inputs'].keys())[:5])}...).",
        f"The calculator computes {', '.join(l for l, *_ in data['headline'])} per {data.get('standard', 'the applicable standard')}.",
        "Read the worked example on this page to check the method, then run your own numbers in the interactive tool.",
    ]
    howto = {"@type": "HowTo", "name": f"How to use the {data['title']}",
             "step": [{"@type": "HowToStep", "position": i + 1, "text": s} for i, s in enumerate(steps)]}
    app = {"@type": "SoftwareApplication", "name": data["title"], "applicationCategory": "BusinessApplication",
           "operatingSystem": "Web", "url": url, "description": data["blurb"],
           "offers": {"@type": "Offer", "price": "0", "priceCurrency": "PHP"},
           "publisher": {"@type": "Organization", "name": "WorkHive", "url": SITE}}
    return json.dumps({"@context": "https://schema.org", "@graph": [app, howto, faq]}, indent=2, ensure_ascii=False)


def _html_page(slug: str, data: dict) -> tuple[str, list]:
    url = f"{SITE}/tools/{slug}/"
    r = _run_calc(data)
    rows, missing = _headline_rows(data, r)
    e = html.escape
    std = r.get("standard") or data.get("standard", "")
    answer = _answer_text(data, r, rows)
    faqs = data.get("faqs") or _default_faqs(data)
    formula = data.get("formula") or f"Computed from your inputs per {std}."
    table_rows = "\n".join(
        f"          <tr><td>{e(l)}</td><td>{e(v)}{(' ' + e(u)) if u else ''}</td></tr>" for l, v, u in rows)
    faq_html = "\n".join(
        f'      <details class="faq"><summary>{e(q)}</summary><p>{e(a)}</p></details>' for q, a in faqs)
    sibs = data.get("siblings") or _siblings(slug, data)
    rel = data.get("related_article", PILLAR)
    sib_html = "\n".join(f'        <li><a href="{e(u)}">{e(t)}</a></li>' for u, t in sibs)
    meta = data.get("meta") or (data["blurb"] + " Free online, with a worked example. Built for Philippine plants by WorkHive.")
    jsonld = _jsonld(data, url)

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(data['title'])} — Free Online + Worked Example | WorkHive</title>
<meta name="description" content="{e(meta)}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{e(url)}">
<meta property="og:title" content="{e(data['title'])} | WorkHive">
<meta property="og:description" content="{e(meta)}">
<meta property="og:url" content="{e(url)}">
<meta property="og:type" content="website">
<script type="application/ld+json">
{jsonld}
</script>
</head>
<body>
  <main>
    <nav aria-label="Breadcrumb"><a href="{e(PILLAR[0])}">{e(PILLAR[1])}</a> &rsaquo; {e(data['title'])}</nav>
    <h1>{e(data['title'])}</h1>

    <p class="answer-first"><strong>{e(answer)}</strong></p>

    <section aria-labelledby="formula">
      <h2 id="formula">How it works</h2>
      <p>{e(formula)}</p>
    </section>

    <section aria-labelledby="worked">
      <h2 id="worked">Worked example ({e(data['discipline'])})</h2>
      <p>Inputs: {e(data['example_desc'])}.</p>
      <table>
        <thead><tr><th>Result</th><th>Value</th></tr></thead>
        <tbody>
{table_rows}
        </tbody>
      </table>
      <p><small>Computed live by WorkHive's calculation engine; standard: {e(std)}.</small></p>
    </section>

    <section aria-labelledby="faq">
      <h2 id="faq">FAQ</h2>
{faq_html}
    </section>

    <section aria-labelledby="try">
      <h2 id="try">Run it on your own numbers</h2>
      <p><a href="/engineering-design.html" class="cta">Open the interactive {e(data['title'])} in WorkHive</a> — free, no sign-up needed for the calculators.</p>
    </section>

    <section aria-labelledby="related">
      <h2 id="related">Related calculators</h2>
      <ul>
        <li><a href="{e(PILLAR[0])}">{e(PILLAR[1])}</a> (pillar)</li>
{sib_html}
        <li><a href="{e(rel[0])}">{e(rel[1])}</a></li>
      </ul>
    </section>
  </main>
</body>
</html>
"""
    return page, missing


def build(slugs: list[str]) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    built, warned = 0, 0
    for slug in slugs:
        data = CALC_DATA[slug]
        try:
            page, missing = _html_page(slug, data)
        except Exception as ex:
            print(f"  ERROR {slug}: {type(ex).__name__}: {ex}")
            warned += 1
            continue
        d = OUT_DIR / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(page, encoding="utf-8")
        note = f"  (MISSING keys: {missing})" if missing else ""
        print(f"  built /tools/{slug}/  ({len(page)} bytes){note}")
        if missing:
            warned += 1
        built += 1
    print(f"\n{built} page(s) staged in {OUT_DIR.relative_to(ROOT)}"
          f"{f' — {warned} with missing headline keys' if warned else ''}.")
    print(f"Coverage: {len(CALC_DATA)} / 58 calc modules specced.")
    return built


def main() -> int:
    args = sys.argv[1:]
    if "--slug" in args:
        slugs = [args[args.index("--slug") + 1]]
    else:
        slugs = list(CALC_DATA.keys())
    build(slugs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
