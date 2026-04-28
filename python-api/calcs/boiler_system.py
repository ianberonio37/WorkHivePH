"""
Boiler System — Mechanical (unifies with Python, was TypeScript-only)
Standards: ASME BPVC Section I/IV, ASME B31.1, PD 8 (Philippines),
           DOLE OSHS Rule 1230, PSME Code
Libraries: iapws (replaces 21-point lookup table for steam properties)

Frontend name: "Boiler System"  ← distinct from "Boiler / Steam System"
Input schema:
  - boiler_type: "Steam" | "Hot Water"
  - Steam branch: steam_pressure_barg, fw_temp_c, fuel_type, efficiency_pct,
                  steam_demand_kg_hr OR heat_load_kw (via load_mode),
                  tds_makeup_ppm, tds_max_ppm, num_boilers, safety_factor
  - Hot Water branch: supply_temp_c, return_temp_c, flow_rate_lhr, fuel_type,
                      efficiency_pct, num_boilers, safety_factor

Improvement over TypeScript:
- iapws.IAPWS97 saturation properties replace 21-point interpolation table
  (accurate to 0.01% vs IAPWS-IF97 standard)
- Hot Water branch: water density from iapws (vs linear regression fit)
"""

try:
    from iapws import IAPWS97
    _HAVE_IAPWS = True
except ImportError:
    _HAVE_IAPWS = False

# Fuel lower heating values (kJ/kg) and liquid densities (kg/L)
FUEL_LHV: dict[str, float] = {
    "LPG":         46100.0,
    "Diesel":      42700.0,
    "Bunker C":    40200.0,
    "Natural Gas": 50000.0,
    "Biomass":     15000.0,
    "Natural gas (LNG)": 50000.0,
}
FUEL_DENSITY: dict[str, float] = {
    "LPG": 0.54, "Diesel": 0.84, "Bunker C": 0.96,
}

# Fallback steam table [P_bara, T_sat_C, hg_kJ_kg, hf_kJ_kg]
_STEAM_TABLE: list[tuple] = [
    (1.0,99.6,2675.0,417.5),(2.0,120.2,2706.3,504.7),(3.0,133.5,2724.9,561.2),
    (5.0,151.8,2748.1,640.1),(7.0,165.0,2763.2,697.2),(10.0,179.9,2777.8,762.6),
    (15.0,198.3,2791.5,844.6),(20.0,212.4,2798.7,908.4),(30.0,233.8,2803.0,1008.3),
    (50.0,263.9,2794.2,1154.2),
]


def _steam_props(p_bara: float) -> tuple[float, float, float]:
    """(T_sat_C, hg_kJ_kg, hf_sat_kJ_kg) via iapws or fallback table."""
    if _HAVE_IAPWS:
        try:
            p_mpa = p_bara / 10.0
            p_mpa = max(0.001, min(20.0, p_mpa))
            sat   = IAPWS97(P=p_mpa, x=1)          # saturated vapour
            liq   = IAPWS97(P=p_mpa, x=0)          # saturated liquid
            return sat.T - 273.15, sat.h, liq.h
        except Exception:
            pass
    # Fallback interpolation
    tbl = _STEAM_TABLE
    if p_bara <= tbl[0][0]:  return tbl[0][1], tbl[0][2], tbl[0][3]
    if p_bara >= tbl[-1][0]: return tbl[-1][1], tbl[-1][2], tbl[-1][3]
    for i in range(len(tbl) - 1):
        p0, t0, hg0, hf0 = tbl[i]
        p1, t1, hg1, hf1 = tbl[i+1]
        if p0 <= p_bara <= p1:
            f = (p_bara - p0) / (p1 - p0)
            return t0+f*(t1-t0), hg0+f*(hg1-hg0), hf0+f*(hf1-hf0)
    return 100.0, 2675.0, 418.0


def _water_density(temp_c: float) -> float:
    """Water density (kg/L) at temperature via iapws; fallback linear fit."""
    if _HAVE_IAPWS:
        try:
            T_K = max(274.0, min(372.0, temp_c + 273.15))
            w   = IAPWS97(T=T_K, P=0.1)
            return w.rho / 1000.0   # kg/m³ → kg/L
        except Exception:
            pass
    return 1.0184 - 0.000619 * temp_c   # linear fit, valid 40–95°C


def calculate(inputs: dict) -> dict:
    boiler_type  = str(inputs.get("boiler_type", "Steam"))
    num_boilers  = max(1, int(inputs.get("num_boilers",   1)))
    fuel_type    = str(inputs.get("fuel_type",    "LPG"))
    eff_pct      = float(inputs.get("efficiency_pct", 82))
    safety_factor = float(inputs.get("safety_factor", 1.25))

    lhv         = FUEL_LHV.get(fuel_type, 42700.0)
    eta         = eff_pct / 100.0
    density_kgl = FUEL_DENSITY.get(fuel_type)

    # ── HOT WATER BRANCH ──────────────────────────────────────────────────────
    if boiler_type == "Hot Water":
        supply_c   = float(inputs.get("supply_temp_c",      80))
        return_c   = float(inputs.get("return_temp_c",      60))
        flow_lhr   = float(inputs.get("flow_rate_lhr",       0))
        sys_press  = float(inputs.get("system_pressure_barg", 3))

        delta_t      = supply_c - return_c
        avg_t        = (supply_c + return_c) / 2.0
        rho          = _water_density(avg_t)
        flow_kgs     = round(flow_lhr * rho / 3600.0, 4)
        q_net_kw     = round(flow_lhr * rho / 3600.0 * 4.187 * delta_t, 1)
        q_net_bhp    = round(q_net_kw / 9.8095, 1)
        q_boiler_kw  = round(q_net_kw * safety_factor, 1)
        q_boiler_bhp = round(q_boiler_kw / 9.8095, 1)
        total_kw     = round(q_boiler_kw  * num_boilers, 1)
        total_bhp    = round(q_boiler_bhp * num_boilers, 1)

        fuel_kg_hr = round(q_boiler_kw / (lhv / 3600.0 * eta), 2) if lhv > 0 and eta > 0 else 0.0
        fuel_l_hr  = round(fuel_kg_hr / density_kgl, 1) if density_kgl else None

        safety_valve_kw = round(q_boiler_kw * 1.1, 1)

        return {
            "boiler_type":             "Hot Water",
            "supply_temp_c":           supply_c,
            "return_temp_c":           return_c,
            "delta_t_c":               delta_t,
            "avg_temp_c":              round(avg_t, 1),
            "water_density_kg_l":      round(rho, 4),
            "flow_rate_kgs":           flow_kgs,
            "q_net_kw":                q_net_kw,
            "q_net_bhp":               q_net_bhp,
            "q_boiler_kw":             q_boiler_kw,
            "q_boiler_bhp":            q_boiler_bhp,
            "total_capacity_kw":       total_kw,
            "total_capacity_bhp":      total_bhp,
            "fuel_lhv_kj_kg":          lhv,
            "fuel_consumption_kg_hr":  fuel_kg_hr,
            "fuel_consumption_lhr":    fuel_l_hr,
            "safety_valve_min_kw":     safety_valve_kw,
            "system_pressure_barg":    sys_press,
        }

    # ── STEAM BRANCH ──────────────────────────────────────────────────────────
    load_mode     = str(inputs.get("load_mode",          "Steam Demand (kg/hr)"))
    steam_demand  = float(inputs.get("steam_demand_kg_hr", 0))
    heat_load_kw  = float(inputs.get("heat_load_kw",      0))
    p_gauge       = float(inputs.get("steam_pressure_barg", 7))
    fw_temp_c     = float(inputs.get("fw_temp_c",         80))
    tds_makeup    = float(inputs.get("tds_makeup_ppm",    200))
    tds_max       = max(tds_makeup + 1, float(inputs.get("tds_max_ppm", 3000)))

    p_bara        = p_gauge + 1.01325
    t_sat, hg, hf_sat = _steam_props(p_bara)
    hf_fw         = 4.187 * fw_temp_c          # feedwater enthalpy (kJ/kg)
    delta_h       = round(hg - hf_fw, 1)        # latent + sensible, kJ/kg

    if "Heat Load" in load_mode:
        steam_demand_kg_hr = round(heat_load_kw * 3600.0 / delta_h, 1) if delta_h > 0 else 0.0
    else:
        steam_demand_kg_hr = steam_demand

    design_kg_hr  = round(steam_demand_kg_hr * safety_factor, 1)
    q_boiler_kw   = round(design_kg_hr * delta_h / 3600.0, 1) if delta_h > 0 else 0.0
    q_boiler_bhp  = round(q_boiler_kw / 9.8095, 1)
    total_kw      = round(q_boiler_kw  * num_boilers, 1)
    total_bhp     = round(q_boiler_bhp * num_boilers, 1)

    fuel_kg_hr = round(q_boiler_kw / (lhv / 3600.0 * eta), 2) if lhv > 0 and eta > 0 else 0.0
    fuel_l_hr  = round(fuel_kg_hr / density_kgl, 1) if density_kgl else None

    blowdown_pct    = round(tds_makeup / (tds_max - tds_makeup) * 100.0, 1) if tds_max > tds_makeup else 0.0
    blowdown_kg_hr  = round(design_kg_hr * blowdown_pct / 100.0, 1)
    makeup_water_kg = round(design_kg_hr + blowdown_kg_hr, 1)
    sv_min_kg_hr    = round(design_kg_hr * 1.1, 1)

    return {
        "boiler_type":                  boiler_type,
        "steam_pressure_bara":          round(p_bara, 3),
        "t_sat_c":                      round(t_sat, 1),
        "hg_kj_kg":                     round(hg, 1),
        "hf_fw_kj_kg":                  round(hf_fw, 1),
        "delta_h_kj_kg":                delta_h,
        "steam_demand_kg_hr":           steam_demand_kg_hr,
        "design_steam_demand_kg_hr":    design_kg_hr,
        "q_boiler_kw":                  q_boiler_kw,
        "q_boiler_bhp":                 q_boiler_bhp,
        "total_capacity_kw":            total_kw,
        "total_capacity_bhp":           total_bhp,
        "fuel_lhv_kj_kg":               lhv,
        "fuel_consumption_kg_hr":       fuel_kg_hr,
        "fuel_consumption_lhr":         fuel_l_hr,
        "blowdown_pct":                 blowdown_pct,
        "blowdown_kg_hr":               blowdown_kg_hr,
        "makeup_water_kg_hr":           makeup_water_kg,
        "safety_valve_min_kg_hr":       sv_min_kg_hr,
    }
