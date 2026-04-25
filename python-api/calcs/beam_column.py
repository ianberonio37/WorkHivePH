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

CONCRETE_GRADES: dict[str, dict] = {
    "f'c 21 MPa (3000 psi)": {"fc_MPa": 21, "beta1": 0.85},
    "f'c 24 MPa (3500 psi)": {"fc_MPa": 24, "beta1": 0.85},
    "f'c 28 MPa (4000 psi)": {"fc_MPa": 28, "beta1": 0.85},
    "f'c 35 MPa (5000 psi)": {"fc_MPa": 35, "beta1": 0.836},
    "f'c 41 MPa (6000 psi)": {"fc_MPa": 41, "beta1": 0.822},
}

REBAR_GRADES: dict[str, dict] = {
    "Grade 40 (ASTM A615)":  {"fy_MPa": 276},
    "Grade 60 (ASTM A615)":  {"fy_MPa": 414},
    "Grade 75 (ASTM A615)":  {"fy_MPa": 517},
    "Grade 60 (ASTM A706)":  {"fy_MPa": 414},
}

# ─── W-section catalogue (partial - most common Philippine import sizes) ──────
# d=depth(mm), bf=flange width(mm), tf=flange thickness(mm), tw=web thickness(mm)
# Ix=moment of inertia(cm⁴), Sx=elastic section modulus(cm³),
# Zx=plastic section modulus(cm³), A=area(cm²)
W_SECTIONS: dict[str, dict] = {
    "W150x13":  {"d":148,"bf":100,"tf": 7.6,"tw": 4.8,"A": 16.8,"Ix": 981,   "Sx": 132,"Zx": 152},
    "W200x19":  {"d":203,"bf":102,"tf": 7.7,"tw": 6.4,"A": 24.8,"Ix":3240,   "Sx": 319,"Zx": 367},
    "W200x27":  {"d":203,"bf":133,"tf": 8.9,"tw": 6.4,"A": 34.4,"Ix":4080,   "Sx": 402,"Zx": 454},
    "W200x36":  {"d":203,"bf":165,"tf": 8.5,"tw": 6.2,"A": 45.9,"Ix":5150,   "Sx": 508,"Zx": 582},
    "W250x25":  {"d":257,"bf":102,"tf": 8.4,"tw": 6.1,"A": 32.1,"Ix":6060,   "Sx": 472,"Zx": 543},
    "W250x33":  {"d":258,"bf":146,"tf": 9.1,"tw": 6.9,"A": 42.0,"Ix":7700,   "Sx": 597,"Zx": 689},
    "W250x45":  {"d":266,"bf":148,"tf":13.0,"tw": 7.6,"A": 57.4,"Ix":11400,  "Sx": 858,"Zx": 984},
    "W310x33":  {"d":313,"bf":102,"tf": 8.9,"tw": 6.6,"A": 42.0,"Ix":12500,  "Sx": 799,"Zx": 910},
    "W310x45":  {"d":313,"bf":166,"tf": 9.7,"tw": 7.1,"A": 57.3,"Ix":16300,  "Sx":1040,"Zx":1180},
    "W310x60":  {"d":302,"bf":203,"tf":13.1,"tw": 7.5,"A": 75.9,"Ix":20400,  "Sx":1350,"Zx":1530},
    "W360x33":  {"d":349,"bf":102,"tf": 8.5,"tw": 6.1,"A": 42.0,"Ix":18500,  "Sx":1060,"Zx":1210},
    "W360x51":  {"d":356,"bf":171,"tf":11.6,"tw": 7.2,"A": 64.9,"Ix":31100,  "Sx":1750,"Zx":1980},
    "W360x79":  {"d":354,"bf":205,"tf":16.8,"tw": 9.4,"A":100.0,"Ix":48000,  "Sx":2710,"Zx":3080},
    "W410x38":  {"d":399,"bf":140,"tf": 8.8,"tw": 6.4,"A": 48.4,"Ix":31600,  "Sx":1584,"Zx":1800},
    "W410x54":  {"d":403,"bf":177,"tf":10.9,"tw": 7.5,"A": 68.5,"Ix":48800,  "Sx":2420,"Zx":2750},
    "W460x52":  {"d":450,"bf":152,"tf":10.8,"tw": 7.6,"A": 66.4,"Ix":55900,  "Sx":2490,"Zx":2820},
    "W460x74":  {"d":457,"bf":190,"tf":14.5,"tw": 9.0,"A": 94.2,"Ix":87500,  "Sx":3830,"Zx":4350},
    "W530x66":  {"d":525,"bf":165,"tf":11.4,"tw": 8.9,"A": 84.3,"Ix":102000, "Sx":3880,"Zx":4430},
    "W610x82":  {"d":599,"bf":178,"tf":12.8,"tw": 9.9,"A":104.0,"Ix":179000, "Sx":5980,"Zx":6870},
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

    return {
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


def _steel_column(sec: dict, Fy: float, E: float,
                  Pu_kN: float, L_m: float, K: float = 1.0) -> dict:
    """AISC 360-22 LRFD column (H-section): Euler + AISC Eq. E3."""
    A_m2    = sec["A"] * 1e-4           # cm² → m²
    # Least radius of gyration (approx from Ix and A; use Iy if provided)
    Ix_m4   = sec["Ix"] * 1e-8
    ry_m    = math.sqrt(Ix_m4 / A_m2)  # conservative: use Ix (should use min of Ix/Iy)

    KL_r    = K * L_m / ry_m            # slenderness ratio
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
