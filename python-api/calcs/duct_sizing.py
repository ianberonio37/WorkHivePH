"""
Duct Sizing - Phase 2d (Equal Friction Method)
Standards: ASHRAE 2021 Fundamentals Ch.21 (Duct Design), SMACNA HVAC Systems
           Duct Design 4th Ed., ASHRAE 62.1, PNS/PSME
Libraries: math (no external dep - all formulas are closed-form)

Key distinction (ASHRAE 2021 Ch.21):
  De - Hydraulic Equivalent Diameter: use for SIZING the duct
       De = 1.30 × (a×b)^0.625 / (a+b)^0.25
  D_h - Hydraulic Diameter: use for PRESSURE DROP after sizing
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

# Galvanized steel duct roughness - ASHRAE 2021 Table 1 Ch.21
ROUGHNESS_M = 0.00009   # 0.09 mm

# ─── Design friction rates (Pa/m) by application - Philippine practice ────────
DESIGN_FRICTION_RATES: dict[str, float] = {
    "Library / Theatre":    0.8,
    "Office / Hospital":    1.0,
    "Hotel":                1.0,
    "Commercial / Retail":  1.2,
    "Industrial":           1.5,
    "Warehouse":            1.5,
}

# ─── Velocity limits (m/s) by duct section - SMACNA ─────────────────────────
VELOCITY_LIMITS: dict[str, dict] = {
    "Supply Main":    {"max": 8.0, "office_max": 5.0, "min": 2.0},
    "Supply Branch":  {"max": 5.0, "office_max": 3.0, "min": 1.5},
    "Return Main":    {"max": 6.0, "office_max": 4.0, "min": 2.0},
    "Return Branch":  {"max": 4.0, "office_max": 3.0, "min": 1.5},
    "Exhaust":        {"max": 6.0, "office_max": 4.0, "min": 2.0},
    "Outdoor Air":    {"max": 4.0, "office_max": 3.0, "min": 1.5},
}

# ─── Standard duct round sizes (mm nominal) - SMACNA ─────────────────────────
ROUND_SIZES_MM = [
    100, 125, 150, 175, 200, 225, 250, 280, 300, 315,
    355, 400, 450, 500, 560, 630, 710, 800, 900, 1000,
    1120, 1250,
]

# ─── Standard rectangular duct dimension increments (mm) - SMACNA ─────────────
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
    Equal Friction Method - circular duct.
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
        vel_note = f"High - exceeds {v_max} m/s limit for {vel_key}"
    elif v_circ < vel_lims["min"]:
        vel_note = f"Low - below {vel_lims['min']} m/s minimum"
    else:
        vel_note = "OK - within SMACNA limits"

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


# ─── The page's segment method (engineering-design.js collectInputs, "Duct Sizing (Equal Friction)") ─────────
# ★THE FORM'S DUCTS WERE NEVER SIZED BY THIS ENGINE (2026-11-02, ED-E1 / census_calc_served_engine.py). The page sends a
# segment schedule - segments[{name, flow_lps, length_m, seg_type}] with duct_shape, friction_rate, air_density,
# aspect_ratio, duct_material - and this module read only "sections" / flow_m3s, so it raised "Duct flow rate must be
# greater than 0" on every form calculation and the edge function's TypeScript sized every duct a person drew. That
# TypeScript (now ported here, its result keys kept for the report) had three defects the port fixes:
#   1. the duct material changed nothing - roughness was fixed at 0.09 mm and smooth-pipe Blasius used below Re 1e5, so a
#      flexible duct (the guide: ~1.5 mm, "15-20x galvanized") was sized as smooth steel. Friction is now Colebrook
#      (Swamee-Jain) at the material's roughness, in the sizing and in the pressure drop - ASHRAE 2021 Ch.21.
#   2. the fan's duct loss was the SUM of every segment, parallel branches included. The fan sees the index (critical)
#      run - ASHRAE 2021 Ch.21 - so the total is now the mains plus the worst branch on each side; the plain sum stays
#      visible as sum_all_dp_pa.
#   3. the drawing reads one duct's numbers (D_std_mm, circular_velocity_ms, rect_*) that the TypeScript never returned,
#      so it printed "O0mm or 0x0mm, v = 0.00 m/s" - it is now given the fan-side main.
# Roughness: the guide's own values, inside ASHRAE 2021 Ch.21 Table 1 ranges (galvanized steel 0.05-0.15 mm, aluminium
# 0.04-0.06 mm, flexible duct 1.0-4.6 mm).
FORM_ROUGHNESS_M: dict[str, float] = {"Galvanized Steel": 0.00009, "Aluminum": 0.00005, "Flexible": 0.0015}
FORM_ROUND_MM = [100, 125, 150, 175, 200, 225, 250, 300, 350, 400, 450, 500, 550, 600, 650, 700, 750, 800, 900,
                 1000, 1100, 1200]
FORM_VEL_LIMITS: dict[str, float] = {"Supply Main": 8.0, "Supply Branch": 5.0, "Return Main": 6.0, "Return Branch": 4.0}
STD_MOTOR_HP = [0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 7.5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 125, 150, 200]
FAN_EFF, MOTOR_EFF, FITTINGS_FACTOR = 0.65, 0.85, 1.5


def _f_colebrook(Re: float, D_h: float, eps: float) -> float:
    """Darcy friction factor: laminar 64/Re, else Swamee-Jain's explicit Colebrook at roughness eps."""
    if Re < 2300:
        return 64 / Re
    return 0.25 / math.log10(eps / (3.7 * D_h) + 5.74 / Re ** 0.9) ** 2


def _dp_per_m_at(Q: float, D_h: float, area: float, rho: float, nu: float, eps: float):
    v = Q / area
    Re = v * D_h / nu
    if Re < 1:
        return 0.0, v, Re, 0.0
    f = _f_colebrook(Re, D_h, eps)
    return f * rho * v * v / (2 * D_h), v, Re, f


def _equal_friction_diameter(Q: float, fr: float, rho: float, nu: float, eps: float) -> float:
    """The round duct whose friction is exactly the design rate (dp/L = fr) - bisection, dp falls as D grows."""
    lo, hi = 0.01, 5.0
    for _ in range(80):
        mid = (lo * hi) ** 0.5
        if _dp_per_m_at(Q, mid, math.pi * mid * mid / 4, rho, nu, eps)[0] > fr:
            lo = mid
        else:
            hi = mid
    return hi


def _form_segments(inputs: dict) -> dict:
    r2 = lambda v: round(v + 0.0, 2)
    shape    = str(inputs.get("duct_shape") or "Circular")
    fr       = float(inputs.get("friction_rate") or 1.0)
    rho      = float(inputs.get("air_density") or 1.20)
    r        = float(inputs.get("aspect_ratio") or 2)
    material = str(inputs.get("duct_material") or "Galvanized Steel")
    eps      = FORM_ROUGHNESS_M.get(material, FORM_ROUGHNESS_M["Galvanized Steel"])
    mu       = 1.90e-5 if rho < 1.175 else 1.81e-5   # tropical 35 C below 1.175 kg/m3, else standard 20 C
    nu       = mu / rho

    rows = []
    for seg in inputs.get("segments") or []:
        Q = float(seg.get("flow_lps") or 0) / 1000
        if Q <= 0:
            continue
        L  = float(seg.get("length_m") or 0)
        st = str(seg.get("seg_type") or "Supply Main")
        D_calc = _equal_friction_diameter(Q, fr, rho, nu, eps)
        D_std_mm = next((d for d in FORM_ROUND_MM if d >= D_calc * 1000 - 1e-9), math.ceil(D_calc * 1000 / 50) * 50)
        D_std = D_std_mm / 1000
        circ = _dp_per_m_at(Q, D_std, math.pi * D_std * D_std / 4, rho, nu, eps)
        # rectangular: the duct of equal friction and flow has De = D_calc; b = r.a, rounded up to 50 mm
        a_m = D_calc * (1 + r) ** 0.25 / (1.30 * r ** 0.625)
        a_mm = math.ceil(round(a_m * 1000, 6) / 50) * 50
        b_mm = math.ceil(round(r * a_m * 1000, 6) / 50) * 50
        a, b = a_mm / 1000, b_mm / 1000
        rect = _dp_per_m_at(Q, 2 * a * b / (a + b), a * b, rho, nu, eps)
        dp_m, v, Re, f = rect if shape == "Rectangular" else circ
        limit = FORM_VEL_LIMITS.get(st, 6.0)
        check = "OK" if v <= limit else ("WARNING" if v <= limit * 1.2 else "HIGH")
        rows.append({
            "name": str(seg.get("name") or ""), "seg_type": st, "flow_lps": float(seg.get("flow_lps")),
            "flow_m3hr": round(Q * 3600, 1), "length_m": L,
            "dim": f"{max(a_mm, b_mm)} × {min(a_mm, b_mm)} mm" if shape == "Rectangular" else f"Ø{D_std_mm} mm",
            "velocity_ms": r2(v), "Re": round(Re), "f": round(f, 4), "dp_pa_m": round(dp_m, 3),
            "dp_pa": r2(dp_m * L), "vel_check": check, "vel_limit_ms": limit,
            "velocity_ok": check == "OK", "velocity_note": check,
            "_circ": {"D_calc_mm": round(D_calc * 1000, 1), "D_std_mm": D_std_mm, "v": circ[1], "dp_m": circ[0]},
            "_rect": {"a_mm": a_mm, "b_mm": b_mm, "v": rect[1], "De_mm": round(_de_from_rect(a, b) * 1000, 1)},
        })

    # the index run: segments in series (the mains) plus the worst branch on each side - branches are parallel paths
    def _worst(kind):
        c = [x for x in rows if x["seg_type"] == kind]
        return [max(c, key=lambda x: x["dp_pa"])] if c else []
    index_run = [x for x in rows if "Branch" not in x["seg_type"]] + _worst("Supply Branch") + _worst("Return Branch")
    for x in rows:
        x["on_index_run"] = any(x is y for y in index_run)

    total_dp   = r2(sum(x["dp_pa"] for x in index_run))
    fan_static = r2(total_dp * FITTINGS_FACTOR)
    max_flow   = max((x["flow_lps"] for x in rows), default=0)
    fan_kw     = r2(max_flow / 1000 * fan_static / (FAN_EFF * MOTOR_EFF * 1000))
    fan_hp     = r2(fan_kw / 0.746)
    fan_hp_std = next((h for h in STD_MOTOR_HP if h >= fan_hp), math.ceil(fan_hp * 10) / 10)

    supply = [x for x in rows if x["seg_type"] == "Supply Main"] or rows
    main = max(supply, key=lambda x: x["flow_lps"]) if supply else None
    drawing = {}
    if main:
        c, t = main["_circ"], main["_rect"]
        drawing = {
            "D_calc_mm": c["D_calc_mm"], "D_std_mm": c["D_std_mm"], "circular_velocity_ms": r2(c["v"]),
            "circular_dp_pam": round(c["dp_m"], 3), "circular_dp_total_pa": r2(c["dp_m"] * main["length_m"]),
            "rect_a_mm": max(t["a_mm"], t["b_mm"]), "rect_b_mm": min(t["a_mm"], t["b_mm"]),
            "rect_aspect": round(max(t["a_mm"], t["b_mm"]) / min(t["a_mm"], t["b_mm"]), 2),
            "rect_De_mm": t["De_mm"], "rect_velocity_ms": r2(t["v"]),
            "friction_rate_pam": fr, "application": main["seg_type"], "flow_m3hr": main["flow_m3hr"],
            "duct_length_m": main["length_m"], "velocity_ok": main["velocity_ok"], "velocity_note": main["velocity_note"],
        }
    for x in rows:
        x.pop("_circ"), x.pop("_rect")

    return {
        "segments":          rows,
        "total_dp_pa":       total_dp,
        "sum_all_dp_pa":     r2(sum(x["dp_pa"] for x in rows)),
        "index_run":         [x["name"] for x in index_run],
        "fittings_factor":   FITTINGS_FACTOR,
        "fan_static_pa":     fan_static,
        "total_length_m":    r2(sum(x["length_m"] for x in rows)),
        "max_flow_lps":      max_flow,
        "fan_motor_kw":      fan_kw,
        "fan_motor_hp_calc": fan_hp,
        "fan_motor_hp_std":  fan_hp_std,
        "duct_shape":        shape,
        "friction_rate":     fr,
        "air_density":       rho,
        "duct_material":     material,
        "roughness_mm":      round(eps * 1000, 3),
        **drawing,
        "calculation_source": "python/math",
        "standard": "ASHRAE 2021 Ch.21 | SMACNA | ASHRAE 62.1",
    }


# formula: duct_sizing_ashrae_2021
def calculate(inputs: dict) -> dict:
    """
    Main entry point - compatible with TypeScript calcDuctSizing() input keys.
    Supports single-section mode (one duct run) and multi-section mode (sections[]).
    """
    # ── Application and friction rate ─────────────────────────────────────────
    application  = str  (inputs.get("application",      "Office / Hospital"))
    fr_pam       = float(inputs.get("friction_rate_pam",
                         DESIGN_FRICTION_RATES.get(application, 1.0)))
    aspect_ratio = float(inputs.get("aspect_ratio",     1.5))   # width:height
    low_noise    = bool (inputs.get("low_noise",         False))

    # ── The page's segment schedule ────────────────────────────────────────────
    if inputs.get("segments"):
        return _form_segments(inputs)

    # ── Check for multi-section input ─────────────────────────────────────────
    raw_sections = inputs.get("sections", [])

    if raw_sections:
        # Multi-section mode - size each independently
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
        "fan_motor_kw":      None,      # Python doesn't size fan motor - renderer should check None
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
