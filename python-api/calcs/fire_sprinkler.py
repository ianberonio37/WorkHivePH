"""
Fire Sprinkler Hydraulic Calculation - Phase 5a
Standards: NFPA 13:2022 (Installation of Sprinkler Systems),
           NFPA 13R:2022 (Residential), PNS NFPA 13 (Philippine adoption),
           BFP (Bureau of Fire Protection) IRR RA 9514
Libraries: math (all formulas closed-form)

Hydraulic method: Hazen-Williams
  P_f = (6.05 × 10^5 × Q^1.85) / (C^1.85 × d^4.87)   [bar per metre]
  Q (L/min), d (mm internal diameter), C = roughness coefficient

Design area method (NFPA 13 §19.3):
  Most remote design area - density × area approach
  Q_total = density (mm/min) × design_area (m²) × conversion
  Plus hose stream allowance per hazard class

K-factor: Q = K × √P   (Q in L/min, P in bar)
  K50 = 50, K80 = 80, K115 = 115, K160 = 160, K200 = 200, K320 = 320
"""

import math

# ─── NFPA 13 hazard occupancy classifications ─────────────────────────────────
# density (mm/min), design_area (m²), hose_stream (L/min)
HAZARD_CLASS: dict[str, dict] = {
    "Light Hazard":            {"density_mm_min": 2.04,  "area_m2": 139, "hose_lpm": 950},
    "Ordinary Hazard Group 1": {"density_mm_min": 4.08,  "area_m2": 139, "hose_lpm": 1900},
    "Ordinary Hazard Group 2": {"density_mm_min": 6.12,  "area_m2": 139, "hose_lpm": 1900},
    "Extra Hazard Group 1":    {"density_mm_min": 8.16,  "area_m2": 232, "hose_lpm": 3785},
    "Extra Hazard Group 2":    {"density_mm_min": 12.24, "area_m2": 232, "hose_lpm": 3785},
}

# Occupancy → hazard class mapping (NFPA 13 Annex B)
OCCUPANCY_MAP: dict[str, str] = {
    "Office":           "Light Hazard",
    "Hotel Room":       "Light Hazard",
    "Hospital":         "Light Hazard",
    "School":           "Light Hazard",
    "Retail":           "Ordinary Hazard Group 1",
    "Restaurant":       "Ordinary Hazard Group 1",
    "Warehouse":        "Ordinary Hazard Group 2",
    "Manufacturing":    "Ordinary Hazard Group 2",
    "Parking":          "Ordinary Hazard Group 1",
    "Woodworking":      "Extra Hazard Group 1",
    "Paint Spray":      "Extra Hazard Group 2",
}

# ─── Sprinkler K-factors (L/min per bar^0.5) - NFPA 13 Table 6.2.3.1 ─────────
K_FACTORS: dict[str, float] = {
    "K50  (Standard Response 1/2\" orifice)":  50.0,
    "K80  (Large Orifice 17/32\" orifice)":    80.0,
    "K115 (Extra Large Orifice)":             115.0,
    "K160 (Extra Large Orifice)":             160.0,
    "K200 (Extra Large Orifice)":             200.0,
    "K320 (ESFR)":                            320.0,
}

# ─── Hazen-Williams C factors by pipe material - NFPA 13 Table A.23.4.2.1 ────
HW_C_FACTOR: dict[str, float] = {
    "Steel (black, unlined)":  120,
    "Steel (galvanized)":      120,
    "CPVC":                    150,
    "Copper":                  150,
    "Ductile Iron":            140,
    "Cast Iron":               100,
}

# ─── Standard steel pipe (Schedule 40) inside diameters - NFPA 13 ─────────────
PIPE_SIZES: list[dict] = [
    {"nominal_mm":  25, "id_mm":  26.6, "nominal_in": "1\""},
    {"nominal_mm":  32, "id_mm":  35.1, "nominal_in": "1-1/4\""},
    {"nominal_mm":  40, "id_mm":  40.9, "nominal_in": "1-1/2\""},
    {"nominal_mm":  50, "id_mm":  52.5, "nominal_in": "2\""},
    {"nominal_mm":  65, "id_mm":  62.7, "nominal_in": "2-1/2\""},
    {"nominal_mm":  80, "id_mm":  77.9, "nominal_in": "3\""},
    {"nominal_mm": 100, "id_mm": 102.3, "nominal_in": "4\""},
    {"nominal_mm": 125, "id_mm": 128.2, "nominal_in": "5\""},
    {"nominal_mm": 150, "id_mm": 154.1, "nominal_in": "6\""},
    {"nominal_mm": 200, "id_mm": 206.5, "nominal_in": "8\""},
]

# ─── NFPA 13 minimum residual pressure at most remote sprinkler ───────────────
MIN_RESIDUAL_BAR = 0.52   # bar = 7.5 psi (NFPA 13 §24.3.1)

# ─── Velocity limit for sprinkler branch lines (NFPA 13 / SFPE) ──────────────
MAX_VELOCITY_MS = 6.0   # m/s


def _hw_pressure_drop(Q_lpm: float, C: float, d_mm: float, L_m: float) -> float:
    """
    Hazen-Williams friction loss (bar) over length L_m.
    P_f = (6.05 × 10^5 × Q^1.85) / (C^1.85 × d^4.87) × L
    Q in L/min, d in mm, L in metres → P_f in bar
    """
    if Q_lpm <= 0 or d_mm <= 0:
        return 0.0
    return (6.05e5 * Q_lpm ** 1.85) / (C ** 1.85 * d_mm ** 4.87) * L_m


def _hw_flow_at_dp(dp_bar: float, C: float, d_mm: float, L_m: float) -> float:
    """Inverse H-W: flow (L/min) given pressure drop."""
    if dp_bar <= 0 or L_m <= 0:
        return 0.0
    return ((dp_bar * C ** 1.85 * d_mm ** 4.87) / (6.05e5 * L_m)) ** (1 / 1.85)


def _velocity(Q_lpm: float, d_mm: float) -> float:
    """Flow velocity in pipe (m/s)."""
    if d_mm <= 0:
        return 0.0
    A = math.pi * (d_mm / 1000 / 2) ** 2
    return (Q_lpm / 1000 / 60) / A


def _select_pipe(Q_lpm: float, C: float, L_m: float,
                 max_velocity: float = MAX_VELOCITY_MS) -> dict:
    """Select smallest pipe where velocity ≤ max_velocity."""
    for ps in PIPE_SIZES:
        v = _velocity(Q_lpm, ps["id_mm"])
        if v <= max_velocity:
            dp = _hw_pressure_drop(Q_lpm, C, ps["id_mm"], L_m)
            return {
                "nominal_mm":   ps["nominal_mm"],
                "nominal_in":   ps["nominal_in"],
                "id_mm":        ps["id_mm"],
                "velocity_ms":  round(v, 2),
                "dp_bar":       round(dp, 4),
                "dp_psi":       round(dp * 14.504, 3),
            }
    ps = PIPE_SIZES[-1]
    v  = _velocity(Q_lpm, ps["id_mm"])
    dp = _hw_pressure_drop(Q_lpm, C, ps["id_mm"], L_m)
    return {
        "nominal_mm":  ps["nominal_mm"],
        "nominal_in":  ps["nominal_in"],
        "id_mm":       ps["id_mm"],
        "velocity_ms": round(v, 2),
        "dp_bar":      round(dp, 4),
        "dp_psi":      round(dp * 14.504, 3),
    }


def calculate(inputs: dict) -> dict:
    """
    Main entry point - compatible with TypeScript calcFireSprinkler() keys.
    """
    # ── Occupancy / hazard ────────────────────────────────────────────────────
    occupancy    = str  (inputs.get("occupancy",      "Office"))
    hazard_key   = str  (inputs.get("hazard_class",
                          OCCUPANCY_MAP.get(occupancy, "Light Hazard")))
    hazard       = HAZARD_CLASS.get(hazard_key, HAZARD_CLASS["Light Hazard"])

    density      = float(inputs.get("density_mm_min",  hazard["density_mm_min"]))
    design_area  = float(inputs.get("design_area_m2",  hazard["area_m2"]))
    hose_lpm     = float(inputs.get("hose_stream_lpm", hazard["hose_lpm"]))

    # ── Sprinkler parameters ──────────────────────────────────────────────────
    k_label      = str  (inputs.get("k_factor_label",  "K80  (Large Orifice 17/32\" orifice)"))
    k_factor     = float(inputs.get("k_factor",
                          K_FACTORS.get(k_label, 80.0)))
    spacing_m    = float(inputs.get("sprinkler_spacing_m", 3.6))   # m between sprinklers
    coverage_m2  = spacing_m ** 2   # m² per sprinkler (square pattern)

    # ── Pipe parameters ───────────────────────────────────────────────────────
    pipe_mat     = str  (inputs.get("pipe_material",    "Steel (black, unlined)"))
    C            = float(inputs.get("hw_c_factor",
                          HW_C_FACTOR.get(pipe_mat, 120)))

    # Pipe lengths (m)
    branch_len   = float(inputs.get("branch_length_m",   20))
    cross_main_len = float(inputs.get("cross_main_length_m", 30))
    feed_main_len  = float(inputs.get("feed_main_length_m",  40))
    elevation_m    = float(inputs.get("elevation_m",         0))   # static head

    # ── Design area sprinkler count ───────────────────────────────────────────
    n_sprinklers = math.ceil(design_area / coverage_m2)

    # Flow per sprinkler from density × coverage
    q_per_sprinkler_lpm = density * coverage_m2   # mm/min × m² = L/min

    # Operating pressure at most remote sprinkler
    # Q = K × √P  →  P = (Q/K)²
    p_remote_bar = (q_per_sprinkler_lpm / k_factor) ** 2
    p_remote_psi = p_remote_bar * 14.504

    # Check minimum residual pressure
    min_pressure_ok = p_remote_bar >= MIN_RESIDUAL_BAR

    # ── Total design flow ─────────────────────────────────────────────────────
    q_sprinklers_lpm = q_per_sprinkler_lpm * n_sprinklers
    q_total_lpm      = q_sprinklers_lpm + hose_lpm
    q_total_m3hr     = q_total_lpm * 60 / 1000
    q_total_lps      = q_total_lpm / 60

    # ── Pipe sizing and pressure drop ─────────────────────────────────────────
    # Branch line (carries flow of n_sprinklers/n_branches - assume 4 per branch)
    n_per_branch = min(n_sprinklers, 4)
    q_branch_lpm = q_per_sprinkler_lpm * n_per_branch
    branch_pipe  = _select_pipe(q_branch_lpm, C, branch_len)

    # Cross main (carries half the design area flow)
    q_cross_lpm  = q_sprinklers_lpm / 2
    cross_pipe   = _select_pipe(q_cross_lpm, C, cross_main_len)

    # Feed main (carries all sprinkler flow)
    feed_pipe    = _select_pipe(q_sprinklers_lpm, C, feed_main_len)

    # ── Pressure losses ───────────────────────────────────────────────────────
    # Friction losses (H-W)
    dp_branch  = branch_pipe["dp_bar"]
    dp_cross   = cross_pipe["dp_bar"]
    dp_feed    = feed_pipe["dp_bar"]

    # Fittings allowance (30% of pipe friction - NFPA 13 equivalent pipe length method)
    fittings_factor = 1.30
    dp_total_friction = (dp_branch + dp_cross + dp_feed) * fittings_factor

    # Static head (elevation): 1 m of water = 0.0981 bar
    static_bar = elevation_m * 0.0981

    # Total system pressure required at pump discharge
    p_system_bar = p_remote_bar + dp_total_friction + static_bar
    p_system_psi = p_system_bar * 14.504

    # ── Compliance checks ─────────────────────────────────────────────────────
    velocity_ok = (branch_pipe["velocity_ms"] <= MAX_VELOCITY_MS and
                   cross_pipe["velocity_ms"]  <= MAX_VELOCITY_MS and
                   feed_pipe["velocity_ms"]   <= MAX_VELOCITY_MS)

    # ── BFP / NFPA 13 field notes ────────────────────────────────────────────
    field_notes = [
        f"Hazard class: {hazard_key} - density {density} mm/min over {design_area} m² design area.",
        f"Hose stream allowance: {hose_lpm} L/min per NFPA 13.",
        f"Minimum residual pressure at most remote sprinkler: "
        f"{MIN_RESIDUAL_BAR} bar (7.5 psi) - {'PASS' if min_pressure_ok else 'FAIL: increase pump pressure'}.",
        "Hydraulic remote area must be the most hydraulically demanding area (highest elevation, longest run).",
        "BFP PD 1185 / RA 9514: sprinkler system requires 3rd-party inspection and BFP acceptance.",
        f"Pipe material: {pipe_mat} (C={C}). Use listed fittings per NFPA 13 §7.",
    ]

    return {
        # Hazard design basis
        "hazard_class":            hazard_key,
        "occupancy":               occupancy,
        "density_mm_min":          density,
        "design_area_m2":          design_area,
        "hose_stream_lpm":         hose_lpm,

        # Sprinkler design
        "k_factor":                k_factor,
        "k_factor_label":          k_label,
        "sprinkler_spacing_m":     spacing_m,
        "coverage_per_sprinkler_m2": round(coverage_m2, 1),
        "n_sprinklers_design_area": n_sprinklers,
        "q_per_sprinkler_lpm":     round(q_per_sprinkler_lpm, 1),
        "p_remote_bar":            round(p_remote_bar, 3),
        "p_remote_psi":            round(p_remote_psi, 2),
        "min_pressure_ok":         min_pressure_ok,
        "min_pressure_bar":        MIN_RESIDUAL_BAR,

        # System flow
        "q_sprinklers_lpm":        round(q_sprinklers_lpm, 1),
        "q_total_lpm":             round(q_total_lpm, 1),
        "q_total_m3hr":            round(q_total_m3hr, 2),
        "q_total_lps":             round(q_total_lps, 2),

        # Pipe sizing
        "branch_pipe":             branch_pipe,
        "cross_main_pipe":         cross_pipe,
        "feed_main_pipe":          feed_pipe,

        # Pressure breakdown
        "dp_branch_bar":           round(dp_branch, 4),
        "dp_cross_main_bar":       round(dp_cross, 4),
        "dp_feed_main_bar":        round(dp_feed, 4),
        "dp_fittings_factor":      fittings_factor,
        "dp_total_friction_bar":   round(dp_total_friction, 4),
        "static_head_bar":         round(static_bar, 4),
        "p_system_required_bar":   round(p_system_bar, 3),
        "p_system_required_psi":   round(p_system_psi, 2),

        # Compliance
        "velocity_ok":             velocity_ok,
        "hw_c_factor":             C,
        "pipe_material":           pipe_mat,

        # Field notes
        "field_notes":             field_notes,

        # Metadata
        "inputs_used": {
            "hazard_class":        hazard_key,
            "k_factor":            k_factor,
            "pipe_material":       pipe_mat,
            "sprinkler_spacing_m": spacing_m,
        },
        "calculation_source": "python/math",
        "standard": "NFPA 13:2022 | PNS NFPA 13 | BFP IRR RA 9514",

        # ── Legacy renderer aliases (frontend renderFireSprinklerReport) ───────
        "N_sprinklers":        n_sprinklers,
        "Q_sprinklers_total":  round(q_sprinklers_lpm, 1),
        "Q_total":             round(q_total_lpm, 1),
        "Q_hose":              round(hose_lpm, 1),
        "Q_per_head":          round(q_per_sprinkler_lpm, 1),
        "P_design":            round(p_remote_bar, 3),
        "P_source":            round(p_system_bar, 3),
        "P_source_kPa":        round(p_system_bar * 100, 1),
        "H_friction":          round(dp_total_friction * 10.2, 2),
        "coverage_per_head":   round(coverage_m2, 1),
        "density":             density,
        "design_area":         design_area,
        "hazard":              hazard_key,
        "pipe_dia":            str(branch_pipe.get("nominal_mm", "-")) + " mm",
        "duration":            60,   # NFPA 13 minimum 60-min water supply
    }
