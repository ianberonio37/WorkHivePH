"""
Domestic Water System — Phase 6a
Standards: PSME Code (Philippine Society of Mechanical Engineers),
           ASHRAE 2021 Fundamentals Ch.50, ASPE Data Book Vol.2,
           PNS 65 (Philippine National Standard — water supply),
           NAMPAP (National Authority for Metropolitan Plumbing)
Libraries: math (all formulas closed-form)

Method: Hunter's Curve (fixture unit method) — ASPE / PSME Code
  WSFUs (Water Supply Fixture Units) → Peak probable flow (L/min)
  Booster pump: TDH = static head + friction losses + residual pressure
  Storage tank: daily demand × storage factor (1/3 day for overhead tank)
"""

import math

# ─── PSME / ASPE fixture unit values ─────────────────────────────────────────
# Water Supply Fixture Units (WSFU) per outlet
FIXTURE_UNITS: dict[str, dict] = {
    "Water Closet (flush valve)":   {"wsfu": 10, "private": 6,  "lpm_demand": 8.3},
    "Water Closet (flush tank)":    {"wsfu": 3,  "private": 3,  "lpm_demand": 6.3},
    "Urinal (flush valve)":         {"wsfu": 5,  "private": 5,  "lpm_demand": 8.3},
    "Lavatory (faucet)":            {"wsfu": 2,  "private": 1,  "lpm_demand": 7.6},
    "Bathtub":                      {"wsfu": 4,  "private": 2,  "lpm_demand": 15.1},
    "Shower head":                  {"wsfu": 2,  "private": 2,  "lpm_demand": 9.5},
    "Kitchen sink":                 {"wsfu": 2,  "private": 2,  "lpm_demand": 7.6},
    "Service sink":                 {"wsfu": 3,  "private": 3,  "lpm_demand": 11.4},
    "Dishwasher":                   {"wsfu": 2,  "private": 2,  "lpm_demand": 7.6},
    "Clothes washer":               {"wsfu": 4,  "private": 4,  "lpm_demand": 15.1},
    "Hose bibb":                    {"wsfu": 5,  "private": 5,  "lpm_demand": 15.1},
    "Drinking fountain":            {"wsfu": 1,  "private": 1,  "lpm_demand": 3.8},
    "Floor drain (with trap)":      {"wsfu": 0,  "private": 0,  "lpm_demand": 0},
}

# ─── Hunter's Curve — WSFU → peak flow (L/min) ────────────────────────────────
# ASPE Data Book Vol.2 Table 1-4 (public system)
# Approximated by piecewise power curve
HUNTER_CURVE: list[dict] = [
    {"wsfu_max":   1,  "a": 0.30,  "b": 0.83},
    {"wsfu_max":   9,  "a": 0.80,  "b": 0.72},
    {"wsfu_max":  50,  "a": 1.10,  "b": 0.69},
    {"wsfu_max": 200,  "a": 1.80,  "b": 0.62},
    {"wsfu_max": 999,  "a": 2.50,  "b": 0.57},
]

def _hunter_flow(wsfu: float) -> float:
    """Peak probable flow (L/min) from total WSFU using Hunter's Curve."""
    if wsfu <= 0:
        return 0.0
    for seg in HUNTER_CURVE:
        if wsfu <= seg["wsfu_max"]:
            return seg["a"] * (wsfu ** seg["b"]) * 10   # scale to L/min
    last = HUNTER_CURVE[-1]
    return last["a"] * (wsfu ** last["b"]) * 10

# ─── Pipe roughness — Hazen-Williams C factors ────────────────────────────────
HW_C: dict[str, float] = {
    "uPVC":             150,
    "CPVC":             150,
    "Copper":           135,
    "GI (Galvanized)":  120,
    "PPR":              150,
    "Stainless Steel":  140,
}

# ─── Standard pipe IDs (mm) for water supply ─────────────────────────────────
PIPE_SIZES: list[dict] = [
    {"nominal_mm":  15, "id_mm": 15.8},
    {"nominal_mm":  20, "id_mm": 20.9},
    {"nominal_mm":  25, "id_mm": 26.6},
    {"nominal_mm":  32, "id_mm": 35.1},
    {"nominal_mm":  40, "id_mm": 40.9},
    {"nominal_mm":  50, "id_mm": 52.5},
    {"nominal_mm":  65, "id_mm": 62.7},
    {"nominal_mm":  80, "id_mm": 77.9},
    {"nominal_mm": 100, "id_mm": 102.3},
    {"nominal_mm": 125, "id_mm": 128.2},
    {"nominal_mm": 150, "id_mm": 154.1},
]

# ─── PSME velocity limits for domestic water (m/s) ────────────────────────────
VELOCITY_LIMITS = {"min": 0.6, "max": 3.0, "ideal": 1.5}

# ─── Per-capita daily demand (L/person/day) — PSME Code ──────────────────────
DAILY_DEMAND: dict[str, float] = {
    "Residential":    200,
    "Office":         50,
    "Hotel":          350,
    "Hospital":       500,
    "Restaurant":     70,    # per meal
    "School":         50,
    "Mall / Retail":  30,
    "Industrial":     80,
}

# ─── Storage factor (fraction of daily demand) — PSME Code ───────────────────
# Overhead gravity tank: store 1/3 day (8 hrs)
# Underground cistern: store 1 full day
STORAGE_FACTOR = {"overhead": 1/3, "cistern": 1.0}

# Standard pump kW sizes
PUMP_KW_SIZES = [0.37, 0.55, 0.75, 1.1, 1.5, 2.2, 3.0, 4.0, 5.5, 7.5,
                 11, 15, 18.5, 22, 30, 37, 45, 55, 75]


def _hw_dp(Q_lpm: float, C: float, d_mm: float, L_m: float) -> float:
    """Hazen-Williams friction loss (bar)."""
    if Q_lpm <= 0 or d_mm <= 0:
        return 0.0
    return (6.05e5 * Q_lpm ** 1.85) / (C ** 1.85 * d_mm ** 4.87) * L_m


def _select_pipe(Q_lpm: float, C: float, L_m: float) -> dict:
    """Select smallest pipe within velocity limits."""
    for ps in PIPE_SIZES:
        id_m = ps["id_mm"] / 1000
        A    = math.pi * (id_m / 2) ** 2
        v    = (Q_lpm / 60000) / A
        if VELOCITY_LIMITS["min"] <= v <= VELOCITY_LIMITS["max"]:
            dp = _hw_dp(Q_lpm, C, ps["id_mm"], L_m)
            return {"nominal_mm": ps["nominal_mm"], "id_mm": ps["id_mm"],
                    "velocity_ms": round(v, 2), "dp_bar": round(dp, 4)}
    ps = PIPE_SIZES[-1]
    id_m = ps["id_mm"] / 1000
    A    = math.pi * (id_m / 2) ** 2
    v    = (Q_lpm / 60000) / A
    dp   = _hw_dp(Q_lpm, C, ps["id_mm"], L_m)
    return {"nominal_mm": ps["nominal_mm"], "id_mm": ps["id_mm"],
            "velocity_ms": round(v, 2), "dp_bar": round(dp, 4)}


def calculate(inputs: dict) -> dict:
    """Main entry point — compatible with TypeScript calcDomesticWater() keys."""
    # ── Building parameters ───────────────────────────────────────────────────
    occupancy_type   = str  (inputs.get("occupancy_type",    "Office"))
    num_persons      = float(inputs.get("num_persons",        50))
    building_floors  = int  (inputs.get("building_floors",    5))
    floor_height_m   = float(inputs.get("floor_height_m",     3.5))
    pipe_material    = str  (inputs.get("pipe_material",      "uPVC"))
    supply_pressure_bar = float(inputs.get("supply_pressure_bar", 1.0))
    residual_pressure_bar = float(inputs.get("residual_pressure_bar", 1.0))
    riser_length_m   = float(inputs.get("riser_length_m",    building_floors * floor_height_m))
    branch_length_m  = float(inputs.get("branch_length_m",   20))
    storage_type     = str  (inputs.get("storage_type",      "overhead"))

    # ── Fixture unit calculation ──────────────────────────────────────────────
    fixtures = inputs.get("fixtures", [])
    total_wsfu = 0.0
    fixture_rows = []

    if fixtures:
        for f in fixtures:
            name   = str  (f.get("fixture_type",  "Lavatory (faucet)"))
            qty    = float(f.get("quantity",        1))
            f_data = FIXTURE_UNITS.get(name, {"wsfu": 2, "lpm_demand": 7.6})
            wsfu   = f_data["wsfu"] * qty
            total_wsfu += wsfu
            fixture_rows.append({
                "fixture_type": name, "quantity": qty,
                "wsfu_each": f_data["wsfu"], "wsfu_total": wsfu,
            })
    else:
        # Estimate from occupancy and persons
        # Rule of thumb: 1 WC+lav per 10 persons (office)
        wc_qty  = math.ceil(num_persons / 10)
        lav_qty = wc_qty
        for name, qty in [("Water Closet (flush valve)", wc_qty),
                           ("Lavatory (faucet)", lav_qty),
                           ("Service sink", 1)]:
            f_data = FIXTURE_UNITS[name]
            wsfu   = f_data["wsfu"] * qty
            total_wsfu += wsfu
            fixture_rows.append({
                "fixture_type": name, "quantity": qty,
                "wsfu_each": f_data["wsfu"], "wsfu_total": wsfu,
            })

    # ── Peak probable flow (Hunter's Curve) ──────────────────────────────────
    peak_flow_lpm  = _hunter_flow(total_wsfu)
    peak_flow_lps  = peak_flow_lpm / 60
    peak_flow_m3hr = peak_flow_lpm * 60 / 1000

    # ── Daily demand ──────────────────────────────────────────────────────────
    lppd = DAILY_DEMAND.get(occupancy_type, 50)
    daily_demand_m3 = num_persons * lppd / 1000

    # ── Storage tank capacity ─────────────────────────────────────────────────
    sf = STORAGE_FACTOR.get(storage_type, 1/3)
    tank_m3 = daily_demand_m3 * sf
    # Standard tank sizes (m³)
    std_tanks_m3 = [0.5, 1, 1.5, 2, 3, 4, 5, 7.5, 10, 15, 20, 25, 30,
                    40, 50, 75, 100]
    rec_tank_m3 = next((t for t in std_tanks_m3 if t >= tank_m3), std_tanks_m3[-1])

    # ── Pipe sizing ───────────────────────────────────────────────────────────
    C = HW_C.get(pipe_material, 150)
    riser_pipe  = _select_pipe(peak_flow_lpm, C, riser_length_m)
    branch_pipe = _select_pipe(peak_flow_lpm / 4, C, branch_length_m)   # 1/4 flow at branch

    # ── Booster pump TDH ─────────────────────────────────────────────────────
    static_head_bar = building_floors * floor_height_m * 0.0981  # elevation
    dp_riser_bar    = riser_pipe["dp_bar"]
    dp_branch_bar   = branch_pipe["dp_bar"]
    fittings_bar    = (dp_riser_bar + dp_branch_bar) * 0.30   # 30% fittings
    tdh_bar         = (static_head_bar + dp_riser_bar + dp_branch_bar +
                       fittings_bar + residual_pressure_bar - supply_pressure_bar)
    tdh_m           = tdh_bar / 0.0981
    tdh_bar         = max(tdh_bar, 0.5)   # minimum reasonable TDH

    # Pump power
    rho = 1000  # kg/m³
    g   = 9.81
    Q_m3s = peak_flow_lps / 1000 * peak_flow_lpm / peak_flow_lpm   # = lps/1000
    Q_m3s = peak_flow_lps / 1000
    pump_eta = 0.65
    motor_eta = 0.92
    pump_kw = (rho * g * Q_m3s * tdh_m) / (pump_eta * motor_eta * 1000)
    rec_pump_kw = next((s for s in PUMP_KW_SIZES if s >= pump_kw), PUMP_KW_SIZES[-1])

    # Booster needed?
    booster_needed = supply_pressure_bar < (static_head_bar + residual_pressure_bar)

    return {
        # Fixture units
        "total_wsfu":           round(total_wsfu, 1),
        "fixture_schedule":     fixture_rows,

        # Flow
        "peak_flow_lpm":        round(peak_flow_lpm, 1),
        "peak_flow_lps":        round(peak_flow_lps, 2),
        "peak_flow_m3hr":       round(peak_flow_m3hr, 2),

        # Daily demand
        "daily_demand_m3":      round(daily_demand_m3, 2),
        "lppd":                 lppd,
        "storage_factor":       sf,
        "tank_required_m3":     round(tank_m3, 2),
        "recommended_tank_m3":  rec_tank_m3,
        "storage_type":         storage_type,

        # Pipe
        "riser_pipe":           riser_pipe,
        "branch_pipe":          branch_pipe,
        "pipe_material":        pipe_material,
        "hw_c_factor":          C,

        # Booster pump
        "booster_needed":       booster_needed,
        "static_head_bar":      round(static_head_bar, 3),
        "tdh_bar":              round(tdh_bar, 3),
        "tdh_m":                round(tdh_m, 1),
        "pump_kw_calculated":   round(pump_kw, 3),
        "recommended_pump_kW":  rec_pump_kw,

        # Metadata
        "inputs_used": {
            "occupancy_type":      occupancy_type,
            "num_persons":         num_persons,
            "building_floors":     building_floors,
            "pipe_material":       pipe_material,
            "storage_type":        storage_type,
        },
        "calculation_source": "python/math",
        "standard": "PSME Code | ASPE Vol.2 | PNS 65 | ASHRAE 2021 Ch.50",
    }
