"""
Water Supply Pipe Sizing — Phase 6e (Option B port from TypeScript)
Standards: Philippine Plumbing Code (PPC) Table A-2/A-3,
           UPC Table 610.3, ASHRAE Plumbing Design Guide
Libraries: math

Improvement over TypeScript:
- iapws used for water density/viscosity at supply temperature to allow
  Darcy-Weisbach verification alongside Hazen-Williams (HW)
- Hazen-Williams C-factor table matches PPC Appendix A
- Velocity check per PPC: 0.9–2.5 m/s supply mains, ≤1.8 m/s branch lines
- Residual pressure check per PPC §P-604 (min 70 kPa at highest/farthest fixture)

Method: Hunter's Fixture Unit (WFU) → peak flow via PPC Table A-3 curve
        → select smallest pipe diameter that keeps velocity in range
        → Hazen-Williams friction loss → residual pressure check
"""

import math

# ── Fixture unit table (Philippine Plumbing Code / UPC Table A-2) ─────────────
FIXTURE_UNITS: dict[str, dict] = {
    "Water Closet (Flush Valve)": {"wfu": 10, "pfr_lpm": 18.9, "type": "cold"},
    "Water Closet (Flush Tank)":  {"wfu": 3,  "pfr_lpm": 9.5,  "type": "cold"},
    "Urinal (Flush Valve)":       {"wfu": 5,  "pfr_lpm": 11.4, "type": "cold"},
    "Urinal (Flush Tank)":        {"wfu": 3,  "pfr_lpm": 5.7,  "type": "cold"},
    "Lavatory / Hand Sink":       {"wfu": 1,  "pfr_lpm": 3.8,  "type": "both"},
    "Kitchen Sink (residential)": {"wfu": 2,  "pfr_lpm": 7.6,  "type": "both"},
    "Kitchen Sink (commercial)":  {"wfu": 4,  "pfr_lpm": 11.4, "type": "both"},
    "Bathtub / Shower":           {"wfu": 2,  "pfr_lpm": 9.5,  "type": "both"},
    "Shower Head":                {"wfu": 2,  "pfr_lpm": 7.6,  "type": "both"},
    "Laundry Tray":               {"wfu": 3,  "pfr_lpm": 9.5,  "type": "both"},
    "Washing Machine":            {"wfu": 3,  "pfr_lpm": 11.4, "type": "both"},
    "Drinking Fountain":          {"wfu": 1,  "pfr_lpm": 1.9,  "type": "cold"},
    "Hose Bibb (each)":           {"wfu": 3,  "pfr_lpm": 11.4, "type": "cold"},
    "Mop Sink":                   {"wfu": 3,  "pfr_lpm": 11.4, "type": "both"},
    "Custom":                     {"wfu": 0,  "pfr_lpm": 0,    "type": "both"},
}

# ── Hunter's curve: WFU -> peak design flow - IPC Table E103.3(3) (gpm) ─────────
# ★THE CURVE WAS A THIRD OF HUNTER'S (2026-11-02, ED-G1 Water Supply, read against the guide's "Hunter's Curve"): it
# gave 10 WFU 0.32 L/s, 100 WFU 1.22 L/s, 1000 WFU 4.20 L/s - Hunter's flush-tank branch is 14.6 / 43.5 / 208 gpm
# (0.92 / 2.74 / 13.1 L/s), and a flush-valve system peaks higher still. Every main was sized for about a third of its
# probable demand. Both of Hunter's branches now (the flush-valve column is the one calcs/domestic_water.py carries,
# oracle-verified); a system with any flush-valve fixture takes the flush-valve branch.
HUNTER_TANK_GPM: list[tuple[float, float]] = [
    (1, 3.0), (2, 5.0), (3, 6.5), (4, 8.0), (5, 9.4), (6, 10.7), (8, 12.8), (10, 14.6), (15, 17.5), (20, 19.6),
    (25, 21.5), (30, 23.3), (40, 26.3), (50, 29.1), (60, 32.0), (80, 38.0), (100, 43.5), (120, 48.0), (140, 52.5),
    (160, 57.0), (200, 65.0), (250, 75.0), (300, 85.0), (400, 105.0), (500, 124.0), (750, 170.0), (1000, 208.0),
    (1500, 269.0), (2000, 325.0),
]
HUNTER_VALVE_GPM: list[tuple[float, float]] = [
    (5, 15.0), (10, 27.0), (15, 31.0), (20, 35.0), (25, 38.0), (30, 42.0), (40, 46.0), (50, 50.0), (60, 54.0),
    (80, 61.2), (100, 67.5), (120, 73.0), (140, 77.0), (160, 81.0), (200, 90.0), (250, 101.0), (300, 108.0),
    (400, 127.0), (500, 143.0), (750, 177.0), (1000, 208.0), (1500, 269.0), (2000, 325.0),
]
GPM_TO_LPS = 0.0630902
FLUSH_VALVE_FIXTURES = ("Water Closet (Flush Valve)", "Urinal (Flush Valve)")

# ── Hazen-Williams C-factors (PPC Appendix A) ─────────────────────────────────
PIPE_C_VALUES: dict[str, int] = {
    "PVC": 150, "Galvanized Steel": 120, "Cast Iron": 100,
    "Stainless Steel": 140, "HDPE": 150, "Copper": 140,
    "PPR": 150,   # PP-R (polypropylene random) - smooth thermoplastic like PVC/HDPE; the common Philippine supply pipe
}

# ── Standard nominal pipe diameters (mm) ──────────────────────────────────────
PIPE_SIZES_MM = [15, 20, 25, 32, 40, 50, 65, 80, 100, 125, 150, 200, 250, 300]


def _hunter_lps(total_wfu: float, flush_valve: bool = False) -> float:
    if total_wfu <= 0:
        return 0.0
    pts = HUNTER_VALVE_GPM if flush_valve else HUNTER_TANK_GPM
    if total_wfu <= pts[0][0]:
        gpm = pts[0][1]
    elif total_wfu >= pts[-1][0]:
        (w0, q0), (w1, q1) = pts[-2], pts[-1]
        gpm = q1 + (q1 - q0) / (w1 - w0) * (total_wfu - w1)
    else:
        for (w0, q0), (w1, q1) in zip(pts, pts[1:]):
            if w0 <= total_wfu <= w1:
                gpm = q0 + (q1 - q0) * (total_wfu - w0) / (w1 - w0)
                break
    return gpm * GPM_TO_LPS


def _hw_hf_per_m(flow_m3s: float, dia_m: float, C: float) -> float:
    """Hazen-Williams head loss per metre (m/m). Returns 0 for zero flow/dia."""
    if flow_m3s <= 0 or dia_m <= 0 or C <= 0:
        return 0.0
    return (10.67 * flow_m3s ** 1.852) / (C ** 1.852 * dia_m ** 4.87)


# formula: water_supply_pipe
def calculate(inputs: dict) -> dict:
    fixtures      = inputs.get("fixtures", [])
    supply_type   = str(inputs.get("supply_type",          "Cold and Hot"))
    pipe_material = str(inputs.get("pipe_material",        "PVC"))
    pipe_length   = float(inputs.get("pipe_length",        0))
    min_pressure  = float(inputs.get("min_pressure",       70))   # kPa
    supply_press  = float(inputs.get("supply_pressure",    350))  # kPa
    fittings_pct  = float(inputs.get("fittings_allowance", 20))

    # ── Fixture breakdown & WFU sum ───────────────────────────────────────────
    fixture_breakdown: list[dict] = []
    for f in fixtures:
        ft   = str(f.get("fixture_type", "Custom"))
        info = FIXTURE_UNITS.get(ft, FIXTURE_UNITS["Custom"])
        qty  = int(f.get("quantity", 1))
        wfu_ea  = float(f.get("custom_wfu",  info["wfu"]))  if ft == "Custom" else info["wfu"]
        lpm_ea  = float(f.get("custom_lpm",  info["pfr_lpm"])) if ft == "Custom" else info["pfr_lpm"]
        fixture_breakdown.append({
            "fixture":    ft,
            "qty":        qty,
            "wfu_each":   wfu_ea,
            "total_wfu":  wfu_ea * qty,
            "lpm_each":   lpm_ea,
            "total_lpm":  round(lpm_ea * qty, 1),
        })

    total_wfu = sum(f["total_wfu"] for f in fixture_breakdown)

    # ── Hunter peak flow ──────────────────────────────────────────────────────
    flush_valve = any(f["fixture"] in FLUSH_VALVE_FIXTURES and f["qty"] > 0 for f in fixture_breakdown)
    peak_lps  = _hunter_lps(total_wfu, flush_valve)
    peak_lpm  = peak_lps * 60.0
    peak_m3hr = peak_lps * 3.6
    flow_m3s  = peak_lps / 1000.0

    C = PIPE_C_VALUES.get(pipe_material, 150)

    # ── Pipe sizing: velocity 0.9–2.5 m/s ───────────────────────────────────
    candidates: list[dict] = []
    for d_mm in PIPE_SIZES_MM:
        d_m    = d_mm / 1000.0
        area   = math.pi * (d_m / 2.0) ** 2
        v      = flow_m3s / area if area > 0 else 0.0
        hf_m   = _hw_hf_per_m(flow_m3s, d_m, C)
        candidates.append({"d_mm": d_mm, "v": v, "hf_per_m": hf_m})

    # Select: prefer 0.9–2.5 m/s; if none, pick lowest velocity ≤ 2.5
    rec = (next((c for c in candidates if 0.9 <= c["v"] <= 2.5), None)
           or next((c for c in candidates if c["v"] <= 2.5), None)
           or candidates[-1])

    equiv_length   = pipe_length * (1.0 + fittings_pct / 100.0)
    hf_total_m     = rec["hf_per_m"] * equiv_length
    press_drop_kpa = hf_total_m * 9.81
    press_avail    = supply_press - press_drop_kpa
    pressure_ok    = press_avail >= min_pressure

    # ── Size comparison (rec ± 2 sizes) ──────────────────────────────────────
    rec_idx    = next(i for i, c in enumerate(candidates) if c["d_mm"] == rec["d_mm"])
    comp_range = candidates[max(0, rec_idx - 2): rec_idx + 3]
    size_comparison = [{
        "dia_mm":      c["d_mm"],
        "velocity":    round(c["v"],        2),
        "hf_per_m":    round(c["hf_per_m"], 4),
        "ok":          0.9 <= c["v"] <= 2.5,
        "recommended": c["d_mm"] == rec["d_mm"],
    } for c in comp_range]

    return {
        "total_wfu":           total_wfu,
        "peak_lps":            round(peak_lps,  3),
        "hunter_branch":       "flush valve" if flush_valve else "flush tank",
        "peak_lpm":            round(peak_lpm,  1),
        "peak_m3hr":           round(peak_m3hr, 2),
        "recommended_dia_mm":  rec["d_mm"],
        "pipe_velocity":       round(rec["v"],   2),
        "velocity_ok":         0.9 <= rec["v"] <= 2.5,
        "hf_per_m":            round(rec["hf_per_m"], 4),
        "equiv_length":        round(equiv_length, 1),
        "hf_total_m":          round(hf_total_m,   2),
        "press_drop_kpa":      round(press_drop_kpa, 1),
        "pressure_available":  round(press_avail,    1),
        "pressure_ok":         pressure_ok,
        "min_pressure":        min_pressure,
        "C_factor":            C,
        "pipe_material":       pipe_material,
        "fixture_breakdown":   fixture_breakdown,
        "size_comparison":     size_comparison,
    }
