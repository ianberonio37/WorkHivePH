"""
Cooling Tower Sizing - Phase 2c
Standards: CTI STD-201 (Cooling Technology Institute), ASHRAE 2021 Fundamentals Ch.39,
           ASHRAE 90.1, PSME Code, ASME PTC 23
Libraries: psychrolib (wet-bulb air state), math

Calculates:
- Heat rejection load (kW, TR) from chiller or HVAC condenser duty
- Condenser water flow rate (L/s, L/min, m3/hr)
- Range (hot-in minus cold-out) and Approach (cold-out minus air wet-bulb)
- Number of Transfer Units (NTU) via Merkel equation
- Tower fill volume and L/G ratio
- Make-up water: evaporation + drift + blowdown per ASHRAE/CTI
- Fan motor kW (induced/forced draft) and pump kW
- Cycle of concentration (CoC) and blowdown rate
- ASHRAE 90.1 cooling tower efficiency check (gpm/hp)
"""

import psychrolib
import math

psychrolib.SetUnitSystem(psychrolib.SI)

# ─── Design wet-bulb temperature - Manila (°C) ────────────────────────────────
# ASHRAE 2021 Fundamentals, Climate Data - Manila design WB = 28°C (99.6% summer)
MANILA_DESIGN_WB = 28.0   # °C

# ─── Typical range and approach values for Philippine practice ─────────────────
# Range = T_hot_in - T_cold_out  (how much water is cooled)
# Approach = T_cold_out - WB_air (how close to wet bulb the cold water gets)
#
# Standard practice:
#   Range:    5–8°C (typical 5.5°C for comfort HVAC, 6°C industrial)
#   Approach: 3–5°C (closer = larger, more expensive tower)

TYPICAL_RANGE    = 5.5   # °C
TYPICAL_APPROACH = 4.0   # °C

# ─── Merkel NTU integration points (4-point Chebyshev) ───────────────────────
# NTU = integral[dT / (hs_water - h_air)]  over the range
# Evaluated at T_cold, T_cold+range/3, T_cold+2range/3, T_cold+range

def _sat_enthalpy(temp_c: float) -> float:
    """Enthalpy of saturated air (J/kg) at temp_c via psychrolib."""
    try:
        w = psychrolib.GetHumRatioFromRelHum(temp_c, 1.0, 101325)
        return psychrolib.GetMoistAirEnthalpy(temp_c, w)
    except Exception:
        # Fallback: simplified sat enthalpy ≈ 2501*w + 1.006*T (kJ/kg) × 1000
        # Use Magnus approximation for w_sat
        es = 6.1078 * math.exp(17.27 * temp_c / (temp_c + 237.3))  # mbar
        w  = 0.622 * es / (1013.25 - es)
        return (1006 * temp_c + w * (2501000 + 1860 * temp_c))


def _air_enthalpy_at_wb(wb_c: float) -> float:
    """Enthalpy of air at wet-bulb condition (entering air)."""
    return _sat_enthalpy(wb_c)   # saturated air at WB = air condition on entering side


def _ntu_merkel(
    t_cold: float, t_hot: float, h_air_in: float,
    l_over_g: float,    # liquid-to-gas ratio (mass water / mass air)
    cp_water: float = 4186.0,
) -> float:
    """
    NTU via 4-point Chebyshev numerical integration of the Merkel equation.
    NTU = (L/G) * Cp_water * integral[dT / (hs_water(T) - h_air(T))]
    Air enthalpy increases linearly from h_air_in to h_air_in + L/G*Cp*(T_hot-T_cold).
    """
    delta_h_air_total = l_over_g * cp_water * (t_hot - t_cold)  # total air enthalpy rise

    temps = [
        t_cold + 0.1 * (t_hot - t_cold),
        t_cold + 0.4 * (t_hot - t_cold),
        t_cold + 0.6 * (t_hot - t_cold),
        t_cold + 0.9 * (t_hot - t_cold),
    ]
    weights = [0.25, 0.25, 0.25, 0.25]   # equal weight 4-point

    ntu = 0.0
    for T, w in zip(temps, weights):
        frac       = (T - t_cold) / (t_hot - t_cold)
        h_air_T    = h_air_in + frac * delta_h_air_total
        hs_water_T = _sat_enthalpy(T)
        denom      = hs_water_T - h_air_T
        if denom < 100:
            denom = 100   # prevent singularity
        ntu += w * (l_over_g * cp_water) / denom

    return ntu * (t_hot - t_cold)   # multiply by range (Merkel form)


# ─── Standard cooling tower fan motor sizes (kW) ─────────────────────────────
TOWER_MOTOR_SIZES_KW = [0.37, 0.55, 0.75, 1.1, 1.5, 2.2, 3.0, 4.0, 5.5, 7.5,
                         11, 15, 18.5, 22, 30, 37, 45, 55, 75, 90, 110]

# ─── Pump motor sizes (kW) ────────────────────────────────────────────────────
PUMP_MOTOR_SIZES_KW  = [0.37, 0.55, 0.75, 1.1, 1.5, 2.2, 3.0, 4.0, 5.5, 7.5,
                         11, 15, 18.5, 22, 30, 37, 45, 55, 75, 90]


def calculate(inputs: dict) -> dict:
    """
    Main entry point - compatible with TypeScript calcCoolingTower() input keys.
    """
    # ── Inputs ────────────────────────────────────────────────────────────────
    # Accept heat rejection load from multiple source keys
    heat_rejection_kw = float(inputs.get("heat_rejection_kw",  0)
                          or  inputs.get("condenser_duty_kw",   0)
                          or  inputs.get("q_rejection_kw",      0))
    heat_rejection_tr = float(inputs.get("heat_rejection_tr",  0))

    # Derive from TR if kW not given
    if heat_rejection_kw <= 0 and heat_rejection_tr > 0:
        heat_rejection_kw = heat_rejection_tr * 3.517

    # If neither given, derive from cooling load (chiller heat rejection ≈ 1.25 × TR)
    if heat_rejection_kw <= 0:
        cooling_kw = float(inputs.get("cooling_kw", 0) or inputs.get("kW", 0))
        if cooling_kw > 0:
            heat_rejection_kw = cooling_kw * 1.25   # typical COP ~4 → HR = 1.25 × Qcooling
        else:
            heat_rejection_kw = 100.0   # safe default

    heat_rejection_tr = heat_rejection_kw / 3.517

    t_hot_in_c   = float(inputs.get("condenser_water_in_c",  35.0))  # hot water entering tower
    t_cold_out_c = float(inputs.get("condenser_water_out_c", 29.5))  # cooled water leaving tower
    wb_design_c  = float(inputs.get("design_wb_c",   MANILA_DESIGN_WB))
    range_c      = t_hot_in_c - t_cold_out_c
    approach_c   = t_cold_out_c - wb_design_c

    if range_c <= 0:
        range_c      = TYPICAL_RANGE
        t_cold_out_c = t_hot_in_c - range_c

    if approach_c <= 0:
        approach_c   = TYPICAL_APPROACH
        t_cold_out_c = wb_design_c + approach_c
        range_c      = t_hot_in_c - t_cold_out_c

    cycles_of_conc = float(inputs.get("cycles_of_concentration", 4.0))   # CoC
    l_over_g       = float(inputs.get("l_over_g",                1.3))   # typical 1.0-1.5
    fan_eff        = float(inputs.get("fan_efficiency_pct",       65)) / 100
    pump_head_m    = float(inputs.get("pump_head_m",              20.0))  # condenser pump TDH
    pump_eff       = float(inputs.get("pump_efficiency_pct",      70)) / 100

    # ── Air inlet psychrometrics ──────────────────────────────────────────────
    h_air_in = _air_enthalpy_at_wb(wb_design_c)   # J/kg - entering air at WB

    # ── Condenser water flow rate ─────────────────────────────────────────────
    # Q = m_dot * Cp * Range   →   m_dot = Q / (Cp * Range)
    cp_water       = 4186.0   # J/(kg·K)
    rho_water      = 995.7    # kg/m3 at ~30°C
    mass_flow_kgs  = heat_rejection_kw * 1000 / (cp_water * range_c)
    flow_lps       = mass_flow_kgs / rho_water
    flow_lmin      = flow_lps * 60
    flow_m3hr      = flow_lps * 3.6
    flow_gpm       = flow_lps * 15.8508   # US GPM

    # ── NTU (Merkel equation) ─────────────────────────────────────────────────
    ntu = _ntu_merkel(t_cold_out_c, t_hot_in_c, h_air_in, l_over_g)

    # ── Air flow rate ─────────────────────────────────────────────────────────
    # G (air mass flow) from L/G ratio: G = m_dot_water / (L/G)
    air_mass_kgs   = mass_flow_kgs / l_over_g
    rho_air_inlet  = 1.15   # kg/m3 at 35°C, Manila
    air_vol_m3s    = air_mass_kgs / rho_air_inlet

    # ── Fan power ─────────────────────────────────────────────────────────────
    # Fan static pressure for cooling tower: typically 150-300 Pa (induced draft)
    fan_static_pa  = 200   # Pa - typical induced draft tower
    fan_kw_calc    = (air_vol_m3s * fan_static_pa) / (fan_eff * 1000)
    rec_fan_kw     = next((s for s in TOWER_MOTOR_SIZES_KW if s >= fan_kw_calc),
                          TOWER_MOTOR_SIZES_KW[-1])
    fan_hp         = round(rec_fan_kw * 1.341, 1)

    # ASHRAE 90.1 / CTI efficiency: gpm per fan hp - target ≥ 38 gpm/hp
    gpm_per_hp     = flow_gpm / max(fan_hp, 0.01)
    tower_eff_ok   = gpm_per_hp >= 38.0

    # ── Condenser water pump ──────────────────────────────────────────────────
    pump_kw_calc   = (flow_lps * pump_head_m * rho_water * 9.81) / (pump_eff * 1e6)
    # More readable form: P = rho * g * Q * H / eta (W)
    pump_kw_calc   = (rho_water * 9.81 * flow_lps * pump_head_m) / (pump_eff * 1000)
    rec_pump_kw    = next((s for s in PUMP_MOTOR_SIZES_KW if s >= pump_kw_calc),
                          PUMP_MOTOR_SIZES_KW[-1])

    # ── Make-up water calculation (CTI / ASHRAE) ──────────────────────────────
    # Evaporation loss: ~0.75% of circulating flow per 5.6°C range (ASHRAE rule)
    evap_rate_pct  = 0.75 * (range_c / 5.6)         # % of flow
    evap_lps       = flow_lps * evap_rate_pct / 100

    # Drift loss: modern towers <0.002% of flow (CTI STD-201 drift eliminators)
    drift_lps      = flow_lps * 0.0002

    # Blowdown to control CoC
    # Blowdown = Evaporation / (CoC - 1)
    blowdown_lps   = evap_lps / max(cycles_of_conc - 1, 0.5)

    # Total make-up
    makeup_lps     = evap_lps + drift_lps + blowdown_lps
    makeup_m3hr    = makeup_lps * 3.6
    makeup_lday    = makeup_lps * 86400

    # ── Basin volume (rule of thumb: 1-2 min hold time) ───────────────────────
    basin_m3       = flow_m3hr * (1.5 / 60)   # 1.5 minutes at circulating flow rate

    # ── Thermal performance summary ───────────────────────────────────────────
    effectiveness  = range_c / max(range_c + approach_c, 1)  # fraction 0-1

    return {
        # Thermal duty
        "heat_rejection_kw":    round(heat_rejection_kw, 2),
        "heat_rejection_tr":    round(heat_rejection_tr, 2),

        # Temperature design
        "t_hot_in_c":           t_hot_in_c,
        "t_cold_out_c":         round(t_cold_out_c, 1),
        "wb_design_c":          wb_design_c,
        "range_c":              round(range_c, 2),
        "approach_c":           round(approach_c, 2),
        "effectiveness":        round(effectiveness, 3),

        # Merkel NTU
        "ntu":                  round(ntu, 3),
        "l_over_g":             l_over_g,
        "h_air_inlet_kJkg":     round(h_air_in / 1000, 2),

        # Water flow
        "water_flow_lps":       round(flow_lps, 3),
        "water_flow_lmin":      round(flow_lmin, 1),
        "water_flow_m3hr":      round(flow_m3hr, 2),
        "water_flow_gpm":       round(flow_gpm, 1),
        "mass_flow_kgs":        round(mass_flow_kgs, 3),

        # Air flow
        "air_flow_m3s":         round(air_vol_m3s, 3),
        "air_mass_kgs":         round(air_mass_kgs, 3),

        # Fan
        "fan_power_kw":         round(fan_kw_calc, 3),
        "recommended_fan_kw":   rec_fan_kw,
        "fan_hp":               fan_hp,
        "gpm_per_hp":           round(gpm_per_hp, 1),
        "tower_efficiency_ok":  tower_eff_ok,

        # Pump
        "pump_power_kw":        round(pump_kw_calc, 3),
        "recommended_pump_kw":  rec_pump_kw,
        "pump_head_m":          pump_head_m,

        # Make-up water
        "evaporation_lps":      round(evap_lps, 4),
        "drift_lps":            round(drift_lps, 5),
        "blowdown_lps":         round(blowdown_lps, 4),
        "makeup_water_lps":     round(makeup_lps, 4),
        "makeup_water_m3hr":    round(makeup_m3hr, 3),
        "makeup_water_L_day":   round(makeup_lday, 1),
        "cycles_of_concentration": cycles_of_conc,

        # Basin
        "basin_volume_m3":      round(basin_m3, 2),

        # Metadata
        "inputs_used": {
            "design_wb_c":              wb_design_c,
            "l_over_g":                 l_over_g,
            "cycles_of_concentration":  cycles_of_conc,
        },
        "calculation_source": "python/psychrolib",
        "standard": "CTI STD-201 | ASHRAE 2021 Ch.39 | ASHRAE 90.1 | ASME PTC 23",

        # ── Legacy renderer aliases (frontend renderCoolingTowerReport) ────────
        "ewt":               t_hot_in_c,
        "lwt":               t_cold_out_c,
        "wbt":               wb_design_c,
        "approach_c":        round(t_cold_out_c - wb_design_c, 2),
        "approach_check":    "PASS" if (t_cold_out_c - wb_design_c) >= 3.0 else "WARN - approach < 3°C",
        "lg_ratio":          l_over_g,
        "coc":               cycles_of_conc,
        "n_cells":           1,
        "q_cell_kw":         round(heat_rejection_kw, 2),
        "q_cell_tr":         round(heat_rejection_tr, 2),
        "q_rejection_kw":    round(heat_rejection_kw, 2),
        "q_rejection_tr":    round(heat_rejection_tr, 2),
        "q_w_lps":           round(water_flow_lps, 2),
        "q_w_m3hr":          round(water_flow_m3hr, 2),
        "q_w_GPM":           round(water_flow_gpm, 1),
        "fan_kw_total":      round(fan_kw_calc, 3),
        "fan_kw_std":        rec_fan_kw,
        "fan_kw_per_cell":   round(fan_kw_calc, 3),
        "fan_kw_per_100kw":  round(fan_kw_calc / max(heat_rejection_kw, 1) * 100, 3),
        "fan_flow_CMH":      round(air_flow_m3s * 3600, 0),
        "fan_flow_CMH_cell": round(air_flow_m3s * 3600, 0),
        "blowdown_lhr":      round(blowdown_lps * 3600, 1),
        "drift_lhr":         round(drift_lps * 3600, 2),
        "evap_lhr":          round(evap_lps * 3600, 1),
        "makeup_lhr":        round(makeup_lps * 3600, 1),
        "makeup_m3day":      round(makeup_lday / 1000, 3),
        "ashrae_ct_check":   "PASS" if tower_eff_ok else "WARN",
        "chiller_cop":       None,
        "chiller_kw_input":  None,
        "chiller_tr_input":  None,
        "load_source":       str(inputs.get("load_source", "direct")),
    }
