"""
Ventilation / ACH — Mechanical (Option B port from TypeScript)
Standards: ASHRAE 62.1:2022 Ventilation Rate Procedure,
           ASHRAE 90.1:2022 (energy), PSME Code, PEC 2017
Libraries: math

Method: ASHRAE 62.1 Ventilation Rate Procedure
  Vbz = Rp × Pz + Ra × Az
  Required ACH = max(ACH_ASHRAE, minimum_ACH_for_space)
  Design airflow = required_ACH × volume × 1.15 safety margin
"""

# Standard fan sizes (m³/hr) — commercial/industrial range
FAN_SIZES_CMH = [100,150,200,300,400,500,600,750,1000,1200,1500,2000,
                 2500,3000,4000,5000,6000,8000,10000]

# ASHRAE 62.1 Table 6-1: Rp (L/s/person), Ra (L/s/m²), min ACH
VENTILATION_RATES: dict[str, dict] = {
    "Office":           {"rp": 2.5, "ra": 0.30, "min_ach": 6,  "label": "Office - General"},
    "Conference":       {"rp": 2.5, "ra": 0.30, "min_ach": 10, "label": "Conference / Meeting Room"},
    "Server Room":      {"rp": 0.0, "ra": 0.00, "min_ach": 20, "label": "Server Room / Data Center"},
    "Production Floor": {"rp": 2.5, "ra": 0.50, "min_ach": 10, "label": "Production / Manufacturing"},
    "Warehouse":        {"rp": 0.0, "ra": 0.15, "min_ach": 4,  "label": "Warehouse / Storage"},
    "Toilet / CR":      {"rp": 0.0, "ra": 0.00, "min_ach": 10, "label": "Toilet / Comfort Room (exhaust)"},
    "Kitchen":          {"rp": 0.0, "ra": 0.00, "min_ach": 15, "label": "Commercial Kitchen (exhaust)"},
    "Laboratory":       {"rp": 2.5, "ra": 0.50, "min_ach": 10, "label": "Laboratory"},
    "Lobby":            {"rp": 2.5, "ra": 0.30, "min_ach": 4,  "label": "Lobby / Reception"},
    "Hospital Ward":    {"rp": 2.5, "ra": 0.30, "min_ach": 6,  "label": "Hospital Ward"},
}


def _round_up_fan(cmh: float) -> int:
    return next((s for s in FAN_SIZES_CMH if s >= cmh), round(cmh / 500) * 500)


def calculate(inputs: dict) -> dict:
    floor_area     = float(inputs.get("floor_area",     50))
    ceiling_height = float(inputs.get("ceiling_height", 3.0))
    persons        = int(inputs.get("persons",          0))
    room_function  = str(inputs.get("room_function",    "Office"))
    vent_type      = str(inputs.get("vent_type",        "Supply and Exhaust"))

    volume = floor_area * ceiling_height

    rates = VENTILATION_RATES.get(room_function,
            {"rp": 2.5, "ra": 0.30, "min_ach": 6, "label": room_function})

    # Exhaust-only rooms: use minimum ACH method
    use_min_ach = (rates["rp"] == 0 and rates["ra"] == 0)
    if use_min_ach:
        vbz_ls = (rates["min_ach"] * volume) / 3.6
    else:
        vbz_ls = rates["rp"] * persons + rates["ra"] * floor_area

    ach_ashrae   = (vbz_ls * 3.6) / volume if volume > 0 else 0.0
    required_ach = max(ach_ashrae, rates["min_ach"])

    supply_cmh = required_ach * volume
    supply_ls  = supply_cmh / 3.6
    supply_cfm = supply_ls * 2.119

    design_cmh = supply_cmh * 1.15
    design_cfm = supply_cfm * 1.15

    rec_fan_cmh = _round_up_fan(design_cmh)
    rec_fan_cfm = round(rec_fan_cmh / 3.6 * 2.119)

    outdoor_cmh = vbz_ls * 3.6
    outdoor_cfm = vbz_ls * 2.119

    return {
        "room_volume":          round(volume, 1),
        "vbz_ls":               round(vbz_ls, 1),
        "ach_ashrae":           round(ach_ashrae, 2),
        "required_ach":         round(required_ach, 2),
        "min_ach_required":     rates["min_ach"],
        "supply_cmh":           round(supply_cmh),
        "supply_ls":            round(supply_ls, 1),
        "supply_cfm":           round(supply_cfm),
        "design_cmh":           round(design_cmh),
        "design_cfm":           round(design_cfm),
        "recommended_fan_cmh":  rec_fan_cmh,
        "recommended_fan_cfm":  rec_fan_cfm,
        "outdoor_air_cmh":      round(outdoor_cmh),
        "outdoor_air_cfm":      round(outdoor_cfm),
        "inputs_used": {
            "rp": rates["rp"], "ra": rates["ra"],
            "min_ach": rates["min_ach"], "space_label": rates["label"],
            "vent_type": vent_type, "use_min_ach": use_min_ach,
        },
    }
