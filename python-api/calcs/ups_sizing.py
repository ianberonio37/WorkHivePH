"""
UPS Sizing — Phase 4e
Standards: IEEE 1184:2006 (Guide for Batteries for Stationary Applications),
           IEC 62040-3:2021 (UPS performance and test requirements),
           IEEE 446 (Emergency/Standby Power), BICSI 002 (Data Center Design)
Libraries: math (all formulas closed-form)

SKILL FORMULAS (IEEE 1184):
  Ah = (kW_design × t_backup_h) / (V_dc/1000 × DOD × η_UPS × η_wire)
  DOD = 0.80  (VRLA design depth of discharge)
  η_wire = 0.98
  η_UPS = 0.94–0.98 (double-conversion typical 0.94)

  Philippine climate: VRLA life halves every 10°C above 25°C (IEEE 1184)
  Plan replacement at Year 3 for unconditioned rooms (>35°C ambient)

DC bus voltage auto-selection (IEEE 1184 / VRLA standard):
  ≤ 10 kVA  → 96 V  (8 × 12V)
  10–40 kVA → 192 V (16 × 12V)
  40–100 kVA→ 240 V (20 × 12V)
  >100 kVA  → 480 V (40 × 12V)

IEC 62040-3 topology codes:
  VFI-SS-111: Online Double-Conversion (zero transfer time)
  VI-SS-111:  Line Interactive (<4 ms transfer)
  VFD-SS-111: Offline/Standby (<10 ms, non-critical only)
"""

import math

# ─── VRLA battery constants (IEEE 1184) ──────────────────────────────────────
DOD_VRLA      = 0.80    # depth of discharge design limit
ETA_WIRE      = 0.98    # battery cable efficiency
CELL_VOLTAGE  = 12.0    # V per VRLA monobloc cell (standard 12V block)

# ─── DC bus voltage by UPS kVA tier ──────────────────────────────────────────
DC_BUS_TIERS: list[dict] = [
    {"max_kva": 10,   "v_dc": 96,  "cells": 8,  "label": "96V (8×12V)"},
    {"max_kva": 40,   "v_dc": 192, "cells": 16, "label": "192V (16×12V)"},
    {"max_kva": 100,  "v_dc": 240, "cells": 20, "label": "240V (20×12V)"},
    {"max_kva": 9999, "v_dc": 480, "cells": 40, "label": "480V (40×12V)"},
]

# ─── UPS topology (IEC 62040-3) ───────────────────────────────────────────────
UPS_TOPOLOGIES: dict[str, dict] = {
    "Online Double-Conversion": {
        "code":        "VFI-SS-111",
        "eta_ups":     0.94,
        "transfer_ms": 0,
        "suitable":    "Critical loads: servers, medical, telecoms, precision process",
        "note":        "Full galvanic isolation; zero transfer time; highest battery use",
    },
    "Line Interactive": {
        "code":        "VI-SS-111",
        "eta_ups":     0.97,
        "transfer_ms": 4,
        "suitable":    "General office equipment, workstations, network switches",
        "note":        "Good efficiency; <4 ms transfer time; moderate battery use",
    },
    "Offline/Standby": {
        "code":        "VFD-SS-111",
        "eta_ups":     0.98,
        "transfer_ms": 10,
        "suitable":    "Non-critical loads only: desktop PCs, printers",
        "note":        "Highest efficiency on mains; <10 ms transfer; NOT suitable for servers",
    },
}

# ─── Standard UPS kVA sizes (market-available) ───────────────────────────────
STD_UPS_KVA = [
    1, 2, 3, 5, 6, 8, 10, 15, 20, 30, 40, 60, 80, 100,
    120, 160, 200, 250, 300, 400, 500, 600, 800, 1000,
    1200, 1600, 2000, 2500, 3000,
]

# ─── Standard VRLA battery Ah ratings ────────────────────────────────────────
STD_BATT_AH = [7, 9, 12, 17, 24, 26, 38, 40, 55, 65, 75, 100,
               120, 150, 200, 250, 300]

# ─── IEEE 446 — UPS loading limit ────────────────────────────────────────────
UPS_LOAD_LIMIT_PCT = 80   # % rated kVA — thermal headroom + redundancy


def _dc_bus(ups_kva: float) -> dict:
    """Select DC bus voltage tier from UPS kVA rating."""
    for tier in DC_BUS_TIERS:
        if ups_kva <= tier["max_kva"]:
            return tier
    return DC_BUS_TIERS[-1]


def _battery_life_factor(ambient_c: float) -> float:
    """
    VRLA life derating above 25°C (IEEE 1184).
    Life halves every 10°C above 25°C.
    Returns fraction of rated life expected.
    """
    if ambient_c <= 25:
        return 1.0
    return 0.5 ** ((ambient_c - 25) / 10)


def _replacement_year(life_factor: float, rated_life_yr: float = 5.0) -> float:
    """Expected replacement interval at elevated temperature."""
    return rated_life_yr * life_factor


def calculate(inputs: dict) -> dict:
    """
    Main entry point — compatible with TypeScript calcUPSSizing() input keys.
    """
    # ── Load inputs ───────────────────────────────────────────────────────────
    load_kw      = float(inputs.get("load_kw",      0))
    load_kva     = float(inputs.get("load_kva",     0))
    power_factor = float(inputs.get("power_factor", 0.90))   # IT loads typically 0.9–0.95

    if load_kw <= 0 and load_kva > 0:
        load_kw = load_kva * power_factor
    if load_kva <= 0 and load_kw > 0:
        load_kva = load_kw / power_factor
    if load_kw <= 0:
        load_kw  = 10.0
        load_kva = load_kw / power_factor

    # ── UPS parameters ────────────────────────────────────────────────────────
    topology       = str  (inputs.get("topology",          "Online Double-Conversion"))
    backup_mins    = float(inputs.get("backup_minutes",     15.0))
    design_margin  = float(inputs.get("design_margin_pct",  20.0))
    ambient_c      = float(inputs.get("ambient_temp_c",     35.0))
    redundancy     = str  (inputs.get("redundancy",         "N"))   # N, N+1, 2N

    topo_data = UPS_TOPOLOGIES.get(topology, UPS_TOPOLOGIES["Online Double-Conversion"])
    eta_ups   = float(inputs.get("ups_efficiency", topo_data["eta_ups"]))

    # ── Design load ───────────────────────────────────────────────────────────
    # IEEE 446: size for 80% loading limit → UPS kVA = load_kVA / 0.80
    # Then add design margin on top
    design_margin_factor = 1 + design_margin / 100
    ups_kva_min = load_kva * design_margin_factor / (UPS_LOAD_LIMIT_PCT / 100)

    # Redundancy adjustment
    if redundancy == "N+1":
        n_modules     = math.ceil(load_kva / (ups_kva_min * 0.80)) + 1
        module_kva    = next((s for s in STD_UPS_KVA if s >= ups_kva_min / n_modules),
                              STD_UPS_KVA[-1])
        rec_ups_kva   = module_kva * n_modules
        config_note   = f"N+1: {n_modules} × {module_kva} kVA modules"
    elif redundancy == "2N":
        module_kva    = next((s for s in STD_UPS_KVA if s >= ups_kva_min),
                              STD_UPS_KVA[-1])
        rec_ups_kva   = module_kva * 2
        config_note   = f"2N: 2 × {module_kva} kVA modules (full redundancy)"
    else:
        rec_ups_kva   = next((s for s in STD_UPS_KVA if s >= ups_kva_min),
                              STD_UPS_KVA[-1])
        config_note   = f"N: {rec_ups_kva} kVA single UPS"

    # Loading at recommended UPS
    loading_pct = load_kva / rec_ups_kva * 100

    # ── DC bus selection ──────────────────────────────────────────────────────
    bus = _dc_bus(rec_ups_kva)
    v_dc      = bus["v_dc"]
    n_cells   = bus["cells"]

    # ── Battery capacity (IEEE 1184) ──────────────────────────────────────────
    # kW_design = load_kW / η_UPS  (power drawn from battery at full load)
    kw_design  = load_kw / eta_ups
    t_hr       = backup_mins / 60

    # Ah = (kW_design × t_h) / (V_dc/1000 × DOD × η_wire)
    ah_required = (kw_design * t_hr) / (v_dc / 1000 * DOD_VRLA * ETA_WIRE)

    # Select next standard Ah
    rec_ah = next((a for a in STD_BATT_AH if a >= ah_required), STD_BATT_AH[-1])

    # Actual backup time at recommended Ah
    actual_backup_h = (rec_ah * v_dc / 1000 * DOD_VRLA * ETA_WIRE) / kw_design
    actual_backup_min = actual_backup_h * 60

    # Number of battery strings (cells in parallel if Ah > single-string limit)
    # Standard: 1 string for < 200 Ah; parallel strings for higher Ah
    strings = math.ceil(ah_required / max(rec_ah, 1))
    strings = max(strings, 1)

    # Total battery count
    total_cells = n_cells * strings
    total_ah    = rec_ah * strings

    # ── Battery life estimate (IEEE 1184 + Philippine climate) ───────────────
    life_factor      = _battery_life_factor(ambient_c)
    expected_life_yr = _replacement_year(life_factor)
    if ambient_c > 30:
        battery_note = (
            f"Ambient {ambient_c}°C: VRLA life reduced to {round(expected_life_yr,1)} years "
            f"(rated 5 yr at 25°C). Plan replacement every {math.ceil(expected_life_yr)} years. "
            "Consider installing UPS in air-conditioned room for full battery life."
        )
    else:
        battery_note = f"Ambient {ambient_c}°C: VRLA life within rated {round(expected_life_yr,1)} years."

    # ── Input/output current ──────────────────────────────────────────────────
    # Input current (AC mains → UPS)
    input_current_a  = (load_kva * 1000) / (230 * math.sqrt(3))   # assume 3-ph 400V input
    # Output current to load
    output_current_a = (load_kva * 1000) / (230 * math.sqrt(3))   # same topology

    # ── Bypass and input breaker ──────────────────────────────────────────────
    std_breakers = [20, 25, 32, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630]
    min_breaker  = input_current_a * 1.25
    rec_breaker  = next((b for b in std_breakers if b >= min_breaker), std_breakers[-1])

    return {
        # Load
        "load_kW":               round(load_kw, 2),
        "load_kVA":              round(load_kva, 2),
        "power_factor":          power_factor,

        # UPS selection
        "ups_kVA_min":           round(ups_kva_min, 2),
        "recommended_kVA":       rec_ups_kva,
        "loading_pct":           round(loading_pct, 1),
        "loading_ok":            loading_pct <= UPS_LOAD_LIMIT_PCT,
        "topology":              topology,
        "topology_code":         topo_data["code"],
        "topology_transfer_ms":  topo_data["transfer_ms"],
        "topology_suitable_for": topo_data["suitable"],
        "redundancy":            redundancy,
        "config_note":           config_note,
        "ups_efficiency":        eta_ups,

        # Battery
        "dc_bus_voltage_V":      v_dc,
        "dc_bus_config":         bus["label"],
        "battery_cells_per_string": n_cells,
        "battery_strings":       strings,
        "total_battery_cells":   total_cells,
        "required_Ah":           round(ah_required, 1),
        "recommended_Ah":        rec_ah,
        "total_Ah":              total_ah,
        "backup_minutes_target": backup_mins,
        "backup_minutes_actual": round(actual_backup_min, 1),

        # Battery life
        "ambient_temp_c":        ambient_c,
        "battery_life_factor":   round(life_factor, 2),
        "expected_battery_life_yr": round(expected_life_yr, 1),
        "battery_note":          battery_note,

        # IEEE 1184 formula components
        "ieee1184": {
            "kW_design":   round(kw_design, 3),
            "t_hr":        round(t_hr, 4),
            "V_dc":        v_dc,
            "DOD":         DOD_VRLA,
            "eta_UPS":     eta_ups,
            "eta_wire":    ETA_WIRE,
            "Ah_formula":  f"({round(kw_design,3)} × {round(t_hr,4)}) / ({v_dc}/1000 × {DOD_VRLA} × {ETA_WIRE})",
        },

        # Electrical
        "input_current_A":       round(input_current_a, 1),
        "output_current_A":      round(output_current_a, 1),
        "recommended_breaker_A": rec_breaker,

        # Metadata
        "inputs_used": {
            "topology":          topology,
            "backup_minutes":    backup_mins,
            "design_margin_pct": design_margin,
            "redundancy":        redundancy,
            "ambient_temp_c":    ambient_c,
        },
        "calculation_source": "python/math",
        "standard": "IEEE 1184:2006 | IEC 62040-3:2021 | IEEE 446 | BICSI 002",
    }
