"""
Harmonic Distortion Analysis — Electrical: Power Quality (Phase 9f)
Standards: IEEE 519-2022 (Recommended Practice for Harmonic Control),
           IEC 61000-3-2:2018 (Limits for Harmonic Current Emissions),
           IEC 61000-3-12 (Low-voltage systems, equipment ≥ 16A/phase)
Libraries: math

Method:
  THD_I = √(Σ Ih²) / I₁ × 100%  (Total Harmonic Distortion of current)
  TDD   = √(Σ Ih²) / I_L × 100% (Total Demand Distortion; I_L = max demand current)
  IEEE 519-2022 Table 2: TDD limits by ISC/IL ratio (point of common coupling)
  Individual harmonic limits per IEEE 519-2022 Table 3

Harmonics input: [{order: 3, current_pct: 25}, {order: 5, current_pct: 18}, ...]
"""

import math

# IEEE 519-2022 Table 2 — Maximum TDD limits at PCC (%)
# ISC/IL ratio: TDD limit %
TDD_LIMITS: list[tuple[float, float]] = [
    (20,   5.0),
    (50,   8.0),
    (100,  12.0),
    (1000, 15.0),
    (float('inf'), 20.0),
]

# IEEE 519-2014/2022 Table 2 — Maximum individual ODD-harmonic current distortion
# (% of IL) at the PCC for systems rated 120 V–69 kV. CRITICAL: each ISC/IL tier has
# DIFFERENT per-band limits — they are NOT a uniform multiple of the <20 row.
# (Fixed 2026-06-23 Arc Q: the engine previously took the <20 row × a single factor
# ×1/2/3/3.5/5, which OVERSTATED every higher-tier limit by 14–43% = too permissive,
# so a non-compliant design could be reported COMPLIANT. Re-anchored to the verbatim
# Table 2 matrix — same change-detector class as the fire_sprinkler density bug.)
# Bands: 3<=h<11, 11<=h<17, 17<=h<23, 23<=h<35, 35<=h<=50.
INDIVIDUAL_LIMITS: list[tuple[float, dict[str, float]]] = [
    # ISC/IL <        3-11    11-17   17-23   23-35   >35
    (20,           {"3-11": 4.0,  "11-17": 2.0, "17-23": 1.5, "23-35": 0.6, ">35": 0.3}),
    (50,           {"3-11": 7.0,  "11-17": 3.5, "17-23": 2.5, "23-35": 1.0, ">35": 0.5}),
    (100,          {"3-11": 10.0, "11-17": 4.5, "17-23": 4.0, "23-35": 1.5, ">35": 0.7}),
    (1000,         {"3-11": 12.0, "11-17": 5.5, "17-23": 5.0, "23-35": 2.0, ">35": 1.0}),
    (float('inf'), {"3-11": 15.0, "11-17": 7.0, "17-23": 6.0, "23-35": 2.5, ">35": 1.4}),
]


def _tdd_limit(isc_il: float) -> float:
    for ratio, limit in TDD_LIMITS:
        if isc_il < ratio:
            return limit
    return 20.0


def _individual_limit_pct(order: int, isc_il: float, il_a: float) -> float:
    """Maximum individual harmonic current as % of IL — IEEE 519 Table 2 (full matrix,
    looked up by (ISC/IL tier, harmonic band); NOT a uniform scale of the <20 row)."""
    if   order < 11: band = "3-11"
    elif order < 17: band = "11-17"
    elif order < 23: band = "17-23"
    elif order < 35: band = "23-35"
    else:            band = ">35"
    for ratio, row in INDIVIDUAL_LIMITS:
        if isc_il < ratio:
            return row[band]
    return INDIVIDUAL_LIMITS[-1][1][band]


# formula: harmonic_distortion_ieee_519_2022
def calculate(inputs: dict) -> dict:
    fundamental_a   = float(inputs.get("fundamental_current_a", 100))
    max_demand_a    = float(inputs.get("max_demand_current_a", 0))   # I_L; if 0, use fundamental
    system_voltage  = float(inputs.get("system_voltage_v",    400))
    isc_a           = float(inputs.get("short_circuit_current_a", 0))  # ISC at PCC
    harmonics       = inputs.get("harmonics", [])   # [{order, current_pct}]

    # Defaults
    if max_demand_a <= 0:
        max_demand_a = fundamental_a
    isc_il = (isc_a / max_demand_a) if (isc_a > 0 and max_demand_a > 0) else 20.0

    # Build harmonic table
    harmonic_table: list[dict] = []
    sum_sq = 0.0
    for h in harmonics:
        order   = int(h.get("order", 3))
        i_pct   = float(h.get("current_pct", 0))   # % of fundamental
        i_a     = fundamental_a * i_pct / 100.0
        pwr_w   = 0.0  # harmonic power (zero-sequence don't deliver real power)
        lim_pct = _individual_limit_pct(order, isc_il, max_demand_a)
        lim_a   = max_demand_a * lim_pct / 100.0
        passes  = i_a <= lim_a
        sum_sq += i_a ** 2
        harmonic_table.append({
            "order":           order,
            "current_pct":     round(i_pct, 2),
            "current_A":       round(i_a, 2),
            "limit_pct_of_IL": round(lim_pct, 2),
            "limit_A":         round(lim_a, 2),
            "pass":            passes,
        })

    # Sort by order
    harmonic_table.sort(key=lambda x: x["order"])

    # THD_I: referred to fundamental
    thd_i = (math.sqrt(sum_sq) / fundamental_a * 100.0) if fundamental_a > 0 else 0.0

    # TDD: referred to max demand current
    tdd   = (math.sqrt(sum_sq) / max_demand_a  * 100.0) if max_demand_a  > 0 else 0.0

    tdd_limit  = _tdd_limit(isc_il)
    tdd_pass   = tdd <= tdd_limit

    # K-factor (transformer de-rating indicator)
    # K = Σ (Ih/I1)² × h²
    k_factor = sum(
        (h["current_pct"] / 100.0) ** 2 * h["order"] ** 2
        for h in harmonic_table
    ) + 1.0   # fundamental contributes 1×(1)² = 1

    # Telephone interference factor (TIF) — simplified
    # TIF = √(Σ (wh × Ih)²) / I_rms where wh = ITU weighting at harmonic h
    # (Simplified: not computed here — flag for future)

    return {
        "fundamental_current_A":    round(fundamental_a, 2),
        "max_demand_current_A":     round(max_demand_a,  2),
        "system_voltage_V":         system_voltage,
        "isc_il_ratio":             round(isc_il, 1),
        "THD_I_pct":                round(thd_i,  2),
        "TDD_pct":                  round(tdd,    2),
        "TDD_limit_pct":            tdd_limit,
        "TDD_pass":                 tdd_pass,
        "TDD_status":               "PASS" if tdd_pass else f"FAIL: TDD {round(tdd,1)}% > limit {tdd_limit}%",
        "K_factor":                 round(k_factor, 2),
        "individual_harmonics":     harmonic_table,
        "all_individuals_pass":     all(h["pass"] for h in harmonic_table),
        "overall_pass":             tdd_pass and all(h["pass"] for h in harmonic_table),
    }
