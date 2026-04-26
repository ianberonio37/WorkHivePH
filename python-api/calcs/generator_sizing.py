"""
Generator Sizing - Phase 4d
Standards: ISO 8528-1:2018 (Reciprocating IC engine driven AC generators),
           IEEE 446 (Emergency/Standby Power), PEC 2017, NFPA 110,
           BS 7671 (IEE Wiring Regulations), PSME Code
Libraries: math (all formulas closed-form)

Calculates:
- Steady-state kW and kVA from panel demand load
- Motor starting kVA (largest motor LRA dominates - often the real sizing driver)
- Transient voltage dip check per ISO 8528-1 (typically ≤ 15% for G3 class)
- Step loading sequence (largest motor started first or last)
- Generator set kVA → next standard size
- Fuel consumption (L/hr at 75% and 100% load) and 24-hour tank sizing
- Altitude and temperature derating (ISO 3046-1)
- Total harmonic distortion (THD) flag for sensitive loads
"""

import math

# ─── ISO 8528-1 generator classes ────────────────────────────────────────────
# G1: ±10% V, ±5% Hz - non-critical (lighting, heating)
# G2: ±2.5% V, ±2.5% Hz - general (lifts, pumps, motors)
# G3: ±1% V, ±0.5% Hz - critical (UPS input, telecoms, hospitals)
# G4: specialty - per equipment spec

GEN_CLASSES: dict[str, dict] = {
    "G1": {"vdip_pct": 25, "hz_dev_pct": 5,   "description": "Non-critical (lighting, heating)"},
    "G2": {"vdip_pct": 15, "hz_dev_pct": 2.5, "description": "General (motors, pumps, lifts)"},
    "G3": {"vdip_pct": 10, "hz_dev_pct": 0.5, "description": "Critical (hospital, UPS input, telecoms)"},
    "G4": {"vdip_pct":  5, "hz_dev_pct": 0.25,"description": "Special (precision process control)"},
}

# ─── Typical motor starting current multipliers ───────────────────────────────
# LRA (Locked Rotor Amps) = FLA × start_multiplier
MOTOR_START: dict[str, dict] = {
    "DOL (Direct-on-Line)":        {"multiplier": 6.0, "pf_start": 0.30},
    "Star-Delta":                  {"multiplier": 2.5, "pf_start": 0.35},
    "Soft Starter":                {"multiplier": 3.0, "pf_start": 0.50},
    "VFD (Variable Frequency Drive)": {"multiplier": 1.2, "pf_start": 0.85},
    "Auto-Transformer (65%)":      {"multiplier": 2.5, "pf_start": 0.35},
}

# ─── Standard generator kVA sizes (PH market, diesel gen-set) ────────────────
STD_GEN_KVA = [
    6.25, 8, 10, 12.5, 15, 18.75, 20, 25, 31.25, 37.5, 40, 50,
    62.5, 75, 87.5, 100, 125, 150, 175, 200, 250, 312.5, 375, 400,
    500, 625, 750, 875, 1000, 1250, 1500, 1750, 2000, 2500, 3000,
]

# ─── Diesel fuel consumption (L/hr per kVA) - manufacturer typical ────────────
# Rule of thumb: 0.27–0.30 L/hr per kW at full load (ISO 3046 reference)
FUEL_L_KW_HR = {
    "100%": 0.28,   # L/hr per kW at full load
    "75%":  0.25,   # L/hr per kW at 75% load (optimal efficiency point)
    "50%":  0.24,   # L/hr per kW at 50%
}

# ─── Altitude/temperature derating (ISO 3046-1 / ISO 8528-1) ─────────────────
# For every 100 m above 1000 m elevation: derate 1%
# For every 5°C above 25°C ambient: derate 1%
ALTITUDE_DERATE_PCT_PER_100M = 1.0   # above 1000 m
TEMP_DERATE_PCT_PER_5C       = 1.0   # above 25°C


def _derate_factor(altitude_m: float, ambient_c: float) -> float:
    """ISO 3046-1 derating factor (fraction of rated kVA available)."""
    alt_derate = max(0, (altitude_m - 1000) / 100) * ALTITUDE_DERATE_PCT_PER_100M
    tmp_derate = max(0, (ambient_c - 25) / 5)      * TEMP_DERATE_PCT_PER_5C
    return 1.0 - (alt_derate + tmp_derate) / 100


def _starting_kva(
    motor_kw: float,
    motor_pf: float,
    start_method: str,
    gen_subtrans_reactance_pct: float = 25.0,
) -> tuple[float, float]:
    """
    Starting kVA of largest motor and resulting voltage dip.
    start_kVA = (FLA × start_multiplier × √3 × V) - simplified as:
      start_kVA = motor_kW / (motor_pf × run_eff) × start_mult / pf_start

    Voltage dip = start_kVA / (gen_kVA / (X''d/100))
    ISO 8528-1: voltage dip ≤ class limit during starting.
    Returns (start_kVA, vdip_pct_per_kVA_gen).
    """
    start_data = MOTOR_START.get(start_method, MOTOR_START["DOL (Direct-on-Line)"])
    mult       = start_data["multiplier"]
    pf_start   = start_data["pf_start"]
    run_eff    = 0.90   # motor running efficiency

    # FLA from motor kW
    # FLA (A) = kW / (√3 × V × PF × eff) - but we work in kVA here
    motor_kva_run = motor_kw / (motor_pf * run_eff)
    start_kva     = motor_kva_run * mult / pf_start * pf_start   # simplifies

    # More accurate: start_kVA = motor_kW × mult / (motor_pf × run_eff × pf_start) × pf_start
    start_kva = motor_kw / (motor_pf * run_eff) * mult

    # Voltage dip: ΔV% = Xs × Istart_pu ≈ X''d × (start_kVA / gen_kVA)
    # ΔV_per_unit_gen_kVA = X''d_pct / 100  (kVA dip per kVA of start load on 1 kVA gen)
    vdip_factor = gen_subtrans_reactance_pct / 100   # fractional voltage dip per unit loading

    return round(start_kva, 2), round(vdip_factor, 4)


def calculate(inputs: dict) -> dict:
    """
    Main entry point - compatible with TypeScript calcGeneratorSizing() keys.
    """
    # ── Steady-state load — from loads array or explicit totals ──────────────
    power_factor = float(inputs.get("power_factor") or inputs.get("overall_pf") or 0.85)

    loads_raw    = inputs.get("loads", []) or []
    load_breakdown: list[dict] = []
    if loads_raw:
        total_va = 0.0
        for ld in loads_raw:
            lt    = str(ld.get("load_type") or ld.get("type") or "General Load")
            qty   = int(ld.get("quantity") or ld.get("qty") or 1)
            w_ea  = float(ld.get("watts_each") or ld.get("watts") or 0)
            pf_ld = float(ld.get("power_factor") or ld.get("pf") or 0.85)
            df    = 1.0   # conservative: all loads assumed running simultaneously
            va_ea = (w_ea / pf_ld) if pf_ld > 0 else w_ea
            va_tot = va_ea * qty * df
            total_va += va_tot
            load_breakdown.append({
                "load_type":     lt,
                "qty":           qty,
                "watts_each":    w_ea,
                "pf":            round(pf_ld, 2),
                "demand_factor": df,
                "demand_va":     round(va_tot, 0),
            })
        demand_kva = total_va / 1000
        demand_kw  = demand_kva * power_factor
    else:
        demand_kw  = float(inputs.get("demand_kw",      0)
                       or  inputs.get("total_demand_kW", 0))
        demand_kva = float(inputs.get("demand_kva",     0)
                       or  inputs.get("total_demand_kVA", 0))

    if demand_kw <= 0 and demand_kva > 0:
        demand_kw = demand_kva * power_factor
    if demand_kva <= 0 and demand_kw > 0:
        demand_kva = demand_kw / power_factor
    if demand_kw <= 0:
        demand_kw  = 50.0
        demand_kva = demand_kw / power_factor

    # ── Largest motor ─────────────────────────────────────────────────────────
    motor_hp_in      = float(inputs.get("motor_hp", 0) or inputs.get("largest_motor_hp", 0))
    largest_motor_kw = float(inputs.get("largest_motor_kw", 0) or (motor_hp_in * 0.746))
    motor_pf         = float(inputs.get("motor_pf",         0.85))
    # Accept short keys from frontend ("DOL", "Star-Delta") → full key
    _sm_raw    = str(inputs.get("start_method", "DOL (Direct-on-Line)"))
    _sm_map    = {"DOL": "DOL (Direct-on-Line)", "Star-delta": "Star-Delta",
                  "Soft starter": "Soft Starter", "VFD": "VFD (Variable Frequency Drive)"}
    start_method = _sm_map.get(_sm_raw, _sm_raw) if _sm_raw in _sm_map else _sm_raw
    gen_xd_pct           = float(inputs.get("subtransient_xd_pct", 25.0))   # X''d typical 20-30%

    # ── Site conditions ───────────────────────────────────────────────────────
    altitude_m   = float(inputs.get("altitude_m",     10.0))   # Manila sea level
    ambient_c    = float(inputs.get("ambient_temp_c",  35.0))
    gen_class    = str  (inputs.get("gen_class",       "G2"))
    backup_hrs   = float(inputs.get("fuel_backup_hrs", 24.0))
    load_factor  = float(inputs.get("load_factor_pct", 75.0)) / 100   # normal operating point
    design_margin_pct = float(inputs.get("design_margin_pct", 20.0))   # gen sizing margin

    # ── Derating factor ───────────────────────────────────────────────────────
    derate = _derate_factor(altitude_m, ambient_c)

    # ── Steady-state generator kVA requirement ────────────────────────────────
    # Add design margin; generator must deliver demand_kVA after derating
    required_kva_steady = demand_kva * (1 + design_margin_pct / 100)

    # ── Motor starting kVA (often the dominant sizing criterion) ─────────────
    if largest_motor_kw > 0:
        start_kva, vdip_per_unit = _starting_kva(
            largest_motor_kw, motor_pf, start_method, gen_xd_pct
        )
        # Remaining running load = demand_kVA - motor_kVA_running
        motor_kva_run = largest_motor_kw / (motor_pf * 0.90)
        remaining_kva = max(demand_kva - motor_kva_run, 0)

        # Total kVA during starting = running load + starting kVA of motor
        kva_during_start = remaining_kva + start_kva
    else:
        start_kva         = 0.0
        kva_during_start  = demand_kva
        vdip_per_unit     = gen_xd_pct / 100

    # ── Governing kVA (larger of steady or start) ─────────────────────────────
    required_kva_governing = max(required_kva_steady, kva_during_start)

    # Account for derating: installed_kVA = required / derate
    installed_kva_needed = required_kva_governing / max(derate, 0.50)

    # Select next standard size
    rec_kva = next((s for s in STD_GEN_KVA if s >= installed_kva_needed),
                   STD_GEN_KVA[-1])
    rec_kw  = round(rec_kva * power_factor, 1)   # generator rated kW at 0.8 PF typical
    rec_kw_08 = round(rec_kva * 0.8, 1)          # ISO 8528 rating at 0.8 PF

    # ── Voltage dip during largest motor start ────────────────────────────────
    # ΔV% = X''d × (start_kVA / gen_kVA)
    vdip_pct = vdip_per_unit * (start_kva / max(rec_kva, 1)) * 100
    vdip_limit = GEN_CLASSES.get(gen_class, GEN_CLASSES["G2"])["vdip_pct"]
    vdip_ok   = vdip_pct <= vdip_limit

    # ── Fuel consumption ──────────────────────────────────────────────────────
    gen_kw_output = rec_kva * load_factor * power_factor
    fuel_lhr_75   = gen_kw_output * FUEL_L_KW_HR["75%"]
    fuel_lhr_100  = rec_kva * power_factor * FUEL_L_KW_HR["100%"]

    # Tank for backup_hrs at 75% load (normal run condition)
    tank_litres   = fuel_lhr_75 * backup_hrs
    # Round up to standard tank sizes
    std_tanks = [200, 500, 1000, 2000, 5000, 10000, 20000, 50000]
    rec_tank_l = next((t for t in std_tanks if t >= tank_litres), std_tanks[-1])

    # ── IEEE 446 loading limit check ─────────────────────────────────────────
    # Generator should not be loaded > 80% continuously
    steady_loading_pct = demand_kva / max(rec_kva, 1) * 100
    loading_ok = steady_loading_pct <= 80.0

    # ── Total Harmonic Distortion flag ────────────────────────────────────────
    # VFD loads generate harmonics - flag if > 30% of load is VFD/non-linear
    vfd_kw = float(inputs.get("vfd_kw", 0))
    thd_flag = (vfd_kw / max(demand_kw, 1)) > 0.30
    thd_note = (
        "VFD / non-linear loads exceed 30% of total - specify low THD generator "
        "with detuned harmonic filter or 12-pulse rectifier. "
        "IEEE 519 THD limit: ≤ 5% voltage at PCC."
    ) if thd_flag else "THD within acceptable range for standard generator."

    # ── Step loading sequence recommendation ─────────────────────────────────
    step_note = (
        f"Start largest motor ({largest_motor_kw} kW, {start_method}) "
        f"LAST after remaining {round(remaining_kva,1)} kVA load has stabilised. "
        f"Expected voltage dip: {round(vdip_pct,1)}% vs {vdip_limit}% limit ({gen_class})."
    ) if largest_motor_kw > 0 else (
        "No large motor identified. Load all circuits in sequence; "
        "avoid simultaneous energisation of multiple large loads."
    )

    return {
        # Load basis
        "demand_kW":               round(demand_kw, 2),
        "demand_kVA":              round(demand_kva, 2),
        "power_factor":            power_factor,

        # Generator sizing
        "required_kVA_steady":     round(required_kva_steady, 2),
        "motor_start_kVA":         start_kva,
        "kVA_during_start":        round(kva_during_start, 2),
        "required_kVA_governing":  round(required_kva_governing, 2),
        "installed_kVA_needed":    round(installed_kva_needed, 2),
        "recommended_kVA":         rec_kva,
        "recommended_kW_08pf":     rec_kw_08,

        # Derating
        "altitude_m":              altitude_m,
        "ambient_c":               ambient_c,
        "derate_factor":           round(derate, 3),
        "derate_pct_loss":         round((1 - derate) * 100, 1),

        # Voltage dip
        "vdip_pct":                round(vdip_pct, 2),
        "vdip_limit_pct":          vdip_limit,
        "vdip_ok":                 vdip_ok,
        "gen_class":               gen_class,
        "gen_class_description":   GEN_CLASSES.get(gen_class, {}).get("description", ""),

        # Loading
        "steady_loading_pct":      round(steady_loading_pct, 1),
        "loading_ok":              loading_ok,

        # Fuel
        "fuel_rate_75pct_Lhr":     round(fuel_lhr_75, 1),
        "fuel_rate_100pct_Lhr":    round(fuel_lhr_100, 1),
        "tank_required_L":         round(tank_litres, 0),
        "recommended_tank_L":      rec_tank_l,
        "backup_hours":            backup_hrs,

        # THD
        "thd_flag":                thd_flag,
        "thd_note":                thd_note,

        # Step loading
        "step_loading_note":       step_note,
        "start_method":            start_method,

        # Metadata
        "inputs_used": {
            "gen_class":           gen_class,
            "design_margin_pct":   design_margin_pct,
            "largest_motor_kw":    largest_motor_kw,
            "start_method":        start_method,
            "altitude_m":          altitude_m,
            "ambient_temp_c":      ambient_c,
        },
        "calculation_source": "python/math",
        "standard": "ISO 8528-1:2018 | ISO 3046-1 | IEEE 446 | PEC 2017 | NFPA 110",

        # ── Legacy renderer aliases (frontend renderGeneratorReport) ───────────
        "design_kva":       round(required_kva_governing, 2),
        "controlling_kva":  round(kva_during_start, 2),
        "selected_kva":     rec_kva,
        "selected_kw":      rec_kw_08,
        "running_kw":       round(demand_kw, 2),
        "running_kva":      round(demand_kva, 2),
        "loading_pct":      round(steady_loading_pct, 1),
        "overall_pf":       power_factor,
        "safety_factor":    round(rec_kva / max(required_kva_governing, 1), 3),
        "motor_kw":         largest_motor_kw,
        "motor_hp":         round(largest_motor_kw / 0.746, 1),
        "fuel_100pct_lhr":  round(fuel_lhr_100, 1),
        "fuel_75pct_lhr":   round(fuel_lhr_75, 1),
        "load_breakdown":   load_breakdown if load_breakdown else [{"load_type": "Total demand", "qty": 1, "watts_each": round(demand_kw * 1000, 0), "pf": power_factor, "demand_factor": 1.0, "demand_va": round(demand_kva * 1000, 0)}],
        # Additional aliases
        "starting_kva":      start_kva,
        "start_multiplier":  MOTOR_START.get(start_method, MOTOR_START["DOL (Direct-on-Line)"])["multiplier"],
        "tank_8hr_litres":   round(tank_litres, 0),
        "total_demand_va":   round(demand_kva * 1000, 0),
        "total_demand_kva":  round(demand_kva, 2),
    }
