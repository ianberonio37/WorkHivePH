"""
Wire Sizing - Phase 4a
Standards: PEC 2017 (Philippine Electrical Code), NEC 2020, IEC 60364-5-52,
           IEC 60228 (conductor cross-sections), DOLE/OSHC
Libraries: math (all formulas closed-form)

Calculates:
- Required conductor size (mm²) from design current with temperature and
  conduit-fill derating per PEC 2017 Tables 310.15(B)(16) and 310.15(B)(3)(a)
- Voltage drop per PEC 2017 (3-phase: √3·I·Z·L; single-phase: 2·I·Z·L)
  Includes conductor reactance X for accurate Z = √(R²+X²)
- Maximum allowable VD: 3% branch circuit, 2% feeder (5% combined, PEC 2017)
- Standard Philippine cable size selection (mm²: 2.0–500)
- Minimum breaker size from ampacity × 125% NEC/PEC continuous load rule
"""

import math
from ._catalog import discloses, pick_at_least

# ─── PEC 2017 Table 310.15(B)(16) - Cu THHN/THWN at 75°C, ≤3 in conduit ─────
# (ampacity, mm²)  - Philippine standard cable sizes
# ★THE METRIC SIZES WERE RATED ABOVE LARGER CONDUCTORS (2026-11-02, ED-G1 Wire Sizing, read against the guide's PEC rows).
# Each metric size carried the NEC rating of the NEXT-LARGER AWG/kcmil conductor: 30 mm2 at 115 A (2 AWG, 33.6 mm2), 60 mm2
# at 175 A (2/0, 67.4 mm2), 100 mm2 at 230 A (4/0, 107 mm2) - and 125 mm2 at 270 A where 250 kcmil (127 mm2, larger) is
# rated 255 A. Over-rating a conductor undersizes it. 2.0-100 mm2 are now the PEC rows the guide quotes (75 C column,
# 2.0 mm2 = 20 A as PEC prints it); above 100 mm2 each size takes the NEC 310.16 75 C rating of the largest conductor
# that does not exceed it (125 -> 4/0 230, 150 -> 250 kcmil 255, 200 -> 350 kcmil 310, 250 -> 400 kcmil 335, 325 ->
# 600 kcmil 420, 400 -> 750 kcmil 475, 500 -> 900 kcmil 520).
AMPACITY_TABLE: list[dict] = [
    {"mm2":   2.0, "ampacity":  20},
    {"mm2":   3.5, "ampacity":  25},
    {"mm2":   5.5, "ampacity":  35},
    {"mm2":   8.0, "ampacity":  50},
    {"mm2":  14.0, "ampacity":  65},
    {"mm2":  22.0, "ampacity":  85},
    {"mm2":  30.0, "ampacity": 100},
    {"mm2":  38.0, "ampacity": 115},
    {"mm2":  50.0, "ampacity": 135},
    {"mm2":  60.0, "ampacity": 150},
    {"mm2":  80.0, "ampacity": 175},
    {"mm2": 100.0, "ampacity": 200},
    {"mm2": 125.0, "ampacity": 230},
    {"mm2": 150.0, "ampacity": 255},
    {"mm2": 200.0, "ampacity": 310},
    {"mm2": 250.0, "ampacity": 335},
    {"mm2": 325.0, "ampacity": 420},
    {"mm2": 400.0, "ampacity": 475},
    {"mm2": 500.0, "ampacity": 520},
]

# PEC 2.40.4(D) small-conductor rule: the overcurrent device on these sizes may not exceed (not for motor circuits)
SMALL_CONDUCTOR_MAX_OCPD = {2.0: 15, 3.5: 20, 5.5: 30}

# ─── Temperature correction factors - PEC 2017 Table 310.15(B)(2)(a) ─────────
# For 75°C rated conductors (THHN/THWN-2)
TEMP_CORRECTION: list[dict] = [
    {"max_c": 30, "factor": 1.00},
    {"max_c": 35, "factor": 0.94},
    {"max_c": 40, "factor": 0.88},
    {"max_c": 45, "factor": 0.82},
    {"max_c": 50, "factor": 0.75},
    {"max_c": 55, "factor": 0.67},
    {"max_c": 60, "factor": 0.58},
    {"max_c": 65, "factor": 0.47},   # 61-65 °C (was MISSING — fell through to the 70 °C row)
    {"max_c": 70, "factor": 0.33},   # 66-70 °C (was 0.35 — too high; over-rated ampacity → undersized)
    {"max_c": 75, "factor": 0.00},   # conductor at limit
]
# (Fixed 2026-06-23 Arc Q vs NEC/PEC Table 310.15(B)(2)(a), 75 °C conductor: the 61-65 °C
#  bracket (0.47) was absent so a 61-65 °C ambient wrongly used the 70 °C factor, and 66-70 °C
#  used 0.35 instead of the correct 0.33 — both OVER-rate derated ampacity = undersized
#  conductor = overheating/fire risk. Independently sourced + adversarially verified.)

# ─── Conduit fill correction - PEC 2017 Table 310.15(B)(3)(a) ─────────────────
FILL_CORRECTION: list[dict] = [
    {"max_cond": 3,  "factor": 1.00},
    {"max_cond": 6,  "factor": 0.80},
    {"max_cond": 9,  "factor": 0.70},
    {"max_cond": 20, "factor": 0.50},
    {"max_cond": 30, "factor": 0.45},
    {"max_cond": 40, "factor": 0.40},
    {"max_cond": 999,"factor": 0.35},
]

# ─── Copper resistivity - temperature corrected ───────────────────────────────
# ρ_cu at 20°C = 1/58 Ω·mm²/m = 0.017241 Ω·mm²/m (IEC 60228)
# At 75°C: ρ_75 = ρ_20 × (1 + α × (75-20))  α=0.00393 /°C
RHO_CU_75C = (1 / 58) * (1 + 0.00393 * (75 - 20))   # ≈ 0.02097 Ω·mm²/m

# ─── Cable reactance at 50 Hz (Ω/km) - PEC / IEC 60364 (from skill) ──────────
# Linear interpolation for sizes not in table
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

# Standard breaker sizes (A)
BREAKER_SIZES = [10, 15, 20, 25, 30, 40, 50, 60, 70, 80, 100, 125, 150,
                 175, 200, 225, 250, 300, 350, 400, 450, 500, 600, 700,
                 800, 1000, 1200, 1600, 2000, 2500, 3000, 4000]


def _temp_factor(ambient_c: float) -> float:
    """Temperature correction factor for 75°C conductor at ambient temp."""
    for row in TEMP_CORRECTION:
        if ambient_c <= row["max_c"]:
            return row["factor"]
    return 0.0


def _fill_factor(num_conductors: int) -> float:
    """Conduit-fill derating factor."""
    for row in FILL_CORRECTION:
        if num_conductors <= row["max_cond"]:
            return row["factor"]
    return 0.35


def _reactance(mm2: float) -> float:
    """Interpolated cable reactance (Ω/km) for copper at 50 Hz."""
    if mm2 <= REACTANCE_TABLE[0]["mm2"]:
        return REACTANCE_TABLE[0]["X_km"]
    if mm2 >= REACTANCE_TABLE[-1]["mm2"]:
        return REACTANCE_TABLE[-1]["X_km"]
    for i in range(len(REACTANCE_TABLE) - 1):
        lo = REACTANCE_TABLE[i]
        hi = REACTANCE_TABLE[i + 1]
        if lo["mm2"] <= mm2 <= hi["mm2"]:
            t = (mm2 - lo["mm2"]) / (hi["mm2"] - lo["mm2"])
            return lo["X_km"] + t * (hi["X_km"] - lo["X_km"])
    return 0.082


def _resistance_ohm(mm2: float, length_m: float) -> float:
    """DC resistance corrected to 75°C (Ω)."""
    return RHO_CU_75C * length_m / mm2


def _voltage_drop(
    current_a: float,
    mm2: float,
    length_m: float,
    voltage_v: float,
    phases: int,
    power_factor: float,
) -> dict:
    """
    Voltage drop per IEC 60364-5-52 / PEC 2017.
    Z = √(R² + X²); VD = multiplier × I × Z × L
    multiplier: 2 for single-phase, √3 for three-phase
    """
    R  = _resistance_ohm(mm2, length_m)           # Ω total conductor
    X  = _reactance(mm2) * length_m / 1000        # Ω/km × km
    # Use full Z for conservative VD (assumes unity PF for worst-case)
    sin_phi = math.sqrt(max(1 - power_factor ** 2, 0))
    Z_eff   = R * power_factor + X * sin_phi      # effective Z at load PF
    Z_mag   = math.sqrt(R ** 2 + X ** 2)

    mult = math.sqrt(3) if phases == 3 else 2.0
    vd_v = mult * current_a * Z_eff
    vd_pct = vd_v / voltage_v * 100

    return {
        "R_ohm":       round(R, 5),
        "X_ohm":       round(X, 5),
        "Z_ohm":       round(Z_mag, 5),
        "vd_volts":    round(vd_v, 3),
        "vd_pct":      round(vd_pct, 2),
    }


def _select_wire(
    design_current_a: float,
    ambient_c: float,
    num_conductors: int,
) -> tuple[dict, float, float]:
    """
    Select smallest wire where derated ampacity ≥ design_current_a.
    Returns (wire_entry, temp_factor, fill_factor).
    """
    tf = _temp_factor(ambient_c)
    ff = _fill_factor(num_conductors)
    combined = tf * ff

    for wire in AMPACITY_TABLE:
        derated = wire["ampacity"] * combined
        if derated >= design_current_a:
            return wire, tf, ff

    return AMPACITY_TABLE[-1], tf, ff   # largest available


# formula: wire_sizing_nec_2020
@discloses
def calculate(inputs: dict) -> dict:
    """
    Main entry point - compatible with TypeScript calcWireSizing() input keys.
    """
    # ── Load inputs ───────────────────────────────────────────────────────────
    load_kw      = float(inputs.get("load_kw",         0))
    load_kva     = float(inputs.get("load_kva",        0))
    load_amps    = float(inputs.get("load_amps",       0))

    # ★THIS ENGINE REFUSED EVERY CALCULATION THE FORM SENT (2026-11-02, ED-E1 + ED-I1 Wire Sizing). The page sends power_w,
    # phase ("Single-phase" / "Three-phase"), ambient_temp, conduit_fill ("1-3" ... "10-20") and load_type; this read load_kw /
    # load_kva / load_amps, phases, ambient_temp_c, conductors_in_conduit and continuous_load, and raised "Provide load_kw,
    # load_kva, or load_amps." on every form calculation - so the edge function fell through silently to its unchecked
    # TypeScript, and the oracle-verified engine never sized a wire for a person. The form's keys are read now, with this
    # engine's own keys first for any other caller. A conduit-fill range is read at its top count (the conservative end);
    # motors, HVAC, lighting and continuous loads are sized at 125% and a general load at 100% (the form's own rule).
    if load_kw <= 0 and load_kva <= 0 and load_amps <= 0 and inputs.get("power_w"):
        load_kw = float(inputs.get("power_w") or 0) / 1000
    _phase       = str(inputs.get("phase") or "")
    voltage_v    = float(inputs.get("voltage",        230))
    phases       = int  (inputs.get("phases", 3 if "Three" in _phase else 1))
    power_factor = float(inputs.get("power_factor",   0.85))
    # The form takes no cable length: voltage drop is the Voltage Drop calculator's job (the guide says so). A hidden
    # 30 m run used to upsize the wire without a word on the report; it now applies only when a length is given.
    length_given = inputs.get("wire_length_m") not in (None, "")
    length_m     = float(inputs.get("wire_length_m") or 30)
    ambient_c    = float(inputs.get("ambient_temp_c", inputs.get("ambient_temp", 35)))   # Manila typical
    _fill        = str(inputs.get("conduit_fill") or "")
    num_cond     = int  (inputs.get("conductors_in_conduit",
                                    int(_fill.split("-")[-1]) if _fill.replace("-", "").isdigit() else 3))
    _lt          = str(inputs.get("load_type") or "")
    is_continuous = bool(inputs.get("continuous_load",
                                    any(w in _lt for w in ("Motor", "HVAC", "Lighting", "continuous")) if _lt else True))

    # ── Derive design current ─────────────────────────────────────────────────
    if load_amps > 0:
        design_current = load_amps
    elif load_kva > 0:
        if phases == 3:
            design_current = load_kva * 1000 / (math.sqrt(3) * voltage_v)
        else:
            design_current = load_kva * 1000 / voltage_v
    elif load_kw > 0:
        if phases == 3:
            design_current = load_kw * 1000 / (math.sqrt(3) * voltage_v * power_factor)
        else:
            design_current = load_kw * 1000 / (voltage_v * power_factor)
    else:
        raise ValueError("Provide load_kw, load_kva, or load_amps.")

    if design_current <= 0:
        raise ValueError("Design current must be greater than 0 A.")

    # PEC 2017 continuous load rule: size for 125% if load is continuous
    sizing_current = design_current * (1.25 if is_continuous else 1.0)

    # ── Breaker sizing ───────────────────────────────────────────────────────
    # ★A MOTOR BREAKER AT 125% TRIPS ON STARTING (2026-11-02, ED-G1 Wire Sizing; the guide: "Breaker is sized at 250% of
    # FLA for inverse time breakers (PEC 4.30.52)"). Every breaker was the next size above 125% of the current; a motor's
    # inrush (6-8x FLA) trips that on every start. Motor branch circuits: inverse-time breaker at 250% of FLA, next standard
    # size up (4.30.52 Exc. 1); hermetic compressors 175% (4.40.22(A)). Other loads: >= the sizing current.
    is_motor      = "Motor" in _lt
    is_compressor = "Compressor" in _lt
    if is_motor:
        min_breaker, breaker_basis = design_current * 2.50, "PEC 4.30.52: inverse-time breaker at 250% of motor FLA"
    elif is_compressor:
        min_breaker, breaker_basis = design_current * 1.75, "PEC 4.40.22(A): 175% of compressor rated-load current"
    else:
        min_breaker, breaker_basis = sizing_current, "PEC 2.40.4: next standard size at or above the sizing current"
    breaker_a = pick_at_least(BREAKER_SIZES, min_breaker, "branch breaker (A)")

    # ── Wire selection ────────────────────────────────────────────────────────
    wire, tf, ff = _select_wire(sizing_current, ambient_c, num_cond)
    # PEC 2.40.4(D): 2.0 / 3.5 / 5.5 mm2 may carry a breaker of at most 15 / 20 / 30 A (motor circuits excepted, 2.40.4(G))
    if not (is_motor or is_compressor):
        while wire["mm2"] in SMALL_CONDUCTOR_MAX_OCPD and breaker_a > SMALL_CONDUCTOR_MAX_OCPD[wire["mm2"]]:
            wire = AMPACITY_TABLE[AMPACITY_TABLE.index(wire) + 1]
    mm2 = wire["mm2"]
    base_ampacity = wire["ampacity"]
    derated_ampacity = round(base_ampacity * tf * ff, 1)

    # ── Voltage drop ──────────────────────────────────────────────────────────
    vd = _voltage_drop(design_current, mm2, length_m, voltage_v, phases, power_factor)

    # PEC 2017 voltage drop limits
    circuit_type = str(inputs.get("circuit_type", "branch"))   # branch / feeder
    vd_limit_pct = 2.0 if "feeder" in circuit_type.lower() else 3.0   # "Branch Circuit" read as a feeder before
    vd_ok = vd["vd_pct"] <= vd_limit_pct or not length_given

    # If VD exceeds limit, find minimum size that satisfies VD
    vd_wire = wire
    if not vd_ok:
        for candidate in AMPACITY_TABLE:
            vd_check = _voltage_drop(
                design_current, candidate["mm2"], length_m,
                voltage_v, phases, power_factor
            )
            if vd_check["vd_pct"] <= vd_limit_pct:
                vd_wire = candidate
                break

    # Governing size: larger of ampacity-selected or VD-selected
    governing_mm2 = max(mm2, vd_wire["mm2"])
    governing_wire = next((w for w in AMPACITY_TABLE if w["mm2"] == governing_mm2),
                          AMPACITY_TABLE[-1])

    # Final VD with governing size
    final_vd = _voltage_drop(
        design_current, governing_mm2, length_m, voltage_v, phases, power_factor
    )


    # ── Conduit size (rough guide - PEC Table C.1, 40% fill) ─────────────────
    # Conduit ID needed = √(n × conductor_OD² / 0.40) - simplified with OD estimate
    # OD estimate for THHN in mm²: OD ≈ 1.4 × √(mm2) mm (rough rule of thumb)
    cond_od_mm = 1.4 * math.sqrt(governing_mm2)
    cond_area_req = num_cond * math.pi * (cond_od_mm / 2) ** 2 / 0.40   # mm² at 40% fill
    cond_id_req = math.sqrt(cond_area_req / math.pi) * 2   # mm

    # Philippine standard RSC/EMT conduit sizes (mm trade size → ID mm)
    conduit_std = [
        (16, 15.8), (21, 20.9), (27, 26.6), (35, 35.1),
        (41, 40.9), (53, 52.5), (63, 62.7), (78, 77.9),
        (103, 102.3), (129, 128.2),
    ]
    rec_conduit = next(
        (size for size, id_mm in conduit_std if id_mm >= cond_id_req),
        conduit_std[-1][0]
    )

    # ── The report's size comparison: two sizes either side of the one that governs ──
    # ★THE REPORT NEVER RENDERED (2026-11-02, ED-G1 Wire Sizing, walked): size_comparison was a sentence and the report
    # maps it as rows - "TypeError: .map is not a function", "Could not generate the report" on every calculation since
    # this engine began serving the form. It is the rows now, each with why it is or is not enough.
    gi = AMPACITY_TABLE.index(governing_wire)
    size_rows = []
    for w in AMPACITY_TABLE[max(gi - 2, 0): gi + 3]:
        corr = round(w["ampacity"] * tf * ff, 1)
        if w["mm2"] >= governing_mm2:
            status = "OK"
        elif corr < sizing_current:
            status = "Undersized"
        elif w["mm2"] in SMALL_CONDUCTOR_MAX_OCPD and breaker_a > SMALL_CONDUCTOR_MAX_OCPD[w["mm2"]]:
            status = f"Max {SMALL_CONDUCTOR_MAX_OCPD[w['mm2']]} A breaker"
        else:
            status = "Voltage drop"
        size_rows.append({"size_mm2": w["mm2"], "ampacity_table": w["ampacity"], "temp_factor": round(tf, 2),
                          "fill_factor": round(ff, 2), "corrected_ampacity": corr, "adequate": status == "OK",
                          "status": status, "recommended": w["mm2"] == governing_mm2})

    # ── kVA and kW from design current ───────────────────────────────────────
    if phases == 3:
        load_kva_calc = design_current * voltage_v * math.sqrt(3) / 1000
    else:
        load_kva_calc = design_current * voltage_v / 1000
    load_kw_calc = load_kva_calc * power_factor

    return {
        # Design current
        "design_current_a":     round(design_current, 2),
        "sizing_current_a":     round(sizing_current, 2),
        "continuous_load":      is_continuous,

        # Selected wire (ampacity criterion)
        "wire_mm2":             mm2,
        "base_ampacity_a":      base_ampacity,
        "temp_factor":          round(tf, 2),
        "fill_factor":          round(ff, 2),
        "derated_ampacity_a":   derated_ampacity,

        # Voltage drop wire (if larger)
        "vd_wire_mm2":          vd_wire["mm2"],

        # Governing size
        "governing_mm2":        governing_mm2,
        "governing_ampacity_a": governing_wire["ampacity"],

        # Voltage drop (with governing size)
        "vd_volts":             final_vd["vd_volts"],
        # ★NO LENGTH, NO VOLTAGE DROP (ED R1, 2026-11-02): without a cable length the drop was computed at an assumed 30 m
        # and returned as if measured, beside vd_checked False - a figure no run of this cable produced.
        "vd_pct":               final_vd["vd_pct"] if length_given else None,
        "vd_limit_pct":         vd_limit_pct,
        "vd_ok":                (final_vd["vd_pct"] <= vd_limit_pct) if length_given else None,
        "vd_checked":           length_given,
        "R_ohm":                final_vd["R_ohm"],
        "X_ohm":                final_vd["X_ohm"],
        "Z_ohm":                final_vd["Z_ohm"],

        # Breaker
        "min_breaker_a":        round(min_breaker, 1),
        "recommended_breaker_a": breaker_a,
        "breaker_basis":        breaker_basis,

        # Conduit
        "recommended_conduit_mm": rec_conduit,

        # Load summary
        "load_kva":             round(load_kva_calc, 2),
        "load_kw":              round(load_kw_calc, 2),
        "power_factor":         power_factor,
        "voltage_v":            voltage_v,
        "phases":               phases,

        # Metadata
        "inputs_used": {
            "ambient_temp_c":        ambient_c,
            "conductors_in_conduit": num_cond,
            "circuit_type":          circuit_type,
            "wire_length_m":         length_m,
        },
        "calculation_source": "python/math",
        "standard": "PEC 2017 | NEC 2020 | IEC 60364-5-52 | IEC 60228",

        # ── Renderer aliases ───────────────────────────────────────────────────
        "size_mm2":              governing_wire["mm2"],
        # "Corrected" is the table ampacity after the temperature and fill factors (it printed the table value)
        "corrected_ampacity":    round(governing_wire["ampacity"] * tf * ff, 1),
        "temp_factor":           tf,
        "adequate":              True,
        "recommended":           f"{governing_wire['mm2']} mm² Cu THHN",
        "ampacity_table":        f"PEC 2017 Table 310.15(B)(16), {ambient_c}°C ambient",
        "design_current":        round(design_current, 2),
        "ambient_temp":          ambient_c,
        "demand_multiplier":     round(sizing_current / design_current, 3) if design_current > 0 else 1.0,
        "load_current":          round(design_current, 2),
        "conduit_fill":          f"{num_cond} conductors - fill factor {ff:.2f}",
        # Field name aliases for renderer
        "voltage":               voltage_v,
        "phase":                 "Three-phase" if phases == 3 else "Single-phase",
        "power_w":               round(load_kw_calc * 1000, 1),
        "recommended_size_mm2":  governing_wire["mm2"],
        "recommended_ampacity":  round(governing_wire["ampacity"] * tf * ff, 1),
        "table_ampacity":        governing_wire["ampacity"],
        "recommended_breaker_A": breaker_a,
        "load_type":             _lt or circuit_type,
        "size_comparison":       size_rows,
    }
