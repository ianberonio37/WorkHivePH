"""
Clean Agent Suppression — Fire Protection (Phase 5d)
Standards: NFPA 2001:2022 (Clean Agent Fire Extinguishing Systems),
           ISO 14520:2015 (Gaseous Fire-Extinguishing Systems),
           DOLE OSHS Rule 1940 (Philippines), BFP IRR RA 9514
Libraries: math

Method: NFPA 2001 / ISO 14520 Design Concentration Method
  W = (V / S) × [C / (100 - C)]
  where:
    W = mass of agent required (kg)
    V = protected volume (m³) adjusted for altitude
    S = specific vapor volume of agent at design temperature (m³/kg)
    C = design concentration (% by volume)

Agents supported:
  FK-5-1-12   (Novec 1230 / 3M)  — NFPA 2001 Table A.5.3.2
  FM-200      (HFC-227ea)         — NFPA 2001 Table A.5.3.2
  Inergen     (IG-541)            — NFPA 2001 §5.4 (inert gas)
  CO2                             — NFPA 12 method (separate standard)
  Argon       (IG-01)             — ISO 14520-7
"""

import math

# Agent properties — NFPA 2001 Table A.5.3.2 / ISO 14520
# s1, s2: specific vapor volume coefficients S = s1 + s2 × T (°C)  [m³/kg]
# c_min:  minimum design concentration (% by volume) — NFPA 2001 design basis
# c_cup:  cup burner extinction concentration (EBC) per NFPA 2001
AGENTS: dict[str, dict] = {
    "FK-5-1-12": {
        "s1": 0.0664, "s2": 0.0002738,
        "c_min": 4.0,  "c_design": 5.0,   # design = 1.25 × EBC (NFPA 2001 §5.3.1)
        "label": "FK-5-1-12 (Novec 1230)",
        "type": "halocarbon",
        "ozone_depletion": 0.0, "gwp": 1,
    },
    "FM-200": {
        "s1": 0.1269, "s2": 0.0005007,
        "c_min": 6.25, "c_design": 7.0,
        "label": "FM-200 / HFC-227ea",
        "type": "halocarbon",
        "ozone_depletion": 0.0, "gwp": 3220,
    },
    "Inergen": {
        "s1": 0.6598, "s2": 0.0024475,   # IG-541 (52% N2, 40% Ar, 8% CO2)
        "c_min": 35.0, "c_design": 38.0,
        "label": "Inergen (IG-541)",
        "type": "inert_gas",
        "ozone_depletion": 0.0, "gwp": 0,
    },
    "CO2": {
        "s1": 0.5541, "s2": 0.002031,
        "c_min": 30.0, "c_design": 34.0,   # total flooding — Class B/C
        "label": "CO2 (Carbon Dioxide)",
        "type": "inert_gas",
        "ozone_depletion": 0.0, "gwp": 1,
    },
}

# Standard cylinder sizes (kg of agent) — common Philippine market
STD_CYLINDER_KG: dict[str, list[float]] = {
    "FK-5-1-12": [16, 32, 50, 80, 100, 150, 200],
    "FM-200":    [16, 25, 50, 80, 100, 150, 200],
    "Inergen":   [60, 80, 100],   # IG cylinders by pressure × volume
    "CO2":       [25, 45, 68, 100],
}


def _specific_vol(agent_key: str, temp_c: float) -> float:
    a = AGENTS[agent_key]
    return a["s1"] + a["s2"] * temp_c


def _altitude_correction(altitude_m: float) -> float:
    """Altitude correction factor for air density per NFPA 2001 §5.5."""
    # P ≈ P0 × (1 - 2.2558e-5 × h)^5.2559
    return (1.0 - 2.2558e-5 * altitude_m) ** 5.2559


def calculate(inputs: dict) -> dict:
    hazard_vol_m3     = float(inputs.get("hazard_volume_m3",       100))
    agent_key         = str(inputs.get("agent_type",               "FK-5-1-12"))
    design_conc       = float(inputs.get("design_concentration_pct", 0))  # 0 = use default
    temp_c            = float(inputs.get("temperature_c",          20))
    altitude_m        = float(inputs.get("altitude_m",             15))   # Manila ~15m
    safety_factor     = float(inputs.get("safety_factor",          1.10)) # NFPA 2001: 10% min
    num_zones         = max(1, int(inputs.get("num_zones",         1)))
    flooding_factor   = float(inputs.get("flooding_factor",        1.0))  # for uncloseable openings

    if agent_key not in AGENTS:
        agent_key = "FK-5-1-12"

    agent = AGENTS[agent_key]
    c_design = design_conc if design_conc > 0 else agent["c_design"]

    # Altitude-corrected volume
    alt_factor = _altitude_correction(altitude_m)
    V_adj      = hazard_vol_m3 * alt_factor

    # Specific vapor volume at design temperature
    S = _specific_vol(agent_key, temp_c)

    # NFPA 2001 / ISO 14520 agent mass formula
    W_calc = (V_adj / S) * (c_design / (100.0 - c_design))
    W_design = W_calc * safety_factor * flooding_factor

    # Per zone (if multiple zones, use worst-case zone quantity per NFPA 2001 §3.3)
    W_per_zone = W_design  # each zone sized for its own volume

    # Cylinder selection
    std_cyl = STD_CYLINDER_KG.get(agent_key, [50, 100, 150])
    # Use fewest cylinders that covers W_per_zone
    cyl_options: list[dict] = []
    for cyl_kg in std_cyl:
        n = math.ceil(W_per_zone / cyl_kg)
        cyl_options.append({"cylinder_kg": cyl_kg, "qty": n, "total_kg": cyl_kg * n})
    # Recommend smallest total overage
    recommended = min(cyl_options, key=lambda x: x["total_kg"] - W_per_zone)

    # Discharge time check (NFPA 2001 §5.3.4 — ≤ 10 s for halocarbons)
    discharge_time_req = "≤ 10 s" if agent["type"] == "halocarbon" else "≤ 60 s"

    # NOAEL check (No Observed Adverse Effect Level)
    noael: dict[str, float] = {
        "FK-5-1-12": 10.0, "FM-200": 9.0, "Inergen": 43.0, "CO2": 5.0,
    }
    noael_pct = noael.get(agent_key, 10.0)
    safe_for_occupied = c_design <= noael_pct

    return {
        "agent_type":              agent_key,
        "agent_label":             agent["label"],
        "agent_class":             agent["type"],
        "gwp":                     agent["gwp"],
        "hazard_volume_m3":        round(hazard_vol_m3, 2),
        "altitude_m":              altitude_m,
        "altitude_correction":     round(alt_factor, 4),
        "adjusted_volume_m3":      round(V_adj, 2),
        "temperature_c":           temp_c,
        "specific_vol_m3_kg":      round(S, 6),
        "design_concentration_pct": c_design,
        "c_min_pct":               agent["c_min"],
        "W_calculated_kg":         round(W_calc,   2),
        "W_design_kg":             round(W_design, 2),
        "safety_factor":           safety_factor,
        "flooding_factor":         flooding_factor,
        "num_zones":               num_zones,
        "recommended_cylinder_kg": recommended["cylinder_kg"],
        "recommended_qty":         recommended["qty"],
        "total_agent_kg":          recommended["total_kg"],
        "discharge_time_req":      discharge_time_req,
        "noael_pct":               noael_pct,
        "safe_for_occupied_spaces": safe_for_occupied,
        "safety_note":             ("Safe for occupied spaces" if safe_for_occupied
                                    else f"EVACUATE before discharge — concentration {c_design}% > NOAEL {noael_pct}%"),
        "cylinder_options":        cyl_options,
    }
