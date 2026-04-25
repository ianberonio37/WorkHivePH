"""
Duct Sizing — Phase 2d (Equal Friction Method)
Standards: ASHRAE 2021 Fundamentals Ch.21 (Duct Design), SMACNA HVAC Systems
           Duct Design 4th Ed., ASHRAE 62.1, PNS/PSME
Libraries: math (no external dep — all formulas are closed-form)

Key distinction (ASHRAE 2021 Ch.21):
  De — Hydraulic Equivalent Diameter: use for SIZING the duct
       De = 1.30 × (a×b)^0.625 / (a+b)^0.25
  D_h — Hydraulic Diameter: use for PRESSURE DROP after sizing
       D_h = 2ab / (a+b)

Equal Friction Method formula (Darcy-Weisbach + Blasius/Swamee-Jain):
  D (m) = [K × Q^1.75 / fr]^(1/4.75)
  K ≈ 0.01740  (tropical air 35°C, Manila)

Velocity limits (SMACNA / ASHRAE 62.1):
  Supply Main:   ≤ 8 m/s  (≤ 5 m/s open-plan offices)
  Supply Branch: ≤ 5 m/s
  Return Main:   ≤ 6 m/s
  Exhaust:       ≤ 6 m/s
"""

import math

# ─── Tropical air constants at 35°C, sea level (Manila design conditions) ─────
# ASHRAE 2021 Fundamentals, standard air properties at 35°C
RHO_AIR   = 1.15          # kg/m3
MU_AIR    = 1.90e-5       # Pa·s  dynamic viscosity (Sutherland ~35°C)
NU_AIR    = MU_AIR / RHO_AIR   # m2/s = 1.652e-5

# Closed-form K constant for Equal Friction formula (tropical air)
# K = 8 × 0.3164 × ρ × (π × ν)^0.25 / (π² × 4^0.25)
# Computed from first principles; matches ASHRAE Table at 35°C
K_TROPICAL = (8 * 0.3164 * RHO_AIR * (math.pi * NU_AIR) ** 0.25
              / (math.pi ** 2 * 4 ** 0.25))
# ≈ 0.01740

# Galvanized steel duct roughness — ASHRAE 2021 Table 1 Ch.21
ROUGHNESS_M = 0.00009   # 0.09 mm

# ─── Design friction rates (Pa/m) by application — Philippine practice ────────
DESIGN_FRICTION_RATES: dict[str, float] = {
    "Library / Theatre":    0.8,
    "Office / Hospital":    1.0,
    "Hotel":                1.0,
    "Commercial / Retail":  1.2,
    "Industrial":           1.5,
    "Warehouse":            1.5,
}

# ─── Velocity limits (m/s) by duct section — SMACNA ─────────────────────────
VELOCITY_LIMITS: dict[str, dict] = {
    "Supply Main":    {"max": 8.0, "office_max": 5.0, "min": 2.0},
    "Supply Branch":  {"max": 5.0, "office_max": 3.0, "min": 1.5},
    "Return Main":    {"max": 6.0, "office_max": 4.0, "min": 2.0},
    "Return Branch":  {"max": 4.0, "office_max": 3.0, "min": 1.5},
    "Exhaust":        {"max": 6.0, "office_max": 4.0, "min": 2.0},
    "Outdoor Air":    {"max": 4.0, "office_max": 3.0, "min": 1.5},
}

# ─── Standard duct round sizes (mm nominal) — SMACNA ─────────────────────────
ROUND_SIZES_MM = [
    100, 125, 150, 175, 200, 225, 250, 280, 300, 315,
    355, 400, 450, 500, 560, 630, 710, 800, 900, 1000,
    1120, 1250,
]

# ─── Standard rectangular duct dimension increments (mm) — SMACNA ─────────────
RECT_INCREMENT_MM = 50   # round up to nearest 50 mm


def _friction_factor(Re: float, D: float) -> float:
    """
    Darcy friction factor.
    Blasius for Re < 100,000; Swamee-Jain for Re >= 100,000.
    ASHRAE 2021 Ch.21.
    """
    if Re < 2300:
        return 64 / Re   # laminar
    eD = ROUGHNESS_M / D
    if Re < 100000:
        # Blasius (turbulent smooth):
        return 0.3164 / Re ** 0.25
    else:
        # Swamee-Jain (fully turbulent, rough):
        return 0.25 / (math.log10(eD / 3.7 + 5.74 / Re ** 0.9)) ** 2


def _dp_per_m(D: float, Q_m3s: float) -> tuple[float, float, float, float]:
    """
    Pressure drop per unit length (Pa/m), velocity (m/s), Re, and f.
    Uses D_h = D for circular, or pass D_h directly for rectangular.
    """
    A  = math.pi * (D / 2) ** 2
    v  = Q_m3s / A
    Re = RHO_AIR * v * D / MU_AIR
    if Re < 1:
        return 0.0, v, Re, 0.0
    f  = _friction_factor(Re, D)
    dp = f * (RHO_AIR * v ** 2 / 2) / D   # Pa/m
    return dp, v, Re, f


def _size_circular(Q_m3s: float, fr_pam: float) -> tuple[float, float]:
    """
    Equal Friction Method — circular duct.
    Returns (D_m calculated, D_m standard).
    D = [K × Q^1.75 / fr]^(1/4.75)
    """
    D_calc = (K_TROPICAL * Q_m3s ** 1.75 / fr_pam) ** (1 / 4.75)
    # Select smallest standard size >= D_calc
    D_calc_mm = D_calc * 1000
    D_std_mm  = next((s for s in ROUND_SIZES_MM if s >= D_calc_mm), ROUND_SIZES_MM[-1])
    return D_calc, D_std_mm / 1000


def _de_from_rect(a_m: float, b_m: float) -> float:
    """
    ASHRAE Hydraulic Equivalent Diameter De for rectangular duct (sizing).
    De = 1.30 × (a×b)^0.625 / (a+b)^0.25
    """
    return 1.30 * (a_m * b_m) ** 0.625 / (a_m + b_m) ** 0.25


def _dh_from_rect(a_m: float, b_m: float) -> float:
    """
    Hydraulic diameter D_h for rectangular duct (pressure drop).
    D_h = 2ab / (a+b)
    """
    return 2 * a_m * b_m / (a_m + b_m)


def _size_rectangular(
    Q_m3s: float, fr_pam: float, aspect_ratio: float = 1.5
) -> dict:
    """
    Size rectangular duct via Equal Friction Method.
    1. Find De from equal friction formula (same as circular D)
    2. Solve for a,b at target aspect ratio: a = De × (1+r)^0.25 / (1.30 × r^0.625)
    3. Round up to nearest 50 mm
    4. Recompute D_h from actual a,b for pressure drop
    """
    r = aspect_ratio
    _, D_std_m = _size_circular(Q_m3s, fr_pam)
    De = D_std_m   # set De equal to equivalent circular D

    a_calc = De * (1 + r) ** 0.25 / (1.30 * r ** 0.625)
    b_calc = r * a_calc

    # Round up to nearest SMACNA increment
    inc = RECT_INCREMENT_MM / 1000
    a_m = math.ceil(a_calc / inc) * inc
    b_m = math.ceil(b_calc / inc) * inc

    D_h = _dh_from_rect(a_m, b_m)
    De_actual = _de_from_rect(a_m, b_m)

    # Pressure drop with actual D_h
    dp, v, Re, f = _dp_per_m_rect(Q_m3s, a_m, b_m)

    return {
        "a_mm":         round(a_m * 1000, 0),
        "b_mm":         round(b_m * 1000, 0),
        "aspect_ratio": round(a_m / b_m, 2),
        "De_mm":        round(De_actual * 1000, 1),
        "Dh_mm":        round(D_h * 1000, 1),
        "velocity_ms":  round(v, 2),
        "Re":           round(Re, 0),
        "friction_f":   round(f, 5),
        "dp_pam":       round(dp, 3),
    }


def _dp_per_m_rect(Q_m3s: float, a_m: float, b_m: float) -> tuple[float, float, float, float]:
    """
    Pressure drop per metre for rectangular duct using D_h.
    """
    D_h = _dh_from_rect(a_m, b_m)
    A   = a_m * b_m
    v   = Q_m3s / A
    Re  = RHO_AIR * v * D_h / MU_AIR
    if Re < 1:
        return 0.0, v, Re, 0.0
    f   = _friction_factor(Re, D_h)
    dp  = f * (RHO_AIR * v ** 2 / 2) / D_h
    return dp, v, Re, f


def _size_section(
    label: str,
    flow_m3s: float,
    length_m: float,
    fr_pam: float,
    aspect_ratio: float,
    section_type: str,
    low_noise: bool,
) -> dict:
    """Size one duct section and return full result dict."""
    # Circular sizing
    D_calc, D_std = _size_circular(flow_m3s, fr_pam)
    dp_circ, v_circ, Re_circ, f_circ = _dp_per_m(D_std, flow_m3s)
    total_dp_circ = dp_circ * length_m

    # Rectangular sizing
    rect = _size_rectangular(flow_m3s, fr_pam, aspect_ratio)

    # Velocity check
    vel_key  = section_type if section_type in VELOCITY_LIMITS else "Supply Main"
    vel_lims = VELOCITY_LIMITS[vel_key]
    v_max    = vel_lims["office_max"] if low_noise else vel_lims["max"]
    v_ok     = vel_lims["min"] <= v_circ <= v_max

    if v_circ > v_max:
        vel_note = f"High — exceeds {v_max} m/s limit for {vel_key}"
    elif v_circ < vel_lims["min"]:
        vel_note = f"Low — below {vel_lims['min']} m/s minimum"
    else:
        vel_note = "OK — within SMACNA limits"

    return {
        "label":         label,
        "section_type":  section_type,
        "flow_m3s":      round(flow_m3s, 4),
        "flow_m3hr":     round(flow_m3s * 3600, 1),
        "length_m":      length_m,
        "friction_rate_pam": fr_pam,

        # Circular result
        "circular": {
            "D_calc_mm":   round(D_calc * 1000, 1),
            "D_std_mm":    round(D_std * 1000, 0),
            "velocity_ms": round(v_circ, 2),
            "Re":          round(Re_circ, 0),
            "friction_f":  round(f_circ, 5),
            "dp_pam":      round(dp_circ, 3),
            "dp_total_pa": round(total_dp_circ, 1),
        },

        # Rectangular result
        "rectangular": rect,

        # Velocity check
        "velocity_ok":   v_ok,
        "velocity_note": vel_note,
    }


def calculate(inputs: dict) -> dict:
    """
    Main entry point — compatible with TypeScript calcDuctSizing() input keys.
    Supports single-section mode (one duct run) and multi-section mode (sections[]).
    """
    # ── Application and friction rate ─────────────────────────────────────────
    application  = str  (inputs.get("application",      "Office / Hospital"))
    fr_pam       = float(inputs.get("friction_rate_pam",
                         DESIGN_FRICTION_RATES.get(application, 1.0)))
    aspect_ratio = float(inputs.get("aspect_ratio",     1.5))   # width:height
    low_noise    = bool (inputs.get("low_noise",         False))

    # ── Check for multi-section input ─────────────────────────────────────────
    raw_sections = inputs.get("sections", [])

    if raw_sections:
        # Multi-section mode — size each independently
        sized = []
        total_dp = 0.0
        for sec in raw_sections:
            label      = str  (sec.get("label",        f"Section {len(sized)+1}"))
            flow       = float(sec.get("flow_m3s",      0)
                           or  sec.get("flow_m3hr", 0) / 3600
                           or  sec.get("flow_cfm",  0) / 2118.88)
            length     = float(sec.get("length_m",      10))
            sec_type   = str  (sec.get("type",          "Supply Main"))
            sec_ar     = float(sec.get("aspect_ratio",  aspect_ratio))
            sec_fr     = float(sec.get("friction_rate_pam", fr_pam))

            if flow <= 0:
                continue

            result = _size_section(label, flow, length, sec_fr, sec_ar, sec_type, low_noise)
            sized.append(result)
            total_dp += result["circular"]["dp_total_pa"]

        # Critical path pressure drop (longest duct run)
        critical_dp_pa = max((s["circular"]["dp_total_pa"] for s in sized), default=0)

        return {
            "sections":            sized,
            "total_sections":      len(sized),
            "critical_path_dp_pa": round(critical_dp_pa, 1),
            "sum_dp_pa":           round(total_dp, 1),
            "friction_rate_pam":   fr_pam,
            "application":         application,
            "calculation_source":  "python/math",
            "standard": "ASHRAE 2021 Ch.21 | SMACNA | ASHRAE 62.1",
        }

    # ── Single-section mode ───────────────────────────────────────────────────
    flow_m3s = float(inputs.get("flow_m3s", 0)
                 or (inputs.get("flow_m3hr",  0) / 3600)
                 or (inputs.get("flow_cfm",   0) / 2118.88)
                 or (inputs.get("supply_flow_m3s", 0)))

    if flow_m3s <= 0:
        raise ValueError("Duct flow rate must be greater than 0 m3/s.")

    length_m    = float(inputs.get("duct_length_m",  30.0))
    section_type = str (inputs.get("section_type", "Supply Main"))

    result = _size_section(
        "Main Duct", flow_m3s, length_m, fr_pam, aspect_ratio, section_type, low_noise
    )

    # Flatten for single-section response compatibility
    circ = result["circular"]
    rect = result["rectangular"]

    return {
        # Circular duct
        "D_calc_mm":        circ["D_calc_mm"],
        "D_std_mm":         circ["D_std_mm"],
        "circular_velocity_ms": circ["velocity_ms"],
        "circular_Re":      circ["Re"],
        "circular_dp_pam":  circ["dp_pam"],
        "circular_dp_total_pa": circ["dp_total_pa"],

        # Rectangular duct
        "rect_a_mm":        rect["a_mm"],
        "rect_b_mm":        rect["b_mm"],
        "rect_aspect":      rect["aspect_ratio"],
        "rect_De_mm":       rect["De_mm"],
        "rect_Dh_mm":       rect["Dh_mm"],
        "rect_velocity_ms": rect["velocity_ms"],
        "rect_dp_pam":      rect["dp_pam"],

        # Velocity compliance
        "velocity_ok":      result["velocity_ok"],
        "velocity_note":    result["velocity_note"],

        # Design parameters
        "friction_rate_pam": fr_pam,
        "application":       application,
        "flow_m3s":          round(flow_m3s, 4),
        "flow_m3hr":         round(flow_m3s * 3600, 1),
        "duct_length_m":     length_m,

        # Air properties used
        "air_density_kgm3":  RHO_AIR,
        "air_viscosity_pas": MU_AIR,
        "K_constant":        round(K_TROPICAL, 5),

        # Metadata
        "inputs_used": {
            "application":   application,
            "aspect_ratio":  aspect_ratio,
            "low_noise":     low_noise,
        },
        "calculation_source": "python/math",
        "standard": "ASHRAE 2021 Ch.21 | SMACNA | ASHRAE 62.1",

        # ── Legacy renderer aliases (frontend renderDuctSizingReport) ──────────
        "fan_static_pa":     circ["dp_total_pa"],
        "total_dp_pa":       circ["dp_total_pa"],
        "total_length_m":    length_m,
        "max_flow_lps":      round(flow_m3s * 1000, 2),
        "fan_motor_kw":      None,      # Python doesn't size fan motor — renderer should check None
        "fan_motor_hp_calc": None,
        "fan_motor_hp_std":  None,
        # Wrap single section into array so renderer can iterate
        "segments": [{
            "section_name": section_type,
            "flow_m3hr":    round(flow_m3s * 3600, 1),
            "flow_lps":     round(flow_m3s * 1000, 2),
            "diameter_mm":  circ["D_std_mm"],
            "velocity_ms":  circ["velocity_ms"],
            "dp_pa_m":      circ["dp_pam"],
            "dp_total_pa":  circ["dp_total_pa"],
            "length_m":     length_m,
        }],
    }
