"""
Load Schedule — Phase 4c
Standards: PEC 2017 (Philippine Electrical Code), NEC 2020,
           IEEE 141 (Red Book), DOLE/OSHC, PEEP (Philippine Energy Efficiency)
Libraries: math (all formulas closed-form)

SKILL RULE: watts_each IS already real power (W). Do NOT multiply by PF to get kW.
  total_connected_kW = Σ(qty × watts_each) / 1000
  total_demand_kW    = Σ(qty × watts_each × demand_factor) / 1000
  kVA = kW / PF  (PF used only when converting to apparent power)

Calculates:
- Connected load (kW, kVA) per circuit and panel total
- Demand load with demand factors per load type (NEC Article 220)
- Panel feeder kVA, breaker size, cable size
- Power factor and reactive power (kVAR) totals
- Load balance across phases (3-phase panels)
- PEEP demand side management flag (loads > 80% panel capacity)
"""

import math

# ─── Demand factors by load type — NEC Article 220 / PEC 2017 ────────────────
DEMAND_FACTORS: dict[str, float] = {
    "Lighting":          1.00,   # NEC 220.12 — lighting at 100%
    "Receptacle":        0.50,   # NEC 220.14(I) — general purpose receptacles
    "HVAC":              1.00,   # NEC 220.60 — largest HVAC at 100% (cooling)
    "Motor":             1.25,   # NEC 430.24 — largest motor × 125% (added to rest)
    "Motor (other)":     1.00,   # remaining motors at 100%
    "Equipment":         1.00,   # fixed equipment at 100%
    "Server / UPS":      1.00,   # IT loads at 100%
    "Elevator":          1.00,   # PEC 620 — at nameplate current
    "Welding":           0.40,   # NEC 630 — intermittent / diversity
    "Kitchen":           0.65,   # NEC 220.56 — commercial kitchen
    "Spare":             0.00,   # spare circuits — no load assumed
}

# ─── Typical power factors by load type ───────────────────────────────────────
LOAD_PF: dict[str, float] = {
    "Lighting":          0.95,   # LED with PF correction
    "Receptacle":        0.90,
    "HVAC":              0.85,
    "Motor":             0.85,
    "Motor (other)":     0.85,
    "Equipment":         0.90,
    "Server / UPS":      0.95,   # modern UPS with active PF correction
    "Elevator":          0.80,
    "Welding":           0.70,
    "Kitchen":           0.90,
    "Spare":             1.00,
}

# ─── Standard breaker sizes (A) ───────────────────────────────────────────────
BREAKER_SIZES = [15, 20, 25, 30, 40, 50, 60, 70, 80, 100, 125, 150,
                 175, 200, 225, 250, 300, 350, 400, 450, 500, 600,
                 700, 800, 1000, 1200, 1600, 2000, 2500, 3000]

# ─── PEC 2017 panel loading limit ────────────────────────────────────────────
PANEL_LOADING_LIMIT_PCT = 80   # % — demand load must not exceed 80% of panel rating


def _next_breaker(amps: float) -> int:
    return next((b for b in BREAKER_SIZES if b >= amps), BREAKER_SIZES[-1])


def _phase_label(phase_idx: int, phases: int) -> str:
    if phases == 1:
        return "L-N"
    labels = ["A", "B", "C"]
    return labels[phase_idx % 3]


def calculate(inputs: dict) -> dict:
    """
    Main entry point — compatible with TypeScript calcLoadSchedule() input keys.

    inputs["loads"] = list of load items:
      {
        "name":          str,
        "qty":           int,
        "watts_each":    float,   # real power per unit (W) — already watts, not kVA
        "load_type":     str,     # key in DEMAND_FACTORS
        "power_factor":  float,   # optional; defaults to LOAD_PF[load_type]
        "demand_factor": float,   # optional; overrides DEMAND_FACTORS[load_type]
        "voltage":       float,   # optional circuit voltage
        "phases":        int,     # 1 or 3
        "circuit_no":    str,     # optional label
      }
    """
    # ── Panel parameters ──────────────────────────────────────────────────────
    panel_voltage   = float(inputs.get("panel_voltage",  400))   # V LV (3-ph) or 230V (1-ph)
    panel_phases    = int  (inputs.get("panel_phases",     3))
    panel_rating_a  = float(inputs.get("panel_rating_a",  0))    # 0 = auto-select
    feeder_length_m = float(inputs.get("feeder_length_m", 30))

    raw_loads = inputs.get("loads", [])

    # If no loads array provided, try single-load shortcut
    if not raw_loads:
        raw_loads = [{
            "name":        inputs.get("load_name",     "Load"),
            "qty":         int(inputs.get("qty",            1)),
            "watts_each":  float(inputs.get("watts_each",   0)
                             or  inputs.get("load_watts",   0)
                             or  inputs.get("load_kw",      0) * 1000),
            "load_type":   inputs.get("load_type",     "Equipment"),
            "power_factor": float(inputs.get("power_factor", 0)),
            "phases":      int(inputs.get("phases",         1)),
        }]

    # ── Process each load ─────────────────────────────────────────────────────
    schedule_rows = []
    total_connected_kW  = 0.0
    total_demand_kW     = 0.0
    total_demand_kVA    = 0.0
    total_demand_kVAR   = 0.0

    # Phase balance tracking (3-phase panel)
    phase_kW = [0.0, 0.0, 0.0]
    circuit_counter = 1

    largest_motor_kW = 0.0   # NEC 430.24 — track for 125% rule

    for i, load in enumerate(raw_loads):
        name        = str  (load.get("name",        f"Load {i+1}"))
        qty         = int  (load.get("qty",              1))
        watts_each  = float(load.get("watts_each",       0))
        load_type   = str  (load.get("load_type",  "Equipment"))
        pf_override = float(load.get("power_factor",     0))
        df_override = float(load.get("demand_factor",   -1))
        ckt_voltage = float(load.get("voltage",          0)) or panel_voltage
        ckt_phases  = int  (load.get("phases",            1))
        ckt_no      = str  (load.get("circuit_no",        str(circuit_counter)))

        # SKILL RULE: watts_each is already real power — do not multiply by PF
        connected_kW = qty * watts_each / 1000

        # Demand factor
        df = df_override if df_override >= 0 else DEMAND_FACTORS.get(load_type, 1.0)

        # Motor special rule: track largest motor for 125% NEC 430.24
        if load_type == "Motor" and connected_kW > largest_motor_kW:
            largest_motor_kW = connected_kW

        demand_kW = connected_kW * df

        # Power factor
        pf = pf_override if pf_override > 0 else LOAD_PF.get(load_type, 0.90)
        pf = max(min(pf, 1.0), 0.50)   # clamp

        demand_kVA  = demand_kW / pf
        demand_kVAR = math.sqrt(max(demand_kVA ** 2 - demand_kW ** 2, 0))

        # Circuit current
        if ckt_phases == 3:
            current_a = demand_kVA * 1000 / (math.sqrt(3) * ckt_voltage)
        else:
            current_a = demand_kVA * 1000 / ckt_voltage

        # Circuit breaker (NEC 240.4 — 125% for continuous loads)
        breaker_a = _next_breaker(current_a * 1.25)

        # Phase assignment (auto-distribute for 3-ph panel)
        phase_idx   = i % 3
        phase_label = _phase_label(phase_idx, panel_phases)
        if panel_phases == 3:
            phase_kW[phase_idx] += demand_kW

        total_connected_kW += connected_kW
        total_demand_kW    += demand_kW
        total_demand_kVA   += demand_kVA
        total_demand_kVAR  += demand_kVAR

        schedule_rows.append({
            "circuit_no":      ckt_no,
            "name":            name,
            "qty":             qty,
            "watts_each_W":    watts_each,
            "load_type":       load_type,
            "connected_kW":    round(connected_kW, 3),
            "demand_factor":   df,
            "demand_kW":       round(demand_kW, 3),
            "power_factor":    pf,
            "demand_kVA":      round(demand_kVA, 3),
            "demand_kVAR":     round(demand_kVAR, 3),
            "current_A":       round(current_a, 1),
            "breaker_A":       breaker_a,
            "phase":           phase_label,
            "voltage_V":       ckt_voltage,
            "phases":          ckt_phases,
        })
        circuit_counter += 1

    # ── NEC 430.24 — add 25% of largest motor to demand ──────────────────────
    motor_adder_kW = largest_motor_kW * 0.25   # extra 25% of largest motor
    total_demand_kW += motor_adder_kW
    pf_panel = total_demand_kW / max(total_demand_kVA, 0.001)
    total_demand_kVA = total_demand_kW / max(pf_panel, 0.01)

    # ── Panel feeder sizing ───────────────────────────────────────────────────
    if panel_phases == 3:
        feeder_current_a = total_demand_kVA * 1000 / (math.sqrt(3) * panel_voltage)
    else:
        feeder_current_a = total_demand_kVA * 1000 / panel_voltage

    # Feeder breaker (125% continuous)
    feeder_breaker_a = _next_breaker(feeder_current_a * 1.25)

    # Auto panel rating
    if panel_rating_a <= 0:
        panel_rating_a = _next_breaker(feeder_current_a * 1.25)

    # ── Loading check ─────────────────────────────────────────────────────────
    # Panel rated current (A) from panel rating (kVA = √3·V·I or V·I)
    if panel_phases == 3:
        panel_kVA_rated = math.sqrt(3) * panel_voltage * panel_rating_a / 1000
    else:
        panel_kVA_rated = panel_voltage * panel_rating_a / 1000

    loading_pct = total_demand_kVA / max(panel_kVA_rated, 0.001) * 100
    loading_ok  = loading_pct <= PANEL_LOADING_LIMIT_PCT

    # ── Phase imbalance (3-ph panels) ─────────────────────────────────────────
    if panel_phases == 3 and sum(phase_kW) > 0:
        avg_phase = sum(phase_kW) / 3
        max_dev   = max(abs(p - avg_phase) for p in phase_kW)
        imbalance_pct = max_dev / max(avg_phase, 0.001) * 100
        phase_balance_ok = imbalance_pct <= 10.0   # PEC limit: ≤ 10%
    else:
        imbalance_pct   = 0.0
        phase_balance_ok = True

    # ── Reactive power and power factor ───────────────────────────────────────
    panel_pf    = total_demand_kW / max(total_demand_kVA, 0.001)
    kvar_total  = math.sqrt(max(total_demand_kVA ** 2 - total_demand_kW ** 2, 0))

    # PF correction capacitor bank sizing (to raise to 0.95)
    target_pf   = 0.95
    if panel_pf < target_pf and total_demand_kW > 0:
        kvar_required = total_demand_kW * (
            math.tan(math.acos(panel_pf)) - math.tan(math.acos(target_pf))
        )
    else:
        kvar_required = 0.0

    return {
        # Totals
        "total_connected_kW":  round(total_connected_kW, 3),
        "total_demand_kW":     round(total_demand_kW, 3),
        "total_demand_kVA":    round(total_demand_kVA, 3),
        "total_demand_kVAR":   round(kvar_total, 3),
        "panel_power_factor":  round(panel_pf, 3),
        "motor_adder_kW":      round(motor_adder_kW, 3),

        # Feeder
        "feeder_current_A":    round(feeder_current_a, 1),
        "feeder_breaker_A":    feeder_breaker_a,
        "panel_rating_A":      panel_rating_a,

        # Loading
        "panel_kVA_rated":     round(panel_kVA_rated, 2),
        "loading_pct":         round(loading_pct, 1),
        "loading_ok":          loading_ok,
        "loading_limit_pct":   PANEL_LOADING_LIMIT_PCT,

        # Phase balance (3-ph only)
        "phase_A_kW":          round(phase_kW[0], 3),
        "phase_B_kW":          round(phase_kW[1], 3),
        "phase_C_kW":          round(phase_kW[2], 3),
        "phase_imbalance_pct": round(imbalance_pct, 1),
        "phase_balance_ok":    phase_balance_ok,

        # PF correction
        "kvar_correction_required": round(kvar_required, 2),
        "target_pf":           target_pf,

        # Schedule
        "schedule":            schedule_rows,
        "total_circuits":      len(schedule_rows),

        # Metadata
        "inputs_used": {
            "panel_voltage_V":   panel_voltage,
            "panel_phases":      panel_phases,
            "feeder_length_m":   feeder_length_m,
        },
        "calculation_source": "python/math",
        "standard": "PEC 2017 | NEC 2020 Art.220 + 430 | IEEE 141",
    }
