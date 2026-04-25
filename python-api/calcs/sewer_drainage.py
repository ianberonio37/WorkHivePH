"""
Sewer / Drainage System — Phase 6b
Standards: NSCP (National Structural Code of the Philippines) Vol.2 Plumbing,
           PSME Code (Philippine Society of Mechanical Engineers),
           ASPE Data Book Vol.2, IPC (International Plumbing Code) adopted by NSCP,
           DPWH Plumbing Code provisions
Libraries: math (all formulas closed-form)

Method:
  Drainage Fixture Units (DFU) → design flow via fixture unit chart
  Manning's equation: Q = (1/n) × A × R^(2/3) × S^(1/2)   [m³/s]
  Partial-flow design: pipes sized at d/D = 0.50 (half-full) to 0.80 max
  Vertical stacks carry full DFU; horizontal branches at d/D = 0.50
"""

import math

# ─── NSCP / ASPE Drainage Fixture Units (DFU) per outlet type ─────────────────
# Based on IPC Table 709.1 and ASPE Data Book Vol.2 Table 1-6
DRAINAGE_FIXTURE_UNITS: dict[str, dict] = {
    "Water Closet":             {"dfu": 4,  "trap_size_mm": 75},
    "Urinal (floor-mounted)":   {"dfu": 4,  "trap_size_mm": 50},
    "Urinal (wall-mounted)":    {"dfu": 2,  "trap_size_mm": 50},
    "Lavatory (single)":        {"dfu": 1,  "trap_size_mm": 32},
    "Lavatory (multiple)":      {"dfu": 2,  "trap_size_mm": 38},
    "Bathtub":                  {"dfu": 2,  "trap_size_mm": 38},
    "Shower (single stall)":    {"dfu": 2,  "trap_size_mm": 38},
    "Kitchen sink (residential)": {"dfu": 2, "trap_size_mm": 38},
    "Kitchen sink (commercial)":  {"dfu": 3, "trap_size_mm": 50},
    "Service sink (mop basin)":   {"dfu": 3, "trap_size_mm": 75},
    "Dishwasher (domestic)":      {"dfu": 2, "trap_size_mm": 38},
    "Clothes washer":             {"dfu": 3, "trap_size_mm": 50},
    "Floor drain (50mm trap)":    {"dfu": 2, "trap_size_mm": 50},
    "Floor drain (75mm trap)":    {"dfu": 3, "trap_size_mm": 75},
    "Drinking fountain":          {"dfu": 1, "trap_size_mm": 32},
    "Dental unit / cuspidor":     {"dfu": 1, "trap_size_mm": 32},
    "Interceptor (grease)":       {"dfu": 3, "trap_size_mm": 50},
}

# ─── DFU → Design Flow conversion (ASPE / IPC Table C) ──────────────────────
# Piecewise power-law fit to IPC/ASPE drainage flow table
# Q (L/s) = a × DFU^b
DFU_FLOW_CURVE: list[dict] = [
    {"dfu_max":   3,  "a": 0.20, "b": 0.80},
    {"dfu_max":  12,  "a": 0.38, "b": 0.68},
    {"dfu_max":  50,  "a": 0.55, "b": 0.62},
    {"dfu_max": 200,  "a": 0.75, "b": 0.56},
    {"dfu_max": 999,  "a": 1.05, "b": 0.50},
]

def _dfu_to_flow(dfu: float) -> float:
    """Peak probable drainage flow (L/s) from total DFU."""
    if dfu <= 0:
        return 0.0
    for seg in DFU_FLOW_CURVE:
        if dfu <= seg["dfu_max"]:
            return seg["a"] * (dfu ** seg["b"])
    last = DFU_FLOW_CURVE[-1]
    return last["a"] * (dfu ** last["b"])

# ─── Manning's n values by pipe material (NSCP / ASPE) ───────────────────────
MANNING_N: dict[str, float] = {
    "uPVC / CPVC":          0.009,
    "Cast Iron (uncoated)": 0.013,
    "Cast Iron (coated)":   0.012,
    "Concrete":             0.013,
    "Vitrified Clay":       0.013,
    "HDPE":                 0.009,
    "Ductile Iron":         0.012,
    "Corrugated Steel":     0.022,
}

# ─── Standard drain pipe sizes (mm nominal) ──────────────────────────────────
DRAIN_PIPE_SIZES: list[dict] = [
    {"nominal_mm":  32, "id_mm":  30.5},
    {"nominal_mm":  40, "id_mm":  38.5},
    {"nominal_mm":  50, "id_mm":  48.5},
    {"nominal_mm":  65, "id_mm":  62.5},
    {"nominal_mm":  75, "id_mm":  73.0},
    {"nominal_mm": 100, "id_mm":  97.5},
    {"nominal_mm": 125, "id_mm": 122.3},
    {"nominal_mm": 150, "id_mm": 147.0},
    {"nominal_mm": 200, "id_mm": 196.0},
    {"nominal_mm": 250, "id_mm": 245.0},
    {"nominal_mm": 300, "id_mm": 294.0},
]

# ─── NSCP minimum slopes for horizontal drain branches ───────────────────────
# NSCP Vol.2 §P-814 / IPC §704.1
MIN_SLOPE: dict[str, float] = {
    "≤75mm":  0.0208,   # 1:48 ≈ 25mm/m (1/4 in/ft)
    "100mm":  0.0208,   # 1:48
    "125mm":  0.0104,   # 1:96 ≈ 13mm/m (1/8 in/ft)
    "150mm":  0.0104,
    ">150mm": 0.0052,   # 1:192 ≈ 5mm/m (1/16 in/ft)
}

def _min_slope(nominal_mm: int) -> float:
    """NSCP minimum slope for horizontal drainage branch."""
    if nominal_mm <= 75:
        return MIN_SLOPE["≤75mm"]
    elif nominal_mm <= 100:
        return MIN_SLOPE["100mm"]
    elif nominal_mm <= 150:
        return MIN_SLOPE["125mm"]
    else:
        return MIN_SLOPE[">150mm"]

# ─── Vent sizing (NSCP / IPC §916) ───────────────────────────────────────────
# Vent pipe not less than 1/2 drain diameter, min 32mm
def _vent_size_mm(drain_nominal_mm: int) -> int:
    v = max(drain_nominal_mm // 2, 32)
    # Round up to next standard size
    for ps in DRAIN_PIPE_SIZES:
        if ps["nominal_mm"] >= v:
            return ps["nominal_mm"]
    return DRAIN_PIPE_SIZES[-1]["nominal_mm"]

# ─── Stormwater / roof drainage design rainfall (mm/hr) ──────────────────────
# NSCP / DPWH design rainfall intensities (5-yr return, 5-min duration)
RAINFALL_INTENSITY: dict[str, float] = {
    "Metro Manila":  200,
    "Cebu City":     180,
    "Davao City":    150,
    "Iloilo City":   170,
    "Cagayan de Oro": 160,
    "General":       180,   # conservative default
}

# ─── Manning's formula helpers ────────────────────────────────────────────────

def _manning_full(d_m: float, n: float, S: float) -> float:
    """Full-pipe flow (m³/s) by Manning's equation for circular pipe."""
    if d_m <= 0 or S <= 0:
        return 0.0
    A = math.pi * (d_m / 2) ** 2          # full cross-section area (m²)
    R = d_m / 4                            # hydraulic radius for full circle = D/4
    return (1 / n) * A * (R ** (2 / 3)) * (S ** 0.5)


def _manning_partial(d_m: float, n: float, S: float, dd_ratio: float) -> float:
    """
    Partial-flow (m³/s) at depth ratio d/D.
    Uses geometric relationships for circular pipe at partial depth.
    """
    if dd_ratio <= 0 or dd_ratio > 1.0:
        return 0.0
    r = d_m / 2
    # Angle θ (radians) subtended at centre for given depth
    # d = r(1 − cos(θ/2)) → cos(θ/2) = 1 − d/r → θ = 2·acos(1 − dd_ratio)
    theta = 2 * math.acos(max(-1, min(1, 1 - dd_ratio)))
    A = (r ** 2) * (theta - math.sin(theta)) / 2     # wetted area
    P = r * theta                                      # wetted perimeter
    if P <= 0:
        return 0.0
    R = A / P                                          # hydraulic radius
    return (1 / n) * A * (R ** (2 / 3)) * (S ** 0.5)


def _velocity_partial(d_m: float, n: float, S: float, dd_ratio: float) -> float:
    """Flow velocity (m/s) at partial depth."""
    Q = _manning_partial(d_m, n, S, dd_ratio)
    r = d_m / 2
    theta = 2 * math.acos(max(-1, min(1, 1 - dd_ratio)))
    A = (r ** 2) * (theta - math.sin(theta)) / 2
    if A <= 0:
        return 0.0
    return Q / A


def _select_drain_pipe(Q_lps: float, n: float, S: float,
                       dd_target: float = 0.50,
                       dd_max:    float = 0.80) -> dict:
    """
    Select smallest drain pipe that carries Q_lps at or below dd_target
    (default half-full design), but never exceeding dd_max.
    Returns sizing results including actual d/D ratio.
    """
    Q_m3s = Q_lps / 1000
    for ps in DRAIN_PIPE_SIZES:
        d_m = ps["id_mm"] / 1000
        Q_full = _manning_full(d_m, n, S)
        if Q_full <= 0:
            continue
        # Actual d/D ratio at design flow using ratio Q/Q_full
        # For Manning partial flow, Q_partial/Q_full ≈ f(d/D) — solve numerically
        # Binary search for d/D
        lo, hi = 0.01, 1.0
        for _ in range(40):
            mid = (lo + hi) / 2
            if _manning_partial(d_m, n, S, mid) < Q_m3s:
                lo = mid
            else:
                hi = mid
        actual_dd = (lo + hi) / 2
        if actual_dd <= dd_max:
            v = _velocity_partial(d_m, n, S, actual_dd)
            Q_at_target = _manning_partial(d_m, n, S, dd_target)
            return {
                "nominal_mm":   ps["nominal_mm"],
                "id_mm":        ps["id_mm"],
                "dd_ratio":     round(actual_dd, 3),
                "dd_target":    dd_target,
                "velocity_ms":  round(v, 2),
                "Q_full_lps":   round(Q_full * 1000, 2),
                "Q_design_lps": round(Q_m3s * 1000, 3),
                "slope_used":   S,
            }
    # Fall through: use largest size
    ps = DRAIN_PIPE_SIZES[-1]
    d_m = ps["id_mm"] / 1000
    Q_full = _manning_full(d_m, n, S)
    lo, hi = 0.01, 1.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if _manning_partial(d_m, n, S, mid) < Q_m3s:
            lo = mid
        else:
            hi = mid
    actual_dd = (lo + hi) / 2
    v = _velocity_partial(d_m, n, S, actual_dd)
    return {
        "nominal_mm":   ps["nominal_mm"],
        "id_mm":        ps["id_mm"],
        "dd_ratio":     round(actual_dd, 3),
        "dd_target":    dd_target,
        "velocity_ms":  round(v, 2),
        "Q_full_lps":   round(Q_full * 1000, 2),
        "Q_design_lps": round(Q_m3s * 1000, 3),
        "slope_used":   S,
    }


def _stormwater_flow(roof_area_m2: float, C: float, i_mmhr: float) -> float:
    """
    Rational method: Q = C × i × A  (L/s)
    C = runoff coefficient (roof = 0.90 per NSCP)
    i = rainfall intensity (mm/hr) → L/s/m² = i/3600000
    A = catchment area (m²)
    Q = C × (i/3600000) × 1000 × A  — simplified: Q_lps = C × i × A / 3600
    """
    return C * i_mmhr * roof_area_m2 / 3600


# ─── Main calculation ─────────────────────────────────────────────────────────

def calculate(inputs: dict) -> dict:
    """Main entry point — compatible with TypeScript calcSewerDrainage() keys."""
    # ── Building / system parameters ─────────────────────────────────────────
    building_floors   = int  (inputs.get("building_floors",    5))
    floor_height_m    = float(inputs.get("floor_height_m",     3.5))
    pipe_material     = str  (inputs.get("pipe_material",      "uPVC / CPVC"))
    n                 = MANNING_N.get(pipe_material, 0.009)

    # ── Fixture unit calculation ──────────────────────────────────────────────
    fixtures = inputs.get("fixtures", [])
    total_dfu = 0.0
    fixture_rows = []

    if fixtures:
        for f in fixtures:
            name   = str  (f.get("fixture_type", "Lavatory (single)"))
            qty    = float(f.get("quantity", 1))
            f_data = DRAINAGE_FIXTURE_UNITS.get(name, {"dfu": 2, "trap_size_mm": 50})
            dfu    = f_data["dfu"] * qty
            total_dfu += dfu
            fixture_rows.append({
                "fixture_type": name,
                "quantity":     qty,
                "dfu_each":     f_data["dfu"],
                "dfu_total":    dfu,
                "trap_mm":      f_data["trap_size_mm"],
            })
    else:
        # Default estimate from building_floors × typical office floor
        wc_qty  = building_floors * 2   # 2 WCs per floor
        lav_qty = building_floors * 2
        fd_qty  = building_floors       # 1 floor drain per floor
        for name, qty in [("Water Closet", wc_qty),
                           ("Lavatory (single)", lav_qty),
                           ("Floor drain (50mm trap)", fd_qty)]:
            f_data = DRAINAGE_FIXTURE_UNITS[name]
            dfu    = f_data["dfu"] * qty
            total_dfu += dfu
            fixture_rows.append({
                "fixture_type": name,
                "quantity":     qty,
                "dfu_each":     f_data["dfu"],
                "dfu_total":    dfu,
                "trap_mm":      f_data["trap_size_mm"],
            })

    # ── Design flow (DFU → L/s) ───────────────────────────────────────────────
    design_flow_lps  = _dfu_to_flow(total_dfu)
    design_flow_lpm  = design_flow_lps * 60
    design_flow_m3hr = design_flow_lps * 3.6

    # ── Vertical stack sizing (NSCP — DFU method) ─────────────────────────────
    # NSCP Table P-803.1: max DFU per stack by pipe size
    STACK_DFU_LIMITS = {
        75:  30, 100: 240, 125: 540, 150: 960, 200: 2200, 250: 3800,
    }
    stack_nominal_mm = 75
    for nom, max_dfu in sorted(STACK_DFU_LIMITS.items()):
        if total_dfu <= max_dfu:
            stack_nominal_mm = nom
            break
    else:
        stack_nominal_mm = 250

    stack_id_mm = next(
        (ps["id_mm"] for ps in DRAIN_PIPE_SIZES if ps["nominal_mm"] == stack_nominal_mm),
        DRAIN_PIPE_SIZES[-1]["id_mm"]
    )

    # ── Horizontal building drain ─────────────────────────────────────────────
    # Default slope = NSCP minimum for the stack size
    slope_input = float(inputs.get("slope",
                          _min_slope(stack_nominal_mm)))
    slope = max(slope_input, _min_slope(stack_nominal_mm))

    horiz_pipe = _select_drain_pipe(design_flow_lps, n, slope, dd_target=0.50, dd_max=0.80)

    # Velocity check: NSCP requires ≥ 0.6 m/s (self-cleansing), ≤ 3.0 m/s
    v_ok = 0.6 <= horiz_pipe["velocity_ms"] <= 3.0

    # Actual minimum slope from Manning (self-cleansing velocity check)
    # Solve S so that v = 0.6 m/s at d/D = 0.50 for selected pipe
    d_m_horiz = horiz_pipe["id_mm"] / 1000
    # At d/D=0.50: A = pi*r^2/2, R = d_m/4, v = (1/n)*R^(2/3)*S^(1/2)
    # → S_min = (n * v / R^(2/3))^2
    R_half = d_m_horiz / 4
    S_min_selfclean = (n * 0.6 / (R_half ** (2/3))) ** 2

    # ── Vent pipe sizing ──────────────────────────────────────────────────────
    vent_nominal_mm = _vent_size_mm(horiz_pipe["nominal_mm"])
    vent_stack_mm   = _vent_size_mm(stack_nominal_mm)

    # ── Stormwater / roof drainage ────────────────────────────────────────────
    roof_area_m2      = float(inputs.get("roof_area_m2", 0))
    location          = str  (inputs.get("location", "General"))
    rainfall_mmhr     = float(inputs.get("rainfall_intensity_mmhr",
                               RAINFALL_INTENSITY.get(location, 180)))
    C_runoff          = float(inputs.get("runoff_coefficient", 0.90))   # roof typical

    storm_flow_lps    = _stormwater_flow(roof_area_m2, C_runoff, rainfall_mmhr)
    storm_pipe: dict  = {}
    if roof_area_m2 > 0:
        # Roof drain slope: typically 1% minimum for flat roofs
        storm_slope = float(inputs.get("storm_slope", 0.01))
        storm_pipe  = _select_drain_pipe(storm_flow_lps, n, storm_slope,
                                          dd_target=0.50, dd_max=0.80)

    # ── Septic / treatment sizing (NSCP Appendix B) ───────────────────────────
    # Liquid volume: 120 L/person/day × 1.5 day retention (NSCP minimum)
    num_persons       = float(inputs.get("num_persons", 0))
    sep_liquid_m3     = 0.0
    sep_recommended_m3 = 0.0
    if num_persons > 0:
        sep_liquid_m3     = num_persons * 120 / 1000 * 1.5
        # Standard septic tank sizes (m³)
        std_sep = [0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 7.5, 10, 15, 20]
        sep_recommended_m3 = next((s for s in std_sep if s >= sep_liquid_m3), std_sep[-1])

    # ── Grease interceptor sizing (NSCP / PDC) ───────────────────────────────
    # Required where commercial kitchen fixtures are present
    has_grease_trap   = any(
        f.get("fixture_type", "") in ["Kitchen sink (commercial)", "Interceptor (grease)"]
        for f in fixtures
    )
    grease_trap_note  = (
        "Grease interceptor required (NSCP §P-1017): size per PDC Table G-1 "
        "based on kitchen fixture units and retention time ≥ 2 min."
        if has_grease_trap else
        "No commercial kitchen fixtures detected — grease trap not required."
    )

    # ── NSCP compliance notes ─────────────────────────────────────────────────
    code_notes = [
        f"Pipe material: {pipe_material} (Manning n = {n}).",
        f"Horizontal drain slope: {round(slope*1000,1)} mm/m "
        f"(NSCP min = {round(_min_slope(horiz_pipe['nominal_mm'])*1000,1)} mm/m).",
        f"Self-cleansing velocity at d/D=0.50: min slope = {round(S_min_selfclean*1000,2)} mm/m.",
        f"Velocity check ({'PASS' if v_ok else 'FAIL'}): {horiz_pipe['velocity_ms']} m/s "
        "(0.6–3.0 m/s per NSCP §P-814).",
        "All horizontal drains shall slope continuously toward the stack (NSCP §P-814.1).",
        "Cleanout required every 15 m and at each change of direction > 45° (NSCP §P-817).",
        "Vent stack must extend ≥ 300 mm above roof, min 1.2 m from any window (NSCP §P-910).",
        grease_trap_note,
    ]

    return {
        # Fixture units
        "total_dfu":           round(total_dfu, 1),
        "fixture_schedule":    fixture_rows,

        # Design flow
        "design_flow_lps":     round(design_flow_lps, 3),
        "design_flow_lpm":     round(design_flow_lpm, 2),
        "design_flow_m3hr":    round(design_flow_m3hr, 3),

        # Vertical stack
        "stack_nominal_mm":    stack_nominal_mm,
        "stack_id_mm":         stack_id_mm,

        # Horizontal building drain
        "horizontal_drain":    horiz_pipe,
        "slope_used_mm_m":     round(slope * 1000, 2),
        "slope_min_nscp_mm_m": round(_min_slope(horiz_pipe["nominal_mm"]) * 1000, 2),
        "slope_selfclean_mm_m": round(S_min_selfclean * 1000, 2),
        "velocity_ok":         v_ok,
        "pipe_material":       pipe_material,
        "manning_n":           n,

        # Vent pipes
        "vent_branch_mm":      vent_nominal_mm,
        "vent_stack_mm":       vent_stack_mm,

        # Stormwater / roof drainage
        "roof_area_m2":        roof_area_m2,
        "rainfall_mmhr":       rainfall_mmhr,
        "runoff_coefficient":  C_runoff,
        "storm_flow_lps":      round(storm_flow_lps, 3) if roof_area_m2 > 0 else None,
        "storm_drain_pipe":    storm_pipe if roof_area_m2 > 0 else None,

        # Septic tank
        "septic_liquid_m3":    round(sep_liquid_m3, 2) if num_persons > 0 else None,
        "septic_recommended_m3": sep_recommended_m3 if num_persons > 0 else None,

        # Code compliance
        "code_notes":          code_notes,

        # Metadata
        "inputs_used": {
            "building_floors":  building_floors,
            "pipe_material":    pipe_material,
            "slope":            slope,
            "num_persons":      num_persons,
            "roof_area_m2":     roof_area_m2,
        },
        "calculation_source": "python/math",
        "standard": "NSCP Vol.2 | PSME Code | ASPE Vol.2 | IPC (as adopted by NSCP)",
    }
