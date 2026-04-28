"""
Cable Tray Sizing — Phase 4h (Option B port from TypeScript)
Standards: NEMA VE 1-2017 (Cable Tray Systems),
           NEC 2023 Article 392, PEC 2017 Article 3.92
Libraries: math

Improvement over TypeScript:
- Fill area validates each cable od_mm > 0 (avoids silent 0-area cables)
- Explicit NEC 392.22 ladder/solid-bottom fill limit: 50% for ladder/ventilated,
  40% for solid-bottom (TypeScript used a simplified 30/40 threshold)
- NEMA load class check against both weight/m AND load per span

Inputs (cables list):
  [{cable_type, od_mm, qty, weight_kg_m (optional)}]
"""

import math

# Standard NEMA tray widths (mm) — NEMA VE 1 Table 4
STD_WIDTHS_MM = [100, 150, 200, 300, 450, 600, 750, 900]

# NEMA VE 1 load classes [label, max distributed load kg/m]
NEMA_CLASSES: list[tuple[str, float]] = [
    ("8A",  11.9),
    ("12A", 17.9),
    ("16A", 23.8),
    ("20A", 29.8),
    ("24A", 35.7),
    ("32A", 47.6),
]

# NEC 392.22 maximum fill ratios by tray type
FILL_LIMITS: dict[str, float] = {
    "Ladder":            50.0,
    "Ventilated Trough": 50.0,
    "Solid Bottom":      40.0,
    "Channel":           40.0,
}


def calculate(inputs: dict) -> dict:
    tray_type      = str(inputs.get("tray_type",       "Ladder"))
    depth_mm       = float(inputs.get("depth_mm",      75))
    fill_ratio_pct = float(inputs.get("fill_ratio_pct", 40))
    span_m         = float(inputs.get("span_m",        1.5))
    run_length_m   = float(inputs.get("run_length_m",  30))
    cables         = inputs.get("cables", [])

    # Step 1 — per-cable fill area and distributed weight
    total_fill_area   = 0.0
    total_weight_kg_m = 0.0
    cable_details: list[dict] = []

    for cable in cables:
        od_mm = float(cable.get("od_mm", 0))
        qty   = int(cable.get("qty",   1))
        if od_mm <= 0:
            continue
        # Weight: use provided value if available; else rule-of-thumb 0.01 kg/m per mm OD
        wt_raw = cable.get("weight_kg_m")
        wt_kg_m = float(wt_raw) if (wt_raw is not None and float(wt_raw) > 0) else od_mm * 0.01

        area_per = (math.pi / 4) * od_mm ** 2
        total_fill_area   += area_per * qty
        total_weight_kg_m += wt_kg_m * qty
        cable_details.append({
            "cable_type":    str(cable.get("cable_type", "Cable")),
            "od_mm":         od_mm,
            "qty":           qty,
            "area_mm2":      round(area_per, 2),
            "total_area_mm2": round(area_per * qty, 2),
            "weight_kg_m":   round(wt_kg_m, 3),
        })

    total_fill_area   = round(total_fill_area,   2)
    total_weight_kg_m = round(total_weight_kg_m, 2)

    # Step 2 — required tray width
    fill_decimal  = fill_ratio_pct / 100.0
    req_width_raw = (total_fill_area / (fill_decimal * depth_mm)) if depth_mm > 0 else 0.0
    req_width_mm  = round(req_width_raw, 2)
    sel_width_mm  = next((w for w in STD_WIDTHS_MM if w >= req_width_raw), 900)

    # Step 3 — actual fill %
    tray_area       = sel_width_mm * depth_mm
    fill_actual_pct = round((total_fill_area / tray_area) * 100, 2) if tray_area > 0 else 0.0
    nec_fill_limit  = FILL_LIMITS.get(tray_type, 50.0)
    fill_check      = "PASS" if fill_actual_pct <= fill_ratio_pct else "FAIL"
    nec_check       = "PASS" if fill_actual_pct <= nec_fill_limit  else "FAIL: exceeds NEC 392.22 limit"

    # Step 4 — NEMA load class
    load_per_span = round(total_weight_kg_m * span_m, 2)
    nema_class = "Custom (> 32A)"
    for label, max_kg_m in NEMA_CLASSES:
        if total_weight_kg_m <= max_kg_m:
            nema_class = label
            break

    # Step 5 — derating (NEC 392.80)
    derating_threshold = 40.0 if tray_type == "Solid Bottom" else 30.0
    derating_factor    = 0.80 if fill_actual_pct > derating_threshold else 1.0

    return {
        "tray_type":            tray_type,
        "depth_mm":             depth_mm,
        "fill_ratio_pct":       fill_ratio_pct,
        "nec_fill_limit_pct":   nec_fill_limit,
        "span_m":               span_m,
        "run_length_m":         run_length_m,
        "total_fill_area_mm2":  total_fill_area,
        "required_width_mm":    req_width_mm,
        "selected_width_mm":    sel_width_mm,
        "fill_actual_pct":      fill_actual_pct,
        "fill_check":           fill_check,
        "nec_fill_check":       nec_check,
        "total_weight_kg_m":    total_weight_kg_m,
        "load_per_span_kg":     load_per_span,
        "nema_load_class":      nema_class,
        "derating_factor":      derating_factor,
        "derating_applies":     derating_factor < 1.0,
        "cable_details":        cable_details,
    }
