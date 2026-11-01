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

# ★THE TABLES WERE IPC, SPLICED, AND CALLED UPC (2026-11-02, ED-G1 Drainage, read against the guide). The stack table was
# IPC Table 710.1(2) (stacks of <= 3 branch intervals: 48/240/540/960/2200); the "2%" horizontal row took IPC's 1/4-in
# building-drain column up to 75 mm (21, 42) and its 1/8-in column above (180, 390, 700, 1600); the "1%" row matched no
# column at all; and a horizontal fixture BRANCH was rated like a building drain (75 mm: 42 DFU - a fixture branch carries
# 20 under IPC, 35 under UPC). The guide and the Philippine plumbing code are UPC, so the capacities are UPC Table 703.2
# (King County / CPC 2022 reproductions): horizontal at 1/4 in per ft, x 0.8 at 1/8 in (note 5); vertical for stacks.
# A pipe of 100 mm carries 216 horizontal (was 180) and 256 vertical (was 240); 75 mm carries 35 horizontal (was 42).
UPC_HORIZONTAL: dict[int, int] = {40: 1, 50: 8, 65: 14, 75: 35, 100: 216, 125: 428, 150: 720, 200: 2640, 250: 4680, 300: 8200}
UPC_VERTICAL:   dict[int, int] = {40: 2, 50: 16, 65: 32, 75: 48, 100: 256, 125: 600, 150: 1380, 200: 3600, 250: 5600, 300: 8400}
HORIZ_TABLE: dict[str, dict[int, int]] = {
    "1%": {d: int(u * 0.8) for d, u in UPC_HORIZONTAL.items()},   # 1/8 in per ft: note 5, x 0.8
    "2%": dict(UPC_HORIZONTAL),                                    # 1/4 in per ft - the table's own basis
    "4%": dict(UPC_HORIZONTAL),                                    # steeper earns no credit in the table
}
STACK_TABLE: dict[int, int] = dict(UPC_VERTICAL)
# Water closets (Table 703.2 notes c, d): none on 50 / 65 mm; a 75 mm pipe takes at most 3 on a horizontal branch or
# drain and 4 on a vertical stack; more needs 100 mm.
WC_LIMIT_75MM = {"horizontal": 3, "vertical": 4}

# Manning's n per pipe material
MANNING_N: dict[str, float] = {
    "PVC": 0.009, "Cast Iron": 0.012, "Concrete": 0.013, "Clay Tile": 0.013,
}


# formula: drainage_pipe_sizing
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

    # UPC Table 703.2 notes c, d: water closets need 75 mm at least, and 75 mm takes no more than 3 on a horizontal
    # branch or drain (4 on a stack) - the old rule here forced 100 mm for a single water closet and called it a UPC rule
    n_wc = sum(int(float(f.get("quantity", 1) or 0)) for f in fixtures if str(f.get("fixture_type", "")) == "Water Closet")
    has_wc = n_wc > 0
    wc_cap = WC_LIMIT_75MM["vertical" if is_stack else "horizontal"]
    wc_min = 0 if not has_wc else (75 if n_wc <= wc_cap else 100)
    wc_override = has_wc and recommended < wc_min
    dfu_selected = recommended
    if wc_override:
        recommended = next(d for d in sorted_sizes if d >= wc_min)

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
        "wc_count":           n_wc,
        "wc_min_dia_mm":      wc_min,
        "dfu_selected_dia_mm": dfu_selected,
        "table_basis":        "UPC Table 703.2 " + ("vertical" if is_stack else "horizontal" + (" x 0.8 (1/8 in per ft)" if slope_str == "1%" else " (1/4 in per ft)")),
        "fixture_breakdown":  fixture_breakdown,
        "size_comparison":    comparison,
    }
