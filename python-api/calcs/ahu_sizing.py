"""
AHU Sizing - Phase 2b
Standards: ASHRAE 62.1, ASHRAE 90.1, ASHRAE 2021 Fundamentals Ch.1 (Psychrometrics),
           SMACNA HVAC Systems Duct Design, PNS/PSME
Libraries: psychrolib (psychrometrics), math

Calculates:
- Supply airflow (m3/s, m3/h, cfm) from sensible cooling load + coil delta-T
- Psychrometric process line: Room → Return → Mixed → Off-coil → Supply
- Cooling coil load (sensible + latent), SHR, coil bypass factor
- Coil face area and velocity at standard 2.0-2.5 m/s face velocity
- Fan total static pressure (supply duct + return duct + coil + filter)
- Fan motor kW sizing with efficiency factor
- ASHRAE 62.1 OA check (ventilation adequacy in the mixed air stream)
- ASHRAE 90.1 fan power limitation (W per L/s)
"""

import psychrolib
import math

psychrolib.SetUnitSystem(psychrolib.SI)

# ─── Standard AHU coil face velocities (m/s) ─────────────────────────────────
COIL_FACE_VELOCITY = {
    "Low":      1.8,   # quiet/low noise application
    "Standard": 2.3,   # typical commercial
    "High":     2.8,   # industrial / compact unit
}

# ─── Typical duct static pressure budgets (Pa) - SMACNA / PSME ───────────────
# Total external static pressure the fan must overcome
FAN_STATIC_BUDGET: dict[str, float] = {
    "Small (<5 kW)":    300,   # Pa - short duct runs
    "Medium (5-25 kW)": 500,
    "Large (>25 kW)":   750,
}

# ─── Filter + coil pressure drops (Pa) ───────────────────────────────────────
FILTER_DP   = 100   # Pa - standard 2-inch throwaway, mid-life
COIL_DP_PA  = 150   # Pa - typical DX or chilled water coil at 2.3 m/s
DAMPER_DP   = 50    # Pa - OA/RA dampers

# ─── ASHRAE 90.1 fan power limit (W per L/s of supply air) ───────────────────
# Table 10.8 - simple systems ≤ 1.2 W/(L/s), VAV systems ≤ 1.6
FAN_POWER_LIMIT_W_LPS = 1.2

# ─── Standard coil bypass factors (CBF) by coil rows ─────────────────────────
CBF_BY_ROWS: dict[int, float] = {
    4: 0.10,
    6: 0.05,
    8: 0.02,
}


def _sat_state(temp_c: float, rh_frac: float) -> tuple[float, float, float, float]:
    """Return (w kg/kg, h J/kg, wb_c, dp_c) via psychrolib."""
    try:
        w  = psychrolib.GetHumRatioFromRelHum(temp_c, rh_frac, 101325)
        h  = psychrolib.GetMoistAirEnthalpy(temp_c, w)
        wb = psychrolib.GetTWetBulbFromHumRatio(temp_c, w, 101325)
        dp = psychrolib.GetTDewPointFromHumRatio(temp_c, w, 101325)
        return w, h, wb, dp
    except Exception:
        # Fallback values (35°C/80% RH outdoor, 24°C/55% RH indoor)
        if temp_c > 30:
            return 0.0278, 106000, 30.2, 28.5
        return 0.0110,  51800,  17.0, 14.0


def _mixed_air_state(
    oa_fraction: float,
    oa_w: float, oa_h: float, oa_db: float,
    ra_w: float, ra_h: float, ra_db: float,
) -> tuple[float, float, float]:
    """
    Mixed air state by mass balance.
    Returns (ma_db °C, ma_w kg/kg, ma_h J/kg).
    """
    ma_db = oa_fraction * oa_db + (1 - oa_fraction) * ra_db
    ma_w  = oa_fraction * oa_w  + (1 - oa_fraction) * ra_w
    ma_h  = oa_fraction * oa_h  + (1 - oa_fraction) * ra_h
    return ma_db, ma_w, ma_h


def _fan_motor_kw(
    flow_m3s: float,
    static_pa: float,
    fan_eff: float = 0.65,
    motor_eff: float = 0.92,
) -> float:
    """
    Shaft power: P = Q * dP / (fan_eff * motor_eff)
    Returns motor input kW.
    """
    return (flow_m3s * static_pa) / (fan_eff * motor_eff * 1000)


# Standard motor kW sizes
MOTOR_SIZES_KW = [0.37, 0.55, 0.75, 1.1, 1.5, 2.2, 3.0, 4.0, 5.5, 7.5,
                  11, 15, 18.5, 22, 30, 37, 45, 55, 75, 90, 110]


def calculate(inputs: dict) -> dict:
    """
    Main entry point - compatible with TypeScript calcAHUSizing() input keys.
    """
    # ── Inputs ────────────────────────────────────────────────────────────────
    q_sensible_w  = float(inputs.get("q_sensible",       0)
                      or  inputs.get("q_sensible_total", 0)
                      or  inputs.get("cooling_load_w",   0))
    q_latent_w    = float(inputs.get("q_latent",         0))
    q_total_w     = float(inputs.get("q_total",          0))

    # If q_total not given, derive
    if q_total_w <= 0 and q_sensible_w > 0:
        q_total_w = q_sensible_w + q_latent_w

    # Allow inputs from HVAC Cooling Load result dict (nested results)
    if q_total_w <= 0:
        q_total_w     = float(inputs.get("q_design",     10000))
        q_sensible_w  = float(inputs.get("q_sensible_total", q_total_w * 0.70))
        q_latent_w    = q_total_w - q_sensible_w

    if q_total_w <= 0:
        raise ValueError("Cooling load must be greater than 0 W.")

    supply_temp_c   = float(inputs.get("supply_air_temp_c",  13.0))  # typical 12-16°C
    indoor_db       = float(inputs.get("indoor_temp",        24.0))
    indoor_rh_pct   = float(inputs.get("indoor_rh_pct",      55.0))
    outdoor_db      = float(inputs.get("outdoor_temp",        35.0))
    outdoor_rh_pct  = float(inputs.get("outdoor_rh_pct",      80.0))
    oa_pct          = float(inputs.get("oa_pct",              20.0))  # % outside air
    face_vel_key    = str  (inputs.get("face_velocity",    "Standard"))
    coil_rows       = int  (inputs.get("coil_rows",             6))
    design_margin   = float(inputs.get("design_margin_pct",    10.0))
    floor_area_m2   = float(inputs.get("floor_area",            50))
    persons         = float(inputs.get("persons",                5))

    # ── Psychrometric state: Room air (return air = room conditions) ──────────
    ra_w, ra_h, ra_wb, ra_dp = _sat_state(indoor_db, indoor_rh_pct / 100)

    # ── Outdoor air state ─────────────────────────────────────────────────────
    oa_w, oa_h, oa_wb, oa_dp = _sat_state(outdoor_db, outdoor_rh_pct / 100)

    # ── Supply air conditions ─────────────────────────────────────────────────
    # Humidity ratio at supply temp - assume RH ~95% (near saturation off coil)
    sa_w, sa_h, sa_wb, sa_dp = _sat_state(supply_temp_c, 0.95)

    # ── Supply airflow from sensible heat equation ────────────────────────────
    # Q_s = m_dot * Cp * (T_room - T_supply)
    # m_dot = Q_s / (Cp * dT)   [kg/s]
    rho_air  = 1.15          # kg/m3 at 35°C Manila ambient (tropical air)
    cp_air   = 1006          # J/(kg·K)
    dT_coil  = max(indoor_db - supply_temp_c, 4.0)   # prevent div-by-zero

    mass_flow_kgs  = q_sensible_w / (cp_air * dT_coil)
    vol_flow_m3s   = mass_flow_kgs / rho_air
    vol_flow_m3hr  = vol_flow_m3s * 3600
    vol_flow_cfm   = vol_flow_m3s * 2118.88

    # Design flow with margin
    vol_flow_design_m3s = vol_flow_m3s * (1 + design_margin / 100)

    # ── Air changes per hour ──────────────────────────────────────────────────
    ceiling_h = float(inputs.get("ceiling_height", 3.0))
    room_vol  = floor_area_m2 * ceiling_h
    ach       = vol_flow_m3hr / max(room_vol, 1)

    # ── Mixed air state ───────────────────────────────────────────────────────
    oa_fraction = oa_pct / 100
    ma_db, ma_w, ma_h = _mixed_air_state(
        oa_fraction,
        oa_w, oa_h, outdoor_db,
        ra_w, ra_h, indoor_db,
    )

    # ── Coil load (mixed air → supply air state) ──────────────────────────────
    # Total coil load = mass flow * (h_mixed - h_supply)
    coil_total_w    = mass_flow_kgs * (ma_h - sa_h)
    # Sensible coil = mass flow * Cp * (T_mixed - T_supply)
    coil_sensible_w = mass_flow_kgs * cp_air * (ma_db - supply_temp_c)
    coil_latent_w   = max(coil_total_w - coil_sensible_w, 0)
    coil_shr        = coil_sensible_w / max(coil_total_w, 1)

    # Coil kW
    coil_kw = round(coil_total_w / 1000, 2)
    coil_tr = round(coil_kw / 3.517, 2)

    # ── Coil bypass factor ────────────────────────────────────────────────────
    cbf = CBF_BY_ROWS.get(coil_rows, 0.05)

    # ── Apparatus Dew Point (ADP) - psychrometric coil performance ────────────
    # ADP is where the coil saturation line intersects the condition line
    # Simplified: ADP = supply_db - CBF * (mixed_db - supply_db)
    adp_c = supply_temp_c - cbf * (ma_db - supply_temp_c)

    # ── Coil face area and velocity ───────────────────────────────────────────
    face_vel_ms  = COIL_FACE_VELOCITY.get(face_vel_key, 2.3)
    coil_area_m2 = vol_flow_design_m3s / face_vel_ms
    # Typical coil face aspect ratio ~1.5:1 (width:height)
    coil_height_m = round(math.sqrt(coil_area_m2 / 1.5), 2)
    coil_width_m  = round(coil_height_m * 1.5, 2)

    # ── Fan static pressure budget ────────────────────────────────────────────
    # Determine budget category by coil load
    if coil_kw < 5:
        fan_sp_pa = FAN_STATIC_BUDGET["Small (<5 kW)"]
    elif coil_kw < 25:
        fan_sp_pa = FAN_STATIC_BUDGET["Medium (5-25 kW)"]
    else:
        fan_sp_pa = FAN_STATIC_BUDGET["Large (>25 kW)"]

    # Total static = external duct + filter + coil + dampers
    fan_total_static_pa = fan_sp_pa + FILTER_DP + COIL_DP_PA + DAMPER_DP

    # ── Fan motor sizing ──────────────────────────────────────────────────────
    fan_motor_kw_calc = _fan_motor_kw(vol_flow_design_m3s, fan_total_static_pa)
    rec_motor_kw      = next((s for s in MOTOR_SIZES_KW if s >= fan_motor_kw_calc),
                              MOTOR_SIZES_KW[-1])

    # ── ASHRAE 90.1 fan power check ───────────────────────────────────────────
    # Limit: 1.2 W per L/s (simple constant volume systems)
    flow_lps            = vol_flow_design_m3s * 1000
    fan_power_w_lps     = (fan_motor_kw_calc * 1000) / max(flow_lps, 1)
    fan_power_ok        = fan_power_w_lps <= FAN_POWER_LIMIT_W_LPS

    # ── ASHRAE 62.1 OA adequacy ───────────────────────────────────────────────
    # Required OA: 2.5 L/s/person + 0.3 L/s/m2 (office default)
    oa_required_lps   = persons * 2.5 + floor_area_m2 * 0.3
    oa_delivered_lps  = flow_lps * oa_fraction
    oa_adequate       = oa_delivered_lps >= oa_required_lps

    # ── Dehumidification capacity ─────────────────────────────────────────────
    # Moisture removed: m_dot * (w_mixed - w_supply)  [kg/s water]
    dehum_kg_hr = mass_flow_kgs * (ma_w - sa_w) * 3600

    return {
        # Airflow
        "supply_flow_m3s":      round(vol_flow_m3s, 4),
        "supply_flow_m3hr":     round(vol_flow_m3hr, 1),
        "supply_flow_cfm":      round(vol_flow_cfm, 1),
        "design_flow_m3s":      round(vol_flow_design_m3s, 4),
        "mass_flow_kgs":        round(mass_flow_kgs, 4),
        "air_changes_per_hr":   round(ach, 1),

        # Coil sizing
        "coil_total_kw":        coil_kw,
        "coil_total_tr":        coil_tr,
        "coil_sensible_w":      round(coil_sensible_w, 1),
        "coil_latent_w":        round(coil_latent_w, 1),
        "coil_shr":             round(coil_shr, 3),
        "coil_bypass_factor":   cbf,
        "coil_rows":            coil_rows,
        "adp_c":                round(adp_c, 1),

        # Coil physical size
        "coil_face_area_m2":    round(coil_area_m2, 3),
        "coil_face_velocity_ms": face_vel_ms,
        "coil_height_m":        coil_height_m,
        "coil_width_m":         coil_width_m,

        # Fan
        "fan_total_static_pa":  fan_total_static_pa,
        "fan_motor_kw":         round(fan_motor_kw_calc, 3),
        "recommended_motor_kw": rec_motor_kw,
        "fan_power_w_lps":      round(fan_power_w_lps, 3),
        "fan_power_ok":         fan_power_ok,

        # Psychrometric process line
        "psychrometrics": {
            "room_db_c":        indoor_db,
            "room_wb_c":        round(ra_wb, 1),
            "room_dp_c":        round(ra_dp, 1),
            "room_rh_pct":      indoor_rh_pct,
            "room_w_gkg":       round(ra_w * 1000, 2),
            "room_h_kJkg":      round(ra_h / 1000, 2),

            "outdoor_db_c":     outdoor_db,
            "outdoor_wb_c":     round(oa_wb, 1),
            "outdoor_dp_c":     round(oa_dp, 1),
            "outdoor_rh_pct":   outdoor_rh_pct,
            "outdoor_w_gkg":    round(oa_w * 1000, 2),
            "outdoor_h_kJkg":   round(oa_h / 1000, 2),

            "mixed_db_c":       round(ma_db, 1),
            "mixed_w_gkg":      round(ma_w * 1000, 2),
            "mixed_h_kJkg":     round(ma_h / 1000, 2),
            "oa_fraction_pct":  oa_pct,

            "supply_db_c":      supply_temp_c,
            "supply_wb_c":      round(sa_wb, 1),
            "supply_dp_c":      round(sa_dp, 1),
            "supply_w_gkg":     round(sa_w * 1000, 2),
            "supply_h_kJkg":    round(sa_h / 1000, 2),

            "adp_c":            round(adp_c, 1),
            "delta_T_c":        round(dT_coil, 1),
        },

        # Ventilation
        "oa_required_lps":      round(oa_required_lps, 1),
        "oa_delivered_lps":     round(oa_delivered_lps, 1),
        "oa_adequate":          oa_adequate,

        # Dehumidification
        "dehumidification_kg_hr": round(dehum_kg_hr, 2),

        # Metadata
        "inputs_used": {
            "supply_air_temp_c":  supply_temp_c,
            "outdoor_air_pct":    oa_pct,
            "face_velocity":      face_vel_key,
            "coil_rows":          coil_rows,
            "design_margin_pct":  design_margin,
        },
        "calculation_source": "python/psychrolib",
        "standard": "ASHRAE 62.1 | ASHRAE 90.1 | ASHRAE 2021 Ch.1 | SMACNA",

        # ── Legacy renderer aliases (frontend renderAHUSizingReport) ──────────
        "Q_coil_total_kW":   coil_kw,
        "Q_coil_TR":         coil_tr,
        "Q_coil_sensible_kW": round(coil_sensible_w / 1000, 2),
        "Q_coil_latent_kW":  round(coil_latent_w / 1000, 2),
        "Q_design_kW":       coil_kw,
        "Q_design_TR":       coil_tr,
        "Q_sensible_kW":     round(coil_sensible_w / 1000, 2),
        "Q_latent_kW":       round(coil_latent_w / 1000, 2),
        "Q_input_kW":        round(fan_motor_kw_calc, 3),
        "Q_sa_m3s":          round(vol_flow_m3s, 4),
        "Q_sa_CMH":          round(vol_flow_m3hr, 1),
        "Q_sa_CMH_each":     round(vol_flow_m3hr, 1),
        "Q_sa_CFM":          round(vol_flow_cfm, 1),
        "Q_oa_CMH":          round(oa_delivered_lps * 3.6, 1),
        "Q_ra_CMH":          round((vol_flow_m3hr - oa_delivered_lps * 3.6), 1),
        "P_fan_kW":          round(fan_motor_kw_calc, 3),
        "P_fan_kW_each":     round(fan_motor_kw_calc, 3),
        "fan_static_pa":     fan_total_static_pa,
        # CHW flow (default dT=5°C, Cp=4.186 kJ/kg·K, rho=1000 kg/m³)
        "Q_chw_lps":         round(coil_kw / (4.186 * 5), 3),
        "Q_chw_m3h":         round(coil_kw / (4.186 * 5) * 3.6, 2),
        "Q_chw_GPM":         round(coil_kw / (4.186 * 5) * 15.8503, 1),
        "dT_chw_C":          5.0,
        "chw_supply_C":      7.0,
        "chw_return_C":      12.0,
        "shr":               round(coil_shr, 3),
        "n_units":           1,
        "nominal_AHU_CMH_total": round(vol_flow_m3hr, 1),
        "nominal_AHU_CMH_each":  round(vol_flow_m3hr, 1),
        "ach_actual":        round(ach, 1),
        "ceiling_height":    ceiling_h,
        "floor_area":        floor_area_m2,   # use internally computed value (defaults to 50 m²)
        "zone_volume":       round(room_vol, 1),
        "persons":           persons,
        "safety_factor":     float(inputs.get("design_margin_pct", 10)) / 100 + 1,
        "oa_pct_used":       oa_pct,
        "oa_per_person_lps": float(inputs.get("oa_per_person_lps", 10.0)),
        "fan_hp_std":        round(rec_motor_kw / 0.746, 1),
        "fan_hp_total":      round(fan_motor_kw_calc / 0.746, 1),
        "fan_power_W_lps":   round(fan_power_w_lps, 3),
        "fan_power_check":   "PASS" if fan_power_ok else "FAIL",
        "ashrae_fan_max":    1.2,
        "ashrae_oa_min_lps_person": 2.5,
        "oa_check":          "PASS" if oa_adequate else "FAIL",
        "T_mixed":           round(ma_db, 1),
        "eta_fan":           0.65,
        "dT_sa":             round(indoor_db - supply_temp_c, 1),
        "fan_static_Pa":     fan_total_static_pa,
    }
