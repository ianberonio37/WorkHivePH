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
# ★AXIAL LOAD WAS IGNORED UP TO 44% OF THE RADIAL, AND A ROLLER'S P COULD FALL BELOW ITS RADIAL LOAD (2026-11-02, ED-G1
# Bearing Life, read against the guide). The old table keyed X/Y on Fa/Fr with thresholds 0.44 / 0.72 / 1.02 ... that match
# no ISO column, so any Fa up to 0.44 Fr was dropped (ISO's e is 0.19-0.44, by f0 Fa / C0); and a roller took
# P = 0.4 Fr + 1.5 Fa for ANY axial load - at Fa = 0.1 Fr that is 0.55 Fr, less than the radial load, life x7.
# ISO 281 Table 3 (single-row deep-groove ball, normal clearance): (f0 Fa / C0, e, Y); X = 0.56 when Fa / Fr > e.
ISO_BALL_E_Y: list[tuple[float, float, float]] = [
    (0.172, 0.19, 2.30), (0.345, 0.22, 1.99), (0.689, 0.26, 1.71), (1.03, 0.28, 1.55), (1.38, 0.30, 1.45),
    (2.07, 0.34, 1.31), (3.45, 0.38, 1.15), (5.17, 0.42, 1.04), (6.89, 0.44, 1.00),
]
C0_OVER_C_EST = 0.55   # deep-groove 62xx / 63xx: C0 / C is about 0.50-0.58 (e.g. 6205 7.8/14.8, 6208 19/32.5)
F0_EST = 14.0          # ISO 281 calculation factor f0 for deep-groove ball bearings, typically 12-16
ROLLER_E, ROLLER_X, ROLLER_Y = 0.40, 0.40, 1.5   # tapered roller, about 15 deg: e = 1.5 tan(a), Y = 0.4 cot(a)


def _ball_e_y(ratio: float) -> tuple[float, float]:
    """e and Y at f0 Fa / C0, linear between the ISO 281 Table 3 rows, held at the ends."""
    rows = ISO_BALL_E_Y
    if ratio <= rows[0][0]:
        return rows[0][1], rows[0][2]
    for (r0, e0, y0), (r1, e1, y1) in zip(rows, rows[1:]):
        if ratio <= r1:
            t = (ratio - r0) / (r1 - r0)
            return e0 + t * (e1 - e0), y0 + t * (y1 - y0)
    return rows[-1][1], rows[-1][2]


# formula: bearing_life_iso_281_2007
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

    e_limit, xy_basis = 0.0, "pure radial load: P = Fr"
    if Fa_kN > 0:
        if bearing_type == "Ball":
            C0_given = float(inputs.get("C0_kN") or 0)
            C0_kN = C0_given if C0_given > 0 else C0_OVER_C_EST * C_kN
            f0 = float(inputs.get("f0") or F0_EST)
            e_limit, Y_iso = _ball_e_y(f0 * Fa_kN / C0_kN) if C0_kN > 0 else (0.19, 2.30)
            if Fr_kN <= 0 or Fa_kN / Fr_kN > e_limit:
                X, Y = 0.56, Y_iso
            xy_basis = (f"ISO 281 Table 3: f0 Fa/C0 = {f0:g} x {Fa_kN:g} / {C0_kN:.2f} -> e = {e_limit:.3f}, Y = {Y_iso:.3f}"
                        + ("" if C0_given > 0 else f" (C0 estimated as {C0_OVER_C_EST} C - enter the catalog C0 for the exact X, Y)"))
        else:
            e_limit = ROLLER_E
            if Fr_kN <= 0 or Fa_kN / Fr_kN > e_limit:
                X, Y = ROLLER_X, ROLLER_Y
            xy_basis = "tapered roller, about 15 deg contact: e = 0.40; P = Fr up to e, then 0.4 Fr + 1.5 Fa"

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
        "e_limit":         round(e_limit, 3),
        "xy_basis":        xy_basis,
        "Fa_Fr_ratio":     Fa_Fr_ratio,
        "X":               X,
        "Y":               round(Y, 3),
        "P_kN":            P_kN,
        "C_over_P":        C_over_P,
        "L10_Mrev":        L10_Mrev,
        "L10h":            L10h,
        "a1":              a1,
        "L10h_adj":        L10h_adj,
        "life_check":      life_check,
        "C_required_kN":   C_req,
    }
