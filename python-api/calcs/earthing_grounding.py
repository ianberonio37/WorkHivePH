"""
Earthing / Grounding System — Phase 7b (Option B port from TypeScript)
Standards: PEC 2017 Art. 2.50 (Grounding), IEC 60364-5-54,
           IEEE Std 142 (Green Book), OSHS PD 856 (Philippines)
Libraries: math

Formulae:
  Rod:   R = (ρ / 2πL) × [ln(8L/d) − 1]  = [ln(4L/a) − 1], a = rod radius   Dwight (1936), IEEE 142 Table 4-5
  Plate: R = ρ / (4r),  r = √(A/π)
  Ring:  R = (ρ / 2π²D) × [ln(8D/d) + ln(4D/s)],  s = 2 × burial depth          IEEE 142 Table 4-5
  Parallel n electrodes (adequate spacing): R_par = R_single / n
"""

import math

# PEC 2.50.66 / NEC Table 250.66 (copper): largest service conductor -> grounding electrode conductor.
# ★THE GEC WAS SMALLER THAN THE TABLE (2026-11-02, ED-G1 Earthing, read against the guide): 6 mm2 for a 35 mm2 service,
# 16 mm2 up to 95 mm2. NEC 250.66 by the service conductor's AWG bracket (compared by area, so a 35 mm2 conductor -
# larger than 2 AWG, 33.6 mm2 - is in the 1 to 1/0 bracket): <= 2 AWG -> 8 AWG; 1-1/0 -> 6; 2/0-3/0 -> 4; to 350 kcmil
# -> 2; to 600 kcmil -> 1/0; to 1100 kcmil -> 2/0; over -> 3/0. The GEC is the PEC size PEC equates with that AWG
# (8 AWG = 8.0 mm2, 6 = 14, 4 = 22, 2 = 38, 1/0 = 60, 2/0 = 80, 3/0 = 100).
GEC_TABLE: list[tuple[float, float, str]] = [
    (33.6,  8.0, "8 AWG"),
    (53.5,  14,  "6 AWG"),
    (85.0,  22,  "4 AWG"),
    (177.3, 38,  "2 AWG"),
    (304.0, 60,  "1/0 AWG"),
    (557.0, 80,  "2/0 AWG"),
]

# Resistance limits per system type (IEEE 142 / PEC 2017)
# ★TWO OF THE FORM'S FOUR SYSTEM TYPES WERE NOT KEYS (2026-11-02, form-option census): the form sends "Substation (IEEE 80)"
# and "Telecommunications"; the table held "Substation / HV" only, and R_LIMITS.get(..., 10.0) judged a substation grid
# against 10 Ohm instead of 1 - a grid of 4 Ohm read PASS. The guide promises telecom 5 Ohm; it was 10.
R_LIMITS: dict[str, float] = {
    "Residential / Commercial": 10.0,
    "Industrial":               5.0,
    "Substation / HV":          1.0,
    "Substation (IEEE 80)":     1.0,
    "Telecommunications":       5.0,
}


# formula: earthing_grounding_iec_60364_5
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
        # ★THE ROD FORMULA TOOK THE DIAMETER FOR THE RADIUS (2026-11-02, ED-G1 Earthing): Dwight's ln(4L/a) is the rod
        # RADIUS (IEEE 142 Table 4-5); with the diameter it read 11% low - a 3 m x 16 mm rod in 100 Ohm-m gave 29.8 Ohm
        # where it is 33.5. ln(8L/d) with the diameter is the same formula.
        r_single = (soil_rho / (2 * math.pi * L)) * (math.log(8 * L / d) - 1)

    elif electrode_type == "Plate":
        W = float(inputs.get("plate_width_m",  0.6))
        H = float(inputs.get("plate_height_m", 0.6))
        plate_area_m2  = W * H
        plate_radius_m = math.sqrt(plate_area_m2 / math.pi)
        r_single = soil_rho / (4 * plate_radius_m)

    else:  # Ring / Loop
        D = float(inputs.get("ring_dia_m",       10))
        d = float(inputs.get("ring_cond_dia_mm", 10)) / 1000.0
        # ★THE RING READ LOWER THAN A SOLID DISC (2026-11-02, ED-G1 Earthing): "ln(8D/d) - 2" gave a 10 m ring in 100
        # Ohm-m 3.54 Ohm - below a solid 10 m surface disc (rho / 2D = 5 Ohm), which a ring cannot be. IEEE 142 Table 4-5
        # (Dwight): rho / (2 pi^2 D) x [ln(8D/d) + ln(4D/s)], s = twice the burial depth; PEC 2.50.53(F) buries a ring at
        # least 750 mm, the default. That ring is 6.22 Ohm.
        ring_depth_m = float(inputs.get("ring_depth_m", 0.75) or 0.75)
        s_ring = 2 * ring_depth_m
        r_single = (soil_rho / (2 * math.pi**2 * D)) * (math.log(8 * D / d) + math.log(4 * D / s_ring))

    r_parallel  = r_single / num_elec
    effective_r = r_parallel if num_elec > 1 else r_single
    passes      = effective_r <= r_limit

    # GEC sizing per PEC 2017 Table 2.50.66
    gec_mm2, gec_label = 100, "3/0 AWG"
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
