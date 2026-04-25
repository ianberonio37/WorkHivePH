"""
Chiller System — Phase 3c (Water-Cooled and Air-Cooled)
Standards: ASHRAE 90.1-2019 Table 6.8.1 (minimum efficiency), AHRI 550/590
           (performance rating), ASHRAE 2021 Fundamentals Ch.2, PSME Code
Libraries: math (all formulas closed-form from thermodynamic first principles)

Calculates:
- Cooling capacity (kW, TR) and compressor input power
- COP (Coefficient of Performance) and EER (Energy Efficiency Ratio)
- IPLV (Integrated Part-Load Value) — ASHRAE 90.1 weighted at 100/75/50/25%
- Evaporator chilled water flow rate (L/s) and delta-T
- Condenser heat rejection and flow rate (water-cooled) or airflow (air-cooled)
- Approach temperatures (evaporator and condenser)
- ASHRAE 90.1 minimum efficiency compliance (kW/TR limit by capacity tier)
- Heat balance verification (Q_condenser = Q_evap + W_compressor)
"""

import math

# ─── ASHRAE 90.1-2019 Table 6.8.1 — Chiller minimum efficiency ───────────────
# Format: (capacity_limit_kW, min_COP_full_load, min_IPLV)
# Water-Cooled (centrifugal / screw)
ASHRAE_90_1_WATER: list[dict] = [
    {"max_kW":  527, "min_COP": 5.50, "min_IPLV": 6.29,  "type": "< 150 TR centrifugal"},
    {"max_kW": 1055, "min_COP": 5.55, "min_IPLV": 6.29,  "type": "150–299 TR centrifugal"},
    {"max_kW": 9999, "min_COP": 5.90, "min_IPLV": 6.63,  "type": ">= 300 TR centrifugal"},
]
# Air-Cooled (scroll / screw)
ASHRAE_90_1_AIR: list[dict] = [
    {"max_kW":  70,  "min_COP": 2.80, "min_IPLV": 3.05,  "type": "< 20 TR air-cooled"},
    {"max_kW": 223,  "min_COP": 2.90, "min_IPLV": 3.20,  "type": "20–63 TR air-cooled"},
    {"max_kW": 9999, "min_COP": 3.00, "min_IPLV": 3.35,  "type": ">= 63 TR air-cooled"},
]

# ─── IPLV weighting factors — AHRI 550/590 ────────────────────────────────────
# IPLV = 0.01·A + 0.42·B + 0.45·C + 0.12·D
# A=100%, B=75%, C=50%, D=25% load
IPLV_WEIGHTS = {"A": 0.01, "B": 0.42, "C": 0.45, "D": 0.12}
IPLV_LOADS   = {"A": 1.00, "B": 0.75, "C": 0.50, "D": 0.25}

# ─── Refrigerant properties for COP estimation (R-134a / R-410A) ─────────────
# For Carnot approximation we only need operating temperatures
# Real COP derating from Carnot (typical chiller compressor isentropic efficiency)
COMP_ISENTROPIC_EFF = 0.78   # typical centrifugal / screw at full load
MECHANICAL_LOSSES   = 0.95   # bearing, seal losses
MOTOR_EFF           = 0.95   # compressor motor

# ─── Heat transfer approach temperatures (LMTD approximations) ───────────────
# These represent typical design values for chiller heat exchangers
EVAP_APPROACH_STD   = 2.0    # K — chilled water approach to evap refrigerant temp
COND_APPROACH_WATER = 2.0    # K — condenser water approach to cond refrigerant temp
COND_APPROACH_AIR   = 8.0    # K — air-cooled condenser is less effective

# ─── Standard chiller capacities (kW) ────────────────────────────────────────
STD_CHILLER_KW = [
    35, 53, 70, 88, 105, 140, 175, 211, 246, 281, 316, 352,
    422, 527, 633, 703, 844, 1055, 1266, 1407, 1758, 2110,
]

# ─── Water properties ─────────────────────────────────────────────────────────
RHO_WATER = 999.0   # kg/m³ at ~10°C
CP_WATER  = 4186.0  # J/(kg·K)


def _cop_carnot(t_evap_c: float, t_cond_c: float) -> float:
    """Theoretical Carnot COP of refrigeration cycle."""
    T_evap = t_evap_c + 273.15
    T_cond = t_cond_c + 273.15
    if T_cond <= T_evap:
        return 99.0
    return T_evap / (T_cond - T_evap)


def _cop_real(cop_carnot: float) -> float:
    """
    Real COP from Carnot, applying compressor isentropic efficiency and losses.
    COP_real = COP_carnot × η_isen × η_mech × η_motor
    """
    return cop_carnot * COMP_ISENTROPIC_EFF * MECHANICAL_LOSSES * MOTOR_EFF


def _part_load_cop(cop_full: float, load_frac: float, chiller_type: str) -> float:
    """
    Part-load COP using ARI 550/590 degradation curve.
    At 50% load, centrifugal chillers typically reach peak efficiency (~10% better).
    At 25% load, efficiency drops back toward full-load.
    PLV curve: COP_pl = COP_full × PLF
    PLF ≈ 1 + 0.2×(1-load) for centrifugal (peaks ~50%); linear for screw/scroll.
    """
    if "Water" in chiller_type:
        # Centrifugal — peaks at ~50% load
        if load_frac >= 0.50:
            plf = 1.0 + 0.12 * (1.0 - load_frac)
        else:
            plf = 1.12 - 0.24 * (0.50 - load_frac)
    else:
        # Air-cooled scroll/screw — more linear, slight improvement at part load
        plf = 1.0 + 0.08 * (1.0 - load_frac)
    return cop_full * max(plf, 0.5)


def _iplv(cop_full: float, chiller_type: str) -> float:
    """
    IPLV = 1 / (0.01/COP_A + 0.42/COP_B + 0.45/COP_C + 0.12/COP_D)
    AHRI 550/590 harmonic mean of part-load COPs.
    """
    cop_pts = {}
    for key, frac in IPLV_LOADS.items():
        cop_pts[key] = _part_load_cop(cop_full, frac, chiller_type)

    denom = sum(IPLV_WEIGHTS[k] / max(cop_pts[k], 0.01) for k in IPLV_WEIGHTS)
    return 1.0 / denom if denom > 0 else 0.0


def _ashrae_limits(capacity_kw: float, chiller_type: str) -> dict:
    """Return ASHRAE 90.1 minimum COP and IPLV for this capacity tier."""
    table = ASHRAE_90_1_WATER if "Water" in chiller_type else ASHRAE_90_1_AIR
    for row in table:
        if capacity_kw <= row["max_kW"]:
            return row
    return table[-1]


def calculate(inputs: dict) -> dict:
    """
    Main entry point — compatible with TypeScript calcChillerSystem() keys.
    Handles both 'Chiller System — Water Cooled' and 'Chiller System — Air Cooled'.
    """
    # ── Inputs ────────────────────────────────────────────────────────────────
    cooling_kw    = float(inputs.get("cooling_kw",         0)
                      or  inputs.get("capacity_kw",         0)
                      or  inputs.get("kW",                  0))
    cooling_tr    = float(inputs.get("cooling_tr",          0)
                      or  inputs.get("TR",                  0))

    if cooling_kw <= 0 and cooling_tr > 0:
        cooling_kw = cooling_tr * 3.517
    if cooling_kw <= 0:
        cooling_kw = 100.0   # default

    cooling_tr = cooling_kw / 3.517

    chiller_type  = str(inputs.get("chiller_type",   "Water Cooled"))
    is_water      = "Water" in chiller_type or "water" in chiller_type

    # Chilled water (evaporator) — standard 6°C CHW delta-T
    chw_supply_c  = float(inputs.get("chw_supply_c",    7.0))
    chw_return_c  = float(inputs.get("chw_return_c",   13.0))
    chw_delta_t   = chw_return_c - chw_supply_c

    # Condenser side
    if is_water:
        cw_supply_c  = float(inputs.get("cw_supply_c",  29.5))  # tower supply
        cw_return_c  = float(inputs.get("cw_return_c",  35.0))  # to tower
        cw_delta_t   = cw_return_c - cw_supply_c
        outdoor_db_c = float(inputs.get("outdoor_temp",  35.0))
    else:
        outdoor_db_c = float(inputs.get("outdoor_temp",  35.0))
        cw_supply_c  = outdoor_db_c   # air-cooled: ambient dry-bulb
        cw_return_c  = outdoor_db_c + 10.0   # rough hot-air leaving temp
        cw_delta_t   = 10.0

    design_margin = float(inputs.get("design_margin_pct", 10.0))

    # ── Refrigerant operating temperatures (from approach temps) ──────────────
    # Evap refrigerant temp = CHW supply - approach
    t_evap_ref = chw_supply_c - EVAP_APPROACH_STD

    # Cond refrigerant temp = condenser entering medium + approach
    cond_approach = COND_APPROACH_WATER if is_water else COND_APPROACH_AIR
    t_cond_ref    = (cw_supply_c if is_water else outdoor_db_c) + cond_approach

    # ── COP calculation ───────────────────────────────────────────────────────
    cop_carnot = _cop_carnot(t_evap_ref, t_cond_ref)
    cop_full   = _cop_real(cop_carnot)

    # Compressor power
    comp_kw     = cooling_kw / cop_full
    eer         = cop_full * 3.412   # COP → EER (BTU/h per W)
    kw_per_tr   = comp_kw / cooling_tr   # efficiency metric used in Philippines

    # Design with margin
    cooling_kw_design = cooling_kw * (1 + design_margin / 100)
    cooling_tr_design = cooling_kw_design / 3.517

    # ── IPLV ─────────────────────────────────────────────────────────────────
    iplv = _iplv(cop_full, chiller_type)

    # ── ASHRAE 90.1 compliance ────────────────────────────────────────────────
    limits      = _ashrae_limits(cooling_kw, chiller_type)
    cop_ok      = cop_full >= limits["min_COP"]
    iplv_ok     = iplv    >= limits["min_IPLV"]
    compliant   = cop_ok and iplv_ok

    # ── Standard chiller size selection ───────────────────────────────────────
    rec_kw = next((s for s in STD_CHILLER_KW if s >= cooling_kw_design),
                  STD_CHILLER_KW[-1])
    rec_tr = round(rec_kw / 3.517, 1)

    # ── Chilled water (evaporator) flow ───────────────────────────────────────
    chw_flow_kgs = cooling_kw * 1000 / (CP_WATER * max(chw_delta_t, 1))
    chw_flow_lps = chw_flow_kgs / RHO_WATER
    chw_flow_m3hr = chw_flow_lps * 3.6

    # ── Condenser heat rejection ──────────────────────────────────────────────
    q_rejection_kw   = cooling_kw + comp_kw   # heat balance
    q_rejection_tr   = q_rejection_kw / 3.517

    if is_water:
        cw_flow_kgs  = q_rejection_kw * 1000 / (CP_WATER * max(cw_delta_t, 1))
        cw_flow_lps  = cw_flow_kgs / RHO_WATER
        cw_flow_m3hr = cw_flow_lps * 3.6
        cw_flow_gpm  = cw_flow_lps * 15.8508
    else:
        # Air-cooled: airflow estimate — ~450 m³/h per kW rejection (typical)
        cw_flow_lps  = 0.0
        cw_flow_m3hr = q_rejection_kw * 450
        cw_flow_gpm  = 0.0

    # ── Part-load performance table ───────────────────────────────────────────
    part_load_table = []
    for key, frac in IPLV_LOADS.items():
        cop_pl = _part_load_cop(cop_full, frac, chiller_type)
        kw_pl  = (cooling_kw * frac) / cop_pl
        part_load_table.append({
            "load_pct":   int(frac * 100),
            "cooling_kW": round(cooling_kw * frac, 1),
            "comp_kW":    round(kw_pl, 2),
            "COP":        round(cop_pl, 3),
            "EER":        round(cop_pl * 3.412, 2),
        })

    return {
        # Capacity
        "cooling_kW":           round(cooling_kw, 2),
        "cooling_TR":           round(cooling_tr, 2),
        "cooling_kW_design":    round(cooling_kw_design, 2),
        "cooling_TR_design":    round(cooling_tr_design, 2),
        "recommended_kW":       rec_kw,
        "recommended_TR":       rec_tr,

        # Efficiency
        "COP_full_load":        round(cop_full, 3),
        "COP_carnot":           round(cop_carnot, 3),
        "EER":                  round(eer, 2),
        "kW_per_TR":            round(kw_per_tr, 3),
        "IPLV":                 round(iplv, 3),

        # Compressor
        "compressor_kW":        round(comp_kw, 2),

        # Thermodynamic state
        "t_evap_ref_c":         round(t_evap_ref, 1),
        "t_cond_ref_c":         round(t_cond_ref, 1),
        "evap_approach_K":      EVAP_APPROACH_STD,
        "cond_approach_K":      cond_approach,

        # Chilled water
        "chw_supply_c":         chw_supply_c,
        "chw_return_c":         chw_return_c,
        "chw_delta_T_c":        chw_delta_t,
        "chw_flow_lps":         round(chw_flow_lps, 3),
        "chw_flow_m3hr":        round(chw_flow_m3hr, 2),

        # Condenser
        "q_rejection_kW":       round(q_rejection_kw, 2),
        "q_rejection_TR":       round(q_rejection_tr, 2),
        "cw_supply_c":          cw_supply_c,
        "cw_return_c":          round(cw_return_c, 1),
        "cw_delta_T_c":         cw_delta_t,
        "cw_flow_lps":          round(cw_flow_lps, 3),
        "cw_flow_m3hr":         round(cw_flow_m3hr, 1),
        "cw_flow_gpm":          round(cw_flow_gpm, 1),

        # ASHRAE 90.1 compliance
        "ashrae_min_COP":       limits["min_COP"],
        "ashrae_min_IPLV":      limits["min_IPLV"],
        "ashrae_tier":          limits["type"],
        "cop_compliant":        cop_ok,
        "iplv_compliant":       iplv_ok,
        "ashrae_90_1_compliant": compliant,

        # Part-load table
        "part_load_performance": part_load_table,

        # Metadata
        "inputs_used": {
            "chiller_type":      chiller_type,
            "chw_supply_c":      chw_supply_c,
            "chw_delta_T_c":     chw_delta_t,
            "outdoor_db_c":      outdoor_db_c,
            "design_margin_pct": design_margin,
        },
        "calculation_source": "python/math",
        "standard": "ASHRAE 90.1-2019 Table 6.8.1 | AHRI 550/590 | ASHRAE 2021 Ch.2",
    }
