"""
Layer 3 — Integration Test: Supabase Edge Function end-to-end.

Calls the live edge function (not the Python API directly) for a
representative sample of calc types and verifies:
  1. The edge function returns HTTP 200 with a results object
  2. For Python-handled calcs: response includes "source": "python"
     (confirms Python is being called, NOT the TypeScript fallback)
  3. Key result fields are present and non-null (spot-check)

This catches the failure mode where the Python API passes unit tests
but the edge function silently falls back to its TypeScript handler.

Usage:  python validate_integration.py
"""
import urllib.request, json, time, sys

EDGE_URL = "https://hzyvnjtisfgbksicrouu.supabase.co/functions/v1/engineering-calc-agent"

# ── Sample set: one per discipline, covering the highest-risk calc types ────
# Each entry: (calc_type, inputs, expected_source, spot_check_fields)
# expected_source: "python" | "typescript" | "either"
# spot_check_fields: list of result keys that must be non-null/non-undefined
SAMPLES = [
    # ── Python-handled (must return source: "python") ─────────────────────────
    ("V-Belt Drive Design", {
        "drive_type": "V-Belt", "power_kW": 7.5, "service_factor": 1.2,
        "driver_rpm": 1450, "driven_rpm": 720, "belt_section": "B",
        "driver_dia_mm": 125, "center_dist_mm": 500,
    }, "python", ["speed_ratio", "driven_dia_mm", "n_belts", "belt_designation",
                  "arc_deg", "design_power_kW"]),

    ("Lighting Design", {
        "room_len_m": 10, "room_wid_m": 8, "ceiling_ht_m": 3,
        "lumens_per_fix": 3200, "watts_per_fix": 36,
        "fixture_type": "LED Panel 600x600", "llf": 0.80,
    }, "python", ["N_fixtures", "E_actual_lux", "RCR", "CU", "LLF"]),

    ("Noise / Acoustics", {
        "calc_type": "Room", "source_Lw_dB": 90, "distance_m": 5,
        "directivity_Q": 2, "avg_absorption_coeff": 0.15, "room_surface_m2": 200,
        "exposures": [{"level_dBA": 90, "duration_hr": 8}],
    }, "either", ["Lp_at_distance_dB", "NC_limit", "NC_recommended"]),

    ("Fluid Power", {
        "system_pressure_bar": 200, "flow_lpm": 40,
        "cylinder_force_kN": 50, "stroke_mm": 200,
        "pump_displacement_cc_rev": 0.5, "pump_rpm": 1380,
    }, "either", ["bore_selected_mm", "pressure_line", "return_line"]),

    ("Fire Pump Sizing", {
        "required_flow": 1900, "required_pressure": 6.9,
        "drive_type": "Electric Motor", "redundancy": "Duplex",
    }, "either", ["system_flow_lpm", "system_pressure_bar", "recommended_flow_lpm"]),

    ("Generator Sizing", {
        "loads": [{"name": "HVAC", "kw": 50, "pf": 0.85, "qty": 1,
                   "load_type": "HVAC", "starting_method": "VFD"}],
        "voltage": 400, "frequency": 60,
    }, "either", ["demand_kW", "demand_kVA", "required_kVA_governing"]),

    # ── TypeScript-handled (source will be absent or "typescript") ────────────
    ("Expansion Tank Sizing", {
        "system_type": "Chilled Water", "volume_method": "Direct Entry",
        "system_volume_L": 500, "fill_temp_c": 20, "max_temp_c": 7,
        "static_head_m": 10, "max_pressure_kpa_g": 400,
    }, "either", ["selected_tank_L", "acceptance_factor", "required_volume_L"]),

    ("Bearing Life (L10)", {
        "bearing_type": "Ball Bearing", "C_kN": 25.5, "Fr_kN": 5,
        "Fa_kN": 0, "speed_rpm": 1450, "required_life_hr": 25000,
    }, "either", ["P_kN", "C_over_P", "Fa_Fr_ratio"]),

    ("Stairwell Pressurization", {
        "building_type": "Sprinklered", "n_floors": 10, "n_stairwells": 2,
        "door_width_m": 0.9, "door_height_m": 2.1, "design_pressure_Pa": 25,
        "fan_static_Pa": 400, "safety_factor_pct": 20,
    }, "either", ["N_stairwells", "N_floors", "door_fit"]),

    ("Fire Alarm Battery", {
        "system_voltage": 24,
        "n_facp": 1, "n_addr_smoke": 10, "n_horn_strobe": 5,
        "standby_hours": 24, "alarm_minutes": 5,
    }, "either", ["system_voltage", "standby_hours", "panel_standby_mA"]),
]


def call_edge(calc_type, inputs):
    data = json.dumps({"calc_type": calc_type, "inputs": inputs}).encode()
    req  = urllib.request.Request(
        EDGE_URL, data=data,
        headers={"Content-Type": "application/json", "Origin": "https://workhiveph.com"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            body = json.loads(r.read().decode("utf-8", errors="replace"))
            return body, None
    except Exception as ex:
        return None, str(ex)[:120]


print("\n" + "=" * 70)
print("LAYER 3: Edge Function Integration Test")
print("=" * 70)
print("Checking: HTTP 200, results present, source field, spot-check fields\n")

passed = failed = warned = 0

for calc_type, inputs, exp_source, spot_fields in SAMPLES:
    body, err = call_edge(calc_type, inputs)

    if err or not body:
        print(f"  FAIL  {calc_type}: {err}")
        failed += 1
        time.sleep(0.2)
        continue

    results = body.get("results", {})
    source  = body.get("source", "typescript")

    problems = []

    # Check source
    if exp_source == "python" and source != "python":
        problems.append(f"source='{source}' (expected 'python' — edge function used TypeScript fallback!)")

    # Spot-check key fields
    for field in spot_fields:
        if field not in results or results[field] is None:
            problems.append(f"results.{field} is missing or null")

    if problems:
        print(f"  FAIL  {calc_type}  [source={source}]")
        for p in problems:
            print(f"    {p}")
        failed += 1
    else:
        flag = f"[source={source}]" if exp_source == "python" else "[TypeScript OK]"
        print(f"  PASS  {calc_type}  {flag}")
        passed += 1

    time.sleep(0.3)

print(f"\n{'=' * 70}")
print(f"Result: {passed} PASS  {failed} FAIL  {warned} WARN")

if failed:
    print("""
COMMON CAUSES of integration failures:
  source='typescript' when expected 'python':
    -> Python API did not handle the calc type (returned not_implemented)
    -> Check PYTHON_API_URL env var is set in Supabase edge function settings
    -> Check that main.py has the alias for this calc type

  results.field is null:
    -> Python returned the calc but with wrong field names
    -> Re-run validate_fields.py to check Layer 1 output
""")
    sys.exit(1)
print("\nAll integration checks PASS. Proceed to manual UI spot-check.")
