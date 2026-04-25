"""
Pressure Vessel Design — Phase 8c
Standards: ASME Boiler and Pressure Vessel Code (BPVC) Section VIII Division 1,
           ASME Section II Part D (Material properties),
           ASME B31.3 (Process Piping, for nozzle connections),
           PD 5500 (UK unfired pressure vessels — for reference),
           DOLE/BOI Philippines: pressure vessel registration required for MAWP > 15 psi
Libraries: math (all formulas closed-form)

Methods:
  Cylindrical shell: t = P×R / (S×E − 0.6P)       ASME VIII-1 UG-27(c)(1)
  Spherical shell:   t = P×R / (2×S×E − 0.2P)     ASME VIII-1 UG-27(d)
  Ellipsoidal head:  t = P×D / (2×S×E − 0.2P)     ASME VIII-1 UG-32(d)
  Hemispherical head: t = P×R / (2×S×E − 0.2P)    ASME VIII-1 UG-32(c)
  Flat head:         t = d × C × √(P/SE)           ASME VIII-1 UG-34
  Hydrostatic test:  P_test = 1.3 × MAWP × (S_test/S_design)  UG-99(b)
  Nozzle reinforcement: A_required = d × t_required  UG-37
"""

import math

# ─── ASME BPVC Sec. II Part D — Allowable stress (MPa) at design temperature ─
# S = allowable stress (MPa) at ≤ 300°F (149°C) unless noted
MATERIALS: dict[str, dict] = {
    "SA-516 Gr.70 (Carbon Steel)":    {"S_MPa": 138, "UTS_MPa": 485, "rho": 7850},
    "SA-516 Gr.60 (Carbon Steel)":    {"S_MPa": 113, "UTS_MPa": 415, "rho": 7850},
    "SA-106 Gr.B (Pipe)":             {"S_MPa": 103, "UTS_MPa": 415, "rho": 7850},
    "SA-240 Type 304 SS":             {"S_MPa": 138, "UTS_MPa": 515, "rho": 8000},
    "SA-240 Type 316 SS":             {"S_MPa": 138, "UTS_MPa": 515, "rho": 8000},
    "SA-240 Type 316L SS":            {"S_MPa": 115, "UTS_MPa": 485, "rho": 8000},
    "SA-285 Gr.C (Carbon Steel)":     {"S_MPa": 95,  "UTS_MPa": 380, "rho": 7850},
    "SA-537 Cl.1 (Carbon Steel)":     {"S_MPa": 138, "UTS_MPa": 485, "rho": 7850},
    "SA-240 Duplex 2205":             {"S_MPa": 172, "UTS_MPa": 620, "rho": 7800},
    "Hastelloy C-276 (SB-575)":       {"S_MPa": 138, "UTS_MPa": 690, "rho": 8890},
}

# ─── ASME VIII-1 joint efficiency E ──────────────────────────────────────────
# E = 1.0 (full radiography), 0.85 (spot), 0.70 (no radiography)
JOINT_EFFICIENCY: dict[str, float] = {
    "Full radiography (Type 1)":  1.00,
    "Spot radiography (Type 1)":  0.85,
    "No radiography (Type 1)":    0.70,
    "Fillet weld (Type 3)":       0.60,
}

# ─── Standard corrosion allowances (mm) ───────────────────────────────────────
CA_DEFAULT: dict[str, float] = {
    "Non-corrosive (dry gas)": 0.0,
    "Mild (water, steam)":     1.6,
    "Moderate (process)":      3.2,
    "Severe (acid)":           6.4,
}

# ─── Head types ───────────────────────────────────────────────────────────────
HEAD_TYPES = ["Ellipsoidal (2:1)", "Hemispherical", "Torispherical (ASME)", "Flat (bolted)"]

# ─── Standard plate thickness series (mm) ─────────────────────────────────────
STD_THICKNESS_MM = [
    3, 4, 5, 6, 8, 10, 12, 14, 16, 18, 20, 22, 25, 28, 32,
    36, 40, 45, 50, 56, 63, 70, 80, 90, 100,
]


def _next_std(t_mm: float) -> float:
    return next((s for s in STD_THICKNESS_MM if s >= t_mm), STD_THICKNESS_MM[-1])


def _shell_thickness(P_MPa: float, R_mm: float, S_MPa: float, E: float) -> float:
    """ASME VIII-1 UG-27(c)(1) — cylindrical shell minimum thickness (mm)."""
    return P_MPa * R_mm / (S_MPa * E - 0.6 * P_MPa)


def _sphere_thickness(P_MPa: float, R_mm: float, S_MPa: float, E: float) -> float:
    """ASME VIII-1 UG-27(d) — spherical shell minimum thickness (mm)."""
    return P_MPa * R_mm / (2 * S_MPa * E - 0.2 * P_MPa)


def _ellipsoidal_head(P_MPa: float, D_mm: float, S_MPa: float, E: float) -> float:
    """ASME VIII-1 UG-32(d) — 2:1 ellipsoidal head thickness (mm)."""
    return P_MPa * D_mm / (2 * S_MPa * E - 0.2 * P_MPa)


def _torispherical_head(P_MPa: float, D_mm: float, S_MPa: float, E: float) -> float:
    """
    ASME VIII-1 UG-32(e) — torispherical (ASME flanged and dished) head.
    t = 0.885 P L / (S E - 0.1 P)   where L = crown radius = D (standard)
    """
    L_mm = D_mm  # crown radius = OD for standard F&D head
    return 0.885 * P_MPa * L_mm / (S_MPa * E - 0.1 * P_MPa)


def _flat_head(P_MPa: float, d_mm: float, S_MPa: float, E: float,
               C: float = 0.33) -> float:
    """ASME VIII-1 UG-34(c)(2) — flat head thickness (mm). C=0.33 bolted."""
    return d_mm * C * math.sqrt(P_MPa / (S_MPa * E))


def _mawp_cylinder(t_mm: float, R_mm: float, S_MPa: float, E: float) -> float:
    """MAWP from actual thickness (no CA) — UG-27 rearranged."""
    return S_MPa * E * t_mm / (R_mm + 0.6 * t_mm)


def _nozzle_reinforcement(t_shell_mm: float, d_nozzle_mm: float,
                           P_MPa: float, S_MPa: float, E: float) -> dict:
    """
    ASME VIII-1 UG-37 nozzle reinforcement area check.
    A_required = d × tr   (tr = required shell thickness)
    A_available = excess metal in shell + nozzle neck
    Simplified: checks if excess shell thickness provides required area.
    """
    tr_mm = _shell_thickness(P_MPa, d_nozzle_mm / 2, S_MPa, E)
    A_req_mm2 = d_nozzle_mm * tr_mm
    # Excess in shell (simplified: 2.5t excess each side)
    A_avail_shell = (t_shell_mm - tr_mm) * d_nozzle_mm * 2
    A_avail_shell = max(A_avail_shell, 0)
    pad_required  = A_avail_shell < A_req_mm2
    A_pad_mm2     = max(0, A_req_mm2 - A_avail_shell)

    return {
        "A_required_mm2":    round(A_req_mm2, 1),
        "A_available_mm2":   round(A_avail_shell, 1),
        "reinforcement_pad_required": pad_required,
        "A_pad_required_mm2": round(A_pad_mm2, 1),
        "tr_nozzle_mm":      round(tr_mm, 3),
    }


def calculate(inputs: dict) -> dict:
    """Main entry point — compatible with TypeScript calcPressureVessel() keys."""
    # ── Design conditions ─────────────────────────────────────────────────────
    P_bar          = float(inputs.get("design_pressure_bar",   10.0))
    P_MPa          = P_bar / 10.0
    T_C            = float(inputs.get("design_temperature_C",  150.0))
    vessel_type    = str  (inputs.get("vessel_type",           "Cylindrical"))   # Cylindrical / Spherical
    ID_mm          = float(inputs.get("inner_diameter_mm",     800.0))
    length_mm      = float(inputs.get("shell_length_mm",      2000.0))
    head_type      = str  (inputs.get("head_type",             "Ellipsoidal (2:1)"))

    mat_key        = str  (inputs.get("material",              "SA-516 Gr.70 (Carbon Steel)"))
    mat            = MATERIALS.get(mat_key, MATERIALS["SA-516 Gr.70 (Carbon Steel)"])
    S_MPa          = mat["S_MPa"]

    joint_key      = str  (inputs.get("joint_efficiency",      "Full radiography (Type 1)"))
    E              = JOINT_EFFICIENCY.get(joint_key, 1.0)

    ca_key         = str  (inputs.get("corrosion_allowance",   "Mild (water, steam)"))
    CA_mm          = float(inputs.get("corrosion_mm",
                             CA_DEFAULT.get(ca_key, 1.6)))

    nozzle_dia_mm  = float(inputs.get("nozzle_diameter_mm",   100.0))
    n_nozzles      = int  (inputs.get("n_nozzles",              2))

    # ── Shell thickness ───────────────────────────────────────────────────────
    R_mm = ID_mm / 2
    if vessel_type == "Spherical":
        t_min_mm = _sphere_thickness(P_MPa, R_mm, S_MPa, E)
    else:
        t_min_mm = _shell_thickness(P_MPa, R_mm, S_MPa, E)

    t_required_mm = t_min_mm + CA_mm
    t_actual_mm   = _next_std(t_required_mm)
    OD_mm         = ID_mm + 2 * t_actual_mm

    # ── MAWP at actual thickness ──────────────────────────────────────────────
    t_net_mm = t_actual_mm - CA_mm   # net thickness (corrosion removed)
    if vessel_type == "Spherical":
        mawp_MPa = _mawp_cylinder(t_net_mm, R_mm, S_MPa, E) * 2  # sphere factor
    else:
        mawp_MPa = _mawp_cylinder(t_net_mm, R_mm, S_MPa, E)
    mawp_bar = mawp_MPa * 10

    # ── Head thickness ────────────────────────────────────────────────────────
    if head_type == "Ellipsoidal (2:1)":
        t_head_min = _ellipsoidal_head(P_MPa, ID_mm, S_MPa, E)
    elif head_type == "Hemispherical":
        t_head_min = _sphere_thickness(P_MPa, R_mm, S_MPa, E)
    elif head_type == "Torispherical (ASME)":
        t_head_min = _torispherical_head(P_MPa, ID_mm, S_MPa, E)
    else:  # Flat
        t_head_min = _flat_head(P_MPa, ID_mm, S_MPa, E)

    t_head_req    = t_head_min + CA_mm
    t_head_actual = _next_std(t_head_req)

    # ── Hydrostatic test pressure (UG-99b) ────────────────────────────────────
    # P_test = 1.3 × MAWP (assume S_test = S_design, same temp)
    P_test_bar = 1.3 * mawp_bar
    P_test_MPa = P_test_bar / 10

    # ── Nozzle reinforcement ──────────────────────────────────────────────────
    nozzle_check = _nozzle_reinforcement(t_net_mm, nozzle_dia_mm, P_MPa, S_MPa, E)

    # ── Weight estimate ────────────────────────────────────────────────────────
    rho = mat["rho"]   # kg/m³
    # Shell volume
    V_shell_m3 = math.pi * ((OD_mm/2000)**2 - (ID_mm/2000)**2) * length_mm / 1000
    # Two heads (approximate as flat discs at head thickness)
    V_heads_m3 = 2 * math.pi * (OD_mm/2000)**2 * t_head_actual / 1000
    W_empty_kg = (V_shell_m3 + V_heads_m3) * rho
    # Water weight for hydro test
    V_fluid_m3 = math.pi * (ID_mm/2000)**2 * length_mm / 1000
    W_hydro_kg = W_empty_kg + V_fluid_m3 * 1000

    # ── Compliance notes ──────────────────────────────────────────────────────
    p_psi = P_bar * 14.504
    code_notes = [
        f"Design pressure: {P_bar} bar ({round(p_psi,1)} psi) @ {T_C}°C.",
        f"Material: {mat_key} — S = {S_MPa} MPa, joint E = {E}.",
        f"Shell: t_min = {round(t_min_mm,3)} mm + CA {CA_mm} mm → "
        f"t_required = {round(t_required_mm,3)} mm → t_actual = {t_actual_mm} mm (std plate).",
        f"MAWP at t_actual: {round(mawp_bar,2)} bar — {'PASS' if mawp_bar >= P_bar else 'FAIL'}.",
        f"Hydrostatic test: {round(P_test_bar,2)} bar (1.3 × MAWP, UG-99b).",
        f"Nozzle {nozzle_dia_mm}mm: reinforcement pad "
        f"{'required' if nozzle_check['reinforcement_pad_required'] else 'NOT required'} (UG-37).",
        "ASME Sec. VIII Div.1 stamp (U-stamp) required; Authorized Inspector (AI) oversight.",
        "Philippines: DOLE registration required for vessels with MAWP > 15 psi (PD 856, OSHS).",
        "NDT: all pressure welds per UW-11; post-weld heat treatment per UCS-56 if t > 38mm (CS).",
    ]

    return {
        # Design basis
        "design_pressure_bar":   P_bar,
        "design_pressure_MPa":   round(P_MPa, 3),
        "design_temperature_C":  T_C,
        "inner_diameter_mm":     ID_mm,
        "outer_diameter_mm":     round(OD_mm, 1),

        # Shell
        "t_shell_min_mm":        round(t_min_mm, 3),
        "t_shell_required_mm":   round(t_required_mm, 3),
        "t_shell_actual_mm":     t_actual_mm,
        "corrosion_allowance_mm": CA_mm,

        # MAWP
        "mawp_bar":              round(mawp_bar, 3),
        "mawp_MPa":              round(mawp_MPa, 4),
        "mawp_ok":               mawp_bar >= P_bar,

        # Head
        "head_type":             head_type,
        "t_head_min_mm":         round(t_head_min, 3),
        "t_head_required_mm":    round(t_head_req, 3),
        "t_head_actual_mm":      t_head_actual,

        # Test
        "hydro_test_bar":        round(P_test_bar, 2),
        "hydro_test_MPa":        round(P_test_MPa, 3),

        # Nozzle
        "nozzle_diameter_mm":    nozzle_dia_mm,
        "n_nozzles":             n_nozzles,
        **{f"nozzle_{k}": v for k, v in nozzle_check.items()},

        # Weight
        "weight_empty_kg":       round(W_empty_kg, 1),
        "weight_hydro_kg":       round(W_hydro_kg, 1),

        # Code
        "material":              mat_key,
        "allowable_stress_MPa":  S_MPa,
        "joint_efficiency":      E,
        "code_notes":            code_notes,

        # Metadata
        "inputs_used": {
            "design_pressure_bar": P_bar,
            "inner_diameter_mm":   ID_mm,
            "material":            mat_key,
            "vessel_type":         vessel_type,
            "head_type":           head_type,
        },
        "calculation_source": "python/math",
        "standard": "ASME BPVC Sec. VIII Div.1 | ASME Sec. II Part D | DOLE OSHS PD 856",
    }
