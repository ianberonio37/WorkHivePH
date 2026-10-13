"""
Pipe Sizing - Phase 1b
Standards: ASHRAE 2021 Fundamentals Ch. 22, PSME Code, PNS/ISO 4427
Libraries: fluids (Darcy-Weisbach, Colebrook-White), iapws (water properties)

Replaces the hand-rolled TypeScript implementation with:
- Colebrook-White friction factor (Churchill equation via fluids)
- Real water properties at operating temperature (iapws IAPWS97)
- Proper minor losses via K-value method (fittings table)
- Recommended pipe size selection by target velocity range
"""

from fluids import friction_factor, Reynolds
from iapws import IAPWS97
import math

# ─── Pipe roughness by material (mm) - ASHRAE 2021 Fundamentals Table 2 ───────
PIPE_ROUGHNESS_MM: dict[str, float] = {
    "PVC":              0.0015,
    "Copper":           0.0015,
    "Galvanized Steel": 0.15,
    "Carbon Steel":     0.046,
    "Cast Iron":        0.26,
    "Stainless Steel":  0.015,
    "HDPE":             0.0015,
    "GI":               0.15,
    "Black Steel":      0.046,
    "uPVC":             0.0015,
}

# ─── Standard pipe inside diameters by nominal size (mm) - PNS/ISO 4427 ──────
PIPE_SIZES: list[dict] = [
    {"nominal": 15,  "id_mm": 15.8},
    {"nominal": 20,  "id_mm": 20.9},
    {"nominal": 25,  "id_mm": 26.6},
    {"nominal": 32,  "id_mm": 35.1},
    {"nominal": 40,  "id_mm": 40.9},
    {"nominal": 50,  "id_mm": 52.5},
    {"nominal": 65,  "id_mm": 62.7},
    {"nominal": 80,  "id_mm": 77.9},
    {"nominal": 100, "id_mm": 102.3},
    {"nominal": 125, "id_mm": 128.2},
    {"nominal": 150, "id_mm": 154.1},
    {"nominal": 200, "id_mm": 206.5},
    {"nominal": 250, "id_mm": 257.4},
    {"nominal": 300, "id_mm": 309.6},
]

# ─── K-values for common fittings - Crane TP-410 ─────────────────────────────
FITTING_K: dict[str, float] = {
    "gate_valve_open":      0.1,
    "globe_valve_open":     10.0,
    "ball_valve_open":      0.05,
    "butterfly_valve_open": 0.6,
    "check_valve_swing":    2.5,
    "elbow_90":             0.9,
    "elbow_45":             0.4,
    "tee_thru":             0.6,
    "tee_branch":           1.8,
    "reducer":              0.5,
    "entrance_sharp":       0.5,
    "exit":                 1.0,
}

# Velocity targets per service type (m/s) - PSME Code / ASHRAE
VELOCITY_TARGETS: dict[str, dict] = {
    "Chilled Water":     {"min": 0.6, "max": 3.0, "ideal": 1.5},
    "Hot Water":         {"min": 0.6, "max": 3.0, "ideal": 1.2},
    "Condenser Water":   {"min": 0.9, "max": 3.5, "ideal": 2.0},
    "Domestic Cold":     {"min": 0.6, "max": 2.5, "ideal": 1.2},
    "Domestic Hot":      {"min": 0.6, "max": 2.0, "ideal": 1.0},
    "Fire Protection":   {"min": 1.2, "max": 4.5, "ideal": 2.5},
    "General":           {"min": 0.6, "max": 3.0, "ideal": 1.5},
}


def _water_props(temp_c: float) -> tuple[float, float]:
    """Return (density kg/m3, dynamic viscosity Pa·s) via IAPWS-IF97."""
    try:
        state = IAPWS97(T=temp_c + 273.15, x=0)
        return state.rho, state.mu
    except Exception:
        return 998.2, 1.002e-3   # fallback: 20°C water


def _pipe_head_loss(
    flow_m3s: float,
    id_m: float,
    length_m: float,
    roughness_m: float,
    rho: float,
    mu: float,
    fittings_k: float = 0.0,
) -> tuple[float, float, float, float, float]:
    """
    Compute head loss for a pipe segment.
    Returns (h_total_m, h_friction_m, h_minor_m, velocity_ms, Re).
    """
    A  = math.pi * (id_m / 2) ** 2
    v  = flow_m3s / A
    Re = Reynolds(V=v, D=id_m, rho=rho, mu=mu)

    if Re < 1:
        return 0.0, 0.0, 0.0, v, Re

    eD      = roughness_m / id_m
    f       = friction_factor(Re=Re, eD=eD)
    h_f     = f * (length_m / id_m) * (v ** 2 / (2 * 9.81))
    h_minor = fittings_k * (v ** 2 / (2 * 9.81))
    h_total = h_f + h_minor
    return h_total, h_f, h_minor, v, Re


def _select_pipe(flow_m3s: float, roughness_m: float, rho: float, mu: float,
                 service: str, length_m: float) -> list[dict]:
    """
    Evaluate all standard pipe sizes and return results sorted by velocity,
    flagging the recommended size based on target velocity range.
    """
    targets  = VELOCITY_TARGETS.get(service, VELOCITY_TARGETS["General"])
    results  = []

    for ps in PIPE_SIZES:
        id_m = ps["id_mm"] / 1000
        A    = math.pi * (id_m / 2) ** 2
        v    = flow_m3s / A
        Re   = Reynolds(V=v, D=id_m, rho=rho, mu=mu)

        if Re < 1:
            continue

        eD  = roughness_m / id_m
        f   = friction_factor(Re=Re, eD=eD)
        hf  = f * (length_m / id_m) * (v ** 2 / (2 * 9.81))
        dp  = f * (length_m / id_m) * (rho * v ** 2 / 2) / 1000  # kPa

        in_range = targets["min"] <= v <= targets["max"]
        results.append({
            "nominal_mm":  ps["nominal"],
            "id_mm":       round(ps["id_mm"], 1),
            "velocity_ms": round(v, 3),
            "Re":          round(Re, 0),
            "friction_f":  round(f, 5),
            "head_loss_m": round(hf, 3),
            "pressure_drop_kpa_per_m": round(dp / length_m, 4),
            "in_velocity_range": in_range,
            "recommended": False,  # flagged below
            # ★THE REPORT READS THESE (2026-10-09, walked KCW41283): its 5.2 comparison table printed "undefined" in
            # every cell - the top-level fields had renderer aliases, the rows never did.
            "dia_mm":      ps["nominal"],
            "velocity":    round(v, 2),
            "hf_per_m":    round(hf / length_m, 5) if length_m > 0 else 0.0,
            "press_kpa_m": round(dp / length_m, 4) if length_m > 0 else 0.0,
        })

    # Flag the smallest pipe whose velocity is within the target range
    for r in results:
        if r["in_velocity_range"]:
            r["recommended"] = True
            break

    # If none in range, flag the one closest to ideal velocity
    if not any(r["recommended"] for r in results):
        best = min(results, key=lambda r: abs(r["velocity_ms"] - targets["ideal"]))
        best["recommended"] = True

    return results


# formula: pipe_sizing_ashrae_2021
def calculate(inputs: dict) -> dict:
    """
    Main entry point - compatible with TypeScript calcPipeSizing() input keys.
    """
    # ── Inputs ────────────────────────────────────────────────────────────────
    flow_lpm    = float(inputs.get("flow_rate",       0) or inputs.get("flow_lpm", 0))
    pipe_dia_mm = float(inputs.get("pipe_diameter",   0))   # 0 = auto-select
    length_m    = float(inputs.get("pipe_length",     50))
    pipe_mat    = str  (inputs.get("pipe_material",   "PVC"))
    temp_c      = float(inputs.get("fluid_temp_c",    25))
    service     = str  (inputs.get("service_type",    "General"))
    # ★THE FORM SENDS fittings_allowance (2026-10-09, walked KCW41283). This read only fittings_allowance_pct, which no
    # caller sends, so every report used 20% whatever the person typed. The legacy key still counts when it is the one given.
    fittings_pct= float(inputs.get("fittings_allowance", inputs.get("fittings_allowance_pct", 20)) or 20)

    if flow_lpm <= 0:
        raise ValueError("Flow rate must be greater than 0 L/min.")

    flow_m3s  = flow_lpm / 1000 / 60
    flow_m3hr = flow_lpm * 60 / 1000
    roughness_m = PIPE_ROUGHNESS_MM.get(pipe_mat, 0.046) / 1000

    # ── Fluid properties ──────────────────────────────────────────────────────
    rho, mu = _water_props(temp_c)
    # The form auto-fills density by service type and invites a change for a special fluid; that change was ignored.
    # Viscosity stays the water value at the operating temperature - the form asks for no viscosity.
    user_rho = float(inputs.get("fluid_density") or 0)
    if user_rho > 0:
        rho = user_rho

    # ── Pipe size selection table ─────────────────────────────────────────────
    size_table = _select_pipe(flow_m3s, roughness_m, rho, mu, service, length_m)
    recommended = next((r for r in size_table if r["recommended"]), size_table[0])

    # ── Detailed calc for the recommended (or user-specified) pipe ────────────
    if pipe_dia_mm > 0:
        # User specified a size - find closest nominal
        chosen = min(PIPE_SIZES, key=lambda p: abs(p["nominal"] - pipe_dia_mm))
    else:
        chosen = next(
            (p for p in PIPE_SIZES if p["nominal"] == recommended["nominal_mm"]),
            PIPE_SIZES[4]   # fallback 50mm
        )

    id_m       = chosen["id_mm"] / 1000
    # ★THE ALLOWANCE IS EXTRA EQUIVALENT LENGTH (2026-10-09). The form defines it so ("extra pipe length equivalent to
    # cover all elbows, tees, valves") and the report prints L_eq = L x (1 + allowance/100). It was turned into a K
    # factor of allowance x 10 - no standard behind it - so "20%" added about half again to a 10 m run and about a
    # twentieth to a 100 m one, and the report's "Equivalent Pipe Length" came out at 3 x L. Now the fittings are the
    # stated share of extra length at the same Darcy-Weisbach friction, for every length.
    equiv_m    = length_m * (1 + fittings_pct / 100)
    h_total, _, _, velocity, Re = _pipe_head_loss(
        flow_m3s, id_m, equiv_m, roughness_m, rho, mu, 0.0
    )
    h_f     = h_total * length_m / equiv_m      # the straight run's share
    h_minor = h_total - h_f                     # the fittings' equivalent length

    # Pressure drop in kPa - over the same equivalent length as the head loss, so the two totals agree; the per-metre
    # gradient is the same either way (it was the straight run alone, which left the fittings out of the total).
    eD = roughness_m / id_m
    f  = friction_factor(Re=Re, eD=eD) if Re > 1 else 0
    dp_kpa = f * (equiv_m / id_m) * (rho * velocity ** 2 / 2) / 1000

    # Velocity zone
    targets = VELOCITY_TARGETS.get(service, VELOCITY_TARGETS["General"])
    if velocity < targets["min"]:
        velocity_zone = "Too Slow - risk of sedimentation"
    elif velocity <= targets["max"]:
        velocity_zone = "Acceptable - within design range"
    else:
        velocity_zone = "High - risk of erosion and noise"

    velocity_ok = targets["min"] <= velocity <= targets["max"]

    return {
        # Recommended pipe
        "recommended_nominal_mm":  recommended["nominal_mm"],
        "recommended_id_mm":       recommended["id_mm"],
        "pipe_dia_mm":             chosen["nominal"],
        "pipe_id_mm":              round(chosen["id_mm"], 1),

        # Flow
        "flow_lpm":    round(flow_lpm, 1),
        "flow_m3hr":   round(flow_m3hr, 3),

        # Hydraulics
        "pipe_velocity":       round(velocity, 3),
        "velocity_ok":         velocity_ok,
        "velocity_zone":       velocity_zone,
        "Reynolds_number":     round(Re, 0),
        "friction_factor":     round(f, 5),
        "head_loss_m":         round(h_total, 3),
        "friction_head_m":     round(h_f, 3),
        "minor_losses_m":      round(h_minor, 3),
        "pressure_drop_kpa":   round(dp_kpa, 3),
        "pressure_drop_kpa_per_m": round(dp_kpa / max(equiv_m, 1e-6), 4),

        # Fluid properties
        "fluid_density_kgm3":  round(rho, 2),
        "fluid_viscosity_pas": round(mu, 6),
        "fluid_temp_c":        temp_c,

        # Size selection table (all evaluated sizes)
        "size_table": size_table,

        # Metadata
        "inputs_used": {
            "pipe_material": pipe_mat,
            "service_type":  service,
            "pipe_roughness_mm": roughness_m * 1000,
        },
        "calculation_source": "python/fluids+iapws",
        "standard": "ASHRAE 2021 Ch.22 | PSME Code | PNS ISO 4427",

        # ── Legacy renderer aliases (frontend renderPipeReport) ───────────────
        "flow_lps":            round(flow_m3s * 1000, 2),
        "dia_mm":              recommended["nominal_mm"],
        "velocity":            round(velocity, 3),
        "recommended_dia_mm":  recommended["nominal_mm"],
        "recommended_velocity": round(velocity, 3),
        "recommended":         f"{recommended['nominal_mm']}mm nominal ({recommended['id_mm']}mm ID)",
        "reynolds_number":     round(Re, 0),           # lowercase alias
        "flow_regime":         ("Turbulent" if Re > 4000 else "Laminar" if Re < 2300 else "Transitional"),
        "hf_total":            round(h_total, 3),
        "hf_per_m":            round(h_total / max(equiv_m, 1e-6), 5),
        "press_drop_total":    round(dp_kpa, 3),
        "press_drop_per_m":    round(dp_kpa / max(equiv_m, 1e-6), 4),
        "press_kpa_m":         round(dp_kpa / max(equiv_m, 1e-6), 4),
        "velocity_head":       round(velocity**2 / (2 * 9.81), 4),
        "velocity_min":        targets["min"],
        "velocity_max":        targets["max"],
        "equiv_length":        round(equiv_m, 1),
        "size_comparison":     size_table,   # renderer alias for size_table
    }
