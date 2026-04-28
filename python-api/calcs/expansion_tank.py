"""
Expansion Tank Sizing — Phase 3d (Option B port from TypeScript)
Standards: ASHRAE 2023 HVAC Systems & Equipment Ch.12,
           ASME Section VIII (Pressure Vessels), ASME B31.9
Libraries: iapws (IAPWS-IF97 real water specific volumes), math

Improvement over TypeScript: uses iapws.IAPWS97 for real saturation
properties instead of a 13-point lookup table — eliminates interpolation
error at intermediate temperatures.

Calculates:
- Net thermal expansion volume using IAPWS-IF97 water specific volumes
- Pre-charge pressure from static head (round up to nearest 10 kPa)
- Fill pressure = pre-charge + 15 kPa safety margin
- Acceptance factor α (ASHRAE minimum 0.25, ASME VIII method)
- Required and selected standard bladder/diaphragm tank volume
"""

import math

try:
    from iapws import IAPWS97
    _HAVE_IAPWS = True
except ImportError:
    _HAVE_IAPWS = False

# Standard bladder/diaphragm expansion tank sizes (L) — manufacturer-agnostic
TANK_SIZES = [8, 12, 18, 24, 35, 50, 60, 80, 100, 150,
              200, 300, 400, 500, 750, 1000, 1500, 2000]

# System volume estimate factor by system type (L per kW of installed capacity)
KW_TO_VOL: dict[str, float] = {
    "Chilled Water":     8.0,
    "Heating Hot Water": 10.0,
    "Condenser Water":   6.0,
}

# Fallback specific volume table (ASHRAE/IAPWS, L/kg) used if iapws absent
_FALLBACK_TABLE: list[tuple[float, float]] = [
    (0,  1.00013), (4,  1.00000), (10, 1.00030), (20, 1.00177),
    (30, 1.00435), (40, 1.00786), (50, 1.01207), (60, 1.01705),
    (70, 1.02277), (80, 1.02900), (90, 1.03601), (95, 1.03996),
]


def _spec_vol_lkg(temp_c: float) -> float:
    """
    Water specific volume (L/kg) at given temperature.
    Uses IAPWS-IF97 at P=0.1 MPa (expansion ratio is pressure-independent
    for liquid water in typical HVAC range). Falls back to table if iapws
    is unavailable.
    """
    if _HAVE_IAPWS:
        T_K = max(274.0, min(372.0, temp_c + 273.15))
        try:
            w = IAPWS97(T=T_K, P=0.1)   # P in MPa
            return w.v * 1000.0           # m³/kg → L/kg
        except Exception:
            pass
    # Fallback: linear interpolation
    t = max(0.0, min(95.0, temp_c))
    for i in range(len(_FALLBACK_TABLE) - 1):
        t0, v0 = _FALLBACK_TABLE[i]
        t1, v1 = _FALLBACK_TABLE[i + 1]
        if t0 <= t <= t1:
            return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return _FALLBACK_TABLE[-1][1]


def calculate(inputs: dict) -> dict:
    system_type     = str(inputs.get("system_type",          "Chilled Water"))
    volume_method   = str(inputs.get("volume_method",        "Direct Entry"))
    system_kw       = float(inputs.get("system_kw",          0))
    fill_temp_c     = float(inputs.get("fill_temp_c",        20))
    max_temp_c      = float(inputs.get("max_temp_c",         7))
    static_head_m   = float(inputs.get("static_head_m",      10))
    max_press_kpa_g = float(inputs.get("max_pressure_kpa_g", 400))

    # System volume (L)
    system_volume_l = float(inputs.get("system_volume_L", 0))
    if volume_method == "Estimate from kW" and system_kw > 0:
        system_volume_l = system_kw * KW_TO_VOL.get(system_type, 8.0)

    # Real water specific volumes at both temperatures
    v_fill = _spec_vol_lkg(fill_temp_c)
    v_max  = _spec_vol_lkg(max_temp_c)

    # Thermal expansion uses T_high vs T_low to ensure E_w ≥ 0 regardless of
    # system type (CHW contracts on start; HHW expands; we size for the swing).
    T_high = max(fill_temp_c, max_temp_c)
    T_low  = min(fill_temp_c, max_temp_c)
    v_high = _spec_vol_lkg(T_high)
    v_low  = _spec_vol_lkg(T_low)

    # Net expansion ratio (ASHRAE 2023 HVAC S&E Ch.12 Eq.12-1)
    E_w = (v_high - v_low) / v_low
    V_expansion = system_volume_l * E_w

    # Pre-charge pressure (gauge kPa): static head rounded up to nearest 10 kPa
    precharge_kpa_g     = max(30.0, math.ceil((9.81 * static_head_m) / 10.0) * 10.0)
    fill_pressure_kpa_g = precharge_kpa_g + 15.0  # 15 kPa safety margin

    # Absolute pressures (P_atm = 101.3 kPa)
    P_atm      = 101.3
    P_fill_abs = fill_pressure_kpa_g + P_atm
    P_max_abs  = max_press_kpa_g     + P_atm

    # Acceptance factor α (ASHRAE minimum 0.25; ASME VIII acceptance ratio method)
    alpha       = 1.0 - P_fill_abs / P_max_abs
    alpha_check = ("PASS" if alpha >= 0.25
                   else "FAIL: increase Pmax or reduce fill pressure")

    # Required tank volume: V_tank = V_expansion / α
    required_volume_l = (V_expansion / alpha) if alpha > 0 else 9999.0

    # Select smallest standard tank ≥ required volume
    selected_tank_l = next(
        (s for s in TANK_SIZES if s >= required_volume_l),
        TANK_SIZES[-1]
    )

    pressure_check = ("PASS" if fill_pressure_kpa_g < max_press_kpa_g
                      else "FAIL: fill pressure exceeds max system pressure")

    return {
        "system_type":         system_type,
        "volume_method":       volume_method,
        "system_volume_L":     round(system_volume_l,   2),
        "fill_temp_c":         fill_temp_c,
        "max_temp_c":          max_temp_c,
        "v_fill":              round(v_fill,            5),
        "v_max":               round(v_max,             5),
        "expansion_ratio":     round(E_w,               5),
        "V_expansion_L":       round(V_expansion,       2),
        "static_head_m":       static_head_m,
        "precharge_kpa_g":     precharge_kpa_g,
        "fill_pressure_kpa_g": fill_pressure_kpa_g,
        "max_pressure_kpa_g":  max_press_kpa_g,
        "acceptance_factor":   round(alpha,             3),
        "acceptance_check":    alpha_check,
        "required_volume_L":   round(required_volume_l, 2),
        "selected_tank_L":     selected_tank_l,
        "pressure_check":      pressure_check,
    }
