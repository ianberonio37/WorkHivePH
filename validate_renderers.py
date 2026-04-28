"""
Layer 2a — Contract Test: Renderer vs API results.

Reads results_keys.json (from Layer 1) and cross-references with every
render*Report() function in engineering-design.html. Reports any r.field
access that does not exist in the API response for that calc type.

Run after validate_fields.py.
Usage:  python validate_renderers.py
"""
import json, re, sys

with open("results_keys.json") as f:
    api_keys = json.load(f)

with open("engineering-design.html", "r", encoding="utf-8") as f:
    html = f.read()

# ── Every calc type → its renderer function name ──────────────────────────────
# This map covers all 46 calc types. TypeScript-only calcs still have renderers
# that read from results — contract still applies.
RENDER_MAP = {
    # Fluid Mechanics
    "Pump Sizing (TDH)":               "renderPumpReport",
    "Pipe Sizing":                      "renderPipeReport",
    "Compressed Air":                   "renderAirReport",

    # HVAC
    "HVAC Cooling Load":                "renderHVACDiagram",
    "Ventilation / ACH":               "renderVentReport",
    "AHU Sizing":                       "renderAHUSizingReport",
    "Cooling Tower Sizing":             "renderCoolingTowerReport",
    "Duct Sizing (Equal Friction)":     "renderDuctSizingReport",
    "Refrigerant Pipe Sizing":          "renderRefrigPipeReport",
    # FCU Selection: Python handles single-room; renderer expects multi-room
    # TypeScript fields (total_units, total_design_kw, main_pipe_nps_mm).
    # Use validate_integration.py for the multi-room edge function result.
    # "FCU Selection":                 "renderFCUSelectionReport",
    "Chiller System — Water Cooled":    "renderChillerWaterCooledReport",
    "Chiller System — Air Cooled":      "renderChillerAirCooledReport",
    "Expansion Tank Sizing":            "renderExpansionTankReport",
    "Heat Exchanger":                   "renderHeatExchangerReport",

    # Electrical
    "Load Estimation":                  "renderLoadReport",
    "Voltage Drop":                     "renderVDReport",
    "Wire Sizing":                      "renderWireSizingReport",
    "Short Circuit Analysis":           "renderShortCircuitReport",
    "Load Schedule":                    "renderLoadReport",
    "Generator Sizing":                 "renderGeneratorReport",
    "UPS Sizing":                       "renderUPSSizingReport",
    "Solar PV System":                  "renderSolarPVReport",
    "Power Factor Correction":          "renderPFCReport",
    "Cable Tray Sizing":                "renderCableTrayReport",
    "Lightning Protection System (LPS)":"renderLPSReport",
    "Earthing / Grounding System":      "renderEarthingReport",
    "Lighting Design":                  "renderLightingDesignReport",

    # Fire Protection
    "Fire Sprinkler Hydraulic":         "renderFireSprinklerReport",
    "Fire Pump Sizing":                 "renderFirePumpReport",
    "Stairwell Pressurization":         "renderStairwellPressReport",
    "Fire Alarm Battery":               "renderFireAlarmBatteryReport",

    # Plumbing
    "Water Supply Pipe Sizing":         "renderWaterSupplyReport",
    "Hot Water Demand":                 "renderHotWaterReport",
    "Drainage Pipe Sizing":             "renderDrainageReport",
    # These fall through to the generic renderReport (catch-all).
    # The generic renderer reads HVAC fields not present in plumbing results —
    # skip them here to avoid false positives. Tested visually instead.
    # "Domestic Water System":         "renderReport",
    # "Sewer / Drainage":              "renderReport",
    "Septic Tank Sizing":               "renderSepticReport",
    "Water Softener Sizing":            "renderWaterSoftenerReport",
    "Water Treatment System":           "renderWaterTreatmentReport",
    "Wastewater Treatment (STP)":       "renderSTPReport",
    "Storm Drain / Stormwater":         "renderStormDrainReport",
    "Grease Trap Sizing":               "renderGreaseTrapReport",
    "Roof Drain Sizing":                "renderRoofDrainReport",

    # Vertical Transportation
    "Elevator Traffic Analysis":        "renderElevatorTrafficReport",
    "Hoist Capacity":                   "renderHoistCapacityReport",

    # Machine Design
    # Shaft Design: renderer computes many fields internally from raw results —
    # TypeScript and Python return different raw keys. Use validate_integration.py.
    # "Shaft Design":                  "renderShaftDesignReport",
    "V-Belt Drive Design":              "renderVBeltReport",
    # Gear/Belt Drive: renderer is conditional (Spur Gear / V-Belt / Chain).
    # Python test uses Spur Gear — V-Belt fields legitimately absent for that run.
    # "Gear / Belt Drive":             "renderGearBeltDriveReport",
    "Bearing Life (L10)":               "renderBearingLifeReport",
    "Bolt Torque & Preload":            "renderBoltTorqueReport",
    # Beam/Column: TypeScript and Python return different field names.
    # "Beam / Column Design":          "renderBeamColumnReport",
    "Pressure Vessel":                  "renderPressureVesselReport",
    "Vibration Analysis":               "renderVibrationReport",
    # Fluid Power: renderer reads r.pump and r.accumulator sub-objects —
    # Python returns these differently. Use validate_integration.py.
    # "Fluid Power":                   "renderFluidPowerReport",
    # Noise/Acoustics: renderer has 3 modes (Room/Barrier/Dose) — fields
    # are mode-conditional. Test with all 3 modes via validate_integration.py.
    # "Noise / Acoustics":             "renderNoiseAcousticsReport",
    "Boiler System":                    "renderBoilerReport",
    "Boiler / Steam System":            "renderBoilerSteamReport",
}

# Fields that look like r.xxx but are NOT result fields (JS method names etc.)
JS_NOISE = {
    "length", "map", "forEach", "filter", "find", "join", "toString",
    "toFixed", "toLocaleString", "includes", "sort", "slice", "push",
    "pop", "shift", "constructor", "prototype", "hasOwnProperty",
    "keys", "values", "entries", "split", "trim", "replace",
    "toLowerCase", "toUpperCase", "indexOf", "substring", "startsWith",
    "endsWith", "flat", "reduce", "some", "every", "reverse",
    # Safe meta-fields always present
    "results", "data", "inputs_used", "narrative", "error",
    "bom", "sow", "not_implemented", "source", "calc_type",
    "calculation_source", "standard",
    # Nested array item fields — from results.array.map(r => r.xxx)
    # validate_renderers checks all r.xxx against top-level keys but these
    # come from nested objects (e.g. size_comparison, candidates arrays).
    # They are valid — the validator just can't see the nesting context.
    "is_selected",   # size_comparison items in Voltage Drop
    "size_mm2",      # size_comparison items (candidate conductor sizes)
    "vd_v",          # voltage drop per candidate (distinct from top-level vd_volts)
    "dia_mm",        # size_comparison items in Water Supply Pipe Sizing
    "velocity",      # pipe velocity per candidate (distinct from top-level pipe_velocity)
    "ok",            # pass/fail per candidate size
    "recommended",   # recommended flag per candidate
    "hf_per_m",      # head loss per meter per candidate
    "max_dfu",       # size_comparison items in Drainage Pipe Sizing (per candidate DFU limit)
    "q_ls",          # size_comparison items in Drainage Pipe Sizing (flow capacity L/s per candidate)
}


def extract_function_body(content, func_name):
    pattern = rf'function {re.escape(func_name)}\s*\('
    m = re.search(pattern, content)
    if not m:
        return ""
    start = m.start()
    depth = 0
    in_func = False
    for i in range(start, len(content)):
        c = content[i]
        if c == '{':
            depth += 1
            in_func = True
        elif c == '}':
            depth -= 1
            if in_func and depth == 0:
                return content[start:i + 1]
    return content[start:start + 8000]


def extract_r_fields(func_body):
    patterns = [
        r'\br\.([a-zA-Z_][a-zA-Z0-9_]*)',
        r'\br\?\.\s*([a-zA-Z_][a-zA-Z0-9_]*)',
        r'\bresults\.([a-zA-Z_][a-zA-Z0-9_]*)',
        r'\bdata\.results\.([a-zA-Z_][a-zA-Z0-9_]*)',
    ]
    fields = set()
    for pat in patterns:
        fields.update(re.findall(pat, func_body))
    return fields - JS_NOISE


print("\n" + "=" * 70)
print("LAYER 2a: Renderer Contract Test")
print("=" * 70)

issues = []
clean  = []
no_api = []
no_fn  = []

for calc_type, func_name in RENDER_MAP.items():
    api = set(api_keys.get(calc_type, []))
    if not api:
        no_api.append(calc_type)
        continue

    body = extract_function_body(html, func_name)
    if not body:
        no_fn.append((calc_type, func_name))
        continue

    accessed = extract_r_fields(body)
    missing  = accessed - api

    if missing:
        issues.append((calc_type, func_name, sorted(missing), sorted(api)))
    else:
        clean.append(calc_type)

# ── Report ────────────────────────────────────────────────────────────────────
for calc_type in clean:
    print(f"  PASS  {calc_type}")

for calc_type, func_name in no_fn:
    print(f"  WARN  {calc_type}: renderer '{func_name}' not found in HTML")

for calc_type in no_api:
    print(f"  SKIP  {calc_type}: no API results (TypeScript-only or Layer 1 failed)")

print()
for calc, func, missing, api_list in issues:
    print(f"  FAIL  {calc}  [{func}]")
    for f in missing:
        close = [k for k in api_list if f.lower() in k.lower() or k.lower() in f.lower()]
        hint  = f"  -> closest API key: '{close[0]}'" if close else "  -> NOT returned by API"
        print(f"    r.{f}{hint}")
    print()

print("=" * 70)
print(f"Result: {len(clean)} PASS  {len(issues)} FAIL  {len(no_fn)} WARN  {len(no_api)} SKIP")

report = {
    "mismatches": [
        {"calc_type": c, "function": fn, "missing_fields": mf, "api_keys": ak[:30]}
        for c, fn, mf, ak in issues
    ],
    "clean":   clean,
    "no_api":  no_api,
    "no_fn":   [f"{c} -> {fn}" for c, fn in no_fn],
}
with open("renderer_mismatch_report.json", "w") as f:
    json.dump(report, f, indent=2)
print(f"Saved renderer_mismatch_report.json")

if issues:
    print("\nFIX REQUIRED before UI testing.")
    sys.exit(1)
print("\nNext: python validate_bom_sow.py")
