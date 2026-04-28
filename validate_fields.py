"""
Layer 1 — Unit Test: Python API field validation.

Calls the live Python API for every handled calc type, captures all returned keys,
and saves them to results_keys.json for use by the other validation layers.

Run this first after any Python handler change.
Usage:  python validate_fields.py
Output: results_keys.json
"""
import urllib.request, json, re, time, sys

BASE = "https://engineering-calc-api.onrender.com/calculate"

# ── Test inputs for every Python-handled calc type ────────────────────────────
# Field names must match what the Python handler (or its alias in main.py) accepts.
# These are the FRONTEND field names — main.py aliases map them to Python internals.
TESTS = {
    # ── Fluid Mechanics ───────────────────────────────────────────────────────
    "Pump Sizing (TDH)": {
        "flow_rate": 10, "static_head": 20, "pipe_material": "uPVC",
        "pipe_diameter_mm": 50, "pipe_length_m": 100,
    },
    "Pipe Sizing": {
        "flow_rate": 10, "pipe_material": "uPVC", "fluid": "Water",
        "velocity_limit": 3,
    },
    "Compressed Air": {
        "tools": [{"name": "Air Gun", "cfm": 10, "qty": 3}],
        "working_pressure_psi": 100, "pipe_length_ft": 200,
        "pipe_material": "Steel", "pipe_diameter_in": 1.0,
    },

    # ── Mechanical ────────────────────────────────────────────────────────────
    "Ventilation / ACH": {
        "floor_area": 100, "ceiling_height": 3, "persons": 20,
        "room_function": "Office", "vent_type": "Supply and Exhaust",
    },

    # ── HVAC ──────────────────────────────────────────────────────────────────
    "HVAC Cooling Load": {
        "floor_area": 100, "ceiling_height": 3, "persons": 10,
        "equipment_kw": 2, "outdoor_temp": 35, "indoor_temp": 24,
    },
    "AHU Sizing": {
        "cooling_load_kW": 50, "space_type": "Office",
        "shr": 0.75, "safety_factor": 1.10,
        "room_temp_C": 24, "supply_temp_C": 14,
        "oa_pct": 20, "fan_static_Pa": 400,
        "chw_supply_C": 7,
    },
    "Cooling Tower Sizing": {
        "heat_rejection_kW": 200, "approach_C": 4, "range_C": 6,
        "wb_C": 27, "flow_source": "direct",
    },
    # NOTE: Python duct handler uses "sections" (not "segments" like the frontend).
    # Multi-segment duct sizing silently falls back to TypeScript via edge function.
    # This single-section test validates the Python handler directly.
    "Duct Sizing (Equal Friction)": {
        "flow_m3hr": 3600, "duct_length_m": 10,
        "friction_rate_pam": 1.0, "section_type": "Supply Main",
    },
    "Refrigerant Pipe Sizing": {
        "capacity_kw": 10, "refrigerant": "R-410A", "application": "AC",
        "lines": [
            {"name": "Suction", "line_type": "Suction", "length_m": 15, "rise_m": 3},
            {"name": "Discharge", "line_type": "Discharge", "length_m": 12, "rise_m": 0},
            {"name": "Liquid", "line_type": "Liquid", "length_m": 15, "rise_m": 3},
        ],
    },
    "FCU Selection": {
        "pipe_system": "2-Pipe (Cooling Only)", "mounting_type": "Ceiling Cassette",
        "chw_supply_c": 7, "chw_return_c": 12, "diversity_factor": 0.9,
        "rooms": [
            {"room_name": "Office 1", "area_m2": 50, "cooling_load_kw": 5, "qty": 1},
        ],
    },
    "Chiller System — Water Cooled": {
        "cooling_load_kW": 500, "chiller_type": "Centrifugal",
        "chw_supply_C": 7, "chw_return_C": 12,
        "cw_supply_C": 29, "cw_return_C": 35,
        "cop": 5.5, "safety_factor": 1.10, "n_units": 2,
    },
    "Chiller System — Air Cooled": {
        "cooling_load_kW": 200, "ambient_temp_C": 35,
        "chw_supply_C": 7, "chw_return_C": 12,
        "cop": 3.0, "safety_factor": 1.15, "n_units": 1,
    },
    "Expansion Tank Sizing": {
        "system_type": "Chilled Water", "volume_method": "Direct Entry",
        "system_volume_L": 500, "fill_temp_c": 20, "max_temp_c": 7,
        "static_head_m": 15, "max_pressure_kpa_g": 400,
    },

    # ── Electrical ────────────────────────────────────────────────────────────
    "Load Estimation": {
        "phase_config": "3-Phase 4-Wire (400V)",
        "loads": [
            {"load_type": "Lighting (General)",    "quantity": 10, "watts_each": 40,   "power_factor": 0.9},
            {"load_type": "Air Conditioning (Unit)","quantity":  2, "watts_each": 1500, "power_factor": 0.85},
        ],
    },
    "Voltage Drop": {
        "circuit_type": "Branch Circuit", "phase": "Single-phase",
        "voltage": 230, "current": 20, "wire_length": 50,
        "conductor_mm2": 5.5, "conductor_mat": "Copper", "vd_limit": 3,
    },
    "Power Factor Correction": {
        "load_kw": 100, "pf_existing": 0.75, "pf_target": 0.95,
        "voltage_v": 400, "phases": 3,
        "monthly_kwh": 15000, "meralco_rate": 12.0,
    },
    "Cable Tray Sizing": {
        "tray_type": "Ladder", "depth_mm": 75, "fill_ratio_pct": 40,
        "span_m": 1.5, "run_length_m": 30,
        "cables": [
            {"cable_type": "Power", "od_mm": 25, "qty": 3, "weight_kg_m": 0.8},
            {"cable_type": "Control", "od_mm": 12, "qty": 6, "weight_kg_m": 0.2},
        ],
    },
    "Wire Sizing": {
        "load_kw": 10, "voltage": 230, "power_factor": 0.85,
        "wire_length_m": 30, "phases": 1,
    },
    "Short Circuit Analysis": {
        "xfmr_kva": 500, "xfmr_impedance_pct": 5.0,
        "primary_voltage": 13800, "secondary_voltage": 400,
        "cable_length_m": 10, "cable_size_mm2": 50,
    },
    "Short Circuit": {
        "xfmr_kva": 500, "xfmr_impedance_pct": 5.0,
        "primary_voltage": 13800, "secondary_voltage": 400,
        "cable_length_m": 10, "cable_size_mm2": 50,
    },
    "Load Schedule": {
        "loads": [
            {"name": "AC Unit", "qty": 2, "watts_each": 2000,
             "power_factor": 0.85, "load_type": "HVAC"},
            {"name": "Lighting", "qty": 10, "watts_each": 36,
             "power_factor": 0.95, "load_type": "Lighting"},
        ],
        "voltage": 230, "phases": 1,
    },
    "Generator Sizing": {
        "loads": [
            {"name": "HVAC",     "kw": 50,  "pf": 0.85, "qty": 1,
             "load_type": "HVAC", "starting_method": "VFD"},
            {"name": "Lighting", "kw": 10,  "pf": 0.90, "qty": 1,
             "load_type": "Lighting", "starting_method": "Direct"},
        ],
        "voltage": 400, "frequency": 60,
    },
    "UPS Sizing": {
        "loads": [
            {"name": "Server", "kva": 5, "pf": 0.9, "qty": 2},
        ],
        "backup_minutes": 30, "topology": "Online Double Conversion",
        "battery_voltage": 192,
    },
    "Solar PV System": {
        "daily_energy_kwh": 20, "peak_sun_hours": 4.5,
        "panel_wp": 400, "system_voltage": 48,
        "system_type": "Grid-tied", "location": "Metro Manila",
        "tilt_deg": 15, "azimuth_deg": 180,
    },

    # ── Fire Protection ───────────────────────────────────────────────────────
    "Fire Sprinkler Hydraulic": {
        "occupancy": "Office", "design_area_m2": 139,
        "sprinkler_spacing_m": 3.6, "pipe_material": "Black Steel Schedule 40",
        "pipe_length": 30, "k_factor": 80,
    },
    "Fire Pump Sizing": {
        "required_flow": 1900, "required_pressure": 6.9,
        "drive_type": "Electric Motor", "redundancy": "Duplex",
        "hose_demand_lpm": 375,
    },
    "Stairwell Pressurization": {
        "building_type": "Sprinklered", "n_stairwells": 2, "n_floors": 10,
        "doors_per_floor": 1, "door_fit": "Average",
        "door_width": 0.9, "door_height": 2.1,
        "fan_static_pressure": 400, "fan_efficiency": 60,
    },
    "Fire Alarm Battery": {
        "system_voltage": 24, "standby_hours": 24, "alarm_minutes": 5,
        "panel_standby_mA": 50, "panel_alarm_mA": 200,
        "n_addr_smoke": 20, "n_conv_smoke": 0, "n_heat": 5,
        "n_pull": 4, "n_horn_strobe": 8, "n_strobe": 0, "n_bell": 0,
    },

    # ── Plumbing ──────────────────────────────────────────────────────────────
    "Hot Water Demand": {
        "supply_temp": 28, "hot_temp": 60, "recovery_hours": 2,
        "peak_fraction": 0.25, "storage_factor": 1.25, "pipe_loss_pct": 10,
        "uses": [
            {"use_type": "Hotel Room", "quantity": 20, "daily_count": 1},
        ],
    },
    "Drainage Pipe Sizing": {
        "pipe_material": "PVC", "system_type": "Horizontal Branch", "slope": "2%",
        "fixtures": [
            {"fixture_type": "Water Closet",         "quantity": 4},
            {"fixture_type": "Lavatory / Hand Sink",  "quantity": 6},
        ],
    },
    "Water Supply Pipe Sizing": {
        "pipe_material": "PVC", "pipe_length": 40,
        "supply_pressure": 350, "min_pressure": 70, "fittings_allowance": 20,
        "fixtures": [
            {"fixture_type": "Water Closet (Flush Tank)", "quantity": 6},
            {"fixture_type": "Lavatory / Hand Sink",      "quantity": 8},
            {"fixture_type": "Kitchen Sink (commercial)", "quantity": 2},
        ],
    },
    "Septic Tank Sizing": {
        "occupancy_type": "Office / Commercial", "occupants": 50,
        "desludge_years": 3, "liquid_depth": 1.5, "lw_ratio": 3, "compartments": 2,
    },
    "Grease Trap Sizing": {
        "suf": 0.75, "meals_per_day": 200,
        "fixtures": [
            {"fixture_type": "Commercial Kitchen Sink", "flow_lpm": 12, "qty": 3},
            {"fixture_type": "Dishwasher",              "flow_lpm": 20, "qty": 2},
        ],
    },
    "Roof Drain Sizing": {
        "roof_area": 500, "n_drains": 2, "intensity_mmhr": 100,
        "leader_slope_pct": 1.0, "has_parapet": "Yes", "pipe_material": "uPVC",
    },
    "Storm Drain / Stormwater": {
        "area_mode": "single", "area_ha": 1.5, "c_value": 0.85,
        "intensity_mmhr": 95, "slope_pct": 0.5, "pipe_material": "Concrete",
        "return_period": 10,
    },
    "Water Softener Sizing": {
        "demand_lpd": 10000, "inlet_hardness": 250, "target_hardness": 50,
        "regen_interval": 3, "salt_dose_gL": 80, "n_units": 1,
    },
    "Water Treatment System": {
        "demand_lpd": 5000, "raw_source": "Deep Well / Bore",
        "turbidity_ntu": 8, "iron_mg": 0.5,
        "bacteria_concern": "yes", "intended_use": "Potable", "peak_factor": 1.5,
    },
    "Domestic Water System": {
        "occupancy_type": "Office", "num_persons": 50,
        "building_floors": 5, "pipe_material": "uPVC",
    },
    "Sewer / Drainage": {
        "building_floors": 5, "pipe_material": "uPVC / CPVC",
        "num_persons": 50, "slope_pct": 2.0,
    },
    "Wastewater Treatment (STP)": {
        "flow_source": "population", "population": 200, "per_capita_lpd": 150,
        "bod_influent": 220, "bod_effluent": 30,
        "srt_days": 8, "mlss_mg_l": 3000, "disinfection": "Chlorination",
    },

    # ── Structural / Lighting / LPS ───────────────────────────────────────────
    "Beam / Column Design": {
        "member_type": "Steel Beam", "span_m": 6,
        "Mu_kNm": 180, "Vu_kN": 90, "w_kNm": 30,
        "section": "W310x45",
    },
    "Lighting Design": {
        "room_len_m": 10, "room_wid_m": 8, "ceiling_ht_m": 3,
        "lumens_per_fix": 3200, "watts_per_fix": 36,
        "fixture_type": "LED Panel 600x600",
        "llf": 0.80, "space_type": "Office — general",
    },
    "Lightning Protection System (LPS)": {
        "building_length_m": 30, "building_width_m": 20,
        "building_height_m": 15, "lpl": "LPL II",
        "structure_type": "General",
        "location_type": "Suburban (Ng = 2.0 /km²/yr)",
    },
    "Earthing / Grounding System": {
        "electrode_type": "Rod", "soil_resistivity": 100,
        "num_electrodes": 2, "system_type": "Industrial",
        "rod_length_m": 3.0, "rod_dia_mm": 16, "service_cond_mm2": 35,
    },

    # ── Machine Design ────────────────────────────────────────────────────────
    "Shaft Design": {
        "power_kW": 7.5, "speed_rpm": 1450, "shaft_rpm": 1450,
        "transverse_load_N": 2000, "span_m": 0.3, "span_mm": 300,
        "material": "AISI 1045 (HR)", "keyway": "No",
        "shock_type": "Minor shock",
    },
    "V-Belt Drive Design": {
        "drive_type": "V-Belt",
        "power_kW": 7.5, "service_factor": 1.2,
        "driver_rpm": 1450, "driven_rpm": 720,
        "belt_section": "B", "driver_dia_mm": 125,
        "center_dist_mm": 500,
    },
    "Gear / Belt Drive": {
        "drive_type": "Spur Gear",
        "power_kW": 10, "n_driver_rpm": 1450, "n_driven_rpm": 725,
        "module_mm": 3, "N_pinion": 20, "N_gear": 40,
        "face_width_mm": 40, "service_factor": 1.25,
    },
    "Pressure Vessel": {
        "design_pressure_bar": 10, "inner_diameter_mm": 800,
        "shell_length_mm": 2000,
        "material": "SA-516 Gr.70 (Carbon Steel)",
    },
    "Heat Exchanger": {
        "duty_kW": 500, "hot_inlet_C": 90, "hot_outlet_C": 60,
        "cold_inlet_C": 25, "cold_outlet_C": 55,
        "hot_flowrate_kgs": 10, "cold_flowrate_kgs": 8,
    },

    # ── Phase 9 ───────────────────────────────────────────────────────────────
    "Vibration Analysis": {
        "mass_kg": 500, "speed_rpm": 1450, "power_kW": 15,
        "machine_class": "Class II (15-300 kW, rigid foundation)",
        "stiffness_N_m": 200000,
    },
    "Fluid Power": {
        "system_pressure_bar": 200, "flow_lpm": 40,
        "cylinder_force_kN": 50, "stroke_mm": 200,
        "bore_mm": 0, "rod_mm": 0,
        "pump_displacement_cc_rev": 0.5, "pump_rpm": 1380,
        "pump_vol_eff": 0.92, "pump_mech_eff": 0.92, "motor_eff": 0.92,
    },
    "Noise / Acoustics": {
        "calc_type": "Room",
        "source_Lw_dB": 90, "distance_m": 5,
        "directivity_Q": 2, "space_type": "Open-plan office",
        "avg_absorption_coeff": 0.15, "room_surface_m2": 200,
        "exposures": [{"level_dBA": 90, "duration_hr": 8}],
    },
    "Boiler / Steam System": {
        "steam_pressure_bar": 10, "feedwater_temp_C": 80,
        "steam_flowrate_kgs": 1.0, "fuel_type": "Natural gas (LNG)",
    },
    "Boiler System": {
        "boiler_type": "Steam", "steam_pressure_barg": 7, "fw_temp_c": 80,
        "fuel_type": "LPG", "efficiency_pct": 82, "safety_factor": 1.25,
        "steam_demand_kg_hr": 500, "tds_makeup_ppm": 200, "tds_max_ppm": 3000,
    },
    "Bearing Life (L10)": {
        "bearing_type": "Ball", "C_kN": 25.5, "speed_rpm": 1450,
        "Fr_kN": 5.0, "Fa_kN": 2.0, "reliability_pct": 90, "required_life_h": 25000,
    },
    "Bolt Torque & Preload": {
        "bolt_size": "M16", "bolt_grade": "8.8", "nut_factor": 0.20,
        "preload_pct": 75, "ext_load_kN": 50, "n_bolts": 4,
    },
    "Hoist Capacity": {
        "rated_load_kg": 2000, "hook_weight_kg": 30, "sling_weight_kg": 15,
        "lift_height_m": 6, "lift_speed_mpm": 8, "n_parts": 1,
        "safety_factor": 5, "mech_eff_pct": 82,
    },
    "Elevator Traffic Analysis": {
        "n_floors": 12, "floor_height": 3.5, "population": 500,
        "n_elevators": 3, "capacity": 13, "speed": 1.5,
        "t_door_open": 2.5, "t_door_close": 3.0, "t_dwell": 2.0,
        "occupancy_type": "Office",
    },
}

# ── TypeScript-only calc types (Python returns not_implemented) ────────────────
# These are handled by the edge function TypeScript — validate_integration.py
# tests them via the edge function.
TYPESCRIPT_ONLY = []  # All calc types are now handled by the Python API


def call(calc_type, inputs):
    data = json.dumps({"calc_type": calc_type, "inputs": inputs}).encode()
    req  = urllib.request.Request(
        BASE, data=data,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            body = json.loads(r.read())
            if body.get("not_implemented"):
                return None, "not_implemented (TypeScript-only)"
            if "results" in body:
                return body["results"], None
            return None, f"unexpected response keys: {list(body.keys())}"
    except Exception as ex:
        return None, str(ex)[:120]


def flatten_keys(d):
    keys = set()
    for k, v in d.items():
        keys.add(k)
        if isinstance(v, dict):
            keys.update(flatten_keys(v))
    return keys


print("\n" + "=" * 70)
print("LAYER 1: Python API Unit Test")
print("=" * 70)

results_map = {}
passed = failed = skipped = 0

for calc, inputs in TESTS.items():
    results, err = call(calc, inputs)
    if results:
        results_map[calc] = sorted(flatten_keys(results))
        print(f"  PASS  {calc}  ({len(results_map[calc])} keys)")
        passed += 1
    else:
        results_map[calc] = []
        status = "SKIP" if "not_implemented" in (err or "") else "FAIL"
        print(f"  {status}  {calc}: {err}")
        if status == "FAIL":
            failed += 1
        else:
            skipped += 1
    time.sleep(0.15)

with open("results_keys.json", "w") as f:
    json.dump(results_map, f, indent=2)

print(f"\nResult: {passed} PASS  {failed} FAIL  {skipped} SKIP")
print(f"Saved results_keys.json")
if failed:
    print(f"\nFAIL means Python returned an error — check the handler inputs above.")
    sys.exit(1)
print("\nNext: python validate_renderers.py")
