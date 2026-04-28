"""
Water Softener Sizing — Phase 6h (Option B port from TypeScript)
Standards: WQA (Water Quality Association) standards, NSF/ANSI 44,
           PNS 1998 / PNSDW (hardness limit 300 mg/L as CaCO3),
           DOH AO No. 2017-0010 (Philippine Drinking Water Standards)
Libraries: math

Method: Ion exchange capacity method
  1. Daily hardness load = demand × (inlet − target hardness)
  2. Load per regen cycle = daily load × regen interval × safety factor
  3. Resin volume = load / exchange capacity (g CaCO3/L resin)
  4. Select standard tank; verify service flow rate (6–25 BV/hr)
  5. Salt consumption; brine tank; rinse water volume
"""

import math

# Standard cation exchange resin tank sizes [dia_in, ht_in, resin_L]
SOFTENER_TANKS: list[tuple[int, int, int]] = [
    (8,  44,  25), (9,  48,  35), (10, 54,  50), (12, 52,  70),
    (13, 54,  85), (14, 65, 120), (16, 65, 160), (18, 65, 200),
    (21, 62, 270), (24, 72, 400), (30, 72, 600), (36, 72, 900),
]

BRINE_TANK_SIZES = [100, 150, 200, 300, 500, 750, 1000, 1500, 2000]


def _select_tank(resin_l: float) -> dict:
    for d, h, r in SOFTENER_TANKS:
        if r >= resin_l:
            return {"dia_in": d, "ht_in": h, "resin_L": r}
    d, h, r = SOFTENER_TANKS[-1]
    return {"dia_in": d, "ht_in": h, "resin_L": r}


def calculate(inputs: dict) -> dict:
    demand_source  = str(inputs.get("demand_source",    "direct"))
    n_people       = int(inputs.get("n_people",         0))
    per_capita     = float(inputs.get("per_capita_lpd", 200))

    # Daily demand
    if demand_source == "people":
        if n_people <= 0:
            return {"error": "Number of people must be greater than 0."}
        demand_lpd = n_people * per_capita
    else:
        demand_lpd = (float(inputs.get("demand_lpd",       0))
                   or float(inputs.get("daily_demand_L",   0))
                   or float(inputs.get("daily_demand_m3",  0)) * 1000)
        if demand_lpd <= 0:
            return {"error": "Daily water demand must be greater than 0."}

    inlet_hardness  = max(1.0,   float(inputs.get("inlet_hardness",  200)))  # mg/L CaCO3
    target_hardness = max(0.0,   float(inputs.get("target_hardness", 17)))
    regen_interval  = max(1, min(7, int(inputs.get("regen_interval", 3))))
    salt_dose       = max(40, min(150, float(inputs.get("salt_dose_gL", 80))))  # g/L resin
    n_units         = max(1, int(inputs.get("n_units", 1)))
    safety_factor   = 1.2

    if inlet_hardness <= target_hardness:
        return {"error": f"Inlet hardness ({inlet_hardness} mg/L) must exceed target ({target_hardness} mg/L)."}

    # Hardness conversion
    inlet_gpg  = round(inlet_hardness  / 17.1, 2)
    target_gpg = round(target_hardness / 17.1, 2)

    # Classification per WQA
    hardness_class = ("Slightly Hard"   if inlet_hardness < 60  else
                      "Moderately Hard" if inlet_hardness < 120 else
                      "Hard"            if inlet_hardness < 180 else
                      "Very Hard"       if inlet_hardness < 300 else "Extremely Hard")

    pns_check = ("WITHIN PNS 1998 limit (≤300 mg/L): softening recommended"
                 if inlet_hardness <= 300
                 else "EXCEEDS PNS 1998 limit (300 mg/L): softening mandatory")

    # Step 1–3: loads and resin volume
    removal_mgl     = inlet_hardness - target_hardness
    daily_load_g    = round(demand_lpd * removal_mgl / 1000, 1)       # g CaCO3/day
    load_per_cycle  = round(daily_load_g * regen_interval * safety_factor)  # g

    exch_cap = (35 if salt_dose <= 40 else 40 if salt_dose <= 60 else
                45 if salt_dose <= 80 else 50 if salt_dose <= 120 else 55)  # g/L

    resin_l_per_unit = round(load_per_cycle / exch_cap / n_units, 1)
    resin_ft3        = round(resin_l_per_unit / 28.317, 2)

    # Step 4: tank selection
    tank           = _select_tank(resin_l_per_unit)
    selected_resin = tank["resin_L"]
    tank_dia_mm    = round(tank["dia_in"] * 25.4)
    tank_ht_mm     = round(tank["ht_in"]  * 25.4)

    # Service flow rates (6–25 BV/hr = bed volumes per hour)
    min_flow   = round(selected_resin * 6  / 60, 1)   # L/min
    max_flow   = round(selected_resin * 25 / 60, 1)
    design_flow = round(demand_lpd / (8 * 60), 1)      # 8 hr/day peak

    flow_ok = min_flow <= design_flow <= max_flow
    if flow_ok:
        flow_check = f"PASS: {design_flow} L/min within {min_flow}–{max_flow} L/min"
    elif design_flow < min_flow:
        flow_check = f"LOW: {design_flow} L/min below min {min_flow} L/min; consider smaller tank"
    else:
        flow_check = f"HIGH: {design_flow} L/min exceeds max {max_flow} L/min; add units"

    # Backwash (5 GPM/ft² ≈ 204 L/min/m²)
    tank_dia_m  = tank["dia_in"] * 0.0254
    tank_area   = math.pi / 4 * tank_dia_m ** 2
    backwash_lpm = round(tank_area * 204)

    # Step 5: salt + brine tank
    salt_per_regen = round(selected_resin * salt_dose / 1000, 1)   # kg
    monthly_salt   = round(salt_per_regen * n_units * 30 / regen_interval, 1)
    brine_min_l    = math.ceil(monthly_salt * 3 / 1.2)             # 3-month supply, 1.2 kg/L
    brine_tank_l   = next((s for s in BRINE_TANK_SIZES if s >= brine_min_l), BRINE_TANK_SIZES[-1])

    # Rinse water
    rinse_l      = round(selected_resin * 5)                        # ~5 BV per regen
    monthly_rinse_m3 = round(rinse_l * n_units * 30 / regen_interval / 1000, 2)
    efficiency_pct  = round(100 - (rinse_l * n_units / (demand_lpd * regen_interval)) * 100, 1)

    return {
        "demand_lpd":            round(demand_lpd),
        "demand_m3day":          round(demand_lpd / 1000, 3),
        "inlet_hardness_mgL":    inlet_hardness,
        "inlet_hardness_gpg":    inlet_gpg,
        "target_hardness_mgL":   target_hardness,
        "target_hardness_gpg":   target_gpg,
        "hardness_class":        hardness_class,
        "pns_check":             pns_check,
        "removal_mgL":           removal_mgl,
        "regen_interval_days":   regen_interval,
        "salt_dose_gL":          salt_dose,
        "n_units":               n_units,
        "exch_capacity_gL":      exch_cap,
        "safety_factor":         safety_factor,
        "daily_load_g":          daily_load_g,
        "load_per_cycle_g":      load_per_cycle,
        "resin_L_per_unit":      resin_l_per_unit,
        "resin_ft3_per_unit":    resin_ft3,
        "tank_dia_in":           tank["dia_in"],
        "tank_ht_in":            tank["ht_in"],
        "tank_dia_mm":           tank_dia_mm,
        "tank_ht_mm":            tank_ht_mm,
        "selected_resin_L":      selected_resin,
        "min_flow_lpm":          min_flow,
        "max_flow_lpm":          max_flow,
        "design_flow_lpm":       design_flow,
        "flow_check":            flow_check,
        "backwash_lpm":          backwash_lpm,
        "salt_per_regen_kg":     salt_per_regen,
        "monthly_salt_kg":       monthly_salt,
        "brine_tank_min_L":      brine_min_l,
        "brine_tank_L":          brine_tank_l,
        "rinse_water_L_per_regen": rinse_l,
        "monthly_rinse_m3":      monthly_rinse_m3,
        "efficiency_pct":        efficiency_pct,
    }
