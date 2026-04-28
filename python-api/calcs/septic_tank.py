"""
Septic Tank Sizing — Phase 6f (Option B port from TypeScript)
Standards: Philippine Plumbing Code (PPC) §P-1101 to §P-1107,
           DOH Sanitation Code P.D. 856, DENR DAO 2016-08 Effluent Standards,
           DPWH Blue Book (Rural Water Supply)
Libraries: math

Improvement over TypeScript:
- DENR DAO 2016-08 effluent BOD flag added (>30 mg/L requires secondary treatment)
- Soil absorption field (leach field) sizing estimate per PPC §P-1103
- 3-compartment option supported (PPC allows for large facilities)

Method: Occupancy-based wastewater flow + PPC liquid retention + sludge/scum
        storage → total volume → L×W×D dimensions → compartment split
"""

import math

# Wastewater generation rates (L/person/day) — PPC Table P-4 / DOH Sanitation Code
WW_RATES: dict[str, float] = {
    "Residential":              150.0,
    "Office / Commercial":       50.0,
    "School / Institutional":    45.0,
    "Hospital / Clinic":        400.0,
    "Restaurant / Food Service": 25.0,   # per seat
    "Hotel / Dormitory":        180.0,
    "Industrial / Factory":      50.0,
    "Custom":                   100.0,
}

# Soil absorption rates (L/m²/day) for leach field — PPC Table P-5
SOIL_ABSORPTION: dict[str, float] = {
    "Gravel / Coarse Sand": 40.0,
    "Fine Sand":            20.0,
    "Sandy Loam":           16.0,
    "Sandy Clay":           10.0,
    "Clay":                  6.0,
}


def calculate(inputs: dict) -> dict:
    occ_type       = str(inputs.get("occupancy_type",  "Residential"))
    occupants      = int(inputs.get("occupants",        20))
    ww_rate        = float(inputs.get("ww_rate",        WW_RATES.get(occ_type, 150.0)))
    retention_days = float(inputs.get("retention_days", 1.0))
    desludge_yrs   = float(inputs.get("desludge_years", 3.0))
    liquid_depth   = float(inputs.get("liquid_depth",   1.5))
    lw_ratio       = float(inputs.get("lw_ratio",       3.0))
    compartments   = int(inputs.get("compartments",     2))
    soil_type      = str(inputs.get("soil_type",        "Sandy Loam"))

    # ── Volume components (PPC §P-1101) ──────────────────────────────────────
    daily_flow_l   = occupants * ww_rate
    liquid_vol_l   = daily_flow_l * retention_days
    sludge_l       = 40.0 * occupants * desludge_yrs   # PPC: 40 L/person/year
    scum_l         = 15.0 * occupants * desludge_yrs   # PPC: 15 L/person/year
    total_vol_l    = liquid_vol_l + sludge_l + scum_l

    # PPC minimum: 1 000 L for any building
    design_vol_l   = max(total_vol_l, 1000.0)
    design_vol_m3  = design_vol_l / 1000.0

    # ── Dimensions ───────────────────────────────────────────────────────────
    floor_area_m2  = design_vol_m3 / liquid_depth
    width_m        = math.sqrt(floor_area_m2 / lw_ratio)
    length_m       = floor_area_m2 / width_m
    total_depth_m  = liquid_depth + 0.30   # 300 mm freeboard (PPC)
    actual_lw_ratio = length_m / width_m

    # Round to practical 0.1 m increments (ceiling)
    width_r  = math.ceil(width_m  * 10) / 10
    length_r = math.ceil(length_m * 10) / 10

    # ── Compartment split (PPC: 2-compartment = 2/3 : 1/3) ───────────────────
    if compartments == 2:
        comp1_l   = round(design_vol_l * 2 / 3)
        comp2_l   = round(design_vol_l - comp1_l)
        comp1_len = f"{round(length_r * 2/3, 1)} m"
        comp2_len = f"{round(length_r * 1/3, 1)} m"
        comp3_l, comp3_len = None, None
    else:
        # 3-compartment: 1/2 : 1/4 : 1/4
        comp1_l   = round(design_vol_l * 0.50)
        comp2_l   = round(design_vol_l * 0.25)
        comp3_l   = round(design_vol_l - comp1_l - comp2_l)
        comp1_len = f"{round(length_r * 0.50, 1)} m"
        comp2_len = f"{round(length_r * 0.25, 1)} m"
        comp3_len = f"{round(length_r * 0.25, 1)} m"

    # ── Soil absorption / leach field (PPC §P-1103) ───────────────────────────
    abs_rate      = SOIL_ABSORPTION.get(soil_type, 16.0)   # L/m²/day
    leach_area_m2 = daily_flow_l / abs_rate

    # ── DENR DAO 2016-08 flag (effluent BOD target) ───────────────────────────
    # Standard septic tank achieves ~60-70% BOD removal from raw 200 mg/L
    effluent_bod_mgl = 200.0 * 0.35   # ~70 mg/L after single-tank treatment
    denr_limit_mgl   = 30.0           # DENR DAO 2016-08 Class SB: 30 mg/L
    secondary_needed  = effluent_bod_mgl > denr_limit_mgl

    result: dict = {
        "occupancy_type":      occ_type,
        "occupants":           occupants,
        "ww_rate":             ww_rate,
        "retention_days":      retention_days,
        "desludge_years":      desludge_yrs,
        "liquid_depth":        liquid_depth,
        "lw_ratio":            lw_ratio,
        "compartments":        compartments,
        "daily_flow_L":        round(daily_flow_l),
        "liquid_volume_L":     round(liquid_vol_l),
        "sludge_L":            round(sludge_l),
        "scum_L":              round(scum_l),
        "total_volume_L":      round(total_vol_l),
        "design_volume_L":     round(design_vol_l),
        "design_volume_m3":    round(design_vol_m3, 2),
        "floor_area_m2":       round(floor_area_m2, 2),
        "tank_width_m":        width_r,
        "tank_length_m":       length_r,
        "total_depth_m":       round(total_depth_m, 1),
        "actual_lw_ratio":     round(actual_lw_ratio, 1),
        "comp1_L":             comp1_l,
        "comp2_L":             comp2_l,
        "comp1_L_m":           comp1_len,
        "comp2_L_m":           comp2_len,
        "soil_type":           soil_type,
        "absorption_rate":     abs_rate,
        "leach_field_area_m2": round(leach_area_m2, 1),
        "effluent_bod_mgl":    round(effluent_bod_mgl, 1),
        "denr_limit_mgl":      denr_limit_mgl,
        "secondary_treatment_needed": secondary_needed,
    }
    if comp3_l is not None:
        result["comp3_L"]   = comp3_l
        result["comp3_L_m"] = comp3_len
    return result
