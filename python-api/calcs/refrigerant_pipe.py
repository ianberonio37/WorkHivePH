"""
Refrigerant Pipe Sizing - Phase 3a
Standards: ASHRAE 2022 Refrigeration Handbook Ch.1, ASTM B280 (ACR copper),
           ASHRAE 90.1 (insulation), PSME Code
Libraries: math (no external dep - property tables are static ASHRAE data)

Method: ASHRAE velocity method
  1.  ṁ = Q_kW / RE,  RE = h(suction, +10 K superheat) − h(liquid at T_cond)   (the refrigerating effect, kg/s)
  2.  Q_v = ṁ / ρ_phase                            (volume flow per phase, m³/s)
  3.  Select smallest ASTM B280 ACR tube where v is within limits
  4.  Verify Darcy-Weisbach pressure drop → convert to ΔT_eq

NOTE: CoolProp is not a runtime dependency (~200 MB). The static tables below were GENERATED with CoolProp 8.0.0
      on 2026-11-02 (tools: the generator is described above REFRIG_PROPS) - see the ★ note there for what they replaced.
"""

import math

# ─── ASTM B280 ACR copper tube outside diameters (mm) ────────────────────────
# Dehydrated and capped - NOT plumbing-grade Type L/K
ACR_OD_MM = [6.35, 9.52, 12.70, 15.88, 19.05, 22.22, 28.58,
             34.93, 41.28, 53.98, 66.68, 79.38]

# Wall thickness (mm) and resulting ID (mm) - ASTM B280 standard
ACR_WALL_MM = {
    6.35:  0.762,
    9.52:  0.889,
    12.70: 0.889,
    15.88: 1.016,
    19.05: 1.143,
    22.22: 1.270,
    28.58: 1.270,
    34.93: 1.397,
    41.28: 1.524,
    53.98: 1.651,
    66.68: 2.032,
    79.38: 2.413,
}

def _acr_id(od_mm: float) -> float:
    wall = ACR_WALL_MM.get(od_mm, 1.0)
    return od_mm - 2 * wall

# ─── Velocity limits (m/s) - ASHRAE 2022 Refrig. Hbk Ch.1 ───────────────────
VELOCITY_LIMITS = {
    "Suction Horizontal": {"min": 4.0,  "max": 10.0},
    "Suction Riser":      {"min": 6.0,  "max": 12.0},  # min 6 for oil return
    "Discharge":          {"min": 5.0,  "max": 15.0},
    "Liquid":             {"min": 0.5,  "max":  1.5},  # prevent flash before TXV
}

# ─── Application → evap temperature mapping (Philippine practice) ────────────
EVAP_TEMP_MAP = {
    "Air Conditioning":           5,
    "Low-Temperature Refrigeration": -10,
    # the form's own spelling (engineering-design.js tg-ref-app) - it never matched, so every low-temperature system
    # was sized at the +5 °C air-conditioning condition (2026-11-02, ED-G1)
    "Low-Temp Refrigeration":        -10,
    "Freezer":                   -35,
}

COND_TEMP_DEFAULT = 45   # °C - Manila ambient, condenser design

# ─── Refrigerant property tables (static ASHRAE saturation data) ─────────────
# Structure: {refrigerant: {evap_temp_c: {props...}, cond_temp_c: {props...}}}
#
# Properties at evaporating temperature (suction side):
#   h_fg_kJkg   - latent heat (kJ/kg)
#   rho_vap     - vapor density (kg/m³)
#   dpdt_kPaK   - dP/dT saturation slope (kPa/K) - for ΔT equivalent
#
# Properties at condensing temperature (liquid / discharge side):
#   rho_vap_dis - discharge vapor density (kg/m³)
#   rho_liq     - liquid density (kg/m³)

# ★THE TABLES WERE NOT WHAT THEY SAID, AND THE MASS FLOW USED THE WRONG ENTHALPY (2026-11-02, ED-G1 Refrigerant Pipe,
# read against the guide and checked with CoolProp 8.0.0). The old static table claimed "≤ 3% vs REFPROP"; against CoolProp
# its suction densities were up to 40% low (R-22 at +5 °C: 14.5 vs 23.5 kg/m3), its evaporating dP/dT up to 33% low, its
# liquid densities up to 9% low, and the mass flow was Q / h_fg - but the liquid reaching the expansion valve is at the
# CONDENSING temperature, so the refrigerating effect is h(suction) - h(liquid at T_cond): 158 kJ/kg for R-410A at 5/45,
# not h_fg 213. Mass flow was 1.3-1.85x low. The discharge and liquid lines also took dP/dT at the EVAPORATING
# temperature (discharge as 0.6x of it - the curve steepens with temperature: R-410A is 64 kPa/K at 45 °C, 28.6 at 5).
# Regenerated with tools/gen_refrigerant_props.py (CoolProp PropsSI; pip install CoolProp, run, paste): suction vapour at +10 K superheat; liquid saturated at T_cond
# (no subcooling, the conservative mass flow); discharge vapour at the compressor outlet, isentropic efficiency 0.70;
# dP/dT from the dew curve, +/-0.5 K. R-407C is CoolProp's pseudo-pure model (its glide is not resolved).
REFRIG_PROPS: dict[str, dict] = {
    "R-410A": {
        "evap": {
              5: {"h_fg_kJkg":  215.2, "rho_vap":  33.44, "dpdt_kPaK":  28.63},
            -10: {"h_fg_kJkg":  233.0, "rho_vap":  20.63, "dpdt_kPaK":  19.79},
            -35: {"h_fg_kJkg":  258.3, "rho_vap":   8.17, "dpdt_kPaK":   9.42},
        },
        "cond": {
            40: {"rho_liq":   975.7, "dpdt_kPaK":  58.72},
            45: {"rho_liq":   943.2, "dpdt_kPaK":  64.36},
            50: {"rho_liq":   907.0, "dpdt_kPaK":  70.46},
        },
        "pair": {   # "evap/cond": refrigerating effect (kJ/kg) and discharge vapour density (kg/m3)
            "5/40": {"RE_kJkg":  167.7, "rho_vap_dis":  75.94, "t_dis_c":  74.5},
            "5/45": {"RE_kJkg":  158.2, "rho_vap_dis":  84.45, "t_dis_c":  82.5},
            "5/50": {"RE_kJkg":  148.1, "rho_vap_dis":  93.70, "t_dis_c":  90.4},
            "-10/40": {"RE_kJkg":  161.8, "rho_vap_dis":  70.30, "t_dis_c":  88.2},
            "-10/45": {"RE_kJkg":  152.3, "rho_vap_dis":  78.17, "t_dis_c":  96.2},
            "-10/50": {"RE_kJkg":  142.2, "rho_vap_dis":  86.71, "t_dis_c": 104.0},
            "-35/40": {"RE_kJkg":  149.8, "rho_vap_dis":  61.45, "t_dis_c": 117.9},
            "-35/45": {"RE_kJkg":  140.3, "rho_vap_dis":  68.32, "t_dis_c": 125.8},
            "-35/50": {"RE_kJkg":  130.3, "rho_vap_dis":  75.77, "t_dis_c": 133.5},
        },
    },
    "R-32": {
        "evap": {
              5: {"h_fg_kJkg":  307.3, "rho_vap":  24.22, "dpdt_kPaK":  29.34},
            -10: {"h_fg_kJkg":  330.3, "rho_vap":  14.95, "dpdt_kPaK":  20.21},
            -35: {"h_fg_kJkg":  362.9, "rho_vap":   5.92, "dpdt_kPaK":   9.57},
        },
        "cond": {
            40: {"rho_liq":   893.0, "dpdt_kPaK":  60.43},
            45: {"rho_liq":   867.3, "dpdt_kPaK":  66.22},
            50: {"rho_liq":   839.3, "dpdt_kPaK":  72.43},
        },
        "pair": {   # "evap/cond": refrigerating effect (kJ/kg) and discharge vapour density (kg/m3)
            "5/40": {"RE_kJkg":  252.8, "rho_vap_dis":  50.53, "t_dis_c":  91.3},
            "5/45": {"RE_kJkg":  242.1, "rho_vap_dis":  55.59, "t_dis_c": 101.5},
            "5/50": {"RE_kJkg":  230.9, "rho_vap_dis":  61.03, "t_dis_c": 111.6},
            "-10/40": {"RE_kJkg":  248.4, "rho_vap_dis":  45.41, "t_dis_c": 115.5},
            "-10/45": {"RE_kJkg":  237.7, "rho_vap_dis":  50.02, "t_dis_c": 125.9},
            "-10/50": {"RE_kJkg":  226.5, "rho_vap_dis":  54.97, "t_dis_c": 136.1},
            "-35/40": {"RE_kJkg":  238.0, "rho_vap_dis":  38.01, "t_dis_c": 167.3},
            "-35/45": {"RE_kJkg":  227.3, "rho_vap_dis":  41.95, "t_dis_c": 177.8},
            "-35/50": {"RE_kJkg":  216.1, "rho_vap_dis":  46.19, "t_dis_c": 188.2},
        },
    },
    "R-22": {
        "evap": {
              5: {"h_fg_kJkg":  201.0, "rho_vap":  23.51, "dpdt_kPaK":  18.27},
            -10: {"h_fg_kJkg":  212.8, "rho_vap":  14.58, "dpdt_kPaK":  12.54},
            -35: {"h_fg_kJkg":  230.1, "rho_vap":   5.75, "dpdt_kPaK":   5.85},
        },
        "cond": {
            40: {"rho_liq":  1128.5, "dpdt_kPaK":  37.41},
            45: {"rho_liq":  1106.0, "dpdt_kPaK":  40.88},
            50: {"rho_liq":  1082.3, "dpdt_kPaK":  44.55},
        },
        "pair": {   # "evap/cond": refrigerating effect (kJ/kg) and discharge vapour density (kg/m3)
            "5/40": {"RE_kJkg":  164.7, "rho_vap_dis":  52.82, "t_dis_c":  78.0},
            "5/45": {"RE_kJkg":  158.0, "rho_vap_dis":  58.62, "t_dis_c":  86.2},
            "5/50": {"RE_kJkg":  151.1, "rho_vap_dis":  64.89, "t_dis_c":  94.3},
            "-10/40": {"RE_kJkg":  158.5, "rho_vap_dis":  49.29, "t_dis_c":  93.7},
            "-10/45": {"RE_kJkg":  151.8, "rho_vap_dis":  54.70, "t_dis_c": 101.9},
            "-10/50": {"RE_kJkg":  144.9, "rho_vap_dis":  60.55, "t_dis_c": 110.0},
            "-35/40": {"RE_kJkg":  147.0, "rho_vap_dis":  43.45, "t_dis_c": 127.6},
            "-35/45": {"RE_kJkg":  140.3, "rho_vap_dis":  48.23, "t_dis_c": 135.8},
            "-35/50": {"RE_kJkg":  133.4, "rho_vap_dis":  53.39, "t_dis_c": 143.9},
        },
    },
    "R-134a": {
        "evap": {
              5: {"h_fg_kJkg":  194.7, "rho_vap":  16.28, "dpdt_kPaK":  12.16},
            -10: {"h_fg_kJkg":  206.0, "rho_vap":   9.57, "dpdt_kPaK":   7.92},
            -35: {"h_fg_kJkg":  222.7, "rho_vap":   3.36, "dpdt_kPaK":   3.30},
        },
        "cond": {
            40: {"rho_liq":  1146.7, "dpdt_kPaK":  27.26},
            45: {"rho_liq":  1125.1, "dpdt_kPaK":  30.10},
            50: {"rho_liq":  1102.3, "dpdt_kPaK":  33.13},
        },
        "pair": {   # "evap/cond": refrigerating effect (kJ/kg) and discharge vapour density (kg/m3)
            "5/40": {"RE_kJkg":  154.2, "rho_vap_dis":  43.60, "t_dis_c":  62.7},
            "5/45": {"RE_kJkg":  146.7, "rho_vap_dis":  49.49, "t_dis_c":  68.9},
            "5/50": {"RE_kJkg":  139.0, "rho_vap_dis":  56.02, "t_dis_c":  75.0},
            "-10/40": {"RE_kJkg":  144.8, "rho_vap_dis":  41.97, "t_dis_c":  70.3},
            "-10/45": {"RE_kJkg":  137.2, "rho_vap_dis":  47.62, "t_dis_c":  76.4},
            "-10/50": {"RE_kJkg":  129.6, "rho_vap_dis":  53.87, "t_dis_c":  82.4},
            "-35/40": {"RE_kJkg":  128.4, "rho_vap_dis":  38.78, "t_dis_c":  87.9},
            "-35/45": {"RE_kJkg":  120.9, "rho_vap_dis":  43.97, "t_dis_c":  93.9},
            "-35/50": {"RE_kJkg":  113.2, "rho_vap_dis":  49.70, "t_dis_c":  99.7},
        },
    },
    "R-407C": {
        "evap": {
              5: {"h_fg_kJkg":  204.6, "rho_vap":  22.04, "dpdt_kPaK":  18.38},
            -10: {"h_fg_kJkg":  218.4, "rho_vap":  13.12, "dpdt_kPaK":  12.18},
            -35: {"h_fg_kJkg":  238.5, "rho_vap":   4.75, "dpdt_kPaK":   5.28},
        },
        "cond": {
            40: {"rho_liq":  1067.8, "dpdt_kPaK":  40.39},
            45: {"rho_liq":  1041.8, "dpdt_kPaK":  44.59},
            50: {"rho_liq":  1014.0, "dpdt_kPaK":  49.12},
        },
        "pair": {   # "evap/cond": refrigerating effect (kJ/kg) and discharge vapour density (kg/m3)
            "5/40": {"RE_kJkg":  161.0, "rho_vap_dis":  55.63, "t_dis_c":  69.8},
            "5/45": {"RE_kJkg":  152.8, "rho_vap_dis":  62.70, "t_dis_c":  77.1},
            "5/50": {"RE_kJkg":  144.3, "rho_vap_dis":  70.49, "t_dis_c":  84.2},
            "-10/40": {"RE_kJkg":  152.9, "rho_vap_dis":  52.56, "t_dis_c":  81.0},
            "-10/45": {"RE_kJkg":  144.6, "rho_vap_dis":  59.22, "t_dis_c":  88.2},
            "-10/50": {"RE_kJkg":  136.1, "rho_vap_dis":  66.55, "t_dis_c":  95.2},
            "-35/40": {"RE_kJkg":  138.1, "rho_vap_dis":  47.22, "t_dis_c": 105.9},
            "-35/45": {"RE_kJkg":  129.8, "rho_vap_dis":  53.17, "t_dis_c": 112.8},
            "-35/50": {"RE_kJkg":  121.3, "rho_vap_dis":  59.70, "t_dis_c": 119.7},
        },
    },
}

COPPER_ROUGHNESS_M = 1.5e-6   # drawn copper tubing, 0.0015 mm (Moody / ASHRAE) - was 1.5e-9 m, 1000x too small (2026-11-02)


def _friction_factor(Re: float, D: float) -> float:
    """Darcy friction factor - Blasius < 100,000; Swamee-Jain ≥ 100,000."""
    if Re < 2300:
        return 64 / Re
    eD = COPPER_ROUGHNESS_M / D
    if Re < 100000:
        return 0.3164 / Re ** 0.25
    return 0.25 / (math.log10(eD / 3.7 + 5.74 / Re ** 0.9)) ** 2


def _nearest_evap_temp(refrig: str, t: int) -> int:
    """Return closest available evap temp key."""
    keys = list(REFRIG_PROPS[refrig]["evap"].keys())
    return min(keys, key=lambda k: abs(k - t))


def _nearest_cond_temp(refrig: str, t: int) -> int:
    """Return closest available cond temp key."""
    keys = list(REFRIG_PROPS[refrig]["cond"].keys())
    return min(keys, key=lambda k: abs(k - t))


def _select_tube(
    flow_m3s: float,
    vel_limits: dict,
    rho: float,
    mu_pas: float,
    length_m: float,
    dpdt_kPaK: float,
    dt_limit_K: float,
) -> dict:
    """
    Select smallest ASTM B280 ACR tube within velocity limits and ΔT_eq budget.
    Returns sizing dict.

    ★THE BUDGET WAS COMPUTED AND NEVER USED (2026-11-01, found once the form's line lengths reached this engine): the loop
    returned the first tube inside the velocity limits whatever its ΔT_eq, so a 60 m suction line kept a 19.05 mm tube at
    2.04 K against the 1 K budget. Now: the smallest tube inside the velocity limits that also meets the budget; if none
    does (a very long run), the velocity-valid tube with the least drop, still flagged dt_ok False.
    """
    fits = []
    for od_mm in ACR_OD_MM:
        id_m = _acr_id(od_mm) / 1000
        A    = math.pi * (id_m / 2) ** 2
        v    = flow_m3s / A
        Re   = rho * v * id_m / mu_pas

        if v < vel_limits["min"] or v > vel_limits["max"]:
            continue

        # Pressure drop
        f      = _friction_factor(Re, id_m)
        dp_pa  = f * (length_m / id_m) * (rho * v ** 2 / 2)
        dp_kPa = dp_pa / 1000

        # ΔT equivalent - ASHRAE: ΔP / (dpdt_sat × 1000)
        dt_eq  = dp_pa / (dpdt_kPaK * 1000)

        sized = {
            "od_mm":       od_mm,
            "id_mm":       round(_acr_id(od_mm), 3),
            "velocity_ms": round(v, 3),
            "Re":          round(Re, 0),
            "friction_f":  round(f, 5),
            "dp_kPa":      round(dp_kPa, 3),
            "dp_Pa_total": round(dp_pa, 1),
            "delta_T_eq_K": round(dt_eq, 3),
            "dt_ok":       dt_eq <= dt_limit_K,
            "velocity_ok": vel_limits["min"] <= v <= vel_limits["max"],
        }
        if sized["dt_ok"]:
            return sized
        fits.append(sized)
    if fits:
        return min(fits, key=lambda s: s["delta_T_eq_K"])

    # Fallback: largest size
    od_mm  = ACR_OD_MM[-1]
    id_m   = _acr_id(od_mm) / 1000
    A      = math.pi * (id_m / 2) ** 2
    v      = flow_m3s / A
    Re     = rho * v * id_m / mu_pas
    f      = _friction_factor(Re, id_m)
    dp_pa  = f * (length_m / id_m) * (rho * v ** 2 / 2)
    dp_kPa = dp_pa / 1000
    dt_eq  = dp_pa / (dpdt_kPaK * 1000)
    return {
        "od_mm":       od_mm,
        "id_mm":       round(_acr_id(od_mm), 3),
        "velocity_ms": round(v, 3),
        "Re":          round(Re, 0),
        "friction_f":  round(f, 5),
        "dp_kPa":      round(dp_kPa, 3),
        "dp_Pa_total": round(dp_pa, 1),
        "delta_T_eq_K": round(dt_eq, 3),
        "dt_ok":       dt_eq <= dt_limit_K,
        "velocity_ok": False,   # oversized - velocity below min
    }


def _make_line(name: str, line_type: str, equiv_length_m: float, sub: dict | None) -> dict | None:
    """Build a line dict with renderer-compatible field names."""
    if not sub:
        return None
    return {
        "name":            name,
        "line_name":       name,
        "line_type":       line_type,
        "equiv_length_m":  equiv_length_m,
        "selected_od_mm":  sub.get("od_mm"),
        "selected_id_mm":  sub.get("id_mm"),
        "velocity_ms":     sub.get("velocity_ms"),
        "vel_check":       "OK" if sub.get("velocity_ok") else "WARN",
        "dp_total_pa":     sub.get("dp_Pa_total"),
        "delta_t_k":       sub.get("delta_T_eq_K"),
        **sub,
    }


# formula: refrigerant_pipe_ashrae_2022
def calculate(inputs: dict) -> dict:
    """
    Main entry point - compatible with TypeScript calcRefrigPipeSizing() keys.
    """
    # ── Inputs ────────────────────────────────────────────────────────────────
    cooling_kw    = float(inputs.get("cooling_kw",       0)
                      or  inputs.get("capacity_kw",      0)
                      or  inputs.get("kW",               0))
    if cooling_kw <= 0:
        cooling_kw = 10.0   # safe default

    refrigerant   = str  (inputs.get("refrigerant",    "R-410A"))
    application   = str  (inputs.get("application",    "Air Conditioning"))
    evap_temp_c   = int  (inputs.get("evap_temp_c",
                          EVAP_TEMP_MAP.get(application, 5)))
    cond_temp_c   = int  (inputs.get("cond_temp_c",    COND_TEMP_DEFAULT))
    suction_len_m = float(inputs.get("suction_length_m",  10.0))
    discharge_len_m = float(inputs.get("discharge_length_m", 10.0))
    liquid_len_m  = float(inputs.get("liquid_length_m",  10.0))
    has_riser     = bool (inputs.get("has_suction_riser", False))
    # ★THE FORM'S LINE SCHEDULE NEVER REACHED THE SIZING (2026-11-01, ED-I1 Refrigerant Pipe, census_calc_input_reach.py -
    # found after the census learned shorthand keys). The page sends lines: [{name, line_type, equiv_length_m}]; this read
    # the three *_length_m keys only, so every line was sized as 10 m whatever the run - 60 m lines gave the same answer as
    # 15 m, and a long suction line's pressure drop (capacity loss, oil return) was never seen. Each scheduled line now sets
    # its type's length; where two lines share a type the longest run governs (one size serves the worst run), and a
    # "Suction: Riser" line turns the riser check on.
    longest: dict[str, float] = {}
    for ln in (inputs.get("lines") or []):
        if not isinstance(ln, dict):
            continue
        lt = str(ln.get("line_type") or "")
        L = float(ln.get("equiv_length_m") or 0)
        kind = next((k for k in ("Suction", "Discharge", "Liquid") if lt.startswith(k)), None)
        if kind is None or L <= 0:
            continue
        longest[kind] = max(longest.get(kind, 0.0), L)
        if kind == "Suction" and "Riser" in lt:
            has_riser = True
    suction_len_m   = longest.get("Suction",   suction_len_m)
    discharge_len_m = longest.get("Discharge", discharge_len_m)
    liquid_len_m    = longest.get("Liquid",    liquid_len_m)

    # ── Refrigerant property lookup ───────────────────────────────────────────
    if refrigerant not in REFRIG_PROPS:
        refrigerant = "R-410A"

    evap_key   = _nearest_evap_temp(refrigerant, evap_temp_c)
    cond_key   = _nearest_cond_temp(refrigerant, cond_temp_c)
    evap_props = REFRIG_PROPS[refrigerant]["evap"][evap_key]
    cond_props = REFRIG_PROPS[refrigerant]["cond"][cond_key]

    pair_props = REFRIG_PROPS[refrigerant]["pair"][f"{evap_key}/{cond_key}"]
    h_fg_kJkg  = evap_props["h_fg_kJkg"]
    re_kJkg    = pair_props["RE_kJkg"]         # refrigerating effect: suction vapour minus liquid at T_cond
    rho_suc    = evap_props["rho_vap"]         # kg/m³ suction vapour, +10 K superheat
    rho_dis    = pair_props["rho_vap_dis"]     # kg/m³ discharge vapour at the compressor outlet
    rho_liq    = cond_props["rho_liq"]         # kg/m³ liquid at condenser
    dpdt       = evap_props["dpdt_kPaK"]       # kPa/K at evap temp - the suction line
    dpdt_cond  = cond_props["dpdt_kPaK"]       # kPa/K at condensing temp - the discharge and liquid lines

    # ── Mass flow ─────────────────────────────────────────────
    # ṁ = Q_kW / RE   (ASHRAE 2022 Refrig. Hbk Ch.1 - the energy balance across the evaporator)
    mass_flow_kgs = cooling_kw / re_kJkg       # kg/s

    # ── Volumetric flows per phase ─────────────────────────────────────────────
    flow_suc_m3s = mass_flow_kgs / rho_suc
    flow_dis_m3s = mass_flow_kgs / rho_dis
    flow_liq_m3s = mass_flow_kgs / rho_liq

    # ── Dynamic viscosity (µ) estimates - refrigerant vapor at design conditions
    # Approximate µ for vapor sizing - error < 5%, adequate for pipe selection
    mu_vap = 1.2e-5   # Pa·s - typical HFC vapor (R-410A/R-32 ~1.1-1.3×10⁻⁵)
    mu_liq = 1.5e-4   # Pa·s - liquid refrigerant (R-410A/R-22 ~1.3-1.8×10⁻⁴)

    # ── Select tubes ─────────────────────────────────────────────────────────
    # Suction horizontal (min 4 m/s, max 10 m/s; ΔT ≤ 1 K)
    suction_horiz = _select_tube(
        flow_suc_m3s,
        VELOCITY_LIMITS["Suction Horizontal"],
        rho_suc, mu_vap, suction_len_m, dpdt, 1.0,
    )

    # Suction riser (min 6 m/s for oil return; ΔT ≤ 1 K)
    suction_riser = _select_tube(
        flow_suc_m3s,
        VELOCITY_LIMITS["Suction Riser"],
        rho_suc, mu_vap, suction_len_m, dpdt, 1.0,
    ) if has_riser else None

    # Discharge (min 5 m/s; ΔT ≤ 2 K)
    discharge = _select_tube(
        flow_dis_m3s,
        VELOCITY_LIMITS["Discharge"],
        rho_dis, mu_vap, discharge_len_m, dpdt_cond, 2.0,
    )

    # Liquid (0.5–1.5 m/s; ΔT ≤ 2 K; liquid line uses ΔP→subcooling loss)
    liquid = _select_tube(
        flow_liq_m3s,
        VELOCITY_LIMITS["Liquid"],
        rho_liq, mu_liq, liquid_len_m, dpdt_cond, 2.0,
    )

    # ── Insulation requirement (ASHRAE 90.1) ─────────────────────────────────
    # Suction line: ≥ 19 mm closed-cell elastomeric foam (ASTM C534) in all
    # Philippine climate conditions (>25°C year-round ambient)
    insulation_note = (
        "Suction line: min 19 mm closed-cell elastomeric foam (ASTM C534). "
        "Liquid line: insulate to prevent heat gain and flashing before TXV. "
        "Discharge line: insulate hot-gas line where run through conditioned space."
    )

    # ── Field installation notes (ASHRAE + PSME) ──────────────────────────────
    field_notes = [
        "Braze all joints with nitrogen purge (OFN) - copper oxide destroys TXV/compressor.",
        "Install oil trap at base of each suction riser + every 6 m on long risers.",
        f"Pressure test at {round(cooling_kw * 0.11 + 25, 0):.0f} bar_g (≥ 1.1× MAWP) "
        "with dry nitrogen - 24-hour hold.",
        "Evacuate to ≤ 500 microns (deep vacuum) before refrigerant charge.",
        "Charge by weight (kg) per manufacturer nameplate - correct for line length difference.",
    ]

    return {
        # Mass and volume flows
        "mass_flow_kgs":      round(mass_flow_kgs, 4),
        "flow_suction_m3s":   round(flow_suc_m3s, 6),
        "flow_discharge_m3s": round(flow_dis_m3s, 6),
        "flow_liquid_m3s":    round(flow_liq_m3s, 7),

        # Tube sizing results
        "suction_horizontal": suction_horiz,
        "suction_riser":      suction_riser,
        "discharge":          discharge,
        "liquid":             liquid,

        # Refrigerant properties used
        "refrigerant_props": {
            "refrigerant":      refrigerant,
            "evap_temp_c":      evap_key,
            "cond_temp_c":      cond_key,
            "h_fg_kJkg":        h_fg_kJkg,
            "refrigerating_effect_kJkg": re_kJkg,
            "t_discharge_c":    pair_props["t_dis_c"],
            "dpdt_cond_kPaK":   dpdt_cond,
            "rho_suction_kgm3": rho_suc,
            "rho_discharge_kgm3": rho_dis,
            "rho_liquid_kgm3":  rho_liq,
            "dpdt_kPaK":        dpdt,
        },

        # Standards compliance
        "insulation_requirement": insulation_note,
        "field_notes":            field_notes,

        # Metadata
        "inputs_used": {
            "application":     application,
            "refrigerant":     refrigerant,
            "cooling_kw":      cooling_kw,
            "evap_temp_c":     evap_key,
            "cond_temp_c":     cond_key,
        },
        "calculation_source": "python/static tables generated with CoolProp 8.0.0",
        "standard": "ASHRAE 2022 Refrig. Hbk Ch.1 | ASTM B280 | ASHRAE 90.1 | PSME",

        # ── Legacy renderer aliases (frontend renderRefrigPipeReport) ──────────
        # Renderer reads r.lines as array - build it from the sub-objects
        "lines": [x for x in [
            _make_line("Suction Line",    "Suction - Horizontal", suction_len_m,   suction_horiz),
            _make_line("Suction Riser",   "Suction - Riser",      suction_len_m,   suction_riser),
            _make_line("Discharge Line",  "Discharge",            discharge_len_m, discharge),
            _make_line("Liquid Line",     "Liquid",               liquid_len_m,    liquid),
        ] if x is not None],
        "evap_temp_c":  evap_key,
        "cond_temp_c":  cond_key,
    }
