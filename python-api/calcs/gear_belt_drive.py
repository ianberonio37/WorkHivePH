"""
Gear / Belt Drive - Phase 8b
Standards: AGMA 2001-D04 (Fundamental Rating Factors for Involute Spur/Helical Gears),
           AGMA 6006-A03 (Design of Worm Gearings),
           ISO 6336 (Gear load capacity),
           RMA IP-20 (Narrow V-Belt Drives),
           Shigley's Mechanical Engineering Design (10th Ed. Ch.13-17)
Libraries: math (all formulas closed-form)

Methods:
  Spur/helical gear: AGMA bending (Lewis) + contact (Hertz) stress
  V-belt drive: belt length, number of belts, power per belt
  Chain drive: chain number selection, sprocket pitch diameter, chain length
"""

import math

# ─── AGMA material grades and allowable stresses ──────────────────────────────
GEAR_MATERIALS: dict[str, dict] = {
    "Grade 1 Steel (through-hardened HB180)":   {"sat_MPa":  190, "sac_MPa":  720, "HB": 180},
    "Grade 2 Steel (through-hardened HB300)":   {"sat_MPa":  260, "sac_MPa": 1000, "HB": 300},
    "Grade 3 Steel (carburized/case HRC58)":    {"sat_MPa":  380, "sac_MPa": 1380, "HB": 580},
    "Cast Iron (AGMA Grade 1)":                 {"sat_MPa":   55, "sac_MPa":  380, "HB": 200},
    "Ductile Iron (Grade 2)":                   {"sat_MPa":  170, "sac_MPa":  520, "HB": 250},
    "Bronze (worm wheel)":                      {"sat_MPa":   70, "sac_MPa":  260, "HB": 150},
}

# ─── AGMA overload factor Ko by load type ────────────────────────────────────
Ko_FACTORS: dict[str, float] = {
    "Uniform":               1.00,
    "Light shock":           1.25,
    "Medium shock":          1.50,
    "Heavy shock":           1.75,
}

# ─── AGMA dynamic factor Kv (Barth equation, module ≥ 1) ─────────────────────
# Kv = B + (200/(200 + V))^B  - V in m/s, B = 0.25*(12-Qv)^(2/3) for AGMA quality Qv

# ─── V-belt section data (RMA/MPTA standard - narrow belts) ──────────────────
VBELT_SECTIONS: dict[str, dict] = {
    "3V (9N)":  {"width_mm": 9,   "depth_mm":  8,   "Pd_max_kW": 5.5,  "Pt_min_kW": 0.4},
    "5V (15N)": {"width_mm": 15,  "depth_mm": 13,   "Pd_max_kW": 22,   "Pt_min_kW": 1.5},
    "8V (25N)": {"width_mm": 25,  "depth_mm": 23,   "Pd_max_kW": 75,   "Pt_min_kW": 7.5},
    "A (13)":   {"width_mm": 13,  "depth_mm":  8,   "Pd_max_kW": 3.7,  "Pt_min_kW": 0.2},
    "B (17)":   {"width_mm": 17,  "depth_mm": 11,   "Pd_max_kW": 7.5,  "Pt_min_kW": 0.5},
    "C (22)":   {"width_mm": 22,  "depth_mm": 14,   "Pd_max_kW": 18.5, "Pt_min_kW": 1.5},
    "D (32)":   {"width_mm": 32,  "depth_mm": 19,   "Pd_max_kW": 55,   "Pt_min_kW": 7.5},
}

# ─── Standard roller chain (ANSI B29.1) ──────────────────────────────────────
CHAIN_NUMBERS: dict[str, dict] = {
    "25":   {"pitch_mm":  6.35,  "Pr_kN":  3.56},
    "35":   {"pitch_mm":  9.525, "Pr_kN":  7.78},
    "40":   {"pitch_mm": 12.70,  "Pr_kN": 14.10},
    "50":   {"pitch_mm": 15.875, "Pr_kN": 21.80},
    "60":   {"pitch_mm": 19.05,  "Pr_kN": 31.10},
    "80":   {"pitch_mm": 25.40,  "Pr_kN": 55.60},
    "100":  {"pitch_mm": 31.75,  "Pr_kN": 86.70},
    "120":  {"pitch_mm": 38.10,  "Pr_kN": 127.0},
    "140":  {"pitch_mm": 44.45,  "Pr_kN": 170.0},
    "160":  {"pitch_mm": 50.80,  "Pr_kN": 222.0},
}

# ─── Standard module series (ISO 54 / AGMA) ──────────────────────────────────
STD_MODULES = [1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10, 12, 16, 20]


def _agma_kv(V_ms: float, Qv: int = 6) -> float:
    """AGMA dynamic factor Kv (Barth equation for cut/shaved gears, Qv 3-12)."""
    B = 0.25 * (12 - Qv) ** (2/3)
    A = 50 + 56 * (1 - B)
    Kv = ((A + math.sqrt(200 * V_ms)) / A) ** B
    return Kv


def _spur_gear(module_mm: float, N_pinion: int, N_gear: int,
               F_mm: float, power_kW: float, n_rpm: float,
               mat_pinion: dict, mat_gear: dict,
               Ko: float = 1.25, Qv: int = 6,
               pressure_angle_deg: float = 20.0) -> dict:
    """
    AGMA 2001-D04 spur gear bending and contact stress.
    Returns: St (bending), Sc (contact), safety factors.
    """
    phi  = math.radians(pressure_angle_deg)
    m    = module_mm                        # mm
    d_p  = m * N_pinion                     # pitch dia pinion (mm)
    d_g  = m * N_gear                       # pitch dia gear (mm)
    r_p  = d_p / 2
    r_g  = d_g / 2

    # Pitch line velocity
    V_ms = math.pi * d_p / 1000 * n_rpm / 60   # m/s

    # Transmitted tangential force
    W_t_N = power_kW * 1000 / V_ms if V_ms > 0 else 0   # N

    # AGMA geometry factor J (Lewis form factor approximation for 20° full-depth)
    # J ≈ 0.32 + 0.0033*N (for 20°, N=12-200, simplified)
    J_p = 0.32 + 0.0033 * N_pinion
    J_g = 0.32 + 0.0033 * N_gear

    # Dynamic factor
    Kv  = _agma_kv(V_ms, Qv)

    # Load distribution factor Km (AGMA Eq. 6-14, simplified for F/d ≤ 2)
    Km  = 1.0 + 0.04 * (F_mm / d_p)

    # Bending stress (MPa): σt = Wt Ko Kv Ks Km / (F m J)
    # Ks = size factor ≈ 1.192(F√Y/P)^0.0535 → use 1.0 for module ≤ 5
    Ks  = max(1.0, 1.192 * (F_mm * math.sqrt(J_p) / (1/m)) ** 0.0535)
    Ks  = min(Ks, 2.0)

    sigma_bending_p = W_t_N * Ko * Kv * Ks * Km / (F_mm * m * J_p)
    sigma_bending_g = W_t_N * Ko * Kv * Ks * Km / (F_mm * m * J_g)

    # Contact stress (MPa): σc = Cp √(Wt Ko Kv Km / (F dp I))
    # I = geometry factor for contact (Shigley's Eq. 13-11)
    sin_phi = math.sin(phi)
    cos_phi = math.cos(phi)
    mN      = N_pinion / N_gear          # gear ratio (< 1 for speed reduction)
    I = (sin_phi * cos_phi) / (2) * mN / (mN + 1)

    Cp = math.sqrt(1 / (math.pi * (1/207000 + 1/207000)))  # elastic coefficient, both steel
    sigma_contact = Cp * math.sqrt(W_t_N * Ko * Kv * Km / (F_mm * d_p * I))

    # Allowable stresses (AGMA 2001)
    # Safety factors: Sf (bending) ≥ 1.2, Sh (contact) ≥ 1.2
    sat_p   = mat_pinion["sat_MPa"]
    sat_g   = mat_gear["sat_MPa"]
    sac_p   = mat_pinion["sac_MPa"]
    sac_g   = mat_gear["sac_MPa"]

    # Stress cycle factors (YN, ZN) - assumed 10^7 cycles (unity for moderate life)
    YN, ZN = 1.0, 1.0
    KT, KR = 1.0, 1.0   # temperature, reliability (90%)

    Sf_p = (sat_p * YN) / (sigma_bending_p * KT * KR) if sigma_bending_p > 0 else 999
    Sf_g = (sat_g * YN) / (sigma_bending_g * KT * KR) if sigma_bending_g > 0 else 999
    Sh_p = (sac_p * ZN) / (sigma_contact   * KT * KR) if sigma_contact   > 0 else 999
    Sh_g = (sac_g * ZN) / (sigma_contact   * KT * KR) if sigma_contact   > 0 else 999

    return {
        "module_mm":         m,
        "d_pinion_mm":       round(d_p, 1),
        "d_gear_mm":         round(d_g, 1),
        "pitch_velocity_ms": round(V_ms, 2),
        "Wt_N":              round(W_t_N, 1),
        "Kv":                round(Kv, 3),
        "Km":                round(Km, 3),
        "bending_stress_pinion_MPa": round(sigma_bending_p, 2),
        "bending_stress_gear_MPa":  round(sigma_bending_g, 2),
        "contact_stress_MPa":       round(sigma_contact, 2),
        "Sf_pinion":         round(Sf_p, 3),
        "Sf_gear":           round(Sf_g, 3),
        "Sh_pinion":         round(Sh_p, 3),
        "Sh_gear":           round(Sh_g, 3),
        "bending_ok":        min(Sf_p, Sf_g) >= 1.2,
        "contact_ok":        min(Sh_p, Sh_g) >= 1.2,
    }


def _vbelt(power_kW: float, n_driver_rpm: float, n_driven_rpm: float,
           centre_dist_mm: float, section: str = "B (17)",
           service_factor: float = 1.2) -> dict:
    """V-belt drive design per RMA IP-20 / Shigley's Ch.17."""
    bd   = VBELT_SECTIONS.get(section, VBELT_SECTIONS["B (17)"])
    ratio = n_driver_rpm / n_driven_rpm if n_driven_rpm > 0 else 1.0

    # Standard sheave diameters: smaller (driver) and larger (driven)
    # Use speed ratio to compute driven diameter from driver
    d_small_mm = float(150)   # default driver pitch diameter
    d_large_mm = d_small_mm * ratio
    C_mm       = centre_dist_mm

    # Belt pitch length (Shigley's Eq. 17-1)
    L_p_mm = 2 * C_mm + math.pi * (d_large_mm + d_small_mm) / 2 + \
             (d_large_mm - d_small_mm)**2 / (4 * C_mm) if C_mm > 0 else 0

    # Angle of wrap on small sheave (degrees)
    theta_s = 180 - 60 * (d_large_mm - d_small_mm) / C_mm if C_mm > 0 else 180
    theta_s = max(theta_s, 90)   # floor

    # Wrap factor Cθ (RMA IP-20 Table 17-12)
    if theta_s >= 180:
        C_theta = 1.00
    elif theta_s >= 150:
        C_theta = 0.92 + (theta_s - 150) / 30 * 0.08
    elif theta_s >= 120:
        C_theta = 0.82 + (theta_s - 120) / 30 * 0.10
    else:
        C_theta = 0.69 + (theta_s - 90)  / 30 * 0.13

    # Design power per belt from section rating (linear approximation)
    # Pd_belt ≈ Pd_max × (n_driver / 3000)^0.5  - simplified for demonstration
    P_belt_kW = bd["Pd_max_kW"] * math.sqrt(n_driver_rpm / 3000) * C_theta
    P_belt_kW = max(P_belt_kW, 0.1)

    # Number of belts
    P_design = power_kW * service_factor
    n_belts  = math.ceil(P_design / P_belt_kW)

    # Belt tensions (for shaft load estimation)
    V_ms = math.pi * d_small_mm / 1000 * n_driver_rpm / 60
    F_net_N = power_kW * 1000 / V_ms if V_ms > 0 else 0     # net belt pull

    return {
        "section":          section,
        "speed_ratio":      round(ratio, 3),
        "d_small_mm":       round(d_small_mm, 0),
        "d_large_mm":       round(d_large_mm, 0),
        "belt_length_mm":   round(L_p_mm, 0),
        "wrap_angle_deg":   round(theta_s, 1),
        "Ctheta":           round(C_theta, 3),
        "P_per_belt_kW":    round(P_belt_kW, 3),
        "n_belts":          n_belts,
        "P_design_kW":      round(P_design, 3),
        "net_belt_pull_N":  round(F_net_N, 1),
    }


def _chain_drive(power_kW: float, n_driver_rpm: float, n_driven_rpm: float,
                 N_driver_teeth: int = 19, service_factor: float = 1.2) -> dict:
    """Roller chain selection per ANSI B29.1 / Shigley's Ch.17."""
    ratio = n_driver_rpm / n_driven_rpm if n_driven_rpm > 0 else 1.0
    N_driven_teeth = round(N_driver_teeth * ratio)

    # Select chain number: design power = P × KS; rating from table
    # Simplified: use chain pitch circle velocity
    # Try each chain until rating OK
    P_design_kW = power_kW * service_factor
    selected = None
    for chain_no, cd in CHAIN_NUMBERS.items():
        p_mm   = cd["pitch_mm"]
        # Pitch diameter of driver sprocket
        d_drv_mm = p_mm / math.sin(math.pi / N_driver_teeth)
        V_ms   = math.pi * d_drv_mm / 1000 * n_driver_rpm / 60
        # Allowable kW: F_allowable × V (simplified: 0.3×Pr×V)
        P_allow_kW = 0.3 * cd["Pr_kN"] * 1000 * V_ms / 1000
        if P_allow_kW >= P_design_kW:
            selected = chain_no
            break
    if selected is None:
        selected = "160"   # largest in table

    cd    = CHAIN_NUMBERS[selected]
    p_mm  = cd["pitch_mm"]
    d_drv_mm  = p_mm / math.sin(math.pi / N_driver_teeth)
    d_drn_mm  = p_mm / math.sin(math.pi / max(N_driven_teeth, 1))

    # Standard centre distance ≈ 30-50 pitches
    C_pitch  = 40   # pitch lengths
    C_mm     = C_pitch * p_mm
    # Chain length in pitches
    L_p = 2 * C_pitch + (N_driver_teeth + N_driven_teeth) / 2 + \
          (N_driven_teeth - N_driver_teeth)**2 / (4 * math.pi**2 * C_pitch)
    L_p = math.ceil(L_p)
    if L_p % 2 != 0:
        L_p += 1   # even number of links preferred

    return {
        "chain_number":      selected,
        "pitch_mm":          p_mm,
        "Pr_kN":             cd["Pr_kN"],
        "N_driver_teeth":    N_driver_teeth,
        "N_driven_teeth":    N_driven_teeth,
        "d_driver_mm":       round(d_drv_mm, 1),
        "d_driven_mm":       round(d_drn_mm, 1),
        "centre_distance_mm": round(C_mm, 0),
        "chain_length_pitches": L_p,
        "chain_length_mm":   round(L_p * p_mm, 0),
        "speed_ratio":       round(ratio, 3),
    }


def calculate(inputs: dict) -> dict:
    """Main entry point - compatible with TypeScript calcGearBeltDrive() keys."""
    drive_type    = str  (inputs.get("drive_type",    "Spur Gear"))   # Spur Gear / V-Belt / Chain
    power_kW      = float(inputs.get("power_kW",     10.0))
    n_driver_rpm  = float(inputs.get("n_driver_rpm", 1450))
    n_driven_rpm  = float(inputs.get("n_driven_rpm",  725))
    service_factor = float(inputs.get("service_factor", 1.25))

    results: dict = {"drive_type": drive_type}

    if drive_type == "Spur Gear":
        module_mm   = float(inputs.get("module_mm",    3.0))
        N_pinion    = int  (inputs.get("N_pinion",    20))
        N_gear      = int  (inputs.get("N_gear",      40))
        F_mm        = float(inputs.get("face_width_mm", 30.0))
        mat_p_key   = str  (inputs.get("pinion_material",
                              "Grade 2 Steel (through-hardened HB300)"))
        mat_g_key   = str  (inputs.get("gear_material",
                              "Grade 2 Steel (through-hardened HB300)"))
        mat_p = GEAR_MATERIALS.get(mat_p_key, GEAR_MATERIALS["Grade 2 Steel (through-hardened HB300)"])
        mat_g = GEAR_MATERIALS.get(mat_g_key, GEAR_MATERIALS["Grade 2 Steel (through-hardened HB300)"])
        Ko    = Ko_FACTORS.get(inputs.get("load_type", "Light shock"), 1.25)

        gear_res = _spur_gear(module_mm, N_pinion, N_gear, F_mm,
                               power_kW, n_driver_rpm, mat_p, mat_g,
                               Ko=Ko, pressure_angle_deg=20.0)
        results.update(gear_res)
        results["pinion_material"] = mat_p_key
        results["gear_material"]   = mat_g_key

    elif drive_type == "V-Belt":
        section      = str  (inputs.get("belt_section",    "B (17)"))
        centre_mm    = float(inputs.get("centre_distance_mm", 500))
        belt_res = _vbelt(power_kW, n_driver_rpm, n_driven_rpm,
                          centre_mm, section, service_factor)
        results.update(belt_res)

    else:  # Chain
        N_drv = int(inputs.get("driver_teeth", 19))
        chain_res = _chain_drive(power_kW, n_driver_rpm, n_driven_rpm,
                                 N_drv, service_factor)
        results.update(chain_res)

    results.update({
        "power_kW":       power_kW,
        "n_driver_rpm":   n_driver_rpm,
        "n_driven_rpm":   n_driven_rpm,
        "overall_ratio":  round(n_driver_rpm / n_driven_rpm, 3) if n_driven_rpm > 0 else 0,
        "inputs_used": {
            "drive_type":    drive_type,
            "power_kW":      power_kW,
            "n_driver_rpm":  n_driver_rpm,
            "n_driven_rpm":  n_driven_rpm,
        },
        "calculation_source": "python/math",
        "standard": "AGMA 2001-D04 | RMA IP-20 | ANSI B29.1 | ISO 6336 | Shigley's MED 10th Ed.",
    })
    return results
