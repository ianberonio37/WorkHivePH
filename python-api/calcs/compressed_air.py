"""
Compressed Air System - Phase 1c
Standards: ISO 1217, PSME Code, ASME B31.3, CAGI (Compressed Air & Gas Institute)
Libraries: fluids (Darcy-Weisbach, pipe sizing), numpy (iteration)

Replaces the hand-rolled TypeScript implementation with:
- Proper isentropic compression power (not simplified approximation)
- Real air density at operating pressure and temperature
- Darcy-Weisbach pressure drop in distribution pipes
- Receiver tank sizing per ISO 1217
- Compressor selection with duty cycle correction
"""

from fluids import friction_factor, Reynolds
import math

# ─── Standard pipe inside diameters (mm) - for compressed air distribution ───
PIPE_SIZES: list[dict] = [
    {"nominal": 15,  "id_mm": 15.8},
    {"nominal": 20,  "id_mm": 20.9},
    {"nominal": 25,  "id_mm": 26.6},
    {"nominal": 32,  "id_mm": 35.1},
    {"nominal": 40,  "id_mm": 40.9},
    {"nominal": 50,  "id_mm": 52.5},
    {"nominal": 65,  "id_mm": 62.7},
    {"nominal": 80,  "id_mm": 77.9},
    {"nominal": 100, "id_mm": 102.3},
    {"nominal": 125, "id_mm": 128.2},
    {"nominal": 150, "id_mm": 154.1},
    {"nominal": 200, "id_mm": 206.5},
]

# Pipe roughness for steel air distribution (mm) - ASME B31.3
STEEL_ROUGHNESS_MM = 0.046

# Standard compressor kW sizes
STD_COMP_KW = [0.75, 1.5, 2.2, 3.7, 5.5, 7.5, 11, 15, 18.5, 22,
               30, 37, 45, 55, 75, 90, 110, 132, 160, 200, 250, 315]

# Air tool consumption (L/min FAD) - CAGI reference
AIR_TOOL_FLOW: dict[str, float] = {
    "Impact Wrench 1/2\"":  170,
    "Impact Wrench 3/4\"":  340,
    "Grinder 4\"":          170,
    "Grinder 7\"":          340,
    "Drill":                113,
    "Sander":               283,
    "Paint Spray Gun":      283,
    "Needle Scaler":        170,
    "Chisel Hammer":        283,
    "Blow Gun":             57,
}


def _air_density(temp_c: float, pressure_bar_g: float) -> float:
    """
    Return air density (kg/m3) at temperature and gauge pressure.
    Uses ideal gas law: rho = P_abs / (R_air * T)
    R_air = 287.05 J/(kg·K)
    """
    P_abs = (pressure_bar_g + 1.01325) * 1e5   # bar_g → Pa absolute
    T_K   = temp_c + 273.15
    return P_abs / (287.05 * T_K)


def _air_viscosity(temp_c: float) -> float:
    """
    Dynamic viscosity of air (Pa·s) via Sutherland's formula.
    Reference: ASHRAE Fundamentals 2021
    """
    T   = temp_c + 273.15
    mu0 = 1.716e-5   # Pa·s at T0=273.15K
    T0  = 273.15
    S   = 110.4      # Sutherland constant for air
    return mu0 * (T / T0) ** 1.5 * (T0 + S) / (T + S)


def _isentropic_power(
    flow_fad_m3min: float,
    p_inlet_bar_a: float,
    p_outlet_bar_a: float,
    temp_inlet_c: float,
    n: float = 1.4,    # isentropic exponent for air
) -> float:
    """
    Isentropic compression power (kW) - ISO 1217 Annex C.
    W_iso = (n/(n-1)) * P1 * Q1 * [(P2/P1)^((n-1)/n) - 1]
    """
    P1    = p_inlet_bar_a * 1e5   # Pa
    Q1    = flow_fad_m3min / 60   # m3/s at inlet (FAD approximation)
    ratio = (p_outlet_bar_a / p_inlet_bar_a) ** ((n - 1) / n)
    W     = (n / (n - 1)) * P1 * Q1 * (ratio - 1)
    return W / 1000   # W → kW


def _pipe_pressure_drop(
    flow_fad_m3min: float,
    pipe_id_m: float,
    length_m: float,
    pressure_bar_g: float,
    temp_c: float,
) -> tuple[float, float, float]:
    """
    Pressure drop in compressed air distribution pipe.
    Returns (dp_bar, velocity_ms, Re).
    Flow is converted from FAD to actual volume at line pressure.
    """
    # Actual volumetric flow at line conditions
    rho   = _air_density(temp_c, pressure_bar_g)
    mu    = _air_viscosity(temp_c)
    # FAD at 1.01325 bar → actual at line pressure
    rho_atm   = _air_density(temp_c, 0)   # atmospheric density
    flow_act  = flow_fad_m3min * (rho_atm / rho) / 60   # m3/s actual

    A     = math.pi * (pipe_id_m / 2) ** 2
    v     = flow_act / A
    Re    = Reynolds(V=v, D=pipe_id_m, rho=rho, mu=mu)

    if Re < 1:
        return 0.0, v, Re

    eD    = (STEEL_ROUGHNESS_MM / 1000) / pipe_id_m
    f     = friction_factor(Re=Re, eD=eD)
    dp_pa = f * (length_m / pipe_id_m) * (rho * v ** 2 / 2)
    dp_bar = dp_pa / 1e5
    return dp_bar, v, Re


def _select_pipe(
    flow_fad_m3min: float,
    length_m: float,
    pressure_bar_g: float,
    temp_c: float,
    max_dp_bar: float = 0.1,   # CAGI: max 10% pressure drop = 0.7 bar for 7 bar system
) -> dict:
    """Select smallest pipe that keeps pressure drop within limit."""
    for ps in PIPE_SIZES:
        id_m = ps["id_mm"] / 1000
        dp, v, Re = _pipe_pressure_drop(flow_fad_m3min, id_m, length_m, pressure_bar_g, temp_c)
        if dp <= max_dp_bar:
            return {
                "nominal_mm":  ps["nominal"],
                "id_mm":       ps["id_mm"],
                "velocity_ms": round(v, 3),
                "dp_bar":      round(dp, 4),
                "Re":          round(Re, 0),
            }
    # Fallback: largest size
    ps = PIPE_SIZES[-1]
    id_m = ps["id_mm"] / 1000
    dp, v, Re = _pipe_pressure_drop(flow_fad_m3min, id_m, length_m, pressure_bar_g, temp_c)
    return {
        "nominal_mm":  ps["nominal"],
        "id_mm":       ps["id_mm"],
        "velocity_ms": round(v, 3),
        "dp_bar":      round(dp, 4),
        "Re":          round(Re, 0),
    }


def calculate(inputs: dict) -> dict:
    """
    Main entry point - compatible with TypeScript calcCompressedAir() input keys.
    """
    # ── Inputs ────────────────────────────────────────────────────────────────
    flow_fad_m3min  = float(inputs.get("flow_rate",          0)
                        or  inputs.get("demand_m3min",        0)
                        or  inputs.get("total_demand_m3min",  0))
    pressure_bar_g  = float(inputs.get("working_pressure",    7)
                        or  inputs.get("pressure_bar_g",      7))
    pipe_length_m   = float(inputs.get("pipe_length",        50))
    temp_c          = float(inputs.get("ambient_temp_c",     35))   # Manila ambient
    duty_cycle_pct  = float(inputs.get("duty_cycle_pct",    70))    # % of time compressor runs
    comp_eff_pct    = float(inputs.get("compressor_eff_pct",85))    # isentropic efficiency
    num_tools       = int  (inputs.get("num_tools",          1))
    safety_factor   = float(inputs.get("safety_factor",     1.25))  # 25% spare capacity

    if flow_fad_m3min <= 0:
        # Try to estimate from tools if no direct flow given
        tool_type = str(inputs.get("tool_type", "Impact Wrench 1/2\""))
        tool_flow = AIR_TOOL_FLOW.get(tool_type, 170)
        flow_fad_m3min = tool_flow * num_tools / 1000  # L/min → m3/min

    if flow_fad_m3min <= 0:
        raise ValueError("Air demand (flow rate) must be greater than 0.")

    # ── Pressures ─────────────────────────────────────────────────────────────
    p_inlet_bar_a  = 1.01325                          # atmospheric
    p_outlet_bar_a = pressure_bar_g + 1.01325         # absolute discharge

    # ── Isentropic compression power - ISO 1217 ───────────────────────────────
    iso_kw     = _isentropic_power(flow_fad_m3min, p_inlet_bar_a, p_outlet_bar_a, temp_c)
    shaft_kw   = iso_kw / (comp_eff_pct / 100)        # actual shaft power
    motor_kw   = shaft_kw / 0.93                      # motor input (93% motor eff)

    # Duty-cycle corrected installed capacity
    installed_kw = motor_kw * (100 / duty_cycle_pct) * safety_factor

    # Next standard compressor size
    recommended_kw = next((s for s in STD_COMP_KW if s >= installed_kw), STD_COMP_KW[-1])
    recommended_hp = round(recommended_kw * 1.341, 1)

    # ── Receiver tank sizing - ISO 1217 ───────────────────────────────────────
    # V = (Q * t * P_atm) / (P_max - P_min)
    # t = 60s (1 min), P_max = working + 0.5 bar, P_min = working - 0.5 bar
    Q_m3s   = flow_fad_m3min / 60
    P_max   = p_outlet_bar_a * 1e5
    P_min   = (pressure_bar_g - 0.5 + 1.01325) * 1e5
    P_atm   = 1.01325e5
    t_sec   = 60   # 1 minute storage
    V_tank  = (Q_m3s * t_sec * P_atm) / (P_max - P_min)   # m3

    # Standard tank sizes (litres)
    std_tanks = [100, 200, 300, 500, 750, 1000, 1500, 2000, 3000, 5000]
    rec_tank  = next((t for t in std_tanks if t >= V_tank * 1000), std_tanks[-1])

    # ── Distribution pipe sizing ───────────────────────────────────────────────
    # CAGI: max pressure drop = 10% of working pressure
    max_dp = pressure_bar_g * 0.10
    pipe   = _select_pipe(flow_fad_m3min, pipe_length_m, pressure_bar_g, temp_c, max_dp)

    # ── Compressed air quality (ISO 8573-1 class reference) ───────────────────
    # Default: Class 1.4.2 suitable for general industrial use
    air_quality = "ISO 8573-1 Class 1.4.2 (General Industrial)"

    # ── Specific power (kW per m3/min FAD) - efficiency metric ───────────────
    specific_power = round(motor_kw / flow_fad_m3min, 2) if flow_fad_m3min > 0 else 0
    # CAGI benchmark: good = <7.5 kW/(m3/min) at 7 bar
    specific_power_ok = specific_power <= 8.0

    return {
        # Compressor sizing
        "iso_power_kw":        round(iso_kw, 3),
        "shaft_power_kw":      round(shaft_kw, 3),
        "motor_power_kw":      round(motor_kw, 3),
        "installed_kw":        round(installed_kw, 3),
        "recommended_kw":      recommended_kw,
        "recommended_hp":      recommended_hp,

        # Air demand
        "total_demand_m3min":  round(flow_fad_m3min, 3),
        "total_demand_cfm":    round(flow_fad_m3min * 35.3147, 2),
        "working_pressure_bar_g": pressure_bar_g,

        # Receiver tank
        "receiver_volume_m3":  round(V_tank, 3),
        "receiver_volume_L":   round(V_tank * 1000, 1),
        "recommended_tank_L":  rec_tank,

        # Distribution pipe
        "recommended_pipe_mm": pipe["nominal_mm"],
        "pipe_id_mm":          pipe["id_mm"],
        "pipe_velocity_ms":    pipe["velocity_ms"],
        "pipe_dp_bar":         pipe["dp_bar"],
        "pipe_dp_pct":         round(pipe["dp_bar"] / pressure_bar_g * 100, 2),

        # Efficiency
        "specific_power_kw_m3min": specific_power,
        "specific_power_ok":       specific_power_ok,
        "duty_cycle_pct":          duty_cycle_pct,
        "air_quality_class":       air_quality,

        # Metadata
        "inputs_used": {
            "compressor_efficiency_pct": comp_eff_pct,
            "safety_factor":             safety_factor,
            "ambient_temp_c":            temp_c,
        },
        "calculation_source": "python/fluids",
        "standard": "ISO 1217 | ISO 8573-1 | ASME B31.3 | CAGI",
    }
