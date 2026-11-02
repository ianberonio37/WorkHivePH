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
from ._catalog import discloses, pick_at_least

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
# ★THE LIMIT WAS NOT 90.1's (2026-11-02, ED-G1 AHU, read against the guide). It read "Table 10.8 - simple systems ≤ 1.2
# W/(L/s)" (Table 10.8 is motor efficiency) and the guide said 0.82 W/(L/s) (that is 0.0011 hp/cfm read as W/cfm).
# 90.1-2019 §6.5.3.1.1 Option 1, constant volume: fan system motor NAMEPLATE kW ≤ 0.0017 × supply L/s (VAV 0.0024),
# required only where the system's total nameplate exceeds 5 hp (3.7 kW).
FAN_POWER_LIMIT_W_LPS = 1.7
FAN_POWER_THRESHOLD_KW = 3.73   # 5 hp

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


# ASHRAE 62.1 Table 6-1 outdoor-air rates (Rp L/s/person, Ra L/s/m²) by the AHU form's space types - the same rows as
# calcs/ventilation_ach.py VENTILATION_RATES; Retail = the table's Sales row (3.8, 0.6)
OA_RATES: dict[str, tuple[float, float]] = {
    "Office":           (2.5, 0.30),
    "Conference":       (2.5, 0.30),
    "Server Room":      (0.0, 0.00),
    "Production Floor": (2.5, 0.50),
    "Hospital Ward":    (2.5, 0.30),
    "Retail":           (3.8, 0.60),
}

# Standard motor kW sizes
MOTOR_SIZES_KW = [0.37, 0.55, 0.75, 1.1, 1.5, 2.2, 3.0, 4.0, 5.5, 7.5,
                  11, 15, 18.5, 22, 30, 37, 45, 55, 75, 90, 110]


# formula: ahu_sizing_ashrae_62
@discloses
def calculate(inputs: dict) -> dict:
    """
    Main entry point - compatible with TypeScript calcAHUSizing() input keys.
    """
    # ── Inputs ────────────────────────────────────────────────────────────────
    # Accept kW input from frontend (cooling_load_kW key → convert to W)
    _kw_in = float(inputs.get("cooling_load_kW", 0))
    q_sensible_w  = float(inputs.get("q_sensible",       0) or (_kw_in * 1000)
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

    # ★TEN OF THE FORM'S VALUES CHANGED NOTHING (2026-10-31, ED-I1 AHU Sizing, tools/census_calc_input_reach.py). The page
    # sends shr, room_temp_C, supply_temp_C, safety_factor, fan_static_Pa, eta_fan, chw_supply_C, chw_return_C, n_units and
    # space_type; this read none of them - the whole load was taken as sensible (airflow from the TOTAL load), the supply and
    # room temperatures were fixed at 13 / 24 °C, the fan's static and efficiency at a budget table and 0.65, the CHW flow at
    # a 7/12 °C ΔT of 5 K, one unit, and the OA check at office rates. Each is read below; a caller that sends the engine's
    # own keys (q_sensible, supply_air_temp_c, indoor_temp, design_margin_pct) keeps them.
    form_shr = inputs.get("shr")
    if _kw_in > 0 and not inputs.get("q_sensible") and form_shr not in (None, "") and 0 < float(form_shr) <= 1:
        q_total_w    = _kw_in * 1000                 # the form's load is the TOTAL load; SHR splits it
        q_sensible_w = q_total_w * float(form_shr)
        q_latent_w   = q_total_w - q_sensible_w

    if q_total_w <= 0:
        raise ValueError("Cooling load must be greater than 0 W.")

    supply_temp_c   = float(inputs.get("supply_air_temp_c", inputs.get("supply_temp_C", 13.0)))  # typical 12-16°C
    indoor_db       = float(inputs.get("indoor_temp",       inputs.get("room_temp_C",   24.0)))
    indoor_rh_pct   = float(inputs.get("indoor_rh_pct",      55.0))
    outdoor_db      = float(inputs.get("outdoor_temp",        35.0))
    # ★THE DEFAULT OUTSIDE AIR WAS A CONDITION MANILA NEVER SEES (2026-11-02, ED-G1 AHU): 35 °C at 80% RH is a 31 °C dew
    # point and 108 kJ/kg; ASHRAE's Manila design is 34.6 °C DB / 26.5 °C MCWB, its 0.4% enthalpy about 89 kJ/kg. The
    # form has no outdoor input, so every AHU's outside-air load was ~25% high. The default is now 35 °C DB / 28 °C WB
    # (about 89 kJ/kg, the enthalpy design point); an explicit RH or WB still wins.
    if inputs.get("outdoor_rh_pct") not in (None, ""):
        outdoor_rh_pct = float(inputs["outdoor_rh_pct"])
    else:
        outdoor_wb_in  = min(float(inputs.get("outdoor_wb_c", 28.0)), outdoor_db)
        outdoor_rh_pct = psychrolib.GetRelHumFromTWetBulb(outdoor_db, outdoor_wb_in, 101325) * 100
    oa_pct          = float(inputs.get("oa_pct",              20.0))  # % outside air
    face_vel_key    = str  (inputs.get("face_velocity",    "Standard"))
    coil_rows       = int  (inputs.get("coil_rows",             6))
    _sf             = inputs.get("safety_factor")
    design_margin   = float(inputs.get("design_margin_pct",
                            (float(_sf) - 1) * 100 if _sf not in (None, "") and float(_sf) >= 1 else 10.0))
    _eta            = float(inputs.get("eta_fan", 0.65) or 0.65)
    fan_eff         = _eta / 100 if _eta > 1 else _eta                 # a percent or a fraction
    form_static_pa  = float(inputs.get("fan_static_Pa", 0) or 0)
    chw_supply_c    = float(inputs.get("chw_supply_C", 7.0) or 7.0)
    chw_return_c    = float(inputs.get("chw_return_C", 12.0) or 12.0)
    n_units         = max(1, int(float(inputs.get("n_units", 1) or 1)))
    space_type      = str(inputs.get("space_type", "Office") or "Office")
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
    # ★THE SAFETY FACTOR NEVER REACHED THE COIL (2026-11-02, ED-G1 AHU, read against the guide: "Q_design = Cooling Load ×
    # Safety Factor"). The margin enlarged the fan and the coil face, but the coil capacity, its chilled water, the
    # dehumidification and the AHU's rated airflow were all computed on the load airflow without it: a 1.10 factor left the
    # coil ~9% short of the air it was given. Everything the unit is selected on now runs at the design airflow.
    vol_flow_design_m3s  = vol_flow_m3s * (1 + design_margin / 100)
    mass_flow_design_kgs = mass_flow_kgs * (1 + design_margin / 100)
    vol_flow_design_m3hr = vol_flow_design_m3s * 3600

    # ── Air changes per hour ──────────────────────────────────────────────────
    ceiling_h = float(inputs.get("ceiling_height", 3.0))
    room_vol  = floor_area_m2 * ceiling_h
    ach       = vol_flow_design_m3hr / max(room_vol, 1)

    # ── Mixed air state ───────────────────────────────────────────────────────
    oa_fraction = oa_pct / 100
    ma_db, ma_w, ma_h = _mixed_air_state(
        oa_fraction,
        oa_w, oa_h, outdoor_db,
        ra_w, ra_h, indoor_db,
    )

    # ── Coil load (mixed air → supply air state) ──────────────────────────────
    # Total coil load = mass flow * (h_mixed - h_supply)
    coil_total_w    = mass_flow_design_kgs * (ma_h - sa_h)
    # Sensible coil = mass flow * Cp * (T_mixed - T_supply)
    coil_sensible_w = mass_flow_design_kgs * cp_air * (ma_db - supply_temp_c)
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

    # Total static = external duct + filter + coil + dampers - or the form's Fan Total Static Pressure when it is given
    fan_total_static_pa = form_static_pa if form_static_pa > 0 else fan_sp_pa + FILTER_DP + COIL_DP_PA + DAMPER_DP

    # ── Fan motor sizing ──────────────────────────────────────────────────────
    # The form's η is the COMBINED fan × motor efficiency (its label and the guide say so); dividing by a further 0.92
    # motor efficiency counted the motor twice (+8.7% fan power). The motor is picked per unit: it was picked for the
    # whole airflow and printed as "per unit".
    fan_motor_kw_calc = _fan_motor_kw(vol_flow_design_m3s, fan_total_static_pa, fan_eff=fan_eff, motor_eff=1.0)
    rec_motor_kw      = pick_at_least(MOTOR_SIZES_KW, fan_motor_kw_calc / n_units, "AHU fan motor per unit (kW)")
    nameplate_total_kw = rec_motor_kw * n_units

    # ── ASHRAE 90.1 fan power check (§6.5.3.1.1 Option 1, constant volume, nameplate) ──
    flow_lps            = vol_flow_design_m3s * 1000
    fan_power_w_lps     = (nameplate_total_kw * 1000) / max(flow_lps, 1)
    fan_power_ok        = fan_power_w_lps <= FAN_POWER_LIMIT_W_LPS
    fan_power_applies   = nameplate_total_kw > FAN_POWER_THRESHOLD_KW

    # ── ASHRAE 62.1 OA adequacy ───────────────────────────────────────────────
    # Required OA: Rp L/s/person + Ra L/s/m2 for the form's space type (ASHRAE 62.1 Table 6-1 - the Ventilation calculator's
    # own rows; Retail is the table's Sales row). It had been office rates for every space.
    rp, ra            = OA_RATES.get(space_type, OA_RATES["Office"])
    oa_required_lps   = persons * rp + floor_area_m2 * ra
    oa_delivered_lps  = flow_lps * oa_fraction
    oa_adequate       = oa_delivered_lps >= oa_required_lps

    # ── Dehumidification capacity ─────────────────────────────────────────────
    # Moisture removed: m_dot * (w_mixed - w_supply)  [kg/s water]
    dehum_kg_hr = mass_flow_design_kgs * (ma_w - sa_w) * 3600

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
            "outdoor_rh_pct":   round(outdoor_rh_pct, 1),
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
        "Q_input_kW":        round(q_total_w / 1000, 3),     # the room load as entered (total)
        "Q_room_sensible_kW": round(q_sensible_w / 1000, 3),
        "Q_room_latent_kW":  round(q_latent_w / 1000, 3),
        # The supply airflow the AHU is selected on is the design airflow (load airflow × the safety factor)
        "Q_sa_load_m3s":     round(vol_flow_m3s, 4),
        "Q_sa_load_CMH":     round(vol_flow_m3hr, 1),
        "Q_sa_m3s":          round(vol_flow_design_m3s, 4),
        "Q_sa_CMH":          round(vol_flow_design_m3hr, 1),
        "Q_sa_CMH_each":     round(vol_flow_design_m3hr / n_units, 1),
        "Q_sa_CFM":          round(vol_flow_design_m3s * 2118.88, 1),
        "Q_oa_CMH":          round(oa_delivered_lps * 3.6, 1),
        "Q_ra_CMH":          round((vol_flow_design_m3hr - oa_delivered_lps * 3.6), 1),
        "rho_air":           rho_air,
        "cp_air_kJ":         round(cp_air / 1000, 3),
        "m_design_kgs":      round(mass_flow_design_kgs, 4),
        "h_mixed_kJkg":      round(ma_h / 1000, 2),
        "h_supply_kJkg":     round(sa_h / 1000, 2),
        "T_outdoor_C":       outdoor_db,
        "P_fan_kW":          round(fan_motor_kw_calc, 3),
        "P_fan_kW_each":     round(fan_motor_kw_calc / n_units, 3),
        "fan_static_pa":     fan_total_static_pa,
        # CHW flow over the form's own supply/return ΔT (Cp=4.186 kJ/kg·K, rho=1000 kg/m³) - it was a fixed 7/12 °C
        "Q_chw_lps":         round(coil_kw / (4.186 * max(chw_return_c - chw_supply_c, 1.0)), 3),
        "Q_chw_m3h":         round(coil_kw / (4.186 * max(chw_return_c - chw_supply_c, 1.0)) * 3.6, 2),
        "Q_chw_GPM":         round(coil_kw / (4.186 * max(chw_return_c - chw_supply_c, 1.0)) * 15.8503, 1),
        "dT_chw_C":          round(max(chw_return_c - chw_supply_c, 1.0), 2),
        "chw_supply_C":      chw_supply_c,
        "chw_return_C":      chw_return_c,
        "shr":               round(coil_shr, 3),
        "n_units":           n_units,
        "nominal_AHU_CMH_total": round(vol_flow_design_m3hr, 1),
        "nominal_AHU_CMH_each":  round(vol_flow_design_m3hr / n_units, 1),
        "ach_actual":        round(ach, 1),
        "ceiling_height":    ceiling_h,
        "floor_area":        floor_area_m2,   # use internally computed value (defaults to 50 m²)
        "zone_volume":       round(room_vol, 1),
        "persons":           persons,
        "safety_factor":     round(design_margin / 100 + 1, 3),
        "oa_pct_used":       oa_pct,
        # OA delivered per person (it printed a fixed 10 whatever the airflow)
        "oa_per_person_lps": round(oa_delivered_lps / persons, 1) if persons > 0 else 0.0,
        "fan_motor_kw_each": rec_motor_kw,
        "fan_nameplate_total_kw": round(nameplate_total_kw, 2),
        "fan_hp_std":        round(rec_motor_kw / 0.746, 1),
        "fan_hp_total":      round(nameplate_total_kw / 0.746, 1),
        "fan_power_W_lps":   round(fan_power_w_lps, 3),
        "fan_power_check":   ("PASS" if fan_power_ok else "FAIL") if fan_power_applies else "N/A",
        "fan_power_basis":   ("ASHRAE 90.1-2019 §6.5.3.1.1 Option 1 (constant volume): nameplate ≤ 1.7 W per L/s"
                              + ("" if fan_power_applies else "; not required at 5 hp (3.7 kW) total nameplate or less")),
        "ashrae_fan_max":    FAN_POWER_LIMIT_W_LPS,
        "ashrae_oa_min_lps_person": rp,
        "ashrae_oa_lps_m2":  ra,
        "space_type":        space_type,
        "oa_check":          "PASS" if oa_adequate else "FAIL",
        "T_mixed":           round(ma_db, 1),
        "eta_fan":           fan_eff,
        "dT_sa":             round(indoor_db - supply_temp_c, 1),
        "fan_static_Pa":     fan_total_static_pa,
    }
