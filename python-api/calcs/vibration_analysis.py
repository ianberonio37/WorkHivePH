"""
Vibration Analysis - Phase 9a
Standards: ISO 10816-1 Annex B (machine classes I-IV and their severity zones, ex ISO 2372),
           ISO 20816-1:2016 (supersedes 10816-1),
           ISO 20816-3:2022 (formerly ISO 10816-3; groups machines above 15 kW by Group 1/2 and
           foundation with its OWN limits - not the class table below, which it never contained),
           ANSI S2.19 (Mechanical vibration),
           Rao's Mechanical Vibrations (6th Ed.) - theory
Libraries: math (all formulas closed-form)

Methods:
  SDOF natural frequency: fn = (1/2π) × √(k/m)
  Damped natural frequency: fd = fn × √(1 − ζ²)
  Critical damping: cc = 2 × √(k × m)
  Frequency response: X/Xst = r²/√[(1−r²)²+(2ζr)²] (base excitation)
  Rotating imbalance: X = (mₑ e ω²) / √[(k−mω²)²+(cω)²]
  Transmissibility: TR = √[(1+(2ζr)²)/((1−r²)²+(2ζr)²)]
  Resonance check: operating frequency vs natural frequency
  ISO 10816 severity zones: A/B/C/D by machine class
"""

import math

# ─── ISO 10816-1 (Annex B) machine classes ──────────────────────────────────────────────
# Class I: small machines ≤ 15 kW
# Class II: medium machines 15–75 kW, or to 300 kW on rigid foundation
# Class III: large machines > 300 kW on rigid foundation
# Class IV: large machines > 300 kW on soft/flexible foundation
ISO10816_ZONES: dict[str, dict] = {
    "Class I (≤15 kW)": {
        "A_mm_s": 0.71,   # New machines - good
        "B_mm_s": 1.80,   # Acceptable for long-term operation
        "C_mm_s": 4.50,   # Acceptable short-term only
        "D_mm_s": 99.0,   # Danger - immediate action
    },
    "Class II (15–300 kW, rigid foundation)": {
        "A_mm_s": 1.12,
        "B_mm_s": 2.80,
        "C_mm_s": 7.10,
        "D_mm_s": 99.0,
    },
    "Class III (>300 kW, rigid foundation)": {
        "A_mm_s": 1.80,
        "B_mm_s": 4.50,
        "C_mm_s": 11.2,
        "D_mm_s": 99.0,
    },
    "Class IV (>300 kW, flexible foundation)": {
        "A_mm_s": 2.80,
        "B_mm_s": 7.10,
        "C_mm_s": 18.0,
        "D_mm_s": 99.0,
    },
}

# ─── ISO 10816-1 class evaluation zones ────────────────────────────────────────────
def _iso_zone(v_rms_mm_s: float, machine_class: str) -> str:
    zones = ISO10816_ZONES.get(machine_class, ISO10816_ZONES["Class II (15–300 kW, rigid foundation)"])
    if v_rms_mm_s <= zones["A_mm_s"]:  return "Zone A - New machine (acceptable)"
    if v_rms_mm_s <= zones["B_mm_s"]:  return "Zone B - Long-term operation (acceptable)"
    if v_rms_mm_s <= zones["C_mm_s"]:  return "Zone C - Short-term only (investigate)"
    return "Zone D - DANGER - immediate shutdown"

# ─── Isolator types, by the static deflection they are rated to take ────────
# ★THE ISOLATOR CHOICE NEVER REACHED THE ENGINE, AND ITS STIFFNESS IGNORED THE MACHINE (2026-11-02, ED-G1 Vibration,
# read against the guide's "Stiffness k - auto-filled when you select an isolator type"): the form has no stiffness or
# damping field, so the payload always sent 200,000 N/m and zeta 0.08 - an air spring, a steel spring and a rigid mount
# all computed as a medium rubber mount. And the table held one total k per type whatever the machine weighed: an air
# spring under a 500 kg machine deflected 245 mm, under 5 t, 2.45 m. Isolators are selected by the static deflection they
# take at their rated load (ASHRAE HVAC Applications, "Noise and Vibration Control"; maker catalogues), so each type is now
# that deflection: k = m.g / delta_st, fn = (1/2pi) sqrt(g / delta_st). Neoprene mounts 3-10 mm, steel springs 19-50 mm,
# an air spring ~2 Hz (62 mm equivalent), a rigid bolt-down 0.1 mm (~50 Hz). An explicit stiffness_N_m still overrides.
G_ACCEL = 9.80665
VIBRATION_ISOLATORS: dict[str, dict] = {
    "Rubber mount (soft)":    {"delta_mm": 10.0, "zeta": 0.10},
    "Rubber mount (medium)":  {"delta_mm": 6.0,  "zeta": 0.08},
    "Rubber mount (hard)":    {"delta_mm": 3.0,  "zeta": 0.06},
    "Steel spring (soft)":    {"delta_mm": 50.0, "zeta": 0.01},
    "Steel spring (medium)":  {"delta_mm": 25.0, "zeta": 0.01},
    "Steel spring (stiff)":   {"delta_mm": 19.0, "zeta": 0.005},
    "Air spring":             {"delta_mm": 62.0, "zeta": 0.15},
    "Rigid mount (no isolation)": {"delta_mm": 0.1, "zeta": 0.02},
}

# The power range each class label states (inclusive at its ends); used only to flag a class that does not fit the power.
CLASS_POWER_KW: dict[str, tuple[float, float]] = {
    "Class I (≤15 kW)": (0.0, 15.0),
    "Class II (15–300 kW, rigid foundation)": (15.0, 300.0),
    "Class III (>300 kW, rigid foundation)": (300.0, float("inf")),
    "Class IV (>300 kW, flexible foundation)": (300.0, float("inf")),
}


def _sdof(mass_kg: float, k_Nm: float, c_Ns_m: float = 0.0) -> dict:
    """SDOF natural frequency, damping ratio, damped frequency."""
    wn   = math.sqrt(k_Nm / mass_kg) if mass_kg > 0 else 0   # rad/s
    fn   = wn / (2 * math.pi)                                  # Hz
    cc   = 2 * math.sqrt(k_Nm * mass_kg)                       # critical damping N·s/m
    zeta = c_Ns_m / cc if cc > 0 else 0
    wd   = wn * math.sqrt(max(1 - zeta**2, 0))
    fd   = wd / (2 * math.pi)
    return {"wn_rad_s": round(wn, 4), "fn_Hz": round(fn, 4),
            "cc_Ns_m":  round(cc, 2), "zeta": round(zeta, 5),
            "wd_rad_s": round(wd, 4), "fd_Hz": round(fd, 4)}


def _frequency_response(r: float, zeta: float) -> dict:
    """
    SDOF forced vibration: magnification factor MF and phase angle.
    MF = 1 / √[(1−r²)² + (2ζr)²]
    φ = arctan(2ζr / (1−r²))
    """
    denom = math.sqrt((1 - r**2)**2 + (2 * zeta * r)**2)
    MF    = 1 / denom if denom > 0 else 999
    if abs(1 - r**2) < 1e-9:
        phase_deg = 90.0
    else:
        phase_deg = math.degrees(math.atan2(2 * zeta * r, 1 - r**2))
    return {"MF": round(MF, 4), "phase_deg": round(phase_deg, 2)}


def _transmissibility(r: float, zeta: float) -> float:
    """
    Force/displacement transmissibility TR.
    TR = √[(1+(2ζr)²) / ((1−r²)²+(2ζr)²)]
    """
    num   = 1 + (2 * zeta * r)**2
    denom = (1 - r**2)**2 + (2 * zeta * r)**2
    return math.sqrt(num / denom) if denom > 0 else 999


def _rotating_imbalance(mass_kg: float, m_e_kg: float, e_mm: float,
                         omega: float, k_Nm: float, c_Ns_m: float) -> dict:
    """
    Rotating imbalance response: X = (mₑ e ω²) / √[(k−mω²)²+(cω)²]
    Returns amplitude X (mm) and transmitted force Ft (N).
    """
    e_m   = e_mm / 1000
    num   = m_e_kg * e_m * omega**2
    denom = math.sqrt((k_Nm - mass_kg * omega**2)**2 + (c_Ns_m * omega)**2)
    X_m   = num / denom if denom > 0 else 0
    X_mm  = X_m * 1000
    # Peak velocity
    V_peak_mm_s = X_mm * omega
    V_rms_mm_s  = V_peak_mm_s / math.sqrt(2)
    # Transmitted force
    Ft_N  = math.sqrt((k_Nm * X_m)**2 + (c_Ns_m * omega * X_m)**2)
    return {"X_mm": round(X_mm, 4), "V_peak_mm_s": round(V_peak_mm_s, 3),
            "V_rms_mm_s": round(V_rms_mm_s, 3), "Ft_N": round(Ft_N, 2)}


# formula: vibration_analysis_iso_10816_3
def calculate(inputs: dict) -> dict:
    """Main entry point - compatible with TypeScript calcVibrationAnalysis() keys."""
    # ── Machine parameters ────────────────────────────────────────────────────
    mass_kg         = float(inputs.get("mass_kg",          500.0))
    speed_rpm       = float(inputs.get("speed_rpm",        1450.0))
    power_kW        = float(inputs.get("power_kW",         15.0))
    machine_class   = str  (inputs.get("machine_class",    "Class II (15–300 kW, rigid foundation)"))
    if machine_class not in ISO10816_ZONES:
        machine_class = "Class II (15–300 kW, rigid foundation)"
    rotor_mass_kg   = float(inputs.get("rotor_mass_kg") or 50.0)
    rotor_mass_kg   = min(rotor_mass_kg, mass_kg) if mass_kg > 0 else rotor_mass_kg

    # Imbalance parameters
    m_e_kg          = float(inputs.get("imbalance_mass_kg",  0.1))    # unbalanced mass
    e_mm            = float(inputs.get("eccentricity_mm",    5.0))     # eccentricity
    v_measured_mm_s = float(inputs.get("measured_velocity_mm_s", 0.0)) # field measurement

    # Support/isolation parameters
    isolator_key    = str  (inputs.get("isolator_type",    "Rubber mount (medium)"))
    if isolator_key not in VIBRATION_ISOLATORS:
        isolator_key = "Rubber mount (medium)"
    iso_data        = VIBRATION_ISOLATORS[isolator_key]
    if inputs.get("stiffness_N_m"):
        k_Nm         = float(inputs["stiffness_N_m"])
        stiffness_basis = "stiffness entered"
    else:
        k_Nm         = mass_kg * G_ACCEL / (iso_data["delta_mm"] / 1000)
        stiffness_basis = f"k = m.g / delta_st, {isolator_key} rated at {iso_data['delta_mm']:g} mm static deflection"
    delta_st_mm     = mass_kg * G_ACCEL / k_Nm * 1000 if k_Nm > 0 else 0.0
    zeta_input      = float(inputs.get("damping_ratio") or iso_data["zeta"])

    # ── Operating frequency ───────────────────────────────────────────────────
    omega_op   = speed_rpm * 2 * math.pi / 60     # rad/s
    f_op_Hz    = speed_rpm / 60                    # Hz

    # ── SDOF parameters ───────────────────────────────────────────────────────
    c_Ns_m     = zeta_input * 2 * math.sqrt(k_Nm * mass_kg)
    sdof       = _sdof(mass_kg, k_Nm, c_Ns_m)
    fn_Hz      = sdof["fn_Hz"]
    zeta       = sdof["zeta"]

    # Frequency ratio r = f_op / fn
    r = f_op_Hz / fn_Hz if fn_Hz > 0 else 0

    # ── Resonance check ───────────────────────────────────────────────────────
    resonance_margin_pct = abs(r - 1.0) * 100
    resonance_risk = resonance_margin_pct < 10   # within ±10% of fn

    # ── Frequency response ────────────────────────────────────────────────────
    fr_data    = _frequency_response(r, zeta)
    MF         = fr_data["MF"]

    # ── Transmissibility ──────────────────────────────────────────────────────
    TR         = _transmissibility(r, zeta)
    isolation_eff_pct = (1 - TR) * 100 if TR <= 1 else 0
    isolation_ok = TR < 1.0   # isolator working (r > √2 ≈ 1.414)

    # ── Rotating imbalance response ───────────────────────────────────────────
    imbalance  = _rotating_imbalance(mass_kg, m_e_kg, e_mm, omega_op, k_Nm, c_Ns_m)
    V_rms      = imbalance["V_rms_mm_s"]

    # ── ISO 10816 assessment ──────────────────────────────────────────────────
    v_assess   = v_measured_mm_s if v_measured_mm_s > 0 else V_rms
    iso_zone   = _iso_zone(v_assess, machine_class)
    zone_ok    = "Zone A" in iso_zone or "Zone B" in iso_zone

    # ── Critical speed check ──────────────────────────────────────────────────
    # Operating should be < 0.8 fn or > 1.2 fn (avoid resonance band)
    in_resonance_band = 0.8 * fn_Hz < f_op_Hz < 1.2 * fn_Hz

    # ── Balancing grade (ISO 21940-11 / ISO 1940-1) ──────────────────────────
    # ★G TOOK THE UNBALANCE MASS'S RADIUS FOR THE ROTOR'S SPECIFIC UNBALANCE, AND DIVIDED BY 1000 (2026-11-02, ED-G1
    # Vibration): G = e_mm x omega / 1000 read 0.759 mm/s for 0.1 kg at 5 mm on any rotor, and the report printed
    # "5 mm x 151.84 rad/s = 0.759". ISO 21940-11's G = e_per x omega, where e_per = U / m_rotor is the residual unbalance
    # per kg of ROTOR (g.mm/kg = um). The same 500 g.mm is G0.15 on a 500 kg rotor and G15 on a 5 kg one. The grade labels
    # also put turbines at G0.4/G1 and pumps at G1/G2.5; ISO 1940-1 Table 1 has turbines at G2.5 and fans/pumps at G6.3.
    U_residual_gmm = m_e_kg * 1000 * e_mm                        # g.mm
    e_per_um       = U_residual_gmm / rotor_mass_kg if rotor_mass_kg > 0 else 0.0   # g.mm/kg = um
    G_grade        = e_per_um / 1000 * omega_op                  # mm/s
    U_per_G6_3_gmm = 6.3 * 1000 / omega_op * rotor_mass_kg if omega_op > 0 else 0.0
    if G_grade <= 0.4:    balance_grade = "G0.4 (precision grinder spindles, gyroscopes)"
    elif G_grade <= 1.0:  balance_grade = "G1 (grinding-machine drives)"
    elif G_grade <= 2.5:  balance_grade = "G2.5 (gas and steam turbines, turbo-compressors, machine-tool drives)"
    elif G_grade <= 6.3:  balance_grade = "G6.3 (fans, pump impellers, electric motor armatures, general machinery)"
    elif G_grade <= 16:   balance_grade = "G16 (cardan shafts, crusher and agricultural machinery parts)"
    elif G_grade <= 40:   balance_grade = "G40 (car wheels, drive shafts)"
    else:                 balance_grade = "worse than G40 (crankshaft drives)"

    # ★THE POWER RATING WAS READ AND NEVER USED (2026-11-02): it now checks the class against the power its label states.
    lo_kw, hi_kw = CLASS_POWER_KW[machine_class]
    class_power_note = "" if lo_kw <= power_kW <= hi_kw else (
        f"A {power_kW:g} kW machine sits outside the {machine_class.split(' (')[0]} power range on the form "
        f"({machine_class.split('(')[1].rstrip(')')}); the zones shown are for the class selected - check the class.")
    zl = ISO10816_ZONES[machine_class]

    return {
        # SDOF
        "k_N_m":               round(k_Nm, 1),
        "delta_st_mm":         round(delta_st_mm, 3),
        "stiffness_basis":     stiffness_basis,
        "fn_Hz":               sdof["fn_Hz"],
        "fn_rpm":              round(sdof["fn_Hz"] * 60, 1),
        "fd_Hz":               sdof["fd_Hz"],
        "wn_rad_s":            sdof["wn_rad_s"],
        "zeta":                sdof["zeta"],
        "cc_Ns_m":             sdof["cc_Ns_m"],

        # Operating
        "f_op_Hz":             round(f_op_Hz, 3),
        "omega_op_rad_s":      round(omega_op, 3),
        "frequency_ratio_r":   round(r, 4),
        "resonance_margin_pct": round(resonance_margin_pct, 2),
        "resonance_risk":      resonance_risk,
        "in_resonance_band":   in_resonance_band,

        # Frequency response
        "magnification_factor": fr_data["MF"],
        "phase_deg":           fr_data["phase_deg"],

        # Transmissibility / isolation
        "transmissibility":    round(TR, 4),
        "isolation_efficiency_pct": round(isolation_eff_pct, 1),
        "isolation_ok":        isolation_ok,
        "isolator_type":       isolator_key,

        # Rotating imbalance
        "X_mm":                imbalance["X_mm"],
        "V_peak_mm_s":         imbalance["V_peak_mm_s"],
        "V_rms_mm_s":          imbalance["V_rms_mm_s"],
        "Ft_N":                imbalance["Ft_N"],

        # ISO 10816 assessment
        "v_assessed_mm_s":     round(v_assess, 3),
        "iso_zone":            iso_zone,
        "zone_ok":             zone_ok,
        "machine_class":       machine_class,
        "zone_limits_mm_s":    {"A_B": zl["A_mm_s"], "B_C": zl["B_mm_s"], "C_D": zl["C_mm_s"]},
        "class_power_note":    class_power_note,

        # Balancing
        "rotor_mass_kg":       round(rotor_mass_kg, 2),
        "U_residual_gmm":      round(U_residual_gmm, 1),
        "e_per_um":            round(e_per_um, 3),
        "G_grade_mm_s":        round(G_grade, 3),
        "balance_grade":       balance_grade,
        "U_per_G6_3_gmm":      round(U_per_G6_3_gmm, 1),

        # Inputs
        "inputs_used": {
            "mass_kg":         mass_kg,
            "speed_rpm":       speed_rpm,
            "stiffness_N_m":   round(k_Nm, 1),
            "damping_ratio":   zeta_input,
            "machine_class":   machine_class,
            "power_kW":        power_kW,
            "rotor_mass_kg":   rotor_mass_kg,
        },
        "calculation_source": "python/math",
        "standard": "ISO 10816-1 (class zones) | ISO 20816-1 | ISO 21940-11 | ANSI S2.19 | Rao Mechanical Vibrations 6th Ed.",
    }
