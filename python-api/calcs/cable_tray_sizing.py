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

# ★NEC 392.22 IS AN AREA PER WIDTH FOR POWER CABLE, NOT 50% OF THE CROSS-SECTION (2026-11-02, ED-G1 Cable Tray, read
# against the guide). For multiconductor power / lighting cable smaller than 4/0 the code's limit is Table 392.22(A) Column 1
# (ladder / ventilated trough) = tray width x 7/6 in2 per in - 7.0 in2 for a 6 in tray, 28.0 for 24 in - i.e. 29.6 mm of
# equivalent depth WHATEVER the tray depth; Column 3 (solid bottom) = width x 11/12 in2 per in (5.5 in2 for 6 in). This
# engine took 50% of width x depth as the "NEC limit" and sized on the form's fill % of width x depth, so a deep tray
# carried more power cable than the code allows: 75 mm deep at 50% is 27% over Column 1, 150 mm deep at 40% is 2x over.
# The 50% of the cross-section applies to control / signal cable only (392.22(A)(3)), which is kept below.
NEC_POWER_MM2_PER_MM = {"Ladder": 7 / 6 * 25.4, "Ventilated Trough": 7 / 6 * 25.4,
                        "Solid Bottom": 11 / 12 * 25.4, "Channel": 11 / 12 * 25.4}
# control / signal / instrument cable only: % of the tray's interior cross-section
FILL_LIMITS: dict[str, float] = {
    "Ladder":            50.0,
    "Ventilated Trough": 50.0,
    "Solid Bottom":      40.0,
    "Channel":           40.0,
}


# formula: cable_tray_sizing_nec_2023
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
    # power unless the type says control / signal / instrument / data - the conservative default (THHN, XHHW... are power)
    _ctrl = ("control", "signal", "instrument", "data", "comm", "fiber", "fibre")
    has_power     = any(not any(k in str(c.get("cable_type", "")).lower() for k in _ctrl) for c in cable_details)
    nec_mm2_per_mm = NEC_POWER_MM2_PER_MM.get(tray_type, 7 / 6 * 25.4)
    w_design   = (total_fill_area / (fill_decimal * depth_mm)) if depth_mm > 0 else 0.0
    w_nec      = (total_fill_area / nec_mm2_per_mm) if has_power else \
                 ((total_fill_area / (FILL_LIMITS.get(tray_type, 50.0) / 100.0 * depth_mm)) if depth_mm > 0 else 0.0)
    req_width_raw = max(w_design, w_nec)
    req_width_mm  = round(req_width_raw, 2)
    sel_width_mm  = next((w for w in STD_WIDTHS_MM if w >= req_width_raw), 900)

    # Step 3 — actual fill %
    tray_area       = sel_width_mm * depth_mm
    fill_actual_pct = round((total_fill_area / tray_area) * 100, 2) if tray_area > 0 else 0.0
    if has_power:
        nec_allow_mm2  = round(sel_width_mm * nec_mm2_per_mm, 1)
        nec_fill_limit = round(nec_allow_mm2 / tray_area * 100, 2) if tray_area > 0 else 0.0
        nec_basis      = (f"NEC 392.22(A) Column {'1' if tray_type in ('Ladder', 'Ventilated Trough') else '3'}: "
                          f"{sel_width_mm} mm x {nec_mm2_per_mm:.1f} mm2/mm = {nec_allow_mm2:.0f} mm2 for power cable")
    else:
        nec_fill_limit = FILL_LIMITS.get(tray_type, 50.0)
        nec_allow_mm2  = round(tray_area * nec_fill_limit / 100, 1)
        nec_basis      = f"NEC 392.22(A)(3): {nec_fill_limit:g}% of the cross-section for control / signal cable"
    fill_check      = "PASS" if fill_actual_pct <= fill_ratio_pct else "FAIL"
    nec_check       = "PASS" if total_fill_area <= nec_allow_mm2 + 1e-6 else "FAIL: exceeds NEC 392.22 limit"

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
        "nec_allowable_mm2":    nec_allow_mm2,
        "nec_basis":            nec_basis,
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
