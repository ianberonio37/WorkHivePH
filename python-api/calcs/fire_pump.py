"""
Fire Pump Sizing — Phase 5b
Standards: NFPA 20:2022 (Installation of Stationary Pumps for Fire Protection),
           NFPA 13:2022 (demand basis), PNS NFPA 20 (Philippine adoption),
           BFP IRR RA 9514
Libraries: math (all formulas closed-form)

NFPA 20 key rules:
- Pump rated flow = system demand + hose stream allowance
- Pump rated pressure ≥ system demand pressure at rated flow
- Pump must deliver 150% of rated flow at ≥ 65% of rated pressure (pump curve)
- At 100% rated flow: pressure ≥ rated pressure
- Shutoff pressure (churn) ≤ 140% of rated pressure (for electric), ≤ 121% (diesel)
- Jockey (pressure maintenance) pump: sized at 1% of main pump flow
- Diesel driver mandatory when pump > 22 kW or when required by AHJ
- Weekly test run required (NFPA 25)
"""

import math

# ─── Standard fire pump flow sizes (L/min) — NFPA 20 Table 4.26 ──────────────
STD_PUMP_LPM = [
    190, 380, 570, 760, 950, 1140, 1325, 1515, 1900, 2840,
    3785, 4730, 5680, 7570, 9460, 11355, 13250,
]

# ─── Standard fire pump kW sizes ─────────────────────────────────────────────
STD_PUMP_KW = [
    1.5, 2.2, 3.0, 4.0, 5.5, 7.5, 11, 15, 18.5, 22, 30, 37, 45, 55,
    75, 90, 110, 132, 160, 200, 250, 315,
]

# ─── NFPA 20 pressure limits ──────────────────────────────────────────────────
CHURN_LIMIT_ELECTRIC_PCT = 140   # % of rated — shutoff must not exceed 140%
CHURN_LIMIT_DIESEL_PCT   = 121   # % of rated — diesel engine driver limit

# ─── Jockey pump sizing (NFPA 20 §A.4.26.5) ───────────────────────────────────
JOCKEY_FLOW_PCT   = 1.0    # % of main pump rated flow
JOCKEY_PRESSURE_ADD_BAR = 0.35   # 5 psi above main pump rated pressure

# ─── Efficiency assumptions ───────────────────────────────────────────────────
PUMP_EFF  = 0.70   # typical fire pump hydraulic efficiency
MOTOR_EFF = 0.92   # electric motor efficiency


def _pump_power_kw(flow_lpm: float, pressure_bar: float) -> float:
    """
    Brake horsepower: P = (Q × ΔP) / (η_pump × η_motor × 60)
    Q in m³/s = L/min / 60000; ΔP in Pa = bar × 100000
    Returns motor input kW.
    """
    Q_m3s  = flow_lpm / 60000
    dp_Pa  = pressure_bar * 100000
    return (Q_m3s * dp_Pa) / (PUMP_EFF * MOTOR_EFF * 1000)


def _pump_curve_points(rated_flow: float, rated_pressure: float) -> list[dict]:
    """
    NFPA 20 pump curve:
    - Churn (0% flow):  pressure ≤ 140% rated (electric)
    - 100% flow:        pressure ≥ 100% rated
    - 150% flow:        pressure ≥ 65% rated
    Approximate with a linear-declining curve through these three points.
    """
    return [
        {"flow_pct": 0,   "flow_lpm": 0,
         "pressure_bar": round(rated_pressure * 1.40, 3),
         "pressure_psi": round(rated_pressure * 1.40 * 14.504, 1),
         "label": "Churn (shutoff)"},
        {"flow_pct": 100, "flow_lpm": round(rated_flow, 0),
         "pressure_bar": round(rated_pressure, 3),
         "pressure_psi": round(rated_pressure * 14.504, 1),
         "label": "Rated point"},
        {"flow_pct": 150, "flow_lpm": round(rated_flow * 1.5, 0),
         "pressure_bar": round(rated_pressure * 0.65, 3),
         "pressure_psi": round(rated_pressure * 0.65 * 14.504, 1),
         "label": "150% overload (NFPA 20 min)"},
    ]


def calculate(inputs: dict) -> dict:
    """
    Main entry point — compatible with TypeScript calcFirePump() keys.
    Accepts system demand from Fire Sprinkler calc or direct input.
    """
    # ── System demand ─────────────────────────────────────────────────────────
    system_flow_lpm  = float(inputs.get("system_flow_lpm",   0)
                         or  inputs.get("q_total_lpm",        0))
    system_press_bar = float(inputs.get("system_pressure_bar", 0)
                         or  inputs.get("p_system_required_bar", 0))

    # Also accept gpm / psi
    if system_flow_lpm <= 0:
        gpm = float(inputs.get("system_flow_gpm", 0))
        if gpm > 0:
            system_flow_lpm = gpm * 3.7854

    if system_press_bar <= 0:
        psi = float(inputs.get("system_pressure_psi", 0))
        if psi > 0:
            system_press_bar = psi / 14.504

    if system_flow_lpm <= 0:
        system_flow_lpm  = 1900.0   # default 500 gpm
    if system_press_bar <= 0:
        system_press_bar = 6.9      # default 100 psi

    driver_type   = str  (inputs.get("driver_type",     "Electric"))   # Electric / Diesel
    redundancy    = str  (inputs.get("redundancy",       "Duplex"))     # Simplex / Duplex
    elevation_m   = float(inputs.get("suction_lift_m",   0.0))         # negative = below pump
    suction_bar   = float(inputs.get("suction_pressure_bar", 0.0))     # positive = pressurised

    design_margin_pct = float(inputs.get("design_margin_pct", 10.0))

    # ── Pump rated point ──────────────────────────────────────────────────────
    # Add design margin; pump rated flow must cover system demand
    rated_flow_lpm  = system_flow_lpm  * (1 + design_margin_pct / 100)
    rated_press_bar = system_press_bar * (1 + design_margin_pct / 100)

    # Select next standard pump size (by flow)
    rec_flow_lpm  = next((s for s in STD_PUMP_LPM if s >= rated_flow_lpm), STD_PUMP_LPM[-1])
    rec_flow_m3hr = round(rec_flow_lpm * 60 / 1000, 1)
    rec_flow_gpm  = round(rec_flow_lpm / 3.7854, 0)

    # ── NFPA 20 pressure limits check ─────────────────────────────────────────
    churn_limit = CHURN_LIMIT_DIESEL_PCT if driver_type == "Diesel" else CHURN_LIMIT_ELECTRIC_PCT
    churn_bar   = rated_press_bar * (churn_limit / 100)
    overload_bar = rated_press_bar * 0.65   # 150% flow point minimum

    # ── Motor / driver sizing ─────────────────────────────────────────────────
    motor_kw_calc = _pump_power_kw(rec_flow_lpm, rated_press_bar)
    # NFPA 20 §9.5.2: motor must be non-overloading at 150% flow and rated pressure
    motor_kw_overload = _pump_power_kw(rec_flow_lpm * 1.5, rated_press_bar * 0.65)
    motor_kw_design   = max(motor_kw_calc, motor_kw_overload) * 1.15   # 15% service factor
    rec_motor_kw      = next((s for s in STD_PUMP_KW if s >= motor_kw_design), STD_PUMP_KW[-1])

    # NFPA 20: diesel driver mandatory if motor > 22 kW or AHJ requires
    diesel_required = (rec_motor_kw > 22) or (driver_type == "Diesel")

    # ── Jockey pump ───────────────────────────────────────────────────────────
    jockey_flow_lpm  = rec_flow_lpm * JOCKEY_FLOW_PCT / 100
    jockey_press_bar = rated_press_bar + JOCKEY_PRESSURE_ADD_BAR
    jockey_kw_calc   = _pump_power_kw(jockey_flow_lpm, jockey_press_bar)
    jockey_kw_design  = jockey_kw_calc * 1.25
    rec_jockey_kw     = next((s for s in STD_PUMP_KW if s >= jockey_kw_design), STD_PUMP_KW[-1])

    # ── Pump curve (NFPA 20 three-point) ─────────────────────────────────────
    pump_curve = _pump_curve_points(rec_flow_lpm, rated_press_bar)

    # ── Net Positive Suction Head (NPSH) check ────────────────────────────────
    # NPSHa = (suction_pressure + atm - vapor_pressure) / (rho × g) - elevation_loss
    # Simplified: NPSHa = 10.33 + suction_bar/0.0981 - elevation_m - 0.24 (water vapor at 25°C)
    atm_head_m   = 10.33   # m (1 atm = 10.33 m water)
    vapor_head_m = 0.33    # m (vapor pressure water at 30°C ≈ 0.0325 bar)
    npsha_m      = atm_head_m + (suction_bar / 0.0981) - elevation_m - vapor_head_m
    # Typical fire pump NPSHr ≈ 3-6 m
    npshr_m      = 5.0
    npsh_ok      = npsha_m >= npshr_m

    # ── Redundancy configuration ──────────────────────────────────────────────
    if redundancy == "Duplex":
        config_note = (
            f"Duplex arrangement: 2 × {rec_flow_lpm} L/min pumps "
            f"({rec_motor_kw} kW each) — one duty, one standby. "
            "Lead/standby alternation per NFPA 20 §10.5."
        )
        n_main_pumps = 2
    else:
        config_note = (
            f"Simplex: 1 × {rec_flow_lpm} L/min pump ({rec_motor_kw} kW). "
            "Add diesel backup per NFPA 20 §4.27 for critical occupancies."
        )
        n_main_pumps = 1

    # ── NFPA 25 test requirements ─────────────────────────────────────────────
    test_notes = [
        "Weekly: run pump at churn (no flow) for ≥ 10 minutes (NFPA 25 §8.3.1).",
        "Annually: full flow test — measure flow, discharge pressure, and motor current.",
        "Jockey pump: verify start/stop pressure settings every 3 months.",
        f"Churn pressure must not exceed {churn_limit}% of rated ({round(churn_bar,2)} bar / "
        f"{round(churn_bar*14.504,1)} psi) per NFPA 20.",
        "BFP acceptance test required before occupancy (IRR RA 9514 Rule 10).",
    ]

    return {
        # System demand basis
        "system_flow_lpm":         round(system_flow_lpm, 1),
        "system_pressure_bar":     round(system_press_bar, 3),
        "system_pressure_psi":     round(system_press_bar * 14.504, 1),

        # Main pump
        "rated_flow_lpm":          round(rated_flow_lpm, 1),
        "recommended_flow_lpm":    rec_flow_lpm,
        "recommended_flow_m3hr":   rec_flow_m3hr,
        "recommended_flow_gpm":    rec_flow_gpm,
        "rated_pressure_bar":      round(rated_press_bar, 3),
        "rated_pressure_psi":      round(rated_press_bar * 14.504, 1),

        # Motor / driver
        "motor_kw_calculated":     round(motor_kw_calc, 2),
        "motor_kw_design":         round(motor_kw_design, 2),
        "recommended_motor_kW":    rec_motor_kw,
        "driver_type":             driver_type,
        "diesel_driver_required":  diesel_required,

        # NFPA 20 compliance (pump curve)
        "churn_pressure_bar":      round(churn_bar, 3),
        "churn_pressure_psi":      round(churn_bar * 14.504, 1),
        "churn_limit_pct":         churn_limit,
        "overload_150pct_press_bar": round(overload_bar, 3),
        "pump_curve":              pump_curve,

        # NPSH
        "npsha_m":                 round(npsha_m, 2),
        "npshr_m":                 npshr_m,
        "npsh_ok":                 npsh_ok,

        # Jockey pump
        "jockey_flow_lpm":         round(jockey_flow_lpm, 1),
        "jockey_pressure_bar":     round(jockey_press_bar, 3),
        "jockey_motor_kW":         rec_jockey_kw,

        # Configuration
        "redundancy":              redundancy,
        "n_main_pumps":            n_main_pumps,
        "config_note":             config_note,

        # Test requirements
        "test_notes":              test_notes,

        # Metadata
        "inputs_used": {
            "driver_type":         driver_type,
            "redundancy":          redundancy,
            "design_margin_pct":   design_margin_pct,
            "suction_lift_m":      elevation_m,
        },
        "calculation_source": "python/math",
        "standard": "NFPA 20:2022 | NFPA 13:2022 | NFPA 25 | BFP IRR RA 9514",

        # ── Legacy renderer aliases (frontend renderFirePumpReport) ────────────
        "Q_Lmin":          rec_flow_lpm,
        "Q_jockey_Lmin":   round(jockey_flow_lpm, 1),
        "P_req_bar":       round(rated_press_bar, 3),
        "P_req_m":         round(rated_press_bar / 0.0981, 1),
        "TDH_bar":         round(rated_press_bar, 3),
        "TDH_m":           round(rated_press_bar / 0.0981, 1),
        "P_motor_kW":      round(motor_kw_design, 2),
        "P_nfpa_kW":       rec_motor_kw,
        "P_shaft_kW":      round(motor_kw_calc, 2),
        "P_motor_HP":      round(motor_kw_design / 0.746, 1),
        "P_nfpa_HP":       round(rec_motor_kw / 0.746, 1),
        "P_shaft_HP":      round(motor_kw_calc / 0.746, 1),
        "P_jockey_bar":    round(jockey_pressure_bar, 3),
        "P_overload":      round(overload_bar, 3),
        "Q_overload":      round(rec_flow_lpm * 1.5, 0),
        "H_friction_m":    round(rated_press_bar / 0.0981 * 0.3, 1),  # approx friction = 30% TDH
        "drive_type":      driver_type,
        "selected_kW":     rec_motor_kw,
        "selected_HP":     round(rec_motor_kw / 0.746, 1),
        "selected_jockey_HP": round(rec_jockey_kw / 0.746, 1),
        "pump_eff_pct":    round(PUMP_EFF * 100, 0),
        "motor_eff_pct":   round(MOTOR_EFF * 100, 0),
        "suction_type":    "Flooded" if elevation_m <= 0 else "Suction lift",
        "suction_head_m":  round(-elevation_m, 2),
        "elev_m":          elevation_m,
        "pipe_material":   "Carbon Steel (ASTM A53)",
        "velocity":        round(rec_flow_lpm / 60000 / (math.pi * (0.1)**2 / 4), 1),
        "nfpa_factor":     round(churn_bar / rated_press_bar * 100, 0),
        "pipe_dia":        "100 mm",
    }
