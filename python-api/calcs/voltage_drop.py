"""
Voltage Drop — Phase 4b (Option B port from TypeScript)
Standards: PEC 2017 Article 2.10.19 (branch: ≤3%), 2.15 (feeder: ≤2%),
           IEC 60364-5-52, IEEE 141 (Red Book)
Libraries: math (numpy not required — pure resistivity formula)

Improvement over TypeScript:
- Temperature-corrected resistivity: ρ(T) = ρ₂₀ × [1 + α(T − 20)]
  instead of fixed 75°C table value. Defaults to 75°C (THWN standard).
- Explicit PEC 2017 combined limit check (branch + feeder total ≤5%).
- Maximum safe length returned per wire size — aids design optimisation.

Formulae (PEC 2017 / IEEE 141):
  Single-phase: VD = 2 × I × R × L        (factor 2: L = one-way, current
  Three-phase:  VD = √3 × I × R × L       flows both conductors / phases)
  where R (Ω/m) = ρ_T / A_mm²
"""

import math

# Standard PEC wire sizes (mm²) — matches PEC Table 3.10
WIRE_SIZES_MM2 = [2.0, 3.5, 5.5, 8.0, 14, 22, 30, 38, 50, 60, 80, 100, 125, 150, 200, 250]

# Base resistivity at 20°C (Ω·mm²/m) — IEC 60228 / IEEE 141
_RHO20_CU = 0.01724   # copper
_RHO20_AL = 0.02830   # aluminium

# Temperature coefficient of resistance per °C (copper/aluminium)
_ALPHA_CU = 0.00393
_ALPHA_AL = 0.00403


def _resistivity(material: str, temp_c: float = 75.0) -> float:
    """
    Conductor resistivity (Ω·mm²/m) at operating temperature.
    Defaults to 75°C (THWN/THHN standard rating temperature per PEC).
    """
    if material.lower().startswith("al"):
        return _RHO20_AL * (1.0 + _ALPHA_AL * (temp_c - 20.0))
    return _RHO20_CU * (1.0 + _ALPHA_CU * (temp_c - 20.0))


def calculate(inputs: dict) -> dict:
    circuit_type   = str(inputs.get("circuit_type",    "Branch Circuit"))
    phase          = str(inputs.get("phase",           "Single-phase"))
    voltage        = float(inputs.get("voltage",       230))
    current        = float(inputs.get("current",       20))
    wire_length    = float(inputs.get("wire_length",   30))
    conductor_mm2  = float(inputs.get("conductor_mm2", 3.5))
    material       = str(inputs.get("conductor_mat",   "Copper"))
    vd_limit       = float(inputs.get("vd_limit",      3.0))
    conductor_temp = float(inputs.get("conductor_temp_c", 75.0))

    rho        = _resistivity(material, conductor_temp)
    factor     = math.sqrt(3) if "three" in phase.lower() else 2.0
    R_selected = rho / conductor_mm2   # Ω/m for selected size

    def compute_vd(size_mm2: float) -> dict:
        R   = rho / size_mm2            # Ω/m
        vd_v   = factor * current * R * wire_length
        vd_pct = (vd_v / voltage) * 100.0
        # Maximum one-way length for this size to meet the VD limit
        max_len = (vd_limit / 100.0 * voltage) / (factor * current * R)
        return {
            "size_mm2":    size_mm2,
            "resistance_ohm_km": round(R * 1000.0, 2),
            "vd_v":        round(vd_v,   2),
            "vd_pct":      round(vd_pct, 2),
            "pass":        vd_pct <= vd_limit,
            "max_length_m": round(max_len),
            "is_selected": size_mm2 == conductor_mm2,
        }

    vd_v     = factor * current * R_selected * wire_length
    vd_pct   = (vd_v / voltage) * 100.0
    vd_limit_v = vd_limit / 100.0 * voltage
    max_len  = (vd_limit / 100.0 * voltage) / (factor * current * R_selected)

    # PEC 2017: branch ≤3%, feeder ≤2%, combined ≤5%
    pec_branch_ok = vd_pct <= 3.0
    pec_feeder_ok = vd_pct <= 2.0
    pec_combined_ok = vd_pct <= 5.0  # worst-case total (feeder + branch)

    comparison = [compute_vd(s) for s in WIRE_SIZES_MM2]

    return {
        "circuit_type":        circuit_type,
        "phase":               phase,
        "voltage":             voltage,
        "current":             current,
        "wire_length":         wire_length,
        "conductor_mm2":       conductor_mm2,
        "conductor_mat":       material,
        "conductor_temp_c":    conductor_temp,
        "vd_limit":            vd_limit,
        "vd_limit_volts":      round(vd_limit_v, 2),
        "resistivity":         round(rho, 5),
        "resistance_ohm_km":   round(R_selected * 1000.0, 2),
        "vd_volts":            round(vd_v,   2),
        "vd_pct":              round(vd_pct, 2),
        "pass":                vd_pct <= vd_limit,
        "max_length_m":        round(max_len),
        "pec_branch_ok":       pec_branch_ok,
        "pec_feeder_ok":       pec_feeder_ok,
        "pec_combined_ok":     pec_combined_ok,
        "size_comparison":     comparison,
    }
