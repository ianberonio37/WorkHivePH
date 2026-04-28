"""
Bearing Life (L10) — Phase 9i (Option B port from TypeScript)
Standards: ISO 281:2007 (Rolling Bearings — Dynamic Load Ratings),
           ABMA Std 11 (Load Ratings Ball Bearings),
           ABMA Std 1 (Roller Bearings)
Libraries: math

Formula (ISO 281):
  P = X × Fr + Y × Fa    (equivalent dynamic load)
  L10 = (C/P)^p           (million revolutions)
  L10h = L10 × 10^6 / (60 × n)    (hours)
  Adjusted life: Lna = a1 × L10h  (reliability factor a1 per ISO 281 Table 1)
"""

import math

# ISO 281 Table 1 reliability factors a1
A1_MAP: dict[int, float] = {
    90: 1.00, 95: 0.62, 96: 0.53, 97: 0.44, 98: 0.33, 99: 0.21
}

# ISO 281 simplified X, Y factors for deep groove ball bearings (Fa/Fr thresholds)
BALL_XY: list[tuple[float, float, float]] = [
    (0.44, 1.0, 0.0),
    (0.72, 0.56, 1.71),
    (1.02, 0.56, 1.40),
    (1.44, 0.56, 1.27),
    (2.28, 0.56, 1.17),
    (float('inf'), 0.56, 1.00),
]


def calculate(inputs: dict) -> dict:
    bearing_type    = str(inputs.get("bearing_type",     "Ball"))
    C_kN            = float(inputs.get("C_kN",           25.5))
    speed_rpm       = float(inputs.get("speed_rpm",      1450))
    Fr_kN           = float(inputs.get("Fr_kN",          5.0))
    Fa_kN           = float(inputs.get("Fa_kN",          0.0))
    reliability_pct = int(inputs.get("reliability_pct",  90))
    required_life_h = float(inputs.get("required_life_h", 25000))

    p_exp = 10.0 / 3.0 if bearing_type == "Roller" else 3.0

    Fa_Fr_ratio = round(Fa_kN / Fr_kN, 2) if Fr_kN > 0 else 0.0
    X, Y = 1.0, 0.0

    if Fa_kN > 0:
        if bearing_type == "Ball":
            for threshold, x, y in BALL_XY:
                if Fa_Fr_ratio <= threshold:
                    X, Y = x, y
                    break
        else:
            X, Y = 0.4, 1.5   # conservative for roller, 15° contact angle

    P_kN = round(X * Fr_kN + Y * Fa_kN, 2)
    C_over_P = round(C_kN / P_kN, 2) if P_kN > 0 else 0.0

    L10_Mrev = round(C_over_P ** p_exp, 2)
    L10h     = round(L10_Mrev * 1e6 / (60.0 * speed_rpm)) if speed_rpm > 0 else 0

    a1      = A1_MAP.get(reliability_pct, 1.00)
    L10h_adj = round(a1 * L10h)

    life_check = "PASS" if L10h_adj >= required_life_h else "FAIL"

    # Minimum C needed to meet required life
    C_req = round(P_kN * ((required_life_h / a1 * 60.0 * speed_rpm) / 1e6) ** (1.0 / p_exp), 1) \
            if (a1 > 0 and speed_rpm > 0) else 0.0

    return {
        "p_exp":           "10/3" if bearing_type == "Roller" else "3",
        "Fa_Fr_ratio":     Fa_Fr_ratio,
        "X":               X,
        "Y":               Y,
        "P_kN":            P_kN,
        "C_over_P":        C_over_P,
        "L10_Mrev":        L10_Mrev,
        "L10h":            L10h,
        "a1":              a1,
        "L10h_adj":        L10h_adj,
        "life_check":      life_check,
        "C_required_kN":   C_req,
    }
