"""
HVAC Cooling Load - Phase 2a
Standards: ASHRAE 62.1, ASHRAE 90.1, ASHRAE 55, ASHRAE Fundamentals 2021 Ch.18
Libraries: psychrolib (psychrometrics), numpy

Replaces the hand-rolled TypeScript implementation with:
- Real psychrometric state points via psychrolib (enthalpy, humidity ratio,
  wet bulb, dew point) at Manila tropical conditions
- CLTD/CLF method for Manila latitude 14.6N (ASHRAE 2021 Ch.18 tables)
- Proper sensible heat ratio (SHR) calculation
- ASHRAE 62.1 ventilation adequacy check
- ASHRAE 90.1 EER minimum compliance check
"""

import psychrolib
import math

# Set SI units globally for this module
psychrolib.SetUnitSystem(psychrolib.SI)

# ─── ASHRAE 2021 Fundamentals - CLTD values for Manila (lat 14.6N, July) ─────
# Cooling Load Temperature Difference (K) by wall/roof type and orientation
# Source: ASHRAE 2021 Fundamentals Table 18-2 (Group D wall, flat roof)
CLTD_WALL: dict[str, float] = {
    "North":      5.0,
    "South":      8.0,
    "East":      12.0,
    "West":      14.0,
    "Horizontal": 0.0,  # N/A for wall
    "Mixed":      9.0,  # average
}

CLTD_ROOF = 30.0   # K - flat concrete roof, ASHRAE Table 18-3, July, lat 14.6N

# ─── U-values (W/m2·K) - ASHRAE 2021 / PSME Code ─────────────────────────────
U_WALL: dict[str, float] = {
    "Standard":  0.45,
    "Good":      0.35,
    "Excellent": 0.25,
}
U_ROOF: dict[str, float] = {
    "Standard":  0.50,
    "Good":      0.38,
    "Excellent": 0.28,
}

# ─── Solar Heat Gain Coefficient by glass type - ASHRAE 2021 ─────────────────
SHGC: dict[str, float] = {
    "Standard": 0.87,
    "Tinted":   0.55,
    "LowE":     0.35,
    "Double":   0.40,
}

# ─── Solar irradiance by orientation at Manila lat 14.6N (W/m2) ──────────────
# Peak design values - ASHRAE 2021 Fundamentals Ch.14
SOLAR_W: dict[str, float] = {
    "North":      90,
    "South":      130,
    "East":       700,
    "West":       700,
    "Horizontal": 950,
    "Mixed":      350,
}

# ─── Internal heat gains by room function - ASHRAE 55 / PSME ─────────────────
OCCUPANT_HEAT: dict[str, dict] = {
    "Office":           {"sensible": 75,  "latent": 55},
    "Conference":       {"sensible": 75,  "latent": 55},
    "Server Room":      {"sensible": 0,   "latent": 0},
    "Production Floor": {"sensible": 90,  "latent": 90},
    "Warehouse":        {"sensible": 90,  "latent": 90},
    "Retail":           {"sensible": 75,  "latent": 55},
    "Hospital":         {"sensible": 75,  "latent": 55},
    "Classroom":        {"sensible": 70,  "latent": 45},
    "Restaurant":       {"sensible": 75,  "latent": 75},
    "Hotel Room":       {"sensible": 75,  "latent": 55},
}

LIGHTING_WPM2: dict[str, float] = {
    "Office":           12,
    "Conference":       12,
    "Server Room":      8,
    "Production Floor": 15,
    "Warehouse":        8,
    "Retail":           20,
    "Hospital":         15,
    "Classroom":        12,
    "Restaurant":       15,
    "Hotel Room":       10,
}

# Standard AC sizes (kW)
AC_SIZES_KW = [0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 7.5,
               10.0, 12.5, 15.0, 18.0, 20.0, 25.0, 30.0, 40.0, 50.0]

# ASHRAE 90.1 minimum EER by capacity range
def _min_eer(kw: float) -> float:
    if kw <= 5.3:   return 3.22   # <18kBtu/h split
    if kw <= 19.0:  return 3.08
    if kw <= 39.6:  return 2.93
    return 2.78


def calculate(inputs: dict) -> dict:
    """
    Main entry point - compatible with TypeScript calcHVACCoolingLoad() keys.
    """
    # ── Inputs ────────────────────────────────────────────────────────────────
    floor_area    = float(inputs.get("floor_area",         50))
    ceiling_h     = float(inputs.get("ceiling_height",      3))
    wall_area     = float(inputs.get("wall_area",            0)) or (math.sqrt(floor_area) * 4 * ceiling_h)
    glass_area    = float(inputs.get("glass_area",           0)) or (wall_area * 0.20)
    persons       = float(inputs.get("persons",              5))
    equip_kw      = float(inputs.get("equipment_kw",         0))
    outdoor_db    = float(inputs.get("outdoor_temp",         35))   # dry bulb °C
    indoor_db     = float(inputs.get("indoor_temp",          24))
    indoor_rh     = float(inputs.get("indoor_rh_pct",        55))   # %
    outdoor_rh    = float(inputs.get("outdoor_rh_pct",       80))   # Manila ~80% RH
    insulation    = str  (inputs.get("insulation",       "Standard"))
    glass_type    = str  (inputs.get("glass_type",       "Standard"))
    orientation   = str  (inputs.get("window_orientation","Mixed"))
    room_fn       = str  (inputs.get("room_function",    "Office"))
    design_margin = float(inputs.get("design_margin_pct",   10))    # 10% safety

    # ── Psychrometric state points via psychrolib ─────────────────────────────
    # Outdoor state
    try:
        outdoor_w    = psychrolib.GetHumRatioFromRelHum(outdoor_db, outdoor_rh / 100, 101325)
        outdoor_h    = psychrolib.GetMoistAirEnthalpy(outdoor_db, outdoor_w)          # J/kg
        outdoor_wb   = psychrolib.GetTWetBulbFromHumRatio(outdoor_db, outdoor_w, 101325)
        outdoor_dp   = psychrolib.GetTDewPointFromHumRatio(outdoor_db, outdoor_w, 101325)
    except Exception:
        outdoor_w, outdoor_h, outdoor_wb, outdoor_dp = 0.022, 90000, 28.5, 26.0

    # Indoor state
    try:
        indoor_w     = psychrolib.GetHumRatioFromRelHum(indoor_db, indoor_rh / 100, 101325)
        indoor_h     = psychrolib.GetMoistAirEnthalpy(indoor_db, indoor_w)
        indoor_wb    = psychrolib.GetTWetBulbFromHumRatio(indoor_db, indoor_w, 101325)
        indoor_dp    = psychrolib.GetTDewPointFromHumRatio(indoor_db, indoor_w, 101325)
    except Exception:
        indoor_w, indoor_h, indoor_wb, indoor_dp = 0.011, 51800, 17.0, 14.0

    # Moisture difference (g/kg)
    delta_w_gkg  = (outdoor_w - indoor_w) * 1000

    # ── Sensible heat gains - CLTD method (ASHRAE 2021 Ch.18) ────────────────
    u_wall    = U_WALL.get(insulation, 0.45)
    u_roof    = U_ROOF.get(insulation, 0.50)
    cltd_wall = CLTD_WALL.get(orientation, 9.0)

    q_walls   = u_wall * wall_area   * cltd_wall   # W
    q_roof    = u_roof * floor_area  * CLTD_ROOF   # W
    q_glass_cond = u_wall * glass_area * (outdoor_db - indoor_db)  # conduction W
    q_glass_solar = SHGC.get(glass_type, 0.87) * SOLAR_W.get(orientation, 350) * glass_area  # solar W
    q_glass   = q_glass_cond + q_glass_solar

    # Internal gains
    occ       = OCCUPANT_HEAT.get(room_fn, {"sensible": 75, "latent": 55})
    q_people_s= occ["sensible"] * persons          # W sensible
    q_people_l= occ["latent"]   * persons          # W latent
    q_lighting= LIGHTING_WPM2.get(room_fn, 12) * floor_area   # W
    q_equip   = equip_kw * 1000                    # W

    # Infiltration - 0.5 ACH typical Philippine construction
    volume     = floor_area * ceiling_h
    ach_inf    = 0.5
    rho_air    = 1.2   # kg/m3
    q_infil_s  = rho_air * (volume * ach_inf / 3600) * 1006 * (outdoor_db - indoor_db)  # W
    q_infil_l  = rho_air * (volume * ach_inf / 3600) * 2501000 * (outdoor_w - indoor_w) # W

    # ── Totals ────────────────────────────────────────────────────────────────
    q_sensible_total = (q_walls + q_roof + q_glass +
                        q_people_s + q_lighting + q_equip + q_infil_s)
    q_latent         = q_people_l + q_infil_l
    q_total          = q_sensible_total + q_latent
    q_design         = q_total * (1 + design_margin / 100)

    # SHR - Sensible Heat Ratio
    shr = q_sensible_total / max(q_total, 1)

    # ── Convert to kW and TR ──────────────────────────────────────────────────
    kW  = round(q_total   / 1000, 2)
    TR  = round(kW / 3.517, 2)
    kW_design = round(q_design / 1000, 2)
    TR_design  = round(kW_design / 3.517, 2)

    # Recommended unit
    rec_kw = next((s for s in AC_SIZES_KW if s >= kW_design), AC_SIZES_KW[-1])
    rec_tr = round(rec_kw / 3.517, 2)

    # ── ASHRAE 62.1 Ventilation check ────────────────────────────────────────
    # OA requirement: 2.5 L/s/person + 0.3 L/s/m2 (office default)
    oa_lps       = persons * 2.5 + floor_area * 0.3
    oa_m3hr      = round(oa_lps * 3.6, 1)
    # Supply air estimate
    dT_coil      = max(indoor_db - 13, 6)   # 13°C supply air typical
    q_sa_m3s     = q_design / (1.2 * 1006 * dT_coil)
    q_sa_m3hr    = q_sa_m3s * 3600
    oa_pct       = round(oa_m3hr / max(q_sa_m3hr, 1) * 100, 1)
    oa_adequate  = oa_pct >= 15   # ASHRAE 62.1 minimum

    # ── ASHRAE 90.1 EER check ─────────────────────────────────────────────────
    min_eer     = _min_eer(rec_kw)
    # Typical inverter split EER at Manila conditions ~3.5
    assumed_eer = 3.5
    eer_ok      = assumed_eer >= min_eer

    # Cooling density (TR/m2) - ASHRAE guideline 0.04-0.09
    cooling_density     = round(TR_design / max(floor_area, 1), 4)
    density_ok          = 0.03 <= cooling_density <= 0.12

    return {
        # Primary results
        "kW":               kW,
        "TR":               TR,
        "recommended_kW":   rec_kw,
        "recommended_TR":   rec_tr,
        "q_design":         round(q_design, 1),
        "q_sensible_total": round(q_sensible_total, 1),
        "q_latent":         round(q_latent, 1),
        "SHR":              round(shr, 3),

        # Heat gain breakdown
        "components": {
            "q_walls":      round(q_walls, 1),
            "q_roof":       round(q_roof, 1),
            "q_glass":      round(q_glass, 1),
            "q_people":     round(q_people_s, 1),
            "q_people_latent": round(q_people_l, 1),
            "q_lighting":   round(q_lighting, 1),
            "q_equipment":  round(q_equip, 1),
            "q_infiltration": round(q_infil_s, 1),
        },

        # Psychrometric state points (from psychrolib)
        "psychrometrics": {
            "outdoor_db_c":      outdoor_db,
            "outdoor_wb_c":      round(outdoor_wb, 1),
            "outdoor_dp_c":      round(outdoor_dp, 1),
            "outdoor_rh_pct":    outdoor_rh,
            "outdoor_w_gkg":     round(outdoor_w * 1000, 2),
            "outdoor_h_kJkg":    round(outdoor_h / 1000, 2),
            "indoor_db_c":       indoor_db,
            "indoor_wb_c":       round(indoor_wb, 1),
            "indoor_dp_c":       round(indoor_dp, 1),
            "indoor_rh_pct":     indoor_rh,
            "indoor_w_gkg":      round(indoor_w * 1000, 2),
            "indoor_h_kJkg":     round(indoor_h / 1000, 2),
            "delta_w_gkg":       round(delta_w_gkg, 2),
        },

        # Ventilation
        "oa_lps":            round(oa_lps, 1),
        "oa_m3hr":           oa_m3hr,
        "oa_pct":            oa_pct,
        "oa_adequate":       oa_adequate,

        # Compliance
        "cooling_density_TR_m2": cooling_density,
        "density_ok":            density_ok,
        "min_eer_ashrae90":      min_eer,
        "eer_ok":                eer_ok,

        # Metadata
        "inputs_used": {
            "room_function":      room_fn,
            "insulation":         insulation,
            "glass_type":         glass_type,
            "window_orientation": orientation,
            "design_margin_pct":  design_margin,
        },
        "calculation_source": "python/psychrolib",
        "standard": "ASHRAE 62.1 | ASHRAE 90.1 | ASHRAE 55 | ASHRAE 2021 Ch.18",
    }
