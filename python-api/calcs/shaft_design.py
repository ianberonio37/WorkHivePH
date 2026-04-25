"""
Shaft Design - Phase 8a
Standards: ASME B106.1M (Design of Transmission Shafting),
           ASME B17.1 (Keys and Keyseats),
           Shigley's Mechanical Engineering Design (10th Ed.),
           NSCP 2015 / ASME standards as adopted in PH practice
Libraries: math (all formulas closed-form)

Methods:
  Static:  Von Mises combined stress σ' = √(σ² + 3τ²)
  Fatigue: ASME DE-Goodman criterion
    16/πd³ × √[(Kf×Ma)² + ¾(Kfs×Ta)²]^0.5 / Se
    + √[(Kf×Mm)² + ¾(Kfs×Tm)²]^0.5 / Sut ≤ 1/nf
  Deflection: δ = FL³/48EI (simply supported midpoint load)
  Critical speed: ωc = π²/L² × √(EI/ρA)  (Rayleigh-Ritz, simply supported)
"""

import math

# ─── Material properties (common shaft steels) ────────────────────────────────
SHAFT_MATERIALS: dict[str, dict] = {
    "AISI 1020 (HR)":     {"Sut_MPa": 380, "Sy_MPa": 210, "E_GPa": 207},
    "AISI 1040 (HR)":     {"Sut_MPa": 520, "Sy_MPa": 290, "E_GPa": 207},
    "AISI 1045 (HR)":     {"Sut_MPa": 570, "Sy_MPa": 310, "E_GPa": 207},
    "AISI 1045 (CD)":     {"Sut_MPa": 625, "Sy_MPa": 530, "E_GPa": 207},
    "AISI 4140 (Q&T)":    {"Sut_MPa": 965, "Sy_MPa": 830, "E_GPa": 207},
    "AISI 4340 (Q&T)":    {"Sut_MPa":1170, "Sy_MPa":1030, "E_GPa": 207},
    "AISI 303 SS":        {"Sut_MPa": 620, "Sy_MPa": 240, "E_GPa": 193},
    "AISI 316 SS":        {"Sut_MPa": 580, "Sy_MPa": 290, "E_GPa": 193},
}

# ─── Endurance limit modifiers (Shigley's §6) ────────────────────────────────
# Surface factor ka = a × Sut^b  (Shigley's Table 6-2)
SURFACE_FACTORS: dict[str, dict] = {
    "Ground":             {"a": 1.58,  "b": -0.085},
    "Machined / CD":      {"a": 4.51,  "b": -0.265},
    "HR (hot rolled)":    {"a": 57.7,  "b": -0.718},
    "Forged":             {"a": 272.0, "b": -0.995},
}

# ─── Stress concentration factors (Kf) - typical values (Shigley's Fig 6-20) ─
# Kf for bending; Kfs = 0.577×Kf for torsion (distortion energy)
STRESS_CONC: dict[str, dict] = {
    "Shoulder fillet (r/d=0.02)":  {"Kf": 2.7, "Kfs": 2.2},
    "Shoulder fillet (r/d=0.05)":  {"Kf": 2.1, "Kfs": 1.8},
    "Shoulder fillet (r/d=0.10)":  {"Kf": 1.7, "Kfs": 1.5},
    "Keyway (end-mill)":           {"Kf": 2.2, "Kfs": 3.0},
    "Keyway (profile)":            {"Kf": 1.6, "Kfs": 1.6},
    "Press fit (no key)":          {"Kf": 2.4, "Kfs": 2.4},
    "Snap ring groove":            {"Kf": 1.5, "Kfs": 1.5},
    "Smooth (no stress conc.)":    {"Kf": 1.0, "Kfs": 1.0},
}

# ─── Standard shaft diameters (mm) ───────────────────────────────────────────
STD_DIAMETERS_MM = [
    10, 12, 15, 17, 20, 22, 25, 28, 30, 32, 35, 38, 40, 42, 45,
    48, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 110, 120, 125,
    130, 140, 150, 160, 170, 180, 190, 200,
]

# Steel density kg/m³
RHO_STEEL = 7850.0


def _endurance_limit(mat: dict, surface: str, d_mm: float,
                     reliability_pct: float = 90.0) -> float:
    """
    Modified endurance limit Se (MPa) - Shigley's Eq. 6-18.
    Se = ka × kb × kc × kd × ke × Se'
    Se' = 0.5 × Sut (for steel, Sut ≤ 1400 MPa)
    """
    Sut = mat["Sut_MPa"]
    Se_prime = min(0.5 * Sut, 700)   # MPa

    # Surface factor ka
    sf = SURFACE_FACTORS.get(surface, SURFACE_FACTORS["Machined / CD"])
    ka = sf["a"] * (Sut ** sf["b"])

    # Size factor kb (Shigley's Eq. 6-20)
    d_in = d_mm / 25.4
    if d_in <= 0.3:
        kb = 1.0
    elif d_in <= 2.0:
        kb = 0.879 * d_in ** (-0.107)
    else:
        kb = 0.91 * d_in ** (-0.157)

    # Load factor kc: bending = 1.0
    kc = 1.0

    # Temperature factor kd: ≤70°C assumed
    kd = 1.0

    # Reliability factor ke (Shigley's Table 6-5)
    ke_map = {50: 1.000, 90: 0.897, 95: 0.868, 99: 0.814, 99.9: 0.753}
    ke = min(ke_map.items(), key=lambda x: abs(x[0] - reliability_pct))[1]

    Se = ka * kb * kc * kd * ke * Se_prime
    return max(Se, 10.0)   # floor


def _section_modulus(d_mm: float):
    """Returns (I in mm⁴, Z in mm³, J in mm⁴, Zp in mm³) for solid circular shaft."""
    r = d_mm / 2
    I  = math.pi * r**4 / 4
    Z  = I / r                   # = π d³ / 32
    J  = 2 * I
    Zp = J / r                   # = π d³ / 16
    return I, Z, J, Zp


def _goodman(d_mm: float, Ma_Nm: float, Mm_Nm: float,
             Ta_Nm: float, Tm_Nm: float,
             Kf: float, Kfs: float,
             Se_MPa: float, Sut_MPa: float) -> dict:
    """
    ASME DE-Goodman (Shigley's Eq. 6-41):
    σ'a = (16/πd³) × √[(Kf×Ma)² + ¾(Kfs×Ta)²]^0.5
    σ'm = (16/πd³) × √[(Kf×Mm)² + ¾(Kfs×Tm)²]^0.5
    n = 1 / (σ'a/Se + σ'm/Sut)
    """
    d_m = d_mm * 1e-3
    coeff = 16 / (math.pi * d_m**3)   # 1/m³ × 1e-6 → MPa conversion handled by units

    # Amplitudes
    Ma_Nm_f  = Kf  * abs(Ma_Nm)
    Ta_Nm_f  = Kfs * abs(Ta_Nm)
    Mm_Nm_f  = Kf  * abs(Mm_Nm)
    Tm_Nm_f  = Kfs * abs(Tm_Nm)

    # Convert Nm to N·mm for σ in MPa
    Ma_f  = Ma_Nm_f  * 1000
    Ta_f  = Ta_Nm_f  * 1000
    Mm_f  = Mm_Nm_f  * 1000
    Tm_f  = Tm_Nm_f  * 1000
    coeff_mm = 16 / (math.pi * d_mm**3)  # gives MPa directly

    sigma_a = coeff_mm * math.sqrt(Ma_f**2 + 0.75 * Ta_f**2)
    sigma_m = coeff_mm * math.sqrt(Mm_f**2 + 0.75 * Tm_f**2)

    lhs = sigma_a / Se_MPa + sigma_m / Sut_MPa
    nf  = 1 / lhs if lhs > 0 else 999

    # Von Mises yield check
    sigma_max = coeff_mm * math.sqrt((Ma_f + Mm_f)**2 + 0.75 * (Ta_f + Tm_f)**2)
    Sy_MPa    = Sut_MPa * 0.60   # approximate if not given
    ny        = Sy_MPa / sigma_max if sigma_max > 0 else 999

    return {
        "sigma_a_MPa":  round(sigma_a, 2),
        "sigma_m_MPa":  round(sigma_m, 2),
        "nf_goodman":   round(nf, 3),
        "ny_yield":     round(ny, 3),
        "fatigue_ok":   nf >= 1.5,
        "yield_ok":     ny >= 1.5,
    }


def calculate(inputs: dict) -> dict:
    """Main entry point - compatible with TypeScript calcShaftDesign() keys."""
    # ── Loads ─────────────────────────────────────────────────────────────────
    power_kW     = float(inputs.get("power_kW",     10.0))
    speed_rpm    = float(inputs.get("speed_rpm",    1450))
    span_m       = float(inputs.get("span_m",       0.5))    # bearing-to-bearing
    radial_load_N = float(inputs.get("radial_load_N", 0.0))  # external radial force at midspan

    # Computed torque
    T_Nm = power_kW * 1000 / (2 * math.pi * speed_rpm / 60) if speed_rpm > 0 else 0.0
    T_Nm += float(inputs.get("torque_Nm_extra", 0.0))

    # Bending moment at critical section (midspan of simply supported shaft)
    # M_midspan = F × L / 4 (point load at midspan)
    M_Nm = radial_load_N * span_m / 4

    # Mean + alternating components (fully reversed bending, steady torque - Shigley's)
    Ma_Nm = M_Nm     # fully reversed bending → Ma = M, Mm = 0
    Mm_Nm = 0.0
    Ta_Nm = 0.0      # steady torque → Tm = T, Ta = 0
    Tm_Nm = T_Nm

    # ── Material ──────────────────────────────────────────────────────────────
    mat_key     = str(inputs.get("material",        "AISI 1045 (HR)"))
    mat         = SHAFT_MATERIALS.get(mat_key, SHAFT_MATERIALS["AISI 1045 (HR)"])
    surface     = str(inputs.get("surface_finish",  "Machined / CD"))
    reliability = float(inputs.get("reliability_pct", 90.0))

    # ── Stress concentration ──────────────────────────────────────────────────
    conc_key  = str(inputs.get("stress_concentration", "Shoulder fillet (r/d=0.05)"))
    conc_data = STRESS_CONC.get(conc_key, STRESS_CONC["Shoulder fillet (r/d=0.05)"])
    Kf   = conc_data["Kf"]
    Kfs  = conc_data["Kfs"]

    # ── Safety factors requested ──────────────────────────────────────────────
    n_design  = float(inputs.get("safety_factor",   2.0))

    # ── Endurance limit ───────────────────────────────────────────────────────
    # First pass with d=25mm estimate for kb
    d_est = float(inputs.get("shaft_diameter_mm", 0.0))
    Se_est = _endurance_limit(mat, surface, d_est if d_est > 0 else 25.0, reliability)

    # ── Minimum diameter from DE-Goodman (Shigley's Eq. 6-42 rearranged) ─────
    # d³ = (16 n / π) × √[(Kf Ma/Se)² + ¾(Kfs Ta/Se)²]^0.5
    #       + [(Kf Mm/Sut)² + ¾(Kfs Tm/Sut)²]^0.5  ... rearranged
    # Simplified: solve iteratively - d from combined amplitude
    Sut = mat["Sut_MPa"]
    Ma_f   = Kf  * abs(Ma_Nm)  * 1000   # N·mm
    Ta_f   = Kfs * abs(Ta_Nm)  * 1000
    Mm_f   = Kf  * abs(Mm_Nm)  * 1000
    Tm_f   = Kfs * abs(Tm_Nm)  * 1000

    A_coeff = math.sqrt(Ma_f**2 + 0.75 * Ta_f**2)
    B_coeff = math.sqrt(Mm_f**2 + 0.75 * Tm_f**2)

    # d³ = 16 n_design / π × (A/Se + B/Sut)  [mm³]
    d_min_mm3 = 16 * n_design / math.pi * (A_coeff / Se_est + B_coeff / Sut)
    d_min_mm  = d_min_mm3 ** (1/3)

    # Select standard size
    d_std_mm = next((s for s in STD_DIAMETERS_MM if s >= d_min_mm), STD_DIAMETERS_MM[-1])
    d_used   = d_est if d_est > 0 else d_std_mm

    # Recompute Se with actual diameter
    Se = _endurance_limit(mat, surface, d_used, reliability)

    # ── Goodman check at selected diameter ────────────────────────────────────
    goodman = _goodman(d_used, Ma_Nm, Mm_Nm, Ta_Nm, Tm_Nm, Kf, Kfs, Se, Sut)

    # ── Deflection ────────────────────────────────────────────────────────────
    E_Pa  = mat["E_GPa"] * 1e9
    r_m   = d_used / 2000
    I_m4  = math.pi * r_m**4 / 4
    # δ_max = FL³/(48EI) - point load at midspan
    delta_mm = (radial_load_N * span_m**3 / (48 * E_Pa * I_m4)) * 1000 if span_m > 0 else 0
    delta_limit_mm = span_m * 1000 / 3000   # L/3000 typical shaft limit

    # ── Critical speed (Rayleigh-Ritz - simply supported) ─────────────────────
    A_m2  = math.pi * r_m**2
    rho   = RHO_STEEL
    # ωc = (π/L)² × √(EI / ρA)   rad/s
    if span_m > 0:
        omega_c = (math.pi / span_m)**2 * math.sqrt(E_Pa * I_m4 / (rho * A_m2))
        nc_rpm  = omega_c * 60 / (2 * math.pi)
    else:
        nc_rpm = 999999
    speed_ratio = speed_rpm / nc_rpm if nc_rpm > 0 else 0
    critical_ok = speed_ratio < 0.8   # operate below 80% of critical speed

    # ── Keyway check (ASME B17.1) ────────────────────────────────────────────
    # Recommended key size: w = d/4, h = d/6
    key_w_mm = round(d_used / 4, 1)
    key_h_mm = round(d_used / 6, 1)
    # Shear stress in key: τ_key = T / (A_shear × r_shaft)
    # A_shear = key_w × key_length; use key_length = 1.5×d as default
    key_len_mm = inputs.get("key_length_mm", 1.5 * d_used)
    A_key_mm2  = key_w_mm * key_len_mm
    tau_key    = (abs(T_Nm) * 1000) / (A_key_mm2 * (d_used / 2)) if A_key_mm2 > 0 else 0
    Ssy        = 0.577 * mat["Sy_MPa"]   # distortion energy shear yield
    n_key      = Ssy / tau_key if tau_key > 0 else 999

    return {
        # Loads
        "power_kW":          power_kW,
        "speed_rpm":         speed_rpm,
        "torque_Nm":         round(T_Nm, 2),
        "bending_moment_Nm": round(M_Nm, 2),

        # Material
        "material":          mat_key,
        "Sut_MPa":           mat["Sut_MPa"],
        "Sy_MPa":            mat["Sy_MPa"],
        "Se_MPa":            round(Se, 2),

        # Sizing
        "d_min_mm":          round(d_min_mm, 2),
        "d_standard_mm":     d_std_mm,
        "d_used_mm":         d_used,

        # Fatigue (DE-Goodman)
        **goodman,
        "Kf":                Kf,
        "Kfs":               Kfs,

        # Deflection
        "deflection_mm":     round(delta_mm, 4),
        "deflection_limit_mm": round(delta_limit_mm, 3),
        "deflection_ok":     delta_mm <= delta_limit_mm,

        # Critical speed
        "critical_speed_rpm": round(nc_rpm, 0),
        "speed_ratio":        round(speed_ratio, 3),
        "critical_speed_ok":  critical_ok,

        # Key
        "key_width_mm":      key_w_mm,
        "key_height_mm":     key_h_mm,
        "tau_key_MPa":       round(tau_key, 2),
        "n_key":             round(n_key, 2),
        "key_ok":            n_key >= 1.5,

        # Metadata
        "inputs_used": {
            "power_kW":    power_kW,
            "speed_rpm":   speed_rpm,
            "material":    mat_key,
            "span_m":      span_m,
        },
        "calculation_source": "python/math",
        "standard": "ASME B106.1M | ASME B17.1 | Shigley's MED 10th Ed.",
    }
