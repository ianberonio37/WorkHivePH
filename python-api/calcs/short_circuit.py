"""
Short Circuit Analysis — Phase 4b
Standards: IEC 60909-0:2016 (Short-circuit currents in AC systems),
           PEC 2017 Article 2.40, IEEE 141 (Red Book), IEEE 242 (Buff Book)
Libraries: math (all formulas closed-form)

Calculates:
- Transformer impedance (Z_trafo) from nameplate %Z rating
- Cable impedance (Z_cable = √(R² + X²)) — skill rule: never use R alone
- Total fault impedance at each bus (Z_total = Z_trafo + Z_cable + Z_source)
- Symmetrical three-phase fault current (Isc_3ph = Vc / (√3 × Z_total))
- Single-phase-to-ground fault (Isc_1ph = V_phase / Z_total)
- Line-to-line fault (Isc_LL = √3/2 × Isc_3ph)
- Peak fault current with asymmetry factor κ (IEC 60909 Fig. 28)
- Breaking current and dc-component decay
- OCPD interrupting capacity check vs calculated Isc
"""

import math

# ─── IEC 60909 voltage factor c ───────────────────────────────────────────────
# c_max for fault current calculation (conservative — use for equipment rating)
C_MAX_LV = 1.05   # ≤ 1 kV systems
C_MAX_HV = 1.10   # > 1 kV systems

# ─── Copper conductor resistivity at 20°C ─────────────────────────────────────
RHO_CU_20C = 1 / 58   # Ω·mm²/m
ALPHA_CU   = 0.00393  # /°C temperature coefficient

# ─── Cable reactance at 50 Hz (Ω/km) — PEC / IEC 60364 ──────────────────────
# (same table as wire_sizing.py — skill reference)
REACTANCE_TABLE: list[dict] = [
    {"mm2":  14, "X_km": 0.085},
    {"mm2":  22, "X_km": 0.083},
    {"mm2":  30, "X_km": 0.082},
    {"mm2":  38, "X_km": 0.080},
    {"mm2":  60, "X_km": 0.079},
    {"mm2": 100, "X_km": 0.077},
    {"mm2": 150, "X_km": 0.076},
    {"mm2": 250, "X_km": 0.074},
]

# ─── Standard transformer %Z values (typical nameplate) ───────────────────────
# IEC 60076-5 / PEC 2017
DEFAULT_Z_PCT: dict[str, float] = {
    "Distribution (< 500 kVA)": 4.0,
    "Medium (500–2500 kVA)":    5.5,
    "Large (> 2500 kVA)":       6.0,
    "Generator":                15.0,  # subtransient reactance X''d
}

# ─── Standard OCPD interrupting capacities (kA) ───────────────────────────────
OCPD_KA = [6, 10, 16, 20, 25, 35, 50, 65, 85, 100, 150, 200]

# ─── IEC 60909 asymmetry factor κ ─────────────────────────────────────────────
# κ = 1.02 + 0.98 × e^(−3R/X)
# Tabulated for common X/R ratios:
def _kappa(r_over_x: float) -> float:
    """IEC 60909 peak factor κ = 1.02 + 0.98·exp(−3·R/X)."""
    if r_over_x <= 0:
        return 2.0
    return 1.02 + 0.98 * math.exp(-3 * r_over_x)


def _reactance_interp(mm2: float) -> float:
    """Interpolated cable reactance (Ω/km) for given cross-section."""
    if mm2 <= REACTANCE_TABLE[0]["mm2"]:
        return REACTANCE_TABLE[0]["X_km"]
    if mm2 >= REACTANCE_TABLE[-1]["mm2"]:
        return REACTANCE_TABLE[-1]["X_km"]
    for i in range(len(REACTANCE_TABLE) - 1):
        lo, hi = REACTANCE_TABLE[i], REACTANCE_TABLE[i + 1]
        if lo["mm2"] <= mm2 <= hi["mm2"]:
            t = (mm2 - lo["mm2"]) / (hi["mm2"] - lo["mm2"])
            return lo["X_km"] + t * (hi["X_km"] - lo["X_km"])
    return 0.082


def _cable_impedance(
    mm2: float, length_m: float, temp_c: float = 20, parallel: int = 1
) -> tuple[float, float, float]:
    """
    Cable impedance at operating temperature.
    Returns (R_ohm, X_ohm, Z_ohm).
    Uses Z = √(R² + X²) — skill rule: never use R alone.
    parallel: number of parallel cable runs (reduces impedance proportionally).
    """
    rho_t = RHO_CU_20C * (1 + ALPHA_CU * (temp_c - 20))
    R = rho_t * length_m / mm2 / parallel
    X = _reactance_interp(mm2) * length_m / 1000 / parallel
    Z = math.sqrt(R ** 2 + X ** 2)
    return R, X, Z


def _trafo_impedance(
    kva: float,
    voltage_hv: float,
    voltage_lv: float,
    z_pct: float,
    xr_ratio: float = 5.0,   # typical distribution transformer X/R ratio
) -> tuple[float, float, float]:
    """
    Transformer impedance referred to LV side.
    Z_base = V_LV² / S_trafo
    Z_trafo = (z_pct/100) × Z_base
    X_trafo = Z_trafo / √(1 + (R/X)²); R_trafo from X/R ratio.
    Returns (R_ohm, X_ohm, Z_ohm) referred to LV.
    """
    z_base    = (voltage_lv ** 2) / (kva * 1000)   # Ω at LV
    z_trafo   = (z_pct / 100) * z_base
    # X/R ratio: x_trafo = z_trafo × sin(θ), r_trafo = z_trafo × cos(θ)
    theta     = math.atan(xr_ratio)
    r_trafo   = z_trafo * math.cos(theta)
    x_trafo   = z_trafo * math.sin(theta)
    return r_trafo, x_trafo, z_trafo


def _source_impedance(
    fault_kva_source: float,
    voltage_lv: float,
) -> tuple[float, float, float]:
    """
    Source (grid) impedance from available fault MVA at PCC.
    Z_source = V² / S_fault_source
    Assumed X/R ≈ 10 for utility grid.
    Returns (R_ohm, X_ohm, Z_ohm) referred to LV.
    """
    if fault_kva_source <= 0:
        return 0.0, 0.0, 0.0
    z_src = (voltage_lv ** 2) / (fault_kva_source * 1000)
    # X/R = 10 for utility
    r_src = z_src / math.sqrt(1 + 10 ** 2)
    x_src = r_src * 10
    return r_src, x_src, z_src


def calculate(inputs: dict) -> dict:
    """
    Main entry point — compatible with TypeScript calcShortCircuit() keys.
    """
    # ── System inputs ─────────────────────────────────────────────────────────
    voltage_lv     = float(inputs.get("voltage",          400))   # V LV bus
    voltage_hv     = float(inputs.get("voltage_hv",     22000))   # V HV supply (22kV typical PH)
    trafo_kva      = float(inputs.get("transformer_kva",  500))
    trafo_z_pct    = float(inputs.get("transformer_z_pct",
                           DEFAULT_Z_PCT["Distribution (< 500 kVA)"]))
    trafo_xr       = float(inputs.get("transformer_xr_ratio", 5.0))
    source_mva     = float(inputs.get("source_fault_mva",  250))   # utility SCC at PCC (MVA)

    # Cable from transformer to fault point
    cable_mm2      = float(inputs.get("cable_mm2",         50))
    cable_length_m = float(inputs.get("cable_length_m",    30))
    cable_parallel = int  (inputs.get("cable_parallel",     1))
    cable_temp_c   = float(inputs.get("cable_temp_c",      75))   # at max load (75°C THHN)

    # Additional cable segment (optional — for bus to panel run)
    cable2_mm2     = float(inputs.get("cable2_mm2",         0))
    cable2_length  = float(inputs.get("cable2_length_m",    0))
    cable2_parallel = int (inputs.get("cable2_parallel",    1))

    # OCPD at fault bus
    ocpd_ka        = float(inputs.get("ocpd_interrupting_ka", 25))

    # IEC 60909 voltage factor
    c_factor       = C_MAX_LV if voltage_lv <= 1000 else C_MAX_HV

    # ── Transformer impedance ─────────────────────────────────────────────────
    R_trafo, X_trafo, Z_trafo = _trafo_impedance(
        trafo_kva, voltage_hv, voltage_lv, trafo_z_pct, trafo_xr
    )

    # ── Source (utility) impedance referred to LV ─────────────────────────────
    source_kva = source_mva * 1000
    R_src, X_src, Z_src = _source_impedance(source_kva, voltage_lv)

    # ── Cable segment 1 impedance ─────────────────────────────────────────────
    R_c1, X_c1, Z_c1 = _cable_impedance(cable_mm2, cable_length_m, cable_temp_c, cable_parallel)

    # ── Cable segment 2 impedance (optional) ─────────────────────────────────
    if cable2_mm2 > 0 and cable2_length > 0:
        R_c2, X_c2, Z_c2 = _cable_impedance(cable2_mm2, cable2_length, cable_temp_c, cable2_parallel)
    else:
        R_c2, X_c2, Z_c2 = 0.0, 0.0, 0.0

    # ── Total impedance at fault bus ──────────────────────────────────────────
    # Series combination: Z_total = Z_source + Z_trafo + Z_cable1 + Z_cable2
    R_total = R_src + R_trafo + R_c1 + R_c2
    X_total = X_src + X_trafo + X_c1 + X_c2
    Z_total = math.sqrt(R_total ** 2 + X_total ** 2)

    if Z_total <= 0:
        raise ValueError("Total impedance cannot be zero.")

    # X/R ratio at fault point
    xr_total = X_total / max(R_total, 1e-9)

    # ── Symmetrical fault currents (IEC 60909) ────────────────────────────────
    # Initial symmetrical short-circuit current I"k
    Isc_3ph  = c_factor * voltage_lv / (math.sqrt(3) * Z_total)   # A rms
    Isc_1ph  = c_factor * voltage_lv / (math.sqrt(3) * Z_total)   # approx — same Z for zero-seq ≈ pos-seq in TN system
    Isc_LL   = (math.sqrt(3) / 2) * Isc_3ph   # line-to-line (2-ph) fault

    # ── Peak fault current (IEC 60909 §4.3.1) ────────────────────────────────
    kappa      = _kappa(R_total / max(X_total, 1e-9))
    Ip_peak    = kappa * math.sqrt(2) * Isc_3ph   # A peak

    # ── DC component at 50 ms (typical CB operating time) ────────────────────
    # i_dc = √2 × Isc × e^(−t × ω × R/X)   at t = 0.05 s, ω = 314 rad/s
    t_cb     = 0.05   # s — typical CB clearing time
    omega    = 2 * math.pi * 50
    i_dc_50ms = math.sqrt(2) * Isc_3ph * math.exp(-t_cb * omega * R_total / max(X_total, 1e-9))

    # ── Fault MVA ─────────────────────────────────────────────────────────────
    fault_mva = (math.sqrt(3) * voltage_lv * Isc_3ph) / 1e6

    # ── OCPD adequacy check ───────────────────────────────────────────────────
    Isc_3ph_kA   = Isc_3ph / 1000
    ocpd_adequate = ocpd_ka >= Isc_3ph_kA

    # Recommend next OCPD rating if inadequate
    rec_ocpd = next((k for k in OCPD_KA if k >= Isc_3ph_kA), OCPD_KA[-1])

    # ── Impedance breakdown for engineering review ────────────────────────────
    def pct_total(z: float) -> float:
        return round(z / max(Z_total, 1e-9) * 100, 1)

    return {
        # System basis
        "voltage_lv_V":         voltage_lv,
        "voltage_hv_V":         voltage_hv,
        "c_factor":             c_factor,

        # Fault currents
        "Isc_3ph_kA":           round(Isc_3ph_kA, 3),
        "Isc_3ph_A":            round(Isc_3ph, 1),
        "Isc_LL_kA":            round(Isc_LL / 1000, 3),
        "Isc_1ph_kA":           round(Isc_1ph / 1000, 3),
        "Ip_peak_kA":           round(Ip_peak / 1000, 3),
        "i_dc_50ms_kA":         round(i_dc_50ms / 1000, 3),
        "fault_MVA":            round(fault_mva, 3),

        # Asymmetry
        "kappa":                round(kappa, 3),
        "xr_ratio_total":       round(xr_total, 2),

        # Impedance breakdown
        "impedance": {
            "Z_source_ohm":     round(Z_src, 6),
            "R_source_ohm":     round(R_src, 6),
            "X_source_ohm":     round(X_src, 6),
            "source_pct":       pct_total(Z_src),

            "Z_trafo_ohm":      round(Z_trafo, 6),
            "R_trafo_ohm":      round(R_trafo, 6),
            "X_trafo_ohm":      round(X_trafo, 6),
            "trafo_pct":        pct_total(Z_trafo),

            "Z_cable1_ohm":     round(Z_c1, 6),
            "R_cable1_ohm":     round(R_c1, 6),
            "X_cable1_ohm":     round(X_c1, 6),
            "cable1_pct":       pct_total(Z_c1),

            "Z_cable2_ohm":     round(Z_c2, 6),
            "cable2_pct":       pct_total(Z_c2),

            "Z_total_ohm":      round(Z_total, 6),
            "R_total_ohm":      round(R_total, 6),
            "X_total_ohm":      round(X_total, 6),
        },

        # OCPD check
        "ocpd_required_kA":     round(Isc_3ph_kA, 3),
        "ocpd_provided_kA":     ocpd_ka,
        "ocpd_adequate":        ocpd_adequate,
        "recommended_ocpd_kA":  rec_ocpd,

        # Inputs used
        "inputs_used": {
            "transformer_kva":     trafo_kva,
            "transformer_z_pct":   trafo_z_pct,
            "transformer_xr":      trafo_xr,
            "source_fault_mva":    source_mva,
            "cable_mm2":           cable_mm2,
            "cable_length_m":      cable_length_m,
            "cable_temp_c":        cable_temp_c,
        },
        "calculation_source": "python/math",
        "standard": "IEC 60909-0:2016 | PEC 2017 Art.2.40 | IEEE 141 | IEEE 242",

        # ── Legacy renderer aliases (frontend renderShortCircuitReport) ─────────
        "Isc_kA":       round(Isc_3ph_kA, 3),
        "Ipeak_kA":     round(Ip_peak / 1000, 3),
        "Z_total_ohm":  round(Z_total, 6),
        "R_cable_ohm":  round(R_c1 + R_c2, 6),
        "X_cable_ohm":  round(X_c1, 6),
        "Z_cable_ohm":  round(Z_c1 + Z_c2, 6),
        "Z_xfmr_ohm":   round(Z_trafo, 6),
        "Z_base_ohm":   round(voltage_lv**2 / (trafo_kva * 1000), 6),
        "ic_check":     "PASS" if ocpd_adequate else "FAIL",
        "ic_min_recommended": rec_ocpd,
        "ic_margin":    round(ocpd_ka - Isc_3ph_kA, 3),
    }
