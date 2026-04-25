"""
Pump Sizing (TDH) - Phase 1
Standards: ISO 9906, PSME Code, ASHRAE 2021 Fundamentals Ch. 22
Libraries: fluids (Darcy-Weisbach, Colebrook-White), iapws (water properties)

Replaces the hand-rolled Hazen-Williams TypeScript implementation with:
- Colebrook-White friction factor iteration (Churchill equation via fluids)
- Real water density and viscosity at operating temperature (iapws IAPWS97)
- Proper NPSH_available calculation with vapor pressure from iapws
- System curve data (Q vs TDH sweep) for pump curve overlay
"""

from fluids import friction_factor, Reynolds
from iapws import IAPWS97
import math

# ─── Pipe roughness by material (mm) - ASHRAE 2021 Fundamentals Table 2 ───────
PIPE_ROUGHNESS_MM: dict[str, float] = {
    "PVC":             0.0015,
    "Copper":          0.0015,
    "Galvanized Steel": 0.15,
    "Carbon Steel":    0.046,
    "Cast Iron":       0.26,
    "Stainless Steel": 0.015,
    "HDPE":            0.0015,
    "GI":              0.15,
}

# ─── Standard pipe inside diameters by nominal size (mm) - PNS / ISO 4427 ────
PIPE_ID_MM: dict[float, float] = {
    15:  15.8,   # 1/2"
    20:  20.9,   # 3/4"
    25:  26.6,   # 1"
    32:  35.1,   # 1-1/4"
    40:  40.9,   # 1-1/2"
    50:  52.5,   # 2"
    65:  62.7,   # 2-1/2"
    80:  77.9,   # 3"
    100: 102.3,  # 4"
    125: 128.2,  # 5"
    150: 154.1,  # 6"
    200: 206.5,  # 8"
    250: 257.4,  # 10"
    300: 309.6,  # 12"
}


def _water_props(temp_c: float) -> tuple[float, float, float]:
    """
    Return (density kg/m3, dynamic viscosity Pa·s, vapor pressure Pa)
    for water at temp_c degrees Celsius using IAPWS-IF97.
    Falls back to 20°C values if temperature is out of range.
    """
    try:
        T_K = temp_c + 273.15
        # Saturated liquid state (x=0) gives liquid properties
        state = IAPWS97(T=T_K, x=0)
        rho   = state.rho          # kg/m3
        mu    = state.mu           # Pa·s (dynamic viscosity)
        pv    = state.P * 1e6      # MPa → Pa (vapor pressure at saturation)
        return rho, mu, pv
    except Exception:
        # Fallback: water at 20°C
        return 998.2, 1.002e-3, 2338.0


def _select_pipe_id(nominal_mm: float) -> float:
    """Return inside diameter for the nearest standard nominal pipe size."""
    sizes = sorted(PIPE_ID_MM.keys())
    nearest = min(sizes, key=lambda s: abs(s - nominal_mm))
    return PIPE_ID_MM[nearest]


def _friction_head(
    flow_m3s: float,
    pipe_id_m: float,
    pipe_length_m: float,
    roughness_m: float,
    rho: float,
    mu: float,
) -> tuple[float, float, float, float]:
    """
    Compute friction head loss using Darcy-Weisbach + Colebrook-White.
    Returns (hf_m, velocity_ms, Re, f).
    """
    A    = math.pi * (pipe_id_m / 2) ** 2   # pipe cross-section m2
    v    = flow_m3s / A                       # velocity m/s
    Re   = Reynolds(V=v, D=pipe_id_m, rho=rho, mu=mu)
    eD   = roughness_m / pipe_id_m           # relative roughness

    if Re < 1:
        return 0.0, v, Re, 0.0

    f    = friction_factor(Re=Re, eD=eD)     # Colebrook-White via Churchill
    hf   = f * (pipe_length_m / pipe_id_m) * (v ** 2 / (2 * 9.81))
    return hf, v, Re, f


def calculate(inputs: dict) -> dict:
    """
    Main entry point - matches the same input keys used by the TypeScript
    calcPumpSizingTDH() function so the frontend needs zero changes.
    """
    # ── Inputs ────────────────────────────────────────────────────────────────
    flow_lpm      = float(inputs.get("flow_rate",       0) or inputs.get("flow_lpm", 0))
    static_head_m = float(inputs.get("static_head",     10))
    pipe_dia_mm   = float(inputs.get("pipe_diameter",   50))
    pipe_length_m = float(inputs.get("pipe_length",     50))
    pipe_mat      = str  (inputs.get("pipe_material",   "PVC"))
    temp_c        = float(inputs.get("fluid_temp_c",    25))
    elev_m        = float(inputs.get("site_elevation_m", 0))   # metres above sea level
    pump_eff_pct  = float(inputs.get("pump_efficiency",  70))
    motor_eff_pct = float(inputs.get("motor_efficiency", 90))
    suction_head_m= float(inputs.get("suction_head",    0))    # negative = lift
    fittings_pct  = float(inputs.get("fittings_allowance_pct", 20))  # % of friction head
    fluid_type    = str  (inputs.get("fluid_type",      "Water"))

    if flow_lpm <= 0:
        raise ValueError("Flow rate must be greater than 0 L/min.")
    if pipe_dia_mm <= 0:
        raise ValueError("Pipe diameter must be greater than 0 mm.")

    # ── Unit conversions ─────────────────────────────────────────────────────
    flow_m3s  = flow_lpm / 1000 / 60          # L/min → m3/s
    flow_m3hr = flow_lpm * 60 / 1000          # L/min → m3/hr

    # ── Water properties at operating temperature (iapws IAPWS-IF97) ─────────
    rho, mu, p_vapor = _water_props(temp_c)

    # ── Pipe geometry ─────────────────────────────────────────────────────────
    pipe_id_m   = _select_pipe_id(pipe_dia_mm) / 1000   # mm → m
    roughness_m = PIPE_ROUGHNESS_MM.get(pipe_mat, 0.046) / 1000  # mm → m

    # ── Friction head - Darcy-Weisbach + Colebrook-White ─────────────────────
    hf, velocity_ms, Re, f = _friction_head(
        flow_m3s, pipe_id_m, pipe_length_m, roughness_m, rho, mu
    )

    # Minor losses as % of friction head (fittings, valves, bends)
    h_minor = hf * (fittings_pct / 100)
    h_friction_total = hf + h_minor

    # ── Velocity head ─────────────────────────────────────────────────────────
    h_velocity = velocity_ms ** 2 / (2 * 9.81)

    # ── Total Dynamic Head ────────────────────────────────────────────────────
    TDH = static_head_m + h_friction_total + h_velocity

    # ── NPSH available ────────────────────────────────────────────────────────
    # Atmospheric pressure at site elevation (barometric formula)
    p_atm  = 101325 * (1 - 2.25577e-5 * elev_m) ** 5.25588   # Pa
    h_atm  = p_atm  / (rho * 9.81)   # m
    h_vap  = p_vapor / (rho * 9.81)  # m

    # Suction pipe friction (assume 20% of total suction pipe length)
    h_fs   = hf * 0.2
    NPSHa  = h_atm + suction_head_m - h_vap - h_fs

    # ── Power calculations ────────────────────────────────────────────────────
    pump_eff  = pump_eff_pct  / 100
    motor_eff = motor_eff_pct / 100

    hydraulic_kw  = rho * 9.81 * flow_m3s * TDH / 1000          # kW (hydraulic power)
    shaft_kw      = hydraulic_kw / pump_eff                       # kW (shaft/brake power)
    motor_kw      = shaft_kw / motor_eff                          # kW (motor input)
    motor_hp      = motor_kw * 1.341                              # HP

    # Next standard motor size (PEC 2017 / IEC standard sizes)
    std_kw = [0.18,0.25,0.37,0.55,0.75,1.1,1.5,2.2,3.0,4.0,5.5,7.5,
              11,15,18.5,22,30,37,45,55,75,90,110,132,160,200,250,315]
    recommended_kw = next((s for s in std_kw if s >= motor_kw * 1.15), std_kw[-1])
    recommended_hp = round(recommended_kw * 1.341, 1)

    # ── Velocity status ───────────────────────────────────────────────────────
    velocity_ok = 0.6 <= velocity_ms <= 3.0
    if velocity_ms < 0.6:
        velocity_zone = "Too Slow - risk of sedimentation"
    elif velocity_ms <= 1.5:
        velocity_zone = "Economical - optimal range"
    elif velocity_ms <= 3.0:
        velocity_zone = "Standard - acceptable"
    else:
        velocity_zone = "High - risk of erosion/noise"

    # ── System curve data (Q vs TDH sweep 0–150% design flow) ────────────────
    system_curve = []
    for pct in range(0, 160, 10):
        q   = flow_m3s * pct / 100
        if q == 0:
            system_curve.append({"Q_lpm": 0, "TDH_m": round(static_head_m, 2)})
            continue
        hf_i, v_i, _, _ = _friction_head(q, pipe_id_m, pipe_length_m, roughness_m, rho, mu)
        h_minor_i = hf_i * (fittings_pct / 100)
        h_vel_i   = v_i ** 2 / (2 * 9.81)
        tdh_i     = static_head_m + hf_i + h_minor_i + h_vel_i
        system_curve.append({
            "Q_lpm": round(q * 1000 * 60, 1),
            "TDH_m": round(tdh_i, 2),
        })

    # ── Return results (same keys as TypeScript for frontend compatibility) ───
    return {
        # Core outputs
        "TDH":                  round(TDH, 2),
        "flow_lpm":             round(flow_lpm, 1),
        "flow_m3hr":            round(flow_m3hr, 3),

        # Pipe hydraulics
        "pipe_velocity":        round(velocity_ms, 3),
        "pipe_dia_mm":          round(pipe_id_m * 1000, 1),
        "Reynolds_number":      round(Re, 0),
        "friction_factor":      round(f, 5),
        "friction_head_m":      round(hf, 3),
        "minor_losses_m":       round(h_minor, 3),
        "velocity_head_m":      round(h_velocity, 3),
        "velocity_ok":          velocity_ok,
        "velocity_zone":        velocity_zone,

        # NPSH
        "npsh_available":       round(NPSHa, 2),
        "static_head":          round(static_head_m, 2),
        "friction_head":        round(h_friction_total, 3),

        # Power
        "hydraulic_kw":         round(hydraulic_kw, 3),
        "shaft_kw":             round(shaft_kw, 3),
        "recommended_kw":       recommended_kw,
        "recommended_hp":       recommended_hp,

        # Fluid properties (from iapws)
        "fluid_density_kgm3":   round(rho, 2),
        "fluid_viscosity_pas":  round(mu, 6),
        "fluid_temp_c":         temp_c,

        # System curve for diagram overlay
        "system_curve":         system_curve,

        # Metadata
        "inputs_used": {
            "pipe_material":    pipe_mat,
            "pump_efficiency":  pump_eff_pct,
            "motor_efficiency": motor_eff_pct,
            "pipe_roughness_mm": roughness_m * 1000,
        },

        # Source tag
        "calculation_source":   "python/fluids+iapws",
        "standard":             "ISO 9906 | PSME Code | ASHRAE 2021 Ch.22",
    }
