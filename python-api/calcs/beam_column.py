"""
Beam / Column Structural Design - Phase 7a
Standards: NSCP 2015 Vol.1 (National Structural Code of the Philippines),
           AISC 360-22 (Steel), ACI 318-19 (Concrete),
           ASCE 7-22 (Loading), ASTM A36 / A992 (Steel), ASTM A615 (Rebar)
Libraries: math (all formulas closed-form)

Methods:
  Steel beam:  AISC LRFD - plastic moment Mp = Fy × Zx; shear Vn = 0.6Fy × Aw
  RC beam:     ACI 318 - Mn = As × fy × (d − a/2); a = As×fy/(0.85×f'c×b)
  Steel column: AISC - Euler buckling, λc classification, φcPn
  RC column:   ACI 318 - Pn = 0.85×f'c×(Ag − Ast) + fy×Ast
  Deflection:  Elastic beam theory - δ = 5wL⁴/(384EI) (UDL), PL³/(48EI) (midpoint)
"""

import math

# ─── Material properties ──────────────────────────────────────────────────────

STEEL_GRADES: dict[str, dict] = {
    "A36":        {"Fy_MPa": 250, "Fu_MPa": 400, "E_MPa": 200_000},
    "A992":       {"Fy_MPa": 345, "Fu_MPa": 450, "E_MPa": 200_000},
    "A572 Gr.50": {"Fy_MPa": 345, "Fu_MPa": 450, "E_MPa": 200_000},
    "A572 Gr.60": {"Fy_MPa": 415, "Fu_MPa": 520, "E_MPa": 200_000},
    "ASTM A53 (Pipe)": {"Fy_MPa": 240, "Fu_MPa": 415, "E_MPa": 200_000},
}

# NOTE: the calc derives β₁ live via _beta1(fc_MPa) (ACI 318-19 §22.2.2.4.3) — that
# function is the single source of truth. The "beta1" values below are reference-only
# (not read by calculate()); kept consistent with the standard so they can't mislead.
# (Fixed 2026-06-23 Arc Q: f'c35 was 0.836 / f'c41 was 0.822 — both wrong; the ACI
#  formula gives 0.80 and 0.757. They were dead data so never served, but a wrong
#  standard constant in a table is a latent change-detector trap.)
CONCRETE_GRADES: dict[str, dict] = {
    "f'c 21 MPa (3000 psi)": {"fc_MPa": 21, "beta1": 0.85},
    "f'c 24 MPa (3500 psi)": {"fc_MPa": 24, "beta1": 0.85},
    "f'c 28 MPa (4000 psi)": {"fc_MPa": 28, "beta1": 0.85},
    "f'c 35 MPa (5000 psi)": {"fc_MPa": 35, "beta1": 0.80},
    "f'c 41 MPa (6000 psi)": {"fc_MPa": 41, "beta1": 0.757},
}

REBAR_GRADES: dict[str, dict] = {
    "Grade 40 (ASTM A615)":  {"fy_MPa": 276},
    "Grade 60 (ASTM A615)":  {"fy_MPa": 414},
    "Grade 75 (ASTM A615)":  {"fy_MPa": 517},
    "Grade 60 (ASTM A706)":  {"fy_MPa": 414},
}

# ─── W-section catalogue (partial - most common Philippine import sizes) ──────
# d=depth(mm), bf=flange width(mm), tf=flange thickness(mm), tw=web thickness(mm)
# Ix=strong-axis moment of inertia(cm⁴), Iy=WEAK-axis moment of inertia(cm⁴),
# Sx=elastic section modulus(cm³), Zx=plastic section modulus(cm³), A=area(cm²)
# ★Ix, Sx AND Zx WERE TWO TO THREE TIMES THE SECTIONS' OWN (2026-11-02, ED-G1 Beam / Column, read against the guide's
# "phi.Mp = phi.Fy.Zx"): W360x33 (W14x22) carried Zx 1,210 cm³ and Ix 18,500 cm⁴ where AISC prints 544 and 8,283 - its
# own d/tf/tw give ~7,980 cm⁴. Every steel beam's bending capacity and stiffness were overstated 1.2x (W150x13) to 3.3x
# (W610x82): a beam failing by half passed, and deflection read a third. d, bf, tf, tw, A, Ix, Sx, Zx are now AISC Shapes
# Database v16.0 (imperial x 25.4 / 6.4516 / 41.6231 / 16.3871), each row named with its imperial shape; Iy unchanged.
# Iy = AISC v16.0 tabulated (Iy[in⁴]×41.6231), added 2026-06-23 Arc Q — the prior
# geometry estimate (tf·bf³/6 + web) was NON-conservative for 8 of 19 sections
# (error −48%…+38%, e.g. W150x13/W200x19 OVERSTATED r → unsafe column capacity).
W_SECTIONS: dict[str, dict] = {
    "W150x13":  {"d":149.9,"bf":100.1,"tf":5.46,"tw":4.32,"A":17.3,"Ix":683,"Iy":91.6,"Sx":91.1,"Zx":102.1},   # W6x9
    "W200x19":  {"d":202.9,"bf":101.6,"tf":6.48,"tw":5.84,"A":24.8,"Ix":1648,"Iy":113.6,"Sx":162.4,"Zx":186.8},   # W8x13
    "W200x27":  {"d":206.8,"bf":133.3,"tf":8.38,"tw":5.84,"A":33.9,"Ix":2576,"Iy":331.7,"Sx":249.1,"Zx":278.6},   # W8x18
    "W200x36":  {"d":201.4,"bf":165.1,"tf":10.16,"tw":6.22,"A":45.7,"Ix":3442,"Iy":761.7,"Sx":342.5,"Zx":378.5},   # W8x24
    "W250x25":  {"d":256.5,"bf":101.9,"tf":8.38,"tw":6.10,"A":32.2,"Ix":3409,"Iy":148.2,"Sx":265.5,"Zx":306.4},   # W10x17
    "W250x33":  {"d":259.1,"bf":146.0,"tf":9.14,"tw":6.10,"A":41.9,"Ix":4912,"Iy":474.5,"Sx":380.2,"Zx":426.1},   # W10x22
    "W250x45":  {"d":266.7,"bf":147.6,"tf":12.95,"tw":7.62,"A":57.0,"Ix":7076,"Iy":695.1,"Sx":530.9,"Zx":599.8},   # W10x30
    "W310x33":  {"d":312.4,"bf":102.4,"tf":10.79,"tw":6.60,"A":41.8,"Ix":6493,"Iy":194.0,"Sx":416.2,"Zx":480.1},   # W12x22
    "W310x45":  {"d":312.4,"bf":165.6,"tf":11.18,"tw":6.60,"A":56.7,"Ix":9906,"Iy":844.9,"Sx":632.5,"Zx":706.3},   # W12x30
    "W310x60":  {"d":302.3,"bf":203.5,"tf":13.08,"tw":7.49,"A":75.5,"Ix":12778,"Iy":1835.6,"Sx":843.9,"Zx":934.1},   # W12x40
    "W360x33":  {"d":348.0,"bf":127.0,"tf":8.51,"tw":5.84,"A":41.9,"Ix":8283,"Iy":291.4,"Sx":475.2,"Zx":544.1},   # W14x22
    "W360x51":  {"d":355.6,"bf":171.4,"tf":11.56,"tw":7.24,"A":64.5,"Ix":14152,"Iy":969.8,"Sx":796.4,"Zx":894.7},   # W14x34
    "W360x79":  {"d":353.1,"bf":204.7,"tf":16.76,"tw":9.40,"A":100.6,"Ix":22518,"Iy":2401.7,"Sx":1274.9,"Zx":1427.3},   # W14x53
    "W410x38":  {"d":398.8,"bf":139.7,"tf":8.76,"tw":6.35,"A":49.5,"Ix":12529,"Iy":399.2,"Sx":629.3,"Zx":724.3},   # W16x26
    "W410x54":  {"d":403.9,"bf":177.5,"tf":10.92,"tw":7.49,"A":68.4,"Ix":18647,"Iy":1019.8,"Sx":925.9,"Zx":1048.8},   # W16x36
    "W460x52":  {"d":449.6,"bf":152.4,"tf":10.79,"tw":7.62,"A":66.5,"Ix":21228,"Iy":636.8,"Sx":943.9,"Zx":1089.7},   # W18x35
    "W460x74":  {"d":457.2,"bf":190.5,"tf":14.48,"tw":9.02,"A":94.8,"Ix":33298,"Iy":1669.1,"Sx":1456.8,"Zx":1655.1},   # W18x50
    "W530x66":  {"d":525.8,"bf":165.1,"tf":11.43,"tw":8.89,"A":83.9,"Ix":35088,"Iy":861.6,"Sx":1337.2,"Zx":1563.3},   # W21x44
    "W610x82":  {"d":599.4,"bf":178.1,"tf":12.83,"tw":10.03,"A":104.5,"Ix":56191,"Iy":1211.2,"Sx":1868.1,"Zx":2195.9},   # W24x55
}

# ─── LRFD resistance factors (AISC / NSCP) ───────────────────────────────────
PHI_B  = 0.90   # bending
PHI_V  = 1.00   # shear (AISC 360-22 Eq. G2-1 compact web)
PHI_C  = 0.90   # compression
PHI_RC = 0.90   # RC beam bending (ACI 318)
PHI_RC_COL = 0.65  # RC tied column

# ─── ACI 318 limits ──────────────────────────────────────────────────────────
RHO_MIN_ACI = 1.4 / 414        # min steel ratio (Grade 60): 1.4/fy (MPa)
RHO_MAX_ACI = 0.75 * 0.85      # conservative max (balanced × 0.75)


def _beta1(fc_MPa: float) -> float:
    """ACI 318-19 §22.2.2.4.3: β₁ factor."""
    if fc_MPa <= 28:
        return 0.85
    return max(0.65, 0.85 - 0.05 * (fc_MPa - 28) / 7)


def _steel_beam(sec: dict, Fy: float, E: float,
                Mu_kNm: float, Vu_kN: float, L_m: float, w_kNm: float) -> dict:
    """AISC 360-22 LRFD steel beam check."""
    Zx_m3  = sec["Zx"] * 1e-6          # cm³ → m³
    Mp_kNm = Fy * 1000 * Zx_m3         # kN·m (Fy in MPa → kN/m²)

    phi_Mp = PHI_B * Mp_kNm

    # Shear capacity (Eq. G2-1 - compact web, Cv1=1.0)
    tw_m   = sec["tw"] / 1000
    d_m    = sec["d"]  / 1000
    Aw     = sec["d"] * sec["tw"] * 1e-6   # m²
    Vn_kN  = 0.6 * Fy * 1000 * Aw          # kN
    phi_Vn = PHI_V * Vn_kN

    DCR_M = Mu_kNm / phi_Mp
    DCR_V = Vu_kN  / phi_Vn

    # Elastic deflection: UDL δ = 5wL⁴/(384EI)
    Ix_m4   = sec["Ix"] * 1e-8             # cm⁴ → m⁴
    E_kNm2  = E * 1000                     # MPa → kN/m²
    w_kNm2  = w_kNm                        # kN/m (UDL)
    delta_m = 5 * w_kNm2 * L_m**4 / (384 * E_kNm2 * Ix_m4) if L_m > 0 else 0
    delta_mm = delta_m * 1000
    limit_mm = L_m * 1000 / 360            # L/360 live load limit

    # phi.Mp (AISC F2-1, yielding) holds only while the compression flange is braced at <= Lp = 1.76 ry sqrt(E/Fy) (F2-5);
    # past that, lateral-torsional buckling lowers Mn. The form takes no bracing length, so the check says so.
    ry_m = (sec["Iy"] / sec["A"]) ** 0.5 / 100 if sec.get("A") else 0.0
    Lp_m = 1.76 * ry_m * (E / Fy) ** 0.5 if Fy > 0 else 0.0

    return {
        # the section's own properties (AISC v16), so the report prints them instead of back-solving them from phi.Mp
        "Zx_mm3":      round(sec["Zx"] * 1000),
        "Aw_mm2":      round(sec["d"] * sec["tw"]),
        "Ix_mm4":      round(sec["Ix"] * 1e4),
        "Mp_kNm":      round(Mp_kNm, 1),
        "phi_Mp_kNm":  round(phi_Mp, 1),
        "Vn_kN":       round(Vn_kN, 1),
        "phi_Vn_kN":   round(phi_Vn, 1),
        "DCR_moment":  round(DCR_M, 3),
        "DCR_shear":   round(DCR_V, 3),
        "moment_ok":   DCR_M <= 1.0,
        "shear_ok":    DCR_V <= 1.0,
        "deflection_mm":   round(delta_mm, 2),
        "deflection_limit_mm": round(limit_mm, 2),
        "deflection_ok":   delta_mm <= limit_mm,
        "Lp_m":            round(Lp_m, 2),
        "braced_assumed":  L_m > Lp_m,
    }


def _rc_beam(b_mm: float, h_mm: float, cover_mm: float,
             bar_dia_mm: float, n_bars: int,
             fc_MPa: float, fy_MPa: float,
             Mu_kNm: float, Vu_kN: float,
             stirrup_dia_mm: float = 10, stirrup_spacing_mm: float = 150) -> dict:
    """ACI 318-19 singly-reinforced RC beam."""
    d_mm    = h_mm - cover_mm - stirrup_dia_mm - bar_dia_mm / 2    # effective depth
    d_m     = d_mm / 1000
    b_m     = b_mm / 1000
    As_mm2  = n_bars * math.pi * (bar_dia_mm / 2) ** 2
    As_m2   = As_mm2 * 1e-6

    rho     = As_mm2 / (b_mm * d_mm)
    rho_min = 1.4 / fy_MPa
    rho_max = 0.75 * (0.85 * _beta1(fc_MPa) * fc_MPa / fy_MPa) * (600 / (600 + fy_MPa))

    beta1   = _beta1(fc_MPa)
    a_mm    = As_mm2 * fy_MPa / (0.85 * fc_MPa * b_mm)    # depth of stress block
    c_mm    = a_mm / beta1                                  # neutral axis depth
    et      = (d_mm - c_mm) / c_mm * 0.003                 # tension strain
    # φ factor: tension-controlled if et ≥ 0.005
    phi_b   = PHI_RC if et >= 0.005 else (0.65 + (et - 0.002) * 250/3 if et >= 0.002 else 0.65)
    phi_b   = min(phi_b, PHI_RC)

    Mn_kNm  = As_m2 * fy_MPa * 1000 * (d_m - (a_mm/1000) / 2)  # kN·m
    phi_Mn  = phi_b * Mn_kNm
    DCR_M   = Mu_kNm / phi_Mn if phi_Mn > 0 else 999

    # Shear (ACI 318 §22.5.5.1 simplified)
    lambda_ = 1.0   # normal weight concrete
    Vc_kN   = 0.17 * lambda_ * math.sqrt(fc_MPa) * b_m * d_m * 1000
    # Stirrup capacity
    Av_mm2  = 2 * math.pi * (stirrup_dia_mm / 2) ** 2   # 2-leg
    Vs_kN   = Av_mm2 * fy_MPa * d_mm / (stirrup_spacing_mm * 1000)
    Vn_kN   = Vc_kN + Vs_kN
    phi_Vn  = 0.75 * Vn_kN
    DCR_V   = Vu_kN / phi_Vn if phi_Vn > 0 else 999

    return {
        "d_mm":           round(d_mm, 1),
        "As_mm2":         round(As_mm2, 1),
        "rho":            round(rho, 5),
        "rho_min":        round(rho_min, 5),
        "rho_max":        round(rho_max, 5),
        "rho_ok":         rho_min <= rho <= rho_max,
        "a_mm":           round(a_mm, 2),
        "c_mm":           round(c_mm, 2),
        "tension_strain": round(et, 5),
        "tension_controlled": et >= 0.005,
        "Mn_kNm":         round(Mn_kNm, 2),
        "phi_Mn_kNm":     round(phi_Mn, 2),
        "DCR_moment":     round(DCR_M, 3),
        "moment_ok":      DCR_M <= 1.0,
        "Vc_kN":          round(Vc_kN, 2),
        "Vs_kN":          round(Vs_kN, 2),
        "phi_Vn_kN":      round(phi_Vn, 2),
        "DCR_shear":      round(DCR_V, 3),
        "shear_ok":       DCR_V <= 1.0,
    }


def _iy_cm4(sec: dict) -> float:
    """Weak-axis second moment of area Iy (cm⁴). Uses the AISC-tabulated value from
    W_SECTIONS when present — the governing axis for an unbraced doubly-symmetric column
    is almost always the weak axis, so this value drives min(Ix,Iy) in the column r.
    Falls back to a geometry estimate (tf·bf³/6 + web, fillets neglected) ONLY when no Iy
    is tabulated. ⚠ That estimate is NOT reliably conservative: vs AISC it ranges
    −48%…+38% and OVERSTATES Iy for shallow/wide shapes, so it is a last-resort fallback,
    never the design basis. (Arc Q 2026-06-23: the column check originally used the
    STRONG-axis r=√(Ix/A) and overstated weak-axis capacity; exact AISC Iy added after the
    geometry estimate was found non-conservative for 8 of 19 sections.)"""
    if sec.get("Iy") is not None:
        return float(sec["Iy"])
    bf, tf, d, tw = sec.get("bf"), sec.get("tf"), sec.get("d"), sec.get("tw")
    if None in (bf, tf, d, tw):
        return sec["Ix"]   # incomplete geometry → fall back to Ix (no worse than before)
    iy_mm4 = (tf * bf ** 3) / 6.0 + ((d - 2 * tf) * tw ** 3) / 12.0
    return iy_mm4 / 1e4    # mm⁴ → cm⁴ (non-conservative fallback only)


def _steel_column(sec: dict, Fy: float, E: float,
                  Pu_kN: float, L_m: float, K: float = 1.0) -> dict:
    """AISC 360-22 LRFD column (H-section): Euler + AISC Eq. E3."""
    A_m2    = sec["A"] * 1e-4           # cm² → m²
    # Governing (least) radius of gyration: weak axis usually controls a doubly-symmetric
    # H-column. Iy is derived from geometry (W_SECTIONS has no Iy column); use min(Ix,Iy).
    Iy_cm4  = _iy_cm4(sec)
    I_min_m4 = min(sec["Ix"], Iy_cm4) * 1e-8
    r_m     = math.sqrt(I_min_m4 / A_m2)

    KL_r    = K * L_m / r_m             # slenderness ratio (governing axis)
    Fe_MPa  = math.pi**2 * E / KL_r**2 # elastic critical stress

    if KL_r <= 4.71 * math.sqrt(E / Fy):
        # Inelastic buckling (AISC Eq. E3-2)
        Fcr_MPa = (0.658 ** (Fy / Fe_MPa)) * Fy
    else:
        # Elastic buckling (AISC Eq. E3-3)
        Fcr_MPa = 0.877 * Fe_MPa

    Pn_kN   = Fcr_MPa * 1000 * A_m2
    phi_Pn  = PHI_C * Pn_kN
    DCR     = Pu_kN / phi_Pn

    return {
        "KL_r":        round(KL_r, 1),
        "KL_r_limit":  round(200, 0),          # AISC §E2 recommended max
        "slender_ok":  KL_r <= 200,
        "Fe_MPa":      round(Fe_MPa, 1),
        "Fcr_MPa":     round(Fcr_MPa, 1),
        "Pn_kN":       round(Pn_kN, 1),
        "phi_Pn_kN":   round(phi_Pn, 1),
        "DCR_axial":   round(DCR, 3),
        "axial_ok":    DCR <= 1.0,
        "Iy_cm4":      round(_iy_cm4(sec), 0),
        "buckling_axis": "weak (y)" if _iy_cm4(sec) < sec["Ix"] else "strong (x)",
    }


def _rc_column(b_mm: float, h_mm: float,
               bar_dia_mm: float, n_bars: int,
               fc_MPa: float, fy_MPa: float,
               Pu_kN: float) -> dict:
    """ACI 318-19 §22.4.2 tied rectangular column (pure axial - conservative)."""
    Ag_mm2  = b_mm * h_mm
    Ast_mm2 = n_bars * math.pi * (bar_dia_mm / 2) ** 2
    rho_g   = Ast_mm2 / Ag_mm2

    # ACI limits
    rho_ok  = 0.01 <= rho_g <= 0.08

    Pn_kN   = 0.85 * fc_MPa * (Ag_mm2 - Ast_mm2) / 1000 + fy_MPa * Ast_mm2 / 1000
    # Tied column reduction: 0.80 per ACI 318 §22.4.2
    phi_Pn  = PHI_RC_COL * 0.80 * Pn_kN
    DCR     = Pu_kN / phi_Pn

    return {
        "Ag_mm2":      Ag_mm2,
        "Ast_mm2":     round(Ast_mm2, 1),
        "rho_g":       round(rho_g, 5),
        "rho_ok":      rho_ok,
        "Pn_kN":       round(Pn_kN, 1),
        "phi_Pn_kN":   round(phi_Pn, 1),
        "DCR_axial":   round(DCR, 3),
        "axial_ok":    DCR <= 1.0,
    }


# formula: beam_column
def calculate(inputs: dict) -> dict:
    """Main entry point - compatible with TypeScript calcBeamColumn() keys."""
    member_type   = str(inputs.get("member_type",   "Steel Beam"))   # Steel Beam / RC Beam / Steel Column / RC Column
    span_m        = float(inputs.get("span_m",      6.0))
    Mu_kNm        = float(inputs.get("Mu_kNm",      0.0))
    Vu_kN         = float(inputs.get("Vu_kN",       0.0))
    Pu_kN         = float(inputs.get("Pu_kN",       0.0))
    w_kNm         = float(inputs.get("w_kNm",       0.0))   # UDL (kN/m) for deflection
    K_factor      = float(inputs.get("K_factor",    1.0))

    results: dict = {}

    if "Steel" in member_type:
        grade_key = str(inputs.get("steel_grade", "A36"))
        mat       = STEEL_GRADES.get(grade_key, STEEL_GRADES["A36"])
        Fy        = mat["Fy_MPa"]
        E         = mat["E_MPa"]
        sec_key   = str(inputs.get("section", "W310x45"))
        sec       = W_SECTIONS.get(sec_key)
        if sec is None:
            raise ValueError(f"Section '{sec_key}' not in catalogue. "
                             f"Available: {sorted(W_SECTIONS.keys())}")

        if "Beam" in member_type:
            results = _steel_beam(sec, Fy, E, Mu_kNm, Vu_kN, span_m, w_kNm)
        else:
            results = _steel_column(sec, Fy, E, Pu_kN, span_m, K_factor)

        results["section"] = sec_key
        results["steel_grade"] = grade_key
        results["Fy_MPa"] = Fy

    else:  # RC
        b_mm          = float(inputs.get("b_mm",       300))
        h_mm          = float(inputs.get("h_mm",       500))
        cover_mm      = float(inputs.get("cover_mm",    40))
        bar_dia_mm    = float(inputs.get("bar_dia_mm",  20))
        n_bars        = int  (inputs.get("n_bars",       4))
        stirrup_dia   = float(inputs.get("stirrup_dia_mm", 10))
        stirrup_s_mm  = float(inputs.get("stirrup_spacing_mm", 150))

        fc_key  = str(inputs.get("concrete_grade", "f'c 28 MPa (4000 psi)"))
        fc_data = CONCRETE_GRADES.get(fc_key, CONCRETE_GRADES["f'c 28 MPa (4000 psi)"])
        fc_MPa  = fc_data["fc_MPa"]

        fy_key  = str(inputs.get("rebar_grade", "Grade 60 (ASTM A615)"))
        fy_data = REBAR_GRADES.get(fy_key, REBAR_GRADES["Grade 60 (ASTM A615)"])
        fy_MPa  = fy_data["fy_MPa"]

        if "Beam" in member_type:
            results = _rc_beam(b_mm, h_mm, cover_mm, bar_dia_mm, n_bars,
                               fc_MPa, fy_MPa, Mu_kNm, Vu_kN,
                               stirrup_dia, stirrup_s_mm)
        else:
            results = _rc_column(b_mm, h_mm, bar_dia_mm, n_bars, fc_MPa, fy_MPa, Pu_kN)

        results["b_mm"]           = b_mm
        results["h_mm"]           = h_mm
        results["concrete_grade"] = fc_key
        results["rebar_grade"]    = fy_key
        results["fc_MPa"]         = fc_MPa
        results["fy_MPa"]         = fy_MPa

    results.update({
        "member_type":  member_type,
        "span_m":       span_m,
        "inputs_used": {
            "member_type": member_type,
            "span_m":      span_m,
            "Mu_kNm":      Mu_kNm,
            "Vu_kN":       Vu_kN,
            "Pu_kN":       Pu_kN,
        },
        "calculation_source": "python/math",
        "standard": "NSCP 2015 Vol.1 | AISC 360-22 | ACI 318-19 | ASCE 7-22",
    })
    return results
