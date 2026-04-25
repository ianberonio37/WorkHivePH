"""
Fluid Power / Hydraulics - Phase 9b
Standards: ISO 4413:2010 (Hydraulic fluid power - safety requirements),
           NFPA T2.12.10 (Hydraulic systems - design),
           Bosch Rexroth Hydraulic Trainer Vol.1,
           Parker Hannifin Hydraulics Training Manual,
           JIS B 8356 (Philippine adoption via DTI/BPS)
Libraries: math (all formulas closed-form)

Methods:
  Cylinder: F = P × A - A = π(D²−d²)/4 (annulus side)
  Pump flow: Q = Vg × n × η_vol
  Power:     P = Q × ΔP / (η_pump × η_motor)
  Hydraulic motor: T = Vg × ΔP × η_mech / (2π)
  Accumulator: V_gas = V_fluid × P2 / (P2−P1) (Boyle's law, isothermal)
  Pipe sizing: velocity method - v ≤ 4 m/s pressure, ≤ 2 m/s return, ≤ 1 m/s suction
  Pressure drop: Hagen-Poiseuille (laminar) or Darcy-Weisbach (turbulent)
"""

import math

# ─── Standard hydraulic cylinder bore sizes (mm) ─────────────────────────────
STD_BORE_MM = [25, 32, 40, 50, 63, 80, 100, 125, 160, 200, 250, 320]
STD_ROD_MM  = [12, 16, 20, 22, 28, 36, 45,  56,  70,  90, 110, 140]

# ─── Standard hydraulic pump displacement sizes (cm³/rev) ────────────────────
STD_PUMP_DISPL_CM3 = [0.5, 1, 2, 3, 4, 5, 7, 9, 11, 14, 18, 22, 28, 36, 45,
                      56, 71, 90, 110, 140, 180, 224, 280, 355, 450]

# ─── Standard hydraulic pipe / hose sizes (nominal DN, mm) ───────────────────
STD_PIPE_OD_MM = [6, 8, 10, 12, 16, 20, 25, 32, 38, 50, 63, 76, 100]
# Wall thickness for 420 bar steel tube (DIN 2391)
PIPE_WALL_MM: dict[int, float] = {
    6: 1.0, 8: 1.0, 10: 1.5, 12: 1.5, 16: 2.0, 20: 2.0,
    25: 2.5, 32: 3.0, 38: 4.0, 50: 5.0, 63: 6.0, 76: 7.0, 100: 8.0,
}

# ─── Hydraulic fluid properties (ISO VG 46 at 40°C) ──────────────────────────
FLUID_PROPS_HYD: dict[str, dict] = {
    "ISO VG 32 (40°C)":   {"rho": 855, "nu_cSt": 32,  "mu": 0.0274},
    "ISO VG 46 (40°C)":   {"rho": 865, "nu_cSt": 46,  "mu": 0.0398},
    "ISO VG 68 (40°C)":   {"rho": 875, "nu_cSt": 68,  "mu": 0.0595},
    "ISO VG 100 (40°C)":  {"rho": 885, "nu_cSt": 100, "mu": 0.0885},
    "Water-glycol 50%":   {"rho": 1060,"nu_cSt": 46,  "mu": 0.0488},
    "Phosphate ester":    {"rho": 1040,"nu_cSt": 46,  "mu": 0.0478},
}

# ─── Velocity limits per ISO 4413 ────────────────────────────────────────────
V_MAX: dict[str, float] = {
    "Pressure line":  4.0,   # m/s
    "Return line":    2.0,
    "Suction line":   1.0,
}


def _cylinder(bore_mm: float, rod_mm: float, P_bar: float,
              stroke_mm: float, flow_lpm: float = 0) -> dict:
    """Hydraulic cylinder force, speed, and flow."""
    D = bore_mm / 1000    # m
    d = rod_mm  / 1000

    A_cap  = math.pi * D**2 / 4              # cap-end area (m²)
    A_rod  = math.pi * (D**2 - d**2) / 4    # rod-end area (m²)
    P_Pa   = P_bar * 1e5

    F_extend  = P_Pa * A_cap    # N - extension
    F_retract = P_Pa * A_rod    # N - retraction

    # Speed if flow known
    Q_m3s = flow_lpm / 60000 if flow_lpm > 0 else 0
    v_extend  = Q_m3s / A_cap  if A_cap > 0 else 0    # m/s
    v_retract = Q_m3s / A_rod  if A_rod > 0 else 0

    # Time for stroke
    t_extend  = stroke_mm / 1000 / v_extend  if v_extend  > 0 else 0
    t_retract = stroke_mm / 1000 / v_retract if v_retract > 0 else 0

    # Flow required for given speed (if speed given instead)
    v_target = float(0)   # not used here - computed from flow

    return {
        "bore_mm":       bore_mm,
        "rod_mm":        rod_mm,
        "A_cap_cm2":     round(A_cap * 1e4, 3),
        "A_rod_cm2":     round(A_rod * 1e4, 3),
        "F_extend_kN":   round(F_extend / 1000, 2),
        "F_retract_kN":  round(F_retract / 1000, 2),
        "v_extend_m_s":  round(v_extend, 3),
        "v_retract_m_s": round(v_retract, 3),
        "t_extend_s":    round(t_extend, 3),
        "t_retract_s":   round(t_retract, 3),
    }


def _required_bore(F_kN: float, P_bar: float) -> int:
    """Select minimum standard bore for required force."""
    F_N  = F_kN * 1000
    P_Pa = P_bar * 1e5
    D_m  = math.sqrt(4 * F_N / (math.pi * P_Pa))
    D_mm = D_m * 1000
    return next((b for b in STD_BORE_MM if b >= D_mm), STD_BORE_MM[-1])


def _pump(Vg_cm3: float, n_rpm: float, eta_vol: float = 0.95,
          eta_mech: float = 0.92, eta_motor: float = 0.90,
          P_bar: float = 200) -> dict:
    """Hydraulic pump flow and power."""
    Q_lpm   = Vg_cm3 * n_rpm * eta_vol / 1000    # L/min
    Q_m3s   = Q_lpm / 60000
    P_hyd_kW = Q_m3s * P_bar * 1e5 / 1000        # kW
    P_shaft_kW = P_hyd_kW / (eta_vol * eta_mech)
    P_motor_kW = P_shaft_kW / eta_motor
    torque_Nm  = P_shaft_kW * 1000 / (2 * math.pi * n_rpm / 60)

    return {
        "Q_lpm":          round(Q_lpm, 2),
        "Q_m3hr":         round(Q_lpm * 60 / 1000, 3),
        "P_hydraulic_kW": round(P_hyd_kW, 3),
        "P_shaft_kW":     round(P_shaft_kW, 3),
        "P_motor_kW":     round(P_motor_kW, 3),
        "torque_Nm":      round(torque_Nm, 2),
        "eta_vol":        eta_vol,
        "eta_mech":       eta_mech,
    }


def _hydraulic_motor(Vg_cm3: float, Q_lpm: float,
                     P_bar: float, eta_vol: float = 0.95,
                     eta_mech: float = 0.92) -> dict:
    """Hydraulic motor speed, torque, and output power."""
    Q_m3s  = Q_lpm / 60000
    n_rpm  = Q_m3s * 1e6 * eta_vol / Vg_cm3 * 60 if Vg_cm3 > 0 else 0
    T_Nm   = Vg_cm3 * 1e-6 * P_bar * 1e5 * eta_mech / (2 * math.pi)
    P_out_kW = T_Nm * 2 * math.pi * n_rpm / 60 / 1000

    return {
        "n_rpm":         round(n_rpm, 1),
        "torque_Nm":     round(T_Nm, 2),
        "P_output_kW":   round(P_out_kW, 3),
    }


def _accumulator(P1_bar: float, P2_bar: float, P3_bar: float,
                 V_fluid_L: float) -> dict:
    """
    Bladder accumulator sizing (ISO 4413 / Parker).
    Boyle's law (isothermal): P0 V0 = P1 V1 = P2 V2
    P0 = pre-charge (N₂) = 0.9 × P1 (ISO recommendation)
    P1 = minimum working pressure, P2 = maximum (relief valve)
    V_fluid = usable fluid volume
    V_gas = total accumulator size
    """
    P0 = 0.9 * P1_bar   # pre-charge pressure (bar)
    # V_fluid = V1 - V2 = V0(P0/P1 - P0/P2)
    # V0 = V_fluid / (P0/P1 - P0/P2)
    if P2_bar <= P1_bar or P1_bar <= 0:
        return {"error": "P2 must be > P1 > 0"}
    V0_L = V_fluid_L / (P0 / P1_bar - P0 / P2_bar)

    # Standard accumulator sizes (L)
    std_acc_L = [0.5, 1, 1.5, 2, 3, 4, 6, 10, 16, 25, 32, 50, 80, 100]
    V_rec_L   = next((s for s in std_acc_L if s >= V0_L), std_acc_L[-1])

    return {
        "pre_charge_bar":    round(P0, 2),
        "V_required_L":      round(V0_L, 3),
        "V_recommended_L":   V_rec_L,
        "V_fluid_usable_L":  V_fluid_L,
    }


def _select_pipe(Q_lpm: float, line_type: str, fluid: dict, P_bar: float) -> dict:
    """Select hydraulic pipe/hose by velocity limit (ISO 4413)."""
    v_max = V_MAX.get(line_type, 4.0)
    Q_m3s = Q_lpm / 60000
    for od_mm in STD_PIPE_OD_MM:
        w_mm   = PIPE_WALL_MM.get(od_mm, 2.0)
        id_mm  = od_mm - 2 * w_mm
        A_m2   = math.pi * (id_mm / 2000)**2
        v      = Q_m3s / A_m2 if A_m2 > 0 else 999
        if v <= v_max:
            # Pressure drop: Darcy-Weisbach
            Re = fluid["rho"] * v * (id_mm / 1000) / fluid["mu"]
            if Re < 2300:
                f = 64 / Re if Re > 0 else 0.05
            else:
                f = 0.316 * Re**(-0.25)   # Blasius (turbulent, smooth)
            return {
                "od_mm":          od_mm,
                "id_mm":          round(id_mm, 1),
                "velocity_m_s":   round(v, 3),
                "Re":             round(Re, 0),
                "friction_factor": round(f, 5),
                "line_type":      line_type,
            }
    # fallback largest
    od_mm  = STD_PIPE_OD_MM[-1]
    w_mm   = PIPE_WALL_MM.get(od_mm, 8.0)
    id_mm  = od_mm - 2 * w_mm
    A_m2   = math.pi * (id_mm / 2000)**2
    v      = Q_m3s / A_m2 if A_m2 > 0 else 0
    return {"od_mm": od_mm, "id_mm": round(id_mm, 1),
            "velocity_m_s": round(v, 3), "line_type": line_type}


def calculate(inputs: dict) -> dict:
    """Main entry point - compatible with TypeScript calcFluidPower() keys."""
    calc_type  = str(inputs.get("calc_type", "Cylinder"))   # Cylinder / Pump / Motor / Accumulator / System

    fluid_key  = str  (inputs.get("fluid",           "ISO VG 46 (40°C)"))
    fluid_data = FLUID_PROPS_HYD.get(fluid_key, FLUID_PROPS_HYD["ISO VG 46 (40°C)"])
    P_bar      = float(inputs.get("system_pressure_bar", 200.0))
    Q_lpm      = float(inputs.get("flow_lpm",           40.0))

    results: dict = {"calc_type": calc_type, "fluid": fluid_key,
                     "system_pressure_bar": P_bar}

    # ── Cylinder ──────────────────────────────────────────────────────────────
    if calc_type in ("Cylinder", "System"):
        F_kN      = float(inputs.get("cylinder_force_kN",  50.0))
        bore_mm   = float(inputs.get("bore_mm",    0.0))
        rod_mm    = float(inputs.get("rod_mm",     0.0))
        stroke_mm = float(inputs.get("stroke_mm", 200.0))

        if bore_mm <= 0:
            bore_mm = _required_bore(F_kN, P_bar)
        if rod_mm <= 0:
            idx     = STD_BORE_MM.index(bore_mm) if bore_mm in STD_BORE_MM else 0
            rod_mm  = STD_ROD_MM[min(idx, len(STD_ROD_MM)-1)]

        cyl = _cylinder(bore_mm, rod_mm, P_bar, stroke_mm, Q_lpm)
        results["cylinder"] = cyl
        results["bore_selected_mm"] = bore_mm
        results["rod_selected_mm"]  = rod_mm

    # ── Pump ──────────────────────────────────────────────────────────────────
    if calc_type in ("Pump", "System"):
        Vg_cm3      = float(inputs.get("pump_displacement_cm3", 0.0))
        n_rpm       = float(inputs.get("pump_speed_rpm",        1450.0))
        eta_vol_p   = float(inputs.get("pump_eta_vol",          0.95))
        eta_mech_p  = float(inputs.get("pump_eta_mech",         0.92))
        eta_motor_p = float(inputs.get("motor_efficiency",      0.92))

        if Vg_cm3 <= 0:
            # Back-calculate required displacement from Q and n
            Q_m3s_req = Q_lpm / 60000
            Vg_req    = Q_m3s_req * 1e6 / (n_rpm * eta_vol_p)
            Vg_cm3    = next((s for s in STD_PUMP_DISPL_CM3 if s >= Vg_req),
                              STD_PUMP_DISPL_CM3[-1])

        pump = _pump(Vg_cm3, n_rpm, eta_vol_p, eta_mech_p, eta_motor_p, P_bar)
        results["pump"]            = pump
        results["pump_displacement_cm3"] = Vg_cm3

    # ── Hydraulic Motor ───────────────────────────────────────────────────────
    if calc_type == "Motor":
        Vg_cm3   = float(inputs.get("motor_displacement_cm3", 28.0))
        eta_vol  = float(inputs.get("motor_eta_vol",           0.95))
        eta_mech = float(inputs.get("motor_eta_mech",          0.92))
        motor    = _hydraulic_motor(Vg_cm3, Q_lpm, P_bar, eta_vol, eta_mech)
        results["motor"] = motor

    # ── Accumulator ───────────────────────────────────────────────────────────
    if calc_type in ("Accumulator", "System"):
        P1_bar    = float(inputs.get("P_min_bar",     150.0))
        P2_bar    = float(inputs.get("P_max_bar",     P_bar))
        P3_bar    = float(inputs.get("P_relief_bar",  P_bar * 1.1))
        V_fluid_L = float(inputs.get("V_fluid_L",     5.0))
        acc       = _accumulator(P1_bar, P2_bar, P3_bar, V_fluid_L)
        results["accumulator"] = acc

    # ── Pipe sizing (all types) ───────────────────────────────────────────────
    Q_use = results.get("pump", {}).get("Q_lpm", Q_lpm)
    results["pressure_line"] = _select_pipe(Q_use, "Pressure line", fluid_data, P_bar)
    results["return_line"]   = _select_pipe(Q_use, "Return line",   fluid_data, P_bar)
    results["suction_line"]  = _select_pipe(Q_use, "Suction line",  fluid_data, P_bar)

    results.update({
        "inputs_used": {
            "calc_type":   calc_type,
            "P_bar":       P_bar,
            "Q_lpm":       Q_lpm,
            "fluid":       fluid_key,
        },
        "calculation_source": "python/math",
        "standard": "ISO 4413:2010 | NFPA T2.12.10 | Bosch Rexroth Hydraulic Trainer | Parker Hydraulics",
    })
    return results
