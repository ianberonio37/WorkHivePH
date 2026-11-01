"""
Roof Drain Sizing — Phase 6l (Option B port from TypeScript)
Standards: IPC 2021 §1106, Philippine Plumbing Code §P-915 to §P-918,
           ASPE Design Handbook Vol. 2, SMACNA Architectural Sheet Metal
Libraries: math

Method: Rational Method for impervious roof (C=1.0)
        Q = I × A / 3600 → select drain body → leader size at design slope

Improvement over TypeScript:
- PAGASA regional intensity input supported (NCR 100mm/hr default)
- Sump overflow check: overflow drain invert at +50mm per IPC §1101.7
"""

import math

# ★THE CAPACITIES WERE 2-8x BELOW THE CODE THEY CITED (2026-11-02, ED-G1 Roof Drain, read against the guide). "IPC 2018
# Table 1106.2" here was 0.76 / 1.51 / 2.65 / 4.16 / 8.83 L/s for 75-200 mm; the table gives 92 / 192 / 360 / 563 / 1208 gpm
# (5.80 / 12.11 / 22.71 / 35.52 / 76.21 L/s) - every drain and leader was oversized several times. The horizontal row
# (0.95 L/s at 75 mm, "Manning half-full") matched neither IPC Table 1106.3 nor Manning (100 mm half-full at 1%, n 0.011,
# is 3.05 L/s). Now the IPC tables (cross-checked against the Engineering Toolbox reproduction and a 4-in = 18,400 ft2 at
# 1 in/h worked example), gpm x 0.06309.
# Vertical conductor / drain outlet capacity (L/s) - IPC Table 1106.2
RD_DRAIN_MM  = [75,   100,   125,   150,   200]
RD_DRAIN_LS  = [5.80, 12.11, 22.71, 35.52, 76.21]

# Horizontal storm drain capacity at 1/8 in per ft (1.0417 %) (L/s) - IPC Table 1106.3; the 1/4 and 1/2 in columns are
# this times sqrt(2) and 2 (Manning), so other slopes scale by sqrt(S / 1.0417)
RD_LEADER_MM = [75,   100,  125,  150,   200]
RD_LEAD_1PCT = [2.15, 4.92, 8.77, 14.01, 30.16]
RD_LEAD_BASE_SLOPE_PCT = 0.125 / 12 * 100

MANNING_N: dict[str, float] = {
    "uPVC": 0.011, "PVC": 0.011, "HDPE": 0.011,
    "Cast Iron": 0.013, "Galv. Steel": 0.013,
}


# formula: roof_drain
def calculate(inputs: dict) -> dict:
    roof_area     = float(inputs.get("roof_area",       0))
    n_drains      = max(1, int(inputs.get("n_drains",   2)))
    intensity     = float(inputs.get("intensity_mmhr",  100))   # PAGASA NCR default
    slope_pct     = float(inputs.get("leader_slope_pct", 1.0))
    has_parapet   = str(inputs.get("has_parapet",       "Yes")).lower() in ("yes", "true", "1")
    pipe_material = str(inputs.get("pipe_material",     "uPVC"))

    manning_n = MANNING_N.get(pipe_material, 0.011)

    # Design flow — IPC §1101 Rational Method, C=1.0 for impervious roof
    q_total_ls = (intensity * roof_area) / 3600.0
    q_each_ls  = q_total_ls / n_drains if n_drains > 0 else q_total_ls

    # Primary roof drain body
    drain_idx  = next((i for i, c in enumerate(RD_DRAIN_LS) if c >= q_each_ls),
                      len(RD_DRAIN_MM) - 1)
    drain_mm   = RD_DRAIN_MM[drain_idx]
    drain_cap  = RD_DRAIN_LS[drain_idx]

    # Vertical leader — same diameter as drain body (IPC §1106.3)
    leader_mm  = drain_mm

    # Horizontal conductor — capacity scales with √(slope / 1%)
    slope_f = math.sqrt(max(slope_pct, 0.1) / RD_LEAD_BASE_SLOPE_PCT)
    horiz_idx = next(
        (i for i, c in enumerate(RD_LEAD_1PCT) if c * slope_f >= q_each_ls),
        len(RD_LEADER_MM) - 1
    )
    horiz_mm  = RD_LEADER_MM[horiz_idx]
    horiz_cap = round(RD_LEAD_1PCT[horiz_idx] * slope_f, 2)

    # Overflow drain — required with parapet (IPC §1101.7)
    overflow_mm = drain_mm if has_parapet else None

    # Compliance checks
    drain_ok        = drain_cap >= q_each_ls
    min_drains_ok   = n_drains >= 2
    overall_status  = "PASS" if (drain_ok and min_drains_ok) else "FAIL"

    return {
        "roof_area_m2":       round(roof_area, 1),
        "n_drains":           n_drains,
        "intensity_mmhr":     intensity,
        "leader_slope_pct":   slope_pct,
        "has_parapet":        has_parapet,
        "pipe_material":      pipe_material,
        "manning_n":          manning_n,
        "q_total_ls":         round(q_total_ls, 2),
        "q_each_ls":          round(q_each_ls,  2),
        "drain_size_mm":      drain_mm,
        "drain_cap_ls":       drain_cap,
        "leader_size_mm":     leader_mm,
        "horiz_leader_mm":    horiz_mm,
        "horiz_leader_cap_ls": horiz_cap,
        "overflow_drain_mm":  overflow_mm,
        "min_drains_check":   ("PASS" if min_drains_ok
                               else "FAIL: minimum 2 drains required per IPC §1106.3"),
        "drain_cap_check":    ("PASS" if drain_ok
                               else f"FAIL: Q_each {round(q_each_ls,2)} L/s exceeds max drain capacity"),
        "overflow_check":     ("Required: overflow at +50mm invert (IPC §1101.7)"
                               if has_parapet else "Not required: no parapet"),
        "overall_status":     overall_status,
    }
