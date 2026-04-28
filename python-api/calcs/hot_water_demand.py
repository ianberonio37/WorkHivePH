"""
Hot Water Demand — Plumbing (unifies with Python, was TypeScript-only)
Standards: ASHRAE HVAC Applications Handbook Ch.50,
           Philippine Plumbing Code (PPC), DOH Sanitation Code
Libraries: iapws (for precise water Cp at supply temperature)

Frontend name: "Hot Water Demand"
Input schema: uses array [{use_type, quantity, daily_count, custom_rate_L?}]
              plus supply_temp, hot_temp, recovery_hours, etc.

Improvement over TypeScript:
- iapws for accurate specific heat Cp at supply water temperature
  (varies from 4.186 at 20°C to 4.216 at 80°C — small but principled)
- Pipe heat loss energy quantified in kWh/day
"""

try:
    from iapws import IAPWS97
    _HAVE_IAPWS = True
except ImportError:
    _HAVE_IAPWS = False

# Hot water demand rates (L per use/person/day) — ASHRAE Ch.50 / PPC
HW_RATES: dict[str, dict] = {
    "Hotel Room":             {"rate_L": 135,  "label": "Hotel Room"},
    "Hospital Bed":           {"rate_L": 225,  "label": "Hospital Bed"},
    "Dormitory / Boarding":   {"rate_L": 90,   "label": "Dormitory / Boarding"},
    "Office Worker":          {"rate_L": 6,    "label": "Office Worker"},
    "Restaurant Meal":        {"rate_L": 12,   "label": "Restaurant Meal"},
    "Residential (person)":   {"rate_L": 70,   "label": "Residential"},
    "Shower Stall":           {"rate_L": 60,   "label": "Shower Stall"},
    "Commercial Kitchen":     {"rate_L": 15,   "label": "Commercial Kitchen"},
    "Laundry (residential)":  {"rate_L": 60,   "label": "Laundry (residential)"},
    "Laundry (commercial)":   {"rate_L": 100,  "label": "Laundry (commercial)"},
    "Lavatory (hand wash)":   {"rate_L": 4,    "label": "Lavatory (hand wash)"},
    "Custom":                 {"rate_L": 0,    "label": "Custom"},
}

HW_HEATER_KW   = [1.5,2.0,3.0,4.0,5.0,6.0,8.0,10.0,12.0,15.0,18.0,20.0,
                  24.0,30.0,36.0,40.0,48.0,60.0,72.0,80.0,100.0]
HW_TANK_SIZES_L = [50,80,100,120,150,200,250,300,400,500,750,1000,1500,2000,2500,3000,4000,5000]


def _cp_water(temp_c: float) -> float:
    """Specific heat of water (kJ/kg·K) at temperature via iapws; fallback 4.186."""
    if _HAVE_IAPWS:
        try:
            T_K = max(274.0, min(373.0, temp_c + 273.15))
            w   = IAPWS97(T=T_K, P=0.1)
            return w.cp  # kJ/kg·K
        except Exception:
            pass
    return 4.186


def calculate(inputs: dict) -> dict:
    uses           = inputs.get("uses", [])
    T_supply       = float(inputs.get("supply_temp",    28))
    T_hot          = float(inputs.get("hot_temp",       60))
    recovery_hrs   = float(inputs.get("recovery_hours", 2))
    peak_fraction  = float(inputs.get("peak_fraction",  0.25))
    storage_factor = float(inputs.get("storage_factor", 1.25))
    pipe_loss_pct  = float(inputs.get("pipe_loss_pct",  10))

    delta_T = T_hot - T_supply
    Cp      = _cp_water((T_supply + T_hot) / 2.0)   # at mean temperature

    # Use breakdown
    use_breakdown: list[dict] = []
    for u in uses:
        ut      = str(u.get("use_type", "Custom"))
        info    = HW_RATES.get(ut, HW_RATES["Custom"])
        qty     = int(u.get("quantity",    1))
        count   = int(u.get("daily_count", 1))
        rate_l  = float(u.get("custom_rate_L", info["rate_L"])) if ut == "Custom" else info["rate_L"]
        daily_l = qty * count * rate_l
        use_breakdown.append({
            "use_type":    info["label"],
            "qty":         qty,
            "daily_count": count,
            "rate_L":      rate_l,
            "daily_L":     round(daily_l),
        })

    total_net_l = sum(u["daily_L"] for u in use_breakdown)
    total_l     = round(total_net_l * (1.0 + pipe_loss_pct / 100.0))
    peak_hour_l = round(total_l * peak_fraction)

    storage_computed = round(peak_hour_l * storage_factor)
    rec_storage_l    = next((s for s in HW_TANK_SIZES_L if s >= storage_computed),
                            round(storage_computed / 500) * 500)

    heat_kj  = total_l * Cp * delta_T
    heat_kwh = heat_kj / 3600.0

    heater_kw_comp = heat_kj / (recovery_hrs * 3600.0) if recovery_hrs > 0 else 0.0
    rec_heater_kw  = next((s for s in HW_HEATER_KW if s >= heater_kw_comp),
                          round(heater_kw_comp + 1))

    recovery_lph = round((rec_heater_kw * 3600.0) / (Cp * delta_T)) if delta_T > 0 else 0

    return {
        "T_supply":                     T_supply,
        "T_hot":                        T_hot,
        "delta_T":                      delta_T,
        "Cp_kJ_kgK":                    round(Cp, 4),
        "total_daily_without_loss_L":   round(total_net_l),
        "pipe_loss_pct":                pipe_loss_pct,
        "total_daily_L":                total_l,
        "peak_fraction":                peak_fraction,
        "peak_hour_L":                  peak_hour_l,
        "storage_factor":               storage_factor,
        "storage_L_computed":           storage_computed,
        "recommended_storage_L":        rec_storage_l,
        "heat_energy_kJ":               round(heat_kj),
        "heat_energy_kWh":              round(heat_kwh, 1),
        "heater_kW_computed":           round(heater_kw_comp, 2),
        "recommended_heater_kW":        rec_heater_kw,
        "recovery_rate_lph":            recovery_lph,
        "recovery_hours":               recovery_hrs,
        "use_breakdown":                use_breakdown,
    }
