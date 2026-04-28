"""
Earthing / Grounding System — Phase 7b (Option B port from TypeScript)
Standards: PEC 2017 Art. 2.50 (Grounding), IEC 60364-5-54,
           IEEE Std 142 (Green Book), OSHS PD 856 (Philippines)
Libraries: math

Formulae:
  Rod:   R = (ρ / 2πL) × [ln(4L/d) − 1]          Dwight (1936)
  Plate: R = ρ / (4r),  r = √(A/π)
  Ring:  R = (ρ / 2π²D) × [ln(8D/d) − 2]         Sunde (1968)
  Parallel n electrodes (adequate spacing): R_par = R_single / n
"""

import math

# PEC 2017 Table 2.50.66: service conductor → minimum GEC size
GEC_TABLE: list[tuple[float, int, str]] = [
    (35,  6,  "min 6 mm2"),
    (50,  10, "min 10 mm2"),
    (95,  16, "min 16 mm2"),
    (185, 35, "min 35 mm2"),
    (300, 50, "min 50 mm2"),
]

# Resistance limits per system type (IEEE 142 / PEC 2017)
R_LIMITS: dict[str, float] = {
    "Residential / Commercial": 10.0,
    "Industrial":               5.0,
    "Substation / HV":          1.0,
}


def calculate(inputs: dict) -> dict:
    electrode_type = str(inputs.get("electrode_type",   "Rod"))
    soil_rho       = float(inputs.get("soil_resistivity", 100))   # Ohm·m
    num_elec       = max(1, int(inputs.get("num_electrodes", 1)))
    sys_type       = str(inputs.get("system_type",        "Residential / Commercial"))
    svc_cond_mm2   = float(inputs.get("service_cond_mm2", 35))

    r_limit = R_LIMITS.get(sys_type, 10.0)

    plate_area_m2  = None
    plate_radius_m = None

    if electrode_type == "Rod":
        L = float(inputs.get("rod_length_m", 3.0))
        d = float(inputs.get("rod_dia_mm",   16)) / 1000.0
        r_single = (soil_rho / (2 * math.pi * L)) * (math.log(4 * L / d) - 1)

    elif electrode_type == "Plate":
        W = float(inputs.get("plate_width_m",  0.6))
        H = float(inputs.get("plate_height_m", 0.6))
        plate_area_m2  = W * H
        plate_radius_m = math.sqrt(plate_area_m2 / math.pi)
        r_single = soil_rho / (4 * plate_radius_m)

    else:  # Ring / Loop
        D = float(inputs.get("ring_dia_m",       10))
        d = float(inputs.get("ring_cond_dia_mm", 10)) / 1000.0
        r_single = (soil_rho / (2 * math.pi**2 * D)) * (math.log(8 * D / d) - 2)

    r_parallel  = r_single / num_elec
    effective_r = r_parallel if num_elec > 1 else r_single
    passes      = effective_r <= r_limit

    # GEC sizing per PEC 2017 Table 2.50.66
    gec_mm2, gec_label = 70, "min 70 mm2"
    for limit, size, label in GEC_TABLE:
        if svc_cond_mm2 <= limit:
            gec_mm2, gec_label = size, label
            break

    result: dict = {
        "r_single_ohm":   round(r_single,   3),
        "r_parallel_ohm": round(r_parallel, 3),
        "r_limit_ohm":    r_limit,
        "pass":           passes,
        "pass_label":     "PASS" if passes else "FAIL",
        "gec_mm2":        gec_mm2,
        "gec_label":      gec_label,
        "plate_area_m2":  round(plate_area_m2, 4)  if plate_area_m2  else None,
        "plate_radius_m": round(plate_radius_m, 4) if plate_radius_m else None,
    }
    return result
