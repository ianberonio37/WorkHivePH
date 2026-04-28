"""
Power Factor Correction — Phase 4f (Option B port from TypeScript)
Standards: IEEE 18-2012 (Shunt Capacitors), IEEE 1036-2010 (Application Guide),
           PEC 2017 Article 4.60, Meralco PF surcharge policy (threshold 0.85)
Libraries: math

Improvement over TypeScript:
- Capacitor bank sizing also returned in kVAR/phase for 3-phase delta banks
- Explicit Meralco ERC-approved surcharge note (monthly_savings_php)
- Payback estimate added if investment_php provided

Formulae (IEEE 18):
  kVAR_required = kW × (tan φ₁ − tan φ₂)
  where φ₁ = arccos(PF_existing), φ₂ = arccos(PF_target)
"""

import math

# Standard capacitor bank sizes (kVAR) — IEEE 18 / manufacturer catalogue
STD_KVAR = [5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 150, 200, 300, 400, 500]


def calculate(inputs: dict) -> dict:
    kw          = float(inputs.get("load_kw",      100))
    pf_existing = float(inputs.get("pf_existing",  0.75))
    pf_target   = float(inputs.get("pf_target",    0.95))
    voltage_v   = float(inputs.get("voltage_v",    400))
    phases      = int(inputs.get("phases",         3))
    monthly_kwh = float(inputs.get("monthly_kwh",  0))
    meralco_rate = float(inputs.get("meralco_rate", 0))
    investment_php = float(inputs.get("investment_php", 0))

    # Clamp PF values to valid range
    pf_existing = max(0.01, min(0.9999, pf_existing))
    pf_target   = max(pf_existing, min(0.9999, pf_target))

    phi1_rad = math.acos(pf_existing)
    phi2_rad = math.acos(pf_target)
    tan_phi1 = math.tan(phi1_rad)
    tan_phi2 = math.tan(phi2_rad)

    # Required capacitor bank size (IEEE 18 Eq.)
    kvar_required = kw * (tan_phi1 - tan_phi2)
    selected_kvar = next((s for s in STD_KVAR if s >= kvar_required),
                         math.ceil(kvar_required / 50) * 50)

    # kVA before and after
    kva_before = kw / pf_existing
    kva_after  = kw / pf_target
    kva_reduction = kva_before - kva_after

    # Feeder current (A)
    divisor = (math.sqrt(3) * voltage_v) if phases == 3 else voltage_v
    current_before     = (kva_before * 1000) / divisor
    current_after      = (kva_after  * 1000) / divisor
    current_reduction  = current_before - current_after
    current_red_pct    = (current_reduction / current_before) * 100 if current_before > 0 else 0

    # Per-phase capacitor for 3-phase delta bank (C = kVAR / (3 × V²) × 10⁶ μF)
    kvar_per_phase = selected_kvar / 3 if phases == 3 else selected_kvar

    # Meralco PF surcharge (threshold 0.85; ERC Case No. 2009-059 RC)
    meralco_penalty = pf_existing < 0.85
    surcharge_pct   = ((0.85 - pf_existing) / 0.85 * 100) if meralco_penalty else 0.0

    # Optional: monthly savings (Meralco PF surcharge ~18% of distribution charge)
    MERALCO_DIST_FRACTION = 0.18
    monthly_savings_php = 0.0
    if meralco_penalty and monthly_kwh > 0 and meralco_rate > 0:
        dist_per_kwh = meralco_rate * MERALCO_DIST_FRACTION
        monthly_dist = monthly_kwh * dist_per_kwh
        monthly_savings_php = monthly_dist * (surcharge_pct / 100)

    # Simple payback (months)
    payback_months = None
    if monthly_savings_php > 0 and investment_php > 0:
        payback_months = round(investment_php / monthly_savings_php, 1)

    out = {
        "kw":                    kw,
        "pf_existing":           pf_existing,
        "pf_target":             pf_target,
        "phi1_deg":              round(math.degrees(phi1_rad), 2),
        "phi2_deg":              round(math.degrees(phi2_rad), 2),
        "tan_phi1":              round(tan_phi1, 4),
        "tan_phi2":              round(tan_phi2, 4),
        "kvar_required":         round(kvar_required, 2),
        "selected_kvar":         selected_kvar,
        "kvar_per_phase":        round(kvar_per_phase, 2),
        "kva_before":            round(kva_before, 2),
        "kva_after":             round(kva_after,  2),
        "kva_reduction":         round(kva_reduction, 2),
        "current_before":        round(current_before,    2),
        "current_after":         round(current_after,     2),
        "current_reduction":     round(current_reduction, 2),
        "current_reduction_pct": round(current_red_pct,   2),
        "meralco_penalty":       meralco_penalty,
        "surcharge_pct":         round(surcharge_pct, 2),
        "monthly_savings_php":   round(monthly_savings_php, 2) if monthly_savings_php else None,
    }
    if payback_months is not None:
        out["payback_months"] = payback_months
    return out
