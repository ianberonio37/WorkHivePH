"""
Bolt Torque & Preload — Phase 9j (Option B port from TypeScript)
Standards: ISO 898-1:2013 (Mechanical Properties of Fasteners),
           VDI 2230:2015 (Systematic Calculation of Bolted Joints),
           ASME B18.2.1, PEC 2017 Annex
Libraries: math

Formula (Shigley / VDI 2230):
  Proof load:  Fp = At × Sp
  Preload:     Fi = (preload_pct/100) × Fp
  Torque:      T  = K × d × Fi       (K = nut factor / torque coefficient)
  3-pass tightening: 30% → 70% → 100% of T_target
"""

# Bolt stress area (mm²) — ISO 898-1 Table 4 / ASME B18
BOLT_DATA: dict[str, tuple[float, float]] = {
    "M6":  (6,    20.1),
    "M8":  (8,    36.6),
    "M10": (10,   58.0),
    "M12": (12,   84.3),
    "M16": (16,  157.0),
    "M20": (20,  245.0),
    "M24": (24,  353.0),
    "M30": (30,  561.0),
    "M36": (36,  817.0),
}

# Proof strength (MPa) per grade — ISO 898-1:2013 Table 3/4
SP_MAP: dict[str, float] = {
    "4.6":  225.0,
    "4.8":  310.0,
    "8.8":  600.0,   # ≥M16; 580 MPa for M5–M14
    "10.9": 830.0,
    "12.9": 970.0,
}

# Nut factor K condition labels
NUT_LABELS: dict[str, str] = {
    "0.12": "Waxed / MoS2 lubricated",
    "0.15": "Machine oil lubricated",
    "0.20": "As-received (dry)",
    "0.25": "Heavily oxidised / dirty",
}


def calculate(inputs: dict) -> dict:
    bolt_size   = str(inputs.get("bolt_size",   "M16"))
    bolt_grade  = str(inputs.get("bolt_grade",  "8.8"))
    nut_factor  = float(inputs.get("nut_factor",  0.20))
    preload_pct = float(inputs.get("preload_pct", 75))
    ext_load_kN = float(inputs.get("ext_load_kN", 0))
    n_bolts     = max(1, int(inputs.get("n_bolts", 4)))

    d_mm, At_mm2 = BOLT_DATA.get(bolt_size, (16, 157.0))
    Sp_MPa = SP_MAP.get(bolt_grade, 600.0)

    # ISO 898-1: Grade 8.8 Sp = 580 MPa for M5–M14
    if bolt_grade == "8.8" and d_mm <= 14:
        Sp_MPa = 580.0

    # Proof load and preload
    Fp_kN = round(At_mm2 * Sp_MPa / 1000.0, 2)
    Fi_kN = round(preload_pct / 100.0 * Fp_kN, 2)

    # Tensile stress check
    sigma_MPa  = round(Fi_kN * 1000.0 / At_mm2, 1)
    stress_util = round(sigma_MPa / Sp_MPa * 100, 1)
    stress_check = "PASS" if sigma_MPa <= Sp_MPa else "FAIL"

    # Tightening torque: T = K × d × Fi  (d in metres, Fi in N)
    d_m      = d_mm / 1000.0
    Fi_N     = Fi_kN * 1000.0
    torque_Nm = round(nut_factor * d_m * Fi_N, 1)
    torque_30 = round(torque_Nm * 0.30, 1)
    torque_70 = round(torque_Nm * 0.70, 1)

    # Joint separation check
    total_clamp_kN = round(n_bolts * Fi_kN, 2)
    separation_sf  = round(total_clamp_kN / ext_load_kN, 2) if ext_load_kN > 0 else None
    n_bolts_min    = max(1, -(-int(ext_load_kN * 1.5 / Fi_kN) if Fi_kN > 0 else 1)) \
                     if ext_load_kN > 0 else 1   # ceil division
    joint_check    = "PASS" if n_bolts >= n_bolts_min else "FAIL"

    nut_condition = NUT_LABELS.get(str(nut_factor), f"K={nut_factor}")

    return {
        "bolt_size":       bolt_size,
        "bolt_grade":      bolt_grade,
        "d_mm":            d_mm,
        "At_mm2":          At_mm2,
        "Sp_MPa":          Sp_MPa,
        "Fp_kN":           Fp_kN,
        "preload_pct":     preload_pct,
        "Fi_kN":           Fi_kN,
        "sigma_MPa":       sigma_MPa,
        "stress_util":     stress_util,
        "stress_check":    stress_check,
        "nut_factor":      nut_factor,
        "nut_condition":   nut_condition,
        "torque_Nm":       torque_Nm,
        "torque_30pct":    torque_30,
        "torque_70pct":    torque_70,
        "n_bolts":         n_bolts,
        "ext_load_kN":     ext_load_kN,
        "total_clamp_kN":  total_clamp_kN,
        "separation_sf":   separation_sf,
        "n_bolts_min":     n_bolts_min,
        "joint_check":     joint_check,
    }
