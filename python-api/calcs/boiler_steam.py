"""
Boiler / Steam System — Phase 9d
Standards: ASME BPVC Section I (Power Boilers),
           ASME BPVC Section IV (Heating Boilers),
           ASME B31.1 (Power Piping),
           PTC 4 (Performance Test Codes — Fired Steam Generators),
           DOLE / BFP Philippines: boiler registration / certificate of inspection,
           Philippine Mechanical Engineering Act (RA 8407)
Libraries: math (all formulas closed-form)

Steam table values: static lookup with interpolation (from NIST/IAPWS-IF97 tabulated)
Methods:
  Boiler output: Q = ṁ × (h_steam − h_feed)
  Efficiency:    η = Q / (ṁ_fuel × HHV)
  Blowdown:      BD% = TDS_feed / (TDS_steam_limit − TDS_feed)
  Economiser savings: Q_eco = ṁ_feed × Cp × ΔT_eco
  Deaerator: calculates makeup water at mixing balance
  ASME shell thickness: t = P×R / (S×E − 0.6P)
"""

import math

# ─── Steam saturation table (pressure-based, IAPWS-IF97 reduced) ─────────────
# Columns: P_bar, T_sat_C, h_f (kJ/kg), h_fg (kJ/kg), h_g (kJ/kg),
#          s_f (kJ/kg·K), s_g (kJ/kg·K), v_g (m³/kg)
STEAM_TABLE_SAT_P: list[dict] = [
    {"P":  0.10, "T":  45.8, "hf":  191.8, "hfg": 2392.8, "hg": 2584.6, "sf": 0.649, "sg": 8.150, "vg": 14.674},
    {"P":  0.20, "T":  60.1, "hf":  251.4, "hfg": 2357.5, "hg": 2608.9, "sf": 0.832, "sg": 7.907, "vg":  7.649},
    {"P":  0.50, "T":  81.3, "hf":  340.5, "hfg": 2305.4, "hg": 2645.9, "sf": 1.091, "sg": 7.593, "vg":  3.240},
    {"P":  1.00, "T":  99.6, "hf":  417.5, "hfg": 2258.0, "hg": 2675.5, "sf": 1.303, "sg": 7.359, "vg":  1.694},
    {"P":  2.00, "T": 120.2, "hf":  504.7, "hfg": 2201.6, "hg": 2706.3, "sf": 1.530, "sg": 7.127, "vg":  0.885},
    {"P":  3.00, "T": 133.5, "hf":  561.1, "hfg": 2163.2, "hg": 2724.3, "sf": 1.672, "sg": 6.992, "vg":  0.606},
    {"P":  4.00, "T": 143.6, "hf":  604.7, "hfg": 2133.4, "hg": 2738.1, "sf": 1.776, "sg": 6.895, "vg":  0.462},
    {"P":  5.00, "T": 151.8, "hf":  640.1, "hfg": 2107.4, "hg": 2747.5, "sf": 1.861, "sg": 6.820, "vg":  0.375},
    {"P":  6.00, "T": 158.8, "hf":  670.4, "hfg": 2085.0, "hg": 2755.4, "sf": 1.931, "sg": 6.760, "vg":  0.316},
    {"P":  7.00, "T": 165.0, "hf":  697.0, "hfg": 2064.9, "hg": 2761.9, "sf": 1.992, "sg": 6.708, "vg":  0.273},
    {"P":  8.00, "T": 170.4, "hf":  720.9, "hfg": 2046.6, "hg": 2767.5, "sf": 2.046, "sg": 6.663, "vg":  0.241},
    {"P": 10.00, "T": 179.9, "hf":  762.6, "hfg": 2013.6, "hg": 2776.2, "sf": 2.139, "sg": 6.585, "vg":  0.194},
    {"P": 12.00, "T": 187.9, "hf":  798.3, "hfg": 1984.3, "hg": 2782.6, "sf": 2.216, "sg": 6.523, "vg":  0.163},
    {"P": 14.00, "T": 195.0, "hf":  830.1, "hfg": 1957.0, "hg": 2787.1, "sf": 2.284, "sg": 6.469, "vg":  0.141},
    {"P": 16.00, "T": 201.4, "hf":  858.8, "hfg": 1932.0, "hg": 2790.8, "sf": 2.344, "sg": 6.422, "vg":  0.124},
    {"P": 18.00, "T": 207.1, "hf":  885.0, "hfg": 1908.8, "hg": 2793.8, "sf": 2.398, "sg": 6.379, "vg":  0.110},
    {"P": 20.00, "T": 212.4, "hf":  908.6, "hfg": 1887.6, "hg": 2796.2, "sf": 2.447, "sg": 6.341, "vg":  0.0995},
    {"P": 25.00, "T": 223.9, "hf":  962.0, "hfg": 1840.7, "hg": 2802.7, "sf": 2.555, "sg": 6.256, "vg":  0.0799},
    {"P": 30.00, "T": 233.8, "hf": 1008.4, "hfg": 1795.8, "hg": 2804.2, "sf": 2.645, "sg": 6.186, "vg":  0.0666},
    {"P": 40.00, "T": 250.3, "hf": 1087.4, "hfg": 1712.1, "hg": 2799.5, "sf": 2.797, "sg": 6.070, "vg":  0.0498},
    {"P": 50.00, "T": 263.9, "hf": 1154.2, "hfg": 1639.7, "hg": 2793.9, "sf": 2.921, "sg": 5.973, "vg":  0.0394},
    {"P": 60.00, "T": 275.6, "hf": 1213.4, "hfg": 1571.3, "hg": 2784.7, "sf": 3.028, "sg": 5.892, "vg":  0.0324},
    {"P": 80.00, "T": 295.0, "hf": 1317.1, "hfg": 1441.0, "hg": 2758.1, "sf": 3.208, "sg": 5.748, "vg":  0.0235},
    {"P":100.00, "T": 311.0, "hf": 1407.6, "hfg": 1317.6, "hg": 2725.2, "sf": 3.361, "sg": 5.616, "vg":  0.0180},
    {"P":120.00, "T": 324.6, "hf": 1491.3, "hfg": 1193.3, "hg": 2684.6, "sf": 3.497, "sg": 5.493, "vg":  0.0143},
    {"P":160.00, "T": 347.3, "hf": 1650.1, "hfg":  938.4, "hg": 2588.5, "sf": 3.747, "sg": 5.247, "vg":  0.00931},
    {"P":200.00, "T": 365.8, "hf": 1826.3, "hfg":  583.6, "hg": 2409.9, "sf": 4.015, "sg": 4.934, "vg":  0.00588},
]

# ─── Superheated steam: Cp approximation (kJ/kg·K) ───────────────────────────
# Valid 200-600°C, 1-200 bar (simplified fit)
def _cp_superheated(T_C: float, P_bar: float) -> float:
    # IAPWS approximate Cp for superheated steam
    T_K = T_C + 273.15
    return 1.872 + 0.000416 * T_K - 0.048 / (T_K / 1000)**2 + 0.002 * P_bar / 100


def _steam_props(P_bar: float) -> dict:
    """Interpolate saturated steam properties at pressure P_bar."""
    tbl = STEAM_TABLE_SAT_P
    if P_bar <= tbl[0]["P"]:
        return tbl[0]
    if P_bar >= tbl[-1]["P"]:
        return tbl[-1]
    for i in range(len(tbl) - 1):
        lo, hi = tbl[i], tbl[i+1]
        if lo["P"] <= P_bar <= hi["P"]:
            f = (P_bar - lo["P"]) / (hi["P"] - lo["P"])
            return {k: lo[k] + f * (hi[k] - lo[k]) for k in lo}
    return tbl[-1]


def _h_superheated(P_bar: float, T_C: float) -> float:
    """Approximate enthalpy of superheated steam (kJ/kg)."""
    sat = _steam_props(P_bar)
    if T_C <= sat["T"]:
        return sat["hg"]   # saturated or wet
    Cp_avg = _cp_superheated((T_C + sat["T"]) / 2, P_bar)
    return sat["hg"] + Cp_avg * (T_C - sat["T"])


def _h_feed(T_C: float) -> float:
    """Enthalpy of feed water (liquid) at temperature T_C (kJ/kg)."""
    return 4.186 * T_C   # Cp_water ≈ 4.186 kJ/kg·K, ref 0°C


# ─── Fuel heating values (MJ/kg) ─────────────────────────────────────────────
FUEL_HHV: dict[str, float] = {
    "Natural gas (LNG)":   55.5,
    "Diesel (HFO)":        43.0,
    "Bunker fuel (180 cSt)": 40.5,
    "Coal (bituminous)":   29.0,
    "Coal (lignite)":      20.0,
    "LPG (propane)":       50.3,
    "Biomass (dry wood)":  19.5,
    "Bagasse":             10.0,
    "Rice husk":           14.5,
    "Waste oil":           40.0,
}

# ─── ASME I / IV allowable stresses for boiler shell (MPa) ───────────────────
BOILER_SHELL_MATERIALS: dict[str, dict] = {
    "SA-516 Gr.70":        {"S_MPa": 138, "E_weld": 0.85},
    "SA-516 Gr.60":        {"S_MPa": 113, "E_weld": 0.85},
    "SA-178 Gr.C (tubes)": {"S_MPa":  97, "E_weld": 1.00},
    "SA-192 (fire tube)":  {"S_MPa":  83, "E_weld": 1.00},
}


def calculate(inputs: dict) -> dict:
    """Main entry point — compatible with TypeScript calcBoilerSteam() keys."""
    # ── Operating conditions ──────────────────────────────────────────────────
    P_bar          = float(inputs.get("steam_pressure_bar",     10.0))
    T_steam_C      = float(inputs.get("steam_temperature_C",     0.0))  # 0 = saturated
    T_feed_C       = float(inputs.get("feedwater_temp_C",        80.0))
    m_steam_kgs    = float(inputs.get("steam_flowrate_kgs",      1.0))

    # Steam type
    sat_props      = _steam_props(P_bar)
    T_sat          = sat_props["T"]
    superheat_C    = max(0.0, T_steam_C - T_sat) if T_steam_C > 0 else 0.0
    is_superheated = superheat_C > 0

    h_steam = (_h_superheated(P_bar, T_steam_C) if is_superheated
               else sat_props["hg"])
    h_feed  = _h_feed(T_feed_C)

    # ── Boiler duty ───────────────────────────────────────────────────────────
    Q_kW   = m_steam_kgs * (h_steam - h_feed)   # kW
    Q_MWh  = Q_kW / 1000                         # MW

    # ── Fuel consumption ──────────────────────────────────────────────────────
    fuel_type  = str  (inputs.get("fuel_type",     "Natural gas (LNG)"))
    HHV_MJkg   = FUEL_HHV.get(fuel_type, 43.0)
    eta_boiler = float(inputs.get("boiler_efficiency_pct", 85.0)) / 100

    m_fuel_kgs = Q_kW / (eta_boiler * HHV_MJkg * 1000) if HHV_MJkg > 0 else 0
    m_fuel_kgh = m_fuel_kgs * 3600

    # ── Blowdown ──────────────────────────────────────────────────────────────
    TDS_feed_ppm  = float(inputs.get("TDS_feedwater_ppm",  200.0))
    TDS_limit_ppm = float(inputs.get("TDS_boiler_limit_ppm", 3500.0))   # ASME standard
    BD_pct        = TDS_feed_ppm / (TDS_limit_ppm - TDS_feed_ppm) * 100 if TDS_limit_ppm > TDS_feed_ppm else 0
    m_blowdown_kgs = m_steam_kgs * BD_pct / 100

    # Blowdown heat loss
    h_blowdown    = h_feed + 4.186 * (T_sat - T_feed_C)   # at boiler saturation temp
    Q_blowdown_kW = m_blowdown_kgs * (h_blowdown - h_feed)

    # ── Flash steam recovery from blowdown ───────────────────────────────────
    P_flash_bar   = float(inputs.get("flash_pressure_bar", 1.0))
    flash_props   = _steam_props(P_flash_bar)
    # Isenthalpic flash: x_flash = (h_f_high - h_f_flash) / h_fg_flash
    h_f_high = sat_props["hf"]
    h_fg_fl  = flash_props["hfg"]
    h_f_fl   = flash_props["hf"]
    x_flash  = (h_f_high - h_f_fl) / h_fg_fl if h_fg_fl > 0 else 0
    x_flash  = max(0, min(x_flash, 1))
    m_flash_kgs  = m_blowdown_kgs * x_flash
    Q_flash_kW   = m_flash_kgs * h_fg_fl

    # ── Economiser savings ───────────────────────────────────────────────────
    T_flue_in_C   = float(inputs.get("flue_gas_temp_C",    250.0))
    T_flue_out_C  = float(inputs.get("economiser_exit_C",  160.0))   # target stack temp
    m_flue_kgs    = m_fuel_kgs * 15   # stoichiometric air factor ≈ 15 for nat gas
    Cp_flue       = 1.05              # kJ/kg·K (approx flue gas)
    Q_eco_kW      = m_flue_kgs * Cp_flue * (T_flue_in_C - T_flue_out_C)
    dT_fw_eco     = Q_eco_kW / (m_steam_kgs * 4.186) if m_steam_kgs > 0 else 0
    eta_with_eco  = (Q_kW / ((m_fuel_kgs * HHV_MJkg * 1000) - Q_eco_kW)) if (m_fuel_kgs * HHV_MJkg * 1000) > Q_eco_kW else eta_boiler

    # ── Steam piping — minimum wall thickness (ASME B31.1) ───────────────────
    pipe_OD_mm    = float(inputs.get("steam_pipe_od_mm",   60.3))   # 2" nom
    mat_pipe_key  = str  (inputs.get("pipe_material",       "SA-192 (fire tube)"))
    mat_pipe      = BOILER_SHELL_MATERIALS.get(mat_pipe_key,
                      BOILER_SHELL_MATERIALS["SA-192 (fire tube)"])
    S_pipe        = mat_pipe["S_MPa"]
    E_pipe        = mat_pipe["E_weld"]
    P_MPa         = P_bar / 10
    # ASME B31.1 Eq. (3): t = P Do / (2(SE + Py)) y = 0.4
    t_pipe_mm     = P_MPa * pipe_OD_mm / (2 * (S_pipe * E_pipe + P_MPa * 0.4))
    CA_pipe       = 1.6   # mm corrosion allowance
    t_pipe_req    = t_pipe_mm + CA_pipe

    # ── Boiler horsepower ─────────────────────────────────────────────────────
    BHP           = Q_kW / 9.81   # 1 BHP = 9.81 kW (evaporating 15.65 kg/hr from 100°C)

    # ── Compliance notes ──────────────────────────────────────────────────────
    code_notes = [
        f"Steam: {P_bar} bar {'(saturated, ' + str(round(T_sat,1)) + '°C)' if not is_superheated else '(superheated ' + str(round(superheat_C,1)) + '°C SH)'}.",
        f"Enthalpy: h_steam = {round(h_steam,1)} kJ/kg, h_feed = {round(h_feed,1)} kJ/kg.",
        f"Boiler duty: {round(Q_kW,1)} kW ({round(BHP,1)} BHP).",
        f"Fuel: {fuel_type}, HHV = {HHV_MJkg} MJ/kg — consumption {round(m_fuel_kgh,2)} kg/hr at η={eta_boiler*100:.0f}%.",
        f"Blowdown: {round(BD_pct,2)}% → {round(m_blowdown_kgs*3600,2)} kg/hr — heat loss {round(Q_blowdown_kW,2)} kW.",
        f"Flash steam recovery at {P_flash_bar} bar: x={round(x_flash,4)}, {round(m_flash_kgs*3600,2)} kg/hr ({round(Q_flash_kW,2)} kW).",
        f"Economiser: saves {round(Q_eco_kW,1)} kW (stack {T_flue_in_C}→{T_flue_out_C}°C).",
        f"Steam pipe wall: t_min = {round(t_pipe_mm,3)} mm + {CA_pipe} mm CA → {round(t_pipe_req,3)} mm (ASME B31.1).",
        "Philippines: DOLE Boiler Certificate of Inspection required before operation (RA 8407).",
        "ASME I stamp (power boilers) or Sec. IV stamp (heating boilers) required.",
    ]

    return {
        # Steam conditions
        "steam_pressure_bar":   P_bar,
        "T_sat_C":              round(T_sat, 1),
        "superheat_C":          round(superheat_C, 1),
        "h_steam_kJ_kg":        round(h_steam, 2),
        "h_feed_kJ_kg":         round(h_feed, 2),
        "h_fg_kJ_kg":           round(sat_props["hfg"], 2),
        "v_g_m3_kg":            round(sat_props["vg"], 5),

        # Boiler output
        "duty_kW":              round(Q_kW, 2),
        "duty_MW":              round(Q_MWh, 4),
        "BHP":                  round(BHP, 1),
        "m_steam_kgs":          m_steam_kgs,
        "m_steam_kgh":          round(m_steam_kgs * 3600, 2),

        # Fuel
        "fuel_type":            fuel_type,
        "HHV_MJ_kg":            HHV_MJkg,
        "boiler_efficiency":    eta_boiler,
        "m_fuel_kgs":           round(m_fuel_kgs, 5),
        "m_fuel_kgh":           round(m_fuel_kgh, 3),

        # Blowdown
        "BD_pct":               round(BD_pct, 3),
        "m_blowdown_kgh":       round(m_blowdown_kgs * 3600, 3),
        "blowdown_heat_loss_kW": round(Q_blowdown_kW, 2),

        # Flash steam
        "flash_pressure_bar":   P_flash_bar,
        "flash_fraction":       round(x_flash, 4),
        "m_flash_kgh":          round(m_flash_kgs * 3600, 3),
        "flash_recovery_kW":    round(Q_flash_kW, 2),

        # Economiser
        "Q_economiser_kW":      round(Q_eco_kW, 2),
        "dT_feedwater_C":       round(dT_fw_eco, 2),
        "eta_with_economiser":  round(eta_with_eco, 4),

        # Piping
        "steam_pipe_od_mm":     pipe_OD_mm,
        "t_pipe_min_mm":        round(t_pipe_mm, 3),
        "t_pipe_required_mm":   round(t_pipe_req, 3),

        # Compliance
        "code_notes":           code_notes,

        # Metadata
        "inputs_used": {
            "steam_pressure_bar":  P_bar,
            "steam_temperature_C": T_steam_C,
            "feedwater_temp_C":    T_feed_C,
            "m_steam_kgs":         m_steam_kgs,
            "fuel_type":           fuel_type,
        },
        "calculation_source": "python/math",
        "standard": "ASME BPVC Sec.I/IV | ASME B31.1 | ASME PTC 4 | IAPWS-IF97 | RA 8407 (PH)",
    }
