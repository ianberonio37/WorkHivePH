"""
Drainage Pipe Sizing — Plumbing (unifies with Python, was TypeScript-only)
Standards: Philippine Plumbing Code (PPC), UPC Table 7-5,
           Manning's Formula for self-cleansing velocity
Libraries: math

Frontend name: "Drainage Pipe Sizing"
Input schema: fixtures array [{fixture_type, quantity, custom_dfu?}]
              system_type, slope (e.g. "2%"), pipe_material

Improvement over TypeScript:
- Already includes the WC 100mm hard rule fix (from session validation)
- Uses exact same DFU tables and Manning's coefficients as TypeScript
"""

import math

# DFU values per fixture (Philippine Plumbing Code / UPC Table 7-5)
DRAIN_DFU: dict[str, dict] = {
    "Water Closet":               {"dfu": 4, "label": "Water Closet"},
    "Lavatory / Hand Sink":       {"dfu": 1, "label": "Lavatory / Hand Sink"},
    "Bathtub":                    {"dfu": 2, "label": "Bathtub"},
    "Shower":                     {"dfu": 2, "label": "Shower"},
    "Kitchen Sink (residential)": {"dfu": 2, "label": "Kitchen Sink (residential)"},
    "Kitchen Sink (commercial)":  {"dfu": 4, "label": "Kitchen Sink (commercial)"},
    "Urinal (flush valve)":       {"dfu": 4, "label": "Urinal (flush valve)"},
    "Urinal (flush tank)":        {"dfu": 2, "label": "Urinal (flush tank)"},
    "Floor Drain (50mm)":         {"dfu": 2, "label": "Floor Drain (50mm)"},
    "Floor Drain (75mm)":         {"dfu": 3, "label": "Floor Drain (75mm)"},
    "Laundry Tray":               {"dfu": 2, "label": "Laundry Tray"},
    "Washing Machine":            {"dfu": 2, "label": "Washing Machine"},
    "Dishwasher":                 {"dfu": 2, "label": "Dishwasher"},
    "Drinking Fountain":          {"dfu": 1, "label": "Drinking Fountain"},
    "Mop Sink":                   {"dfu": 3, "label": "Mop Sink"},
    "Custom":                     {"dfu": 0, "label": "Custom"},
}

# UPC Table 7-5: horizontal branch capacity by slope (mm → max DFU)
HORIZ_TABLE: dict[str, dict[int, int]] = {
    "1%": {75:21, 100:96,  125:216, 150:384,  200:864,  250:1584, 300:2520},
    "2%": {50:21, 75:42,  100:180, 125:390,  150:700,  200:1600, 250:2900, 300:4600},
    "4%": {40:3,  50:21,  75:42,  100:180,  125:390,  150:700,  200:1600},
}

# UPC Table 7-5: stack capacity (total DFU)
STACK_TABLE: dict[int, int] = {
    50:10, 75:48, 100:240, 125:540, 150:960, 200:2200, 250:3800, 300:6000,
}

# Manning's n per pipe material
MANNING_N: dict[str, float] = {
    "PVC": 0.009, "Cast Iron": 0.012, "Concrete": 0.013, "Clay Tile": 0.013,
}


def calculate(inputs: dict) -> dict:
    fixtures     = inputs.get("fixtures", [])
    system_type  = str(inputs.get("system_type",   "Horizontal Branch"))
    slope_str    = str(inputs.get("slope",         "2%"))
    pipe_mat     = str(inputs.get("pipe_material", "PVC"))
    n            = MANNING_N.get(pipe_mat, 0.009)

    try:
        slope_pct = float(slope_str.replace("%", "")) / 100.0
    except ValueError:
        slope_pct = 0.02

    # Fixture breakdown and DFU sum
    fixture_breakdown: list[dict] = []
    for f in fixtures:
        ft      = str(f.get("fixture_type", "Custom"))
        info    = DRAIN_DFU.get(ft, DRAIN_DFU["Custom"])
        qty     = int(f.get("quantity", 1))
        dfu_ea  = float(f.get("custom_dfu", info["dfu"])) if ft == "Custom" else info["dfu"]
        fixture_breakdown.append({
            "fixture":   info["label"],
            "qty":       qty,
            "dfu_each":  dfu_ea,
            "dfu_total": dfu_ea * qty,
        })

    total_dfu = sum(f["dfu_total"] for f in fixture_breakdown)

    is_stack = system_type == "Drain Stack"
    table_raw = STACK_TABLE if is_stack else HORIZ_TABLE.get(slope_str, HORIZ_TABLE["2%"])
    sorted_sizes = sorted(table_raw.keys())

    # Smallest diameter where capacity >= totalDFU
    recommended = next((d for d in sorted_sizes if table_raw[d] >= total_dfu),
                       sorted_sizes[-1])

    # UPC/PPC hard rule: 75mm horizontal branch cannot serve water closets
    has_wc     = any(str(f.get("fixture_type", "")) == "Water Closet" for f in fixtures)
    wc_override = (not is_stack) and has_wc and recommended < 100
    if wc_override:
        recommended = 100

    # Manning's flow capacity for comparison sizes
    half_full  = not is_stack
    cand_sizes = [d for d in sorted_sizes if d <= max(recommended * 2, 300)]

    comparison: list[dict] = []
    for d_mm in cand_sizes:
        d_m = d_mm / 1000.0
        A   = (math.pi * d_m**2 / 8.0) if half_full else (math.pi * d_m**2 / 4.0)
        R   = d_m / 4.0
        S   = 1.0 if is_stack else slope_pct
        Q   = (1.0 / n) * A * R**(2.0/3.0) * S**0.5
        V   = Q / A if A > 0 else 0.0
        comparison.append({
            "dia_mm":      d_mm,
            "max_dfu":     table_raw.get(d_mm, 0),
            "q_ls":        round(Q * 1000, 2),
            "velocity":    round(V, 2),
            "velocity_ok": V >= 0.6,
            "ok":          table_raw.get(d_mm, 0) >= total_dfu,
            "recommended": d_mm == recommended,
        })

    rec_data     = next((c for c in comparison if c["dia_mm"] == recommended), {})
    slope_mm_m   = round(slope_pct * 1000, 1) if not is_stack else None

    return {
        "total_dfu":          total_dfu,
        "system_type":        system_type,
        "slope_pct":          float(slope_str.replace("%", "")),
        "slope_mm_per_m":     slope_mm_m,
        "recommended_dia_mm": recommended,
        "capacity_q_ls":      rec_data.get("q_ls", 0),
        "design_velocity":    rec_data.get("velocity", 0),
        "velocity_ok":        rec_data.get("velocity", 0) >= 0.6,
        "pipe_material":      pipe_mat,
        "manning_n":          n,
        "wc_override":        wc_override,
        "fixture_breakdown":  fixture_breakdown,
        "size_comparison":    comparison,
    }
