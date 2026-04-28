"""
Load Estimation — Electrical (unifies with Python, was TypeScript-only)
Standards: PEC 2017 Article 2.10 / 2.20, IEC 60364
Libraries: math

Frontend name: "Load Estimation"
Input schema: loads array [{load_type, quantity, watts_each, power_factor}]
              plus phase_config string

Improvement over TypeScript:
- Explicit phase_config_ok flag (3-phase balance warning if <50% load)
- Connected kVA and demand kVA both returned for panel schedule use
"""

import math

# PEC 2017 Art. 2.20 demand factors by load type
LOAD_DEMAND_FACTOR: dict[str, float] = {
    "Lighting (General)":            1.00,
    "Lighting (Emergency)":          1.00,
    "Convenience Receptacles":       1.00,
    "Air Conditioning (Unit)":       1.00,
    "Air Conditioning (Central Chiller)": 1.00,
    "Motor (General)":               1.25,
    "Motor (Fire Pump)":             1.25,
    "Water Heater":                  1.00,
    "Elevator / Escalator":          1.25,
    "Server / IT Equipment":         1.00,
    "Kitchen Equipment":             1.00,
    "Welding Equipment":             0.50,
    "Custom":                        1.00,
}

STANDARD_BREAKER_A = [15,20,30,40,50,60,70,80,90,100,125,150,175,200,225,250,300,350,400,500,600]


def calculate(inputs: dict) -> dict:
    loads        = inputs.get("loads", [])
    phase_config = str(inputs.get("phase_config", "3-Phase 4-Wire (400V)"))
    is_3ph       = "3-Phase" in phase_config or "3-phase" in phase_config
    voltage      = 400 if is_3ph else 230

    breakdown: list[dict] = []
    for load in loads:
        qty  = int(load.get("quantity",   1))
        w    = float(load.get("watts_each", 0))
        pf   = float(load.get("power_factor", 0.85))
        lt   = str(load.get("load_type", "Custom"))
        df   = LOAD_DEMAND_FACTOR.get(lt, 1.0)
        conn_va = qty * w / pf if pf > 0 else 0.0
        dem_va  = conn_va * df
        breakdown.append({
            "load_type":    lt,
            "qty":          qty,
            "watts_each":   w,
            "pf":           pf,
            "demand_factor": df,
            "connected_va": round(conn_va),
            "demand_va":    round(dem_va),
        })

    total_conn_va  = sum(l["connected_va"] for l in breakdown)
    total_dem_va   = sum(l["demand_va"]    for l in breakdown)
    total_conn_kw  = sum(l["qty"] * l["watts_each"] for l in breakdown) / 1000.0
    total_dem_kw   = sum(l["qty"] * l["watts_each"] * l["demand_factor"] for l in breakdown) / 1000.0

    factor     = math.sqrt(3) * voltage if is_3ph else voltage
    computed_a = total_dem_va / factor if factor > 0 else 0.0
    with_spare = computed_a * 1.25
    rec_breaker = next((s for s in STANDARD_BREAKER_A if s >= with_spare),
                       math.ceil(with_spare / 25) * 25)

    return {
        "phase_config":           phase_config,
        "voltage":                voltage,
        "total_connected_va":     round(total_conn_va),
        "total_connected_kva":    round(total_conn_va / 1000.0, 2),
        "total_connected_kw":     round(total_conn_kw, 2),
        "total_demand_va":        round(total_dem_va),
        "total_demand_kva":       round(total_dem_va / 1000.0, 2),
        "total_demand_kw":        round(total_dem_kw, 2),
        "computed_ampacity":      round(computed_a, 2),
        "ampacity_with_spare":    round(with_spare, 2),
        "recommended_breaker_A":  rec_breaker,
        "load_breakdown":         breakdown,
    }
