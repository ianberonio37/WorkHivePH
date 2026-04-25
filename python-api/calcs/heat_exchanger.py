"""
Heat Exchanger Design - Phase 8d
Standards: TEMA (Tubular Exchanger Manufacturers Association) 10th Ed.,
           ASME Sec. VIII Div.1 (pressure parts),
           HEDH (Heat Exchanger Design Handbook),
           Kern's Process Heat Transfer (McGraw-Hill),
           VDI Heat Atlas
Libraries: math (all formulas closed-form)

Methods:
  LMTD method:    Q = U × A × F × LMTD
  NTU-ε method:   ε = f(NTU, Cr) - shell-and-tube, counterflow, crossflow
  TEMA fouling resistances Rd
  Tube-side and shell-side heat transfer coefficients (Dittus-Boelter / Kern)
  Tube bundle layout, shell diameter estimate
"""

import math

# ─── TEMA fouling resistances (m²·K/W) Table R-2.4 ───────────────────────────
FOULING_FACTORS: dict[str, float] = {
    "Clean water (city/demin)":    0.0001,
    "River water (clean)":         0.0002,
    "Seawater (< 43°C)":           0.0001,
    "Seawater (> 43°C)":           0.0002,
    "Cooling tower water (treated)": 0.0002,
    "Boiler feed water (treated)": 0.0001,
    "Steam (clean)":               0.0001,
    "Process fluid (clean organic)": 0.0002,
    "Process fluid (light oil)":   0.0003,
    "Process fluid (heavy oil)":   0.0005,
    "Refrigerants (liquid)":       0.0001,
    "Air / Gas (clean)":           0.0002,
    "Crude oil (< 120°C)":         0.0005,
}

# ─── TEMA shell types ─────────────────────────────────────────────────────────
TEMA_SHELLS = {
    "E (single pass)":      {"F_correction": 0.95, "passes": 1},
    "F (two pass)":         {"F_correction": 1.00, "passes": 2},
    "G (split flow)":       {"F_correction": 0.85, "passes": 1},
    "H (double split)":     {"F_correction": 0.90, "passes": 1},
    "J (divided flow)":     {"F_correction": 0.88, "passes": 1},
    "X (crossflow)":        {"F_correction": 0.80, "passes": 1},
}

# ─── Standard tube OD sizes (mm) ─────────────────────────────────────────────
STD_TUBE_OD_MM = [12.7, 15.875, 19.05, 25.4, 31.75, 38.1, 50.8]
STD_BWG: dict[str, dict] = {
    # tube OD: {BWG: wall thickness mm}
    "19.05": {16: 1.65, 14: 2.11, 12: 2.77},
    "25.40": {16: 1.65, 14: 2.11, 12: 2.77, 10: 3.40},
}

# ─── Fluid properties at typical process temperatures ─────────────────────────
# rho (kg/m³), Cp (kJ/kg·K), mu (Pa·s), k (W/m·K), Pr
FLUID_PROPS: dict[str, dict] = {
    "Water (30°C)":          {"rho": 996,  "Cp": 4.18, "mu": 7.97e-4, "k": 0.615, "Pr": 5.42},
    "Water (60°C)":          {"rho": 983,  "Cp": 4.18, "mu": 4.67e-4, "k": 0.651, "Pr": 3.00},
    "Water (90°C)":          {"rho": 965,  "Cp": 4.21, "mu": 3.14e-4, "k": 0.675, "Pr": 1.95},
    "Ethylene glycol 50%":   {"rho": 1065, "Cp": 3.56, "mu": 2.0e-3,  "k": 0.415, "Pr": 17.2},
    "Light oil (60°C)":      {"rho": 840,  "Cp": 2.10, "mu": 3.0e-3,  "k": 0.145, "Pr": 43.4},
    "Air (20°C, 1 atm)":     {"rho": 1.20, "Cp": 1.005,"mu": 1.82e-5, "k": 0.0257,"Pr": 0.713},
    "Steam (150°C, 5 bar)":  {"rho": 2.67, "Cp": 2.06, "mu": 1.43e-5, "k": 0.0286,"Pr": 1.03},
    "R-410A liquid (5°C)":   {"rho": 1085, "Cp": 1.60, "mu": 1.7e-4,  "k": 0.105, "Pr": 2.6},
    "R-134a liquid (10°C)":  {"rho": 1195, "Cp": 1.40, "mu": 2.0e-4,  "k": 0.092, "Pr": 3.1},
}

# ─── Standard heat exchanger areas (m²) - TEMA ────────────────────────────────
STD_AREAS_M2 = [5, 10, 15, 20, 30, 40, 50, 75, 100, 150, 200, 300, 500]


def _lmtd(T_hi: float, T_ho: float, T_ci: float, T_co: float,
          flow_config: str = "Counterflow") -> float:
    """
    Log Mean Temperature Difference (K).
    Counterflow: ΔT1 = Th_in − Tc_out, ΔT2 = Th_out − Tc_in
    Parallel:    ΔT1 = Th_in − Tc_in,  ΔT2 = Th_out − Tc_out
    """
    if flow_config == "Counterflow":
        dT1 = T_hi - T_co
        dT2 = T_ho - T_ci
    else:  # Parallel
        dT1 = T_hi - T_ci
        dT2 = T_ho - T_co

    if abs(dT1 - dT2) < 1e-6:
        return dT1
    if dT1 <= 0 or dT2 <= 0:
        return abs(dT1 - dT2) / 2   # prevent log of negative/zero
    return (dT1 - dT2) / math.log(dT1 / dT2)


def _ntu_effectiveness(NTU: float, Cr: float, config: str = "Counterflow") -> float:
    """
    NTU-effectiveness relations (Incropera, Table 11.4).
    Cr = C_min / C_max
    """
    if config == "Counterflow":
        if abs(Cr - 1.0) < 1e-6:
            return NTU / (1 + NTU)
        exp = math.exp(-NTU * (1 - Cr))
        return (1 - exp) / (1 - Cr * exp)
    elif config == "Parallel":
        return (1 - math.exp(-NTU * (1 + Cr))) / (1 + Cr)
    elif config == "Shell-and-tube (1-2)":
        # Bowman et al. correction for 1 shell pass, 2 tube passes
        exp = math.exp(-NTU * math.sqrt(1 + Cr**2))
        return 2 / (1 + Cr + math.sqrt(1 + Cr**2) * (1 + exp) / (1 - exp))
    else:
        # Crossflow (both unmixed - approximate)
        return 1 - math.exp((NTU**0.22 / Cr) * (math.exp(-Cr * NTU**0.78) - 1))


def _dittus_boelter(Re: float, Pr: float, heating: bool = False) -> float:
    """
    Dittus-Boelter equation: Nu = 0.023 Re^0.8 Pr^n
    n = 0.4 (heating), 0.3 (cooling)
    Valid: Re > 10000, 0.6 ≤ Pr ≤ 160, L/D > 10
    """
    n = 0.4 if heating else 0.3
    return 0.023 * Re**0.8 * Pr**n


def _tube_side_h(m_dot: float, n_tubes: int, n_passes: int,
                 d_i_mm: float, props: dict) -> dict:
    """
    Tube-side heat transfer coefficient h (W/m²·K).
    Uses Dittus-Boelter; flags laminar (Re < 10000) for Sieder-Tate correction.
    """
    A_tube = math.pi * (d_i_mm / 2000)**2    # m² per tube
    n_tubes_per_pass = max(n_tubes // n_passes, 1)
    G = m_dot / (n_tubes_per_pass * A_tube)   # kg/m²·s
    Re = G * (d_i_mm / 1000) / props["mu"]
    Pr = props["Cp"] * 1000 * props["mu"] / props["k"]
    laminar = Re < 4000

    if not laminar and Re >= 10000:
        Nu = _dittus_boelter(Re, Pr, heating=True)
    elif laminar:
        # Sieder-Tate laminar: Nu = 1.86 (Re Pr d/L)^1/3
        L_D = 50   # assumed L/D
        Nu  = 1.86 * (Re * Pr / L_D)**(1/3)
    else:
        # Transition: interpolate
        Nu = 0.023 * Re**0.8 * Pr**0.4

    h = Nu * props["k"] / (d_i_mm / 1000)
    return {"Re": round(Re, 0), "Nu": round(Nu, 2), "h_W_m2K": round(h, 1),
            "laminar": laminar, "Pr_tube": round(Pr, 2)}


def _overall_U(h_i: float, h_o: float,
               d_i_mm: float, d_o_mm: float,
               k_wall: float,
               Rd_i: float, Rd_o: float) -> float:
    """
    Overall heat transfer coefficient U (W/m²·K) based on outer area.
    1/U = 1/ho + Rdo + (do/2k)ln(do/di) + (do/di)(Rdi + 1/hi)
    """
    d_i = d_i_mm / 1000
    d_o = d_o_mm / 1000
    t_wall = (d_o - d_i) / 2
    R_wall  = (d_o / (2 * k_wall)) * math.log(d_o / d_i) if d_i > 0 else 0
    inv_U = (1/h_o + Rd_o + R_wall + (d_o/d_i) * (Rd_i + 1/h_i))
    return 1 / inv_U if inv_U > 0 else 0


def calculate(inputs: dict) -> dict:
    """Main entry point - compatible with TypeScript calcHeatExchanger() keys."""
    # ── Process conditions ────────────────────────────────────────────────────
    Q_kW         = float(inputs.get("duty_kW",           500.0))   # heat duty

    # Hot side
    T_hi         = float(inputs.get("hot_inlet_C",        90.0))
    T_ho         = float(inputs.get("hot_outlet_C",        60.0))
    m_hot        = float(inputs.get("hot_flowrate_kgs",    10.0))   # kg/s
    hot_fluid    = str  (inputs.get("hot_fluid",           "Water (90°C)"))
    fouling_hot  = str  (inputs.get("fouling_hot",         "Cooling tower water (treated)"))

    # Cold side
    T_ci         = float(inputs.get("cold_inlet_C",        25.0))
    T_co         = float(inputs.get("cold_outlet_C",       55.0))
    m_cold       = float(inputs.get("cold_flowrate_kgs",   8.0))
    cold_fluid   = str  (inputs.get("cold_fluid",          "Water (30°C)"))
    fouling_cold = str  (inputs.get("fouling_cold",        "Cooling tower water (treated)"))

    # ── Flow configuration ────────────────────────────────────────────────────
    config       = str  (inputs.get("flow_config",         "Counterflow"))
    shell_type   = str  (inputs.get("shell_type",          "E (single pass)"))
    n_tube_passes = int (inputs.get("tube_passes",          2))

    # ── Tube geometry ─────────────────────────────────────────────────────────
    d_o_mm       = float(inputs.get("tube_od_mm",          19.05))
    wall_mm      = float(inputs.get("wall_thickness_mm",    2.11))
    d_i_mm       = d_o_mm - 2 * wall_mm
    tube_length_m = float(inputs.get("tube_length_m",       3.0))
    pitch_ratio   = float(inputs.get("pitch_ratio",         1.25))   # triangular
    pitch_mm      = d_o_mm * pitch_ratio

    # ── Material ──────────────────────────────────────────────────────────────
    k_wall_map = {"Carbon Steel": 50, "Stainless Steel 316": 16,
                  "Copper": 385, "Admiralty Brass": 111, "Titanium": 21}
    tube_mat   = str(inputs.get("tube_material", "Stainless Steel 316"))
    k_wall     = k_wall_map.get(tube_mat, 16)

    # ── Fluid properties ──────────────────────────────────────────────────────
    hot_props  = FLUID_PROPS.get(hot_fluid,  FLUID_PROPS["Water (90°C)"])
    cold_props = FLUID_PROPS.get(cold_fluid, FLUID_PROPS["Water (30°C)"])

    # ── Duty check ────────────────────────────────────────────────────────────
    Q_hot  = m_hot  * hot_props["Cp"]  * abs(T_hi - T_ho)   # kW
    Q_cold = m_cold * cold_props["Cp"] * abs(T_co - T_ci)   # kW
    Q_duty = Q_kW if Q_kW > 0 else (Q_hot + Q_cold) / 2
    heat_balance_ok = abs(Q_hot - Q_cold) / Q_duty < 0.10 if Q_duty > 0 else True

    # ── LMTD ──────────────────────────────────────────────────────────────────
    lmtd_val  = _lmtd(T_hi, T_ho, T_ci, T_co, config)
    F_factor  = TEMA_SHELLS.get(shell_type, TEMA_SHELLS["E (single pass)"])["F_correction"]
    lmtd_corr = lmtd_val * F_factor

    # ── NTU-ε method ──────────────────────────────────────────────────────────
    C_hot  = m_hot  * hot_props["Cp"]   * 1000   # W/K
    C_cold = m_cold * cold_props["Cp"]  * 1000
    C_min  = min(C_hot, C_cold)
    C_max  = max(C_hot, C_cold)
    Cr     = C_min / C_max if C_max > 0 else 0
    Q_max  = C_min * (T_hi - T_ci)   # W
    epsilon = Q_duty * 1000 / Q_max if Q_max > 0 else 0
    epsilon = min(epsilon, 0.99)

    # NTU from effectiveness
    if config in ["Counterflow"] and abs(Cr - 1.0) > 1e-4:
        NTU = math.log((epsilon - 1) / (epsilon * Cr - 1)) / (Cr - 1) if abs(epsilon * Cr - 1) > 1e-6 else epsilon
    else:
        NTU = -math.log(1 - epsilon * (1 + Cr)) / (1 + Cr) if (1 - epsilon * (1 + Cr)) > 0 else 5

    # ── Fouling resistances ───────────────────────────────────────────────────
    Rd_i = FOULING_FACTORS.get(fouling_cold, 0.0002)   # tube-side (cold)
    Rd_o = FOULING_FACTORS.get(fouling_hot,  0.0002)   # shell-side (hot)

    # ── Tube-side h (cold fluid inside tubes) ────────────────────────────────
    # Initial estimate: assume 100 tubes per pass
    n_tubes_est = 100
    tube_h_data = _tube_side_h(m_cold, n_tubes_est, n_tube_passes, d_i_mm, cold_props)
    h_i = tube_h_data["h_W_m2K"]

    # ── Shell-side h (hot fluid, Kern method simplified) ─────────────────────
    # De = 1.10/pitch × (pitch² − 0.917 d_o²)  for triangular pitch
    De_mm = 1.10 / d_o_mm * (pitch_mm**2 - 0.917 * d_o_mm**2) if d_o_mm > 0 else d_o_mm
    De_mm = max(De_mm, 5.0)

    # Estimate shell diameter from n_tubes
    n_tubes_shell = n_tubes_est
    Ds_mm = 1.15 * pitch_mm * math.sqrt(n_tubes_shell)   # triangular rough estimate
    # Shell cross-section area at baffle: As = Ds × C' × B / pitch
    C_prime = pitch_mm - d_o_mm   # clearance
    B_mm    = 0.25 * Ds_mm        # baffle spacing = 25% of Ds
    As_m2   = Ds_mm / 1000 * C_prime / 1000 * B_mm / 1000 / (pitch_mm / 1000)
    Gs      = m_hot / As_m2 if As_m2 > 0 else 0   # kg/m²·s
    Re_s    = Gs * (De_mm / 1000) / hot_props["mu"]
    Pr_s    = hot_props["Cp"] * 1000 * hot_props["mu"] / hot_props["k"]
    # Kern j-factor: jH ≈ 0.36 Re^−0.44 (simplified for baffled shell)
    jH      = 0.36 * Re_s**(-0.44) if Re_s > 0 else 0.01
    Nu_s    = jH * Re_s * Pr_s**(1/3)
    h_o     = Nu_s * hot_props["k"] / (De_mm / 1000) if De_mm > 0 else 1000

    # ── Overall U ────────────────────────────────────────────────────────────
    U_design = _overall_U(h_i, h_o, d_i_mm, d_o_mm, k_wall, Rd_i, Rd_o)
    # Clean U (no fouling)
    U_clean  = _overall_U(h_i, h_o, d_i_mm, d_o_mm, k_wall, 0, 0)

    # ── Required area ─────────────────────────────────────────────────────────
    A_req_m2 = Q_duty * 1000 / (U_design * lmtd_corr) if (U_design * lmtd_corr) > 0 else 999
    A_std_m2 = next((s for s in STD_AREAS_M2 if s >= A_req_m2), STD_AREAS_M2[-1])

    # ── Number of tubes ───────────────────────────────────────────────────────
    A_per_tube = math.pi * d_o_mm / 1000 * tube_length_m
    n_tubes    = math.ceil(A_req_m2 / A_per_tube) if A_per_tube > 0 else 0
    # Correct tube-side h with actual tube count
    tube_h_data = _tube_side_h(m_cold, max(n_tubes, 1), n_tube_passes, d_i_mm, cold_props)

    # Shell diameter estimate (triangular pitch)
    Ds_est_mm = 1.15 * pitch_mm * math.sqrt(n_tubes)

    # ── Compliance notes ──────────────────────────────────────────────────────
    code_notes = [
        f"Duty: {round(Q_duty,1)} kW | LMTD: {round(lmtd_val,2)} K → "
        f"corrected {round(lmtd_corr,2)} K (F={F_factor}, {shell_type}).",
        f"U_design = {round(U_design,1)} W/m²·K (fouling Rd_i={Rd_i}, Rd_o={Rd_o} m²K/W).",
        f"U_clean  = {round(U_clean,1)} W/m²·K.",
        f"A_required = {round(A_req_m2,2)} m² → recommended standard size {A_std_m2} m².",
        f"n_tubes ≈ {n_tubes} × {d_o_mm}mm OD × {tube_length_m}m (estimated).",
        f"Estimated shell ID ≈ {round(Ds_est_mm,0)} mm (triangular pitch {round(pitch_mm,1)}mm).",
        f"Tube-side Re = {tube_h_data['Re']} ({'LAMINAR - use Sieder-Tate' if tube_h_data['laminar'] else 'turbulent - Dittus-Boelter'}).",
        f"NTU = {round(NTU,3)}, ε = {round(epsilon,3)}, Cr = {round(Cr,3)}.",
        "TEMA class R (severe service) or C (general) - specify on data sheet.",
        "Heat balance check: " + ('PASS' if heat_balance_ok else 'WARN - hot/cold duties differ > 10%'),
    ]

    return {
        # Process
        "duty_kW":               round(Q_duty, 2),
        "Q_hot_kW":              round(Q_hot, 2),
        "Q_cold_kW":             round(Q_cold, 2),
        "heat_balance_ok":       heat_balance_ok,

        # LMTD
        "lmtd_K":                round(lmtd_val, 3),
        "F_correction":          F_factor,
        "lmtd_corrected_K":      round(lmtd_corr, 3),

        # NTU-ε
        "NTU":                   round(NTU, 3),
        "effectiveness":         round(epsilon, 4),
        "Cr":                    round(Cr, 4),

        # Heat transfer
        "h_tube_side_W_m2K":     tube_h_data["h_W_m2K"],
        "Re_tube":               tube_h_data["Re"],
        "Pr_tube":               tube_h_data["Pr_tube"],
        "tube_flow_regime":      "Laminar" if tube_h_data["laminar"] else "Turbulent",
        "h_shell_side_W_m2K":    round(h_o, 1),
        "Re_shell":              round(Re_s, 0),

        # Overall U
        "U_design_W_m2K":        round(U_design, 1),
        "U_clean_W_m2K":         round(U_clean, 1),
        "Rd_tube_m2KW":          Rd_i,
        "Rd_shell_m2KW":         Rd_o,

        # Sizing
        "A_required_m2":         round(A_req_m2, 2),
        "A_standard_m2":         A_std_m2,
        "n_tubes":               n_tubes,
        "tube_od_mm":            d_o_mm,
        "tube_id_mm":            round(d_i_mm, 2),
        "tube_length_m":         tube_length_m,
        "shell_id_estimate_mm":  round(Ds_est_mm, 0),
        "pitch_mm":              round(pitch_mm, 2),

        # Notes
        "code_notes":            code_notes,

        # Metadata
        "inputs_used": {
            "duty_kW":           Q_duty,
            "hot_inlet_C":       T_hi,
            "hot_outlet_C":      T_ho,
            "cold_inlet_C":      T_ci,
            "cold_outlet_C":     T_co,
            "flow_config":       config,
            "shell_type":        shell_type,
        },
        "calculation_source": "python/math",
        "standard": "TEMA 10th Ed. | ASME Sec. VIII Div.1 | Kern Process Heat Transfer | VDI Heat Atlas",
    }
