"""
Layer 2b — Contract Test: BOM/SOW edge function vs API results.

Parses the engineering-bom-sow/index.ts source file to extract every
rec.field access per calc type, then cross-references against
results_keys.json. Reports any field the BOM/SOW reads that does not
exist in the API response.

Run after validate_fields.py.
Usage:  python validate_bom_sow.py
"""
import json, re, sys

with open("results_keys.json") as f:
    api_keys = json.load(f)

with open("supabase/functions/engineering-bom-sow/index.ts", encoding="utf-8") as f:
    ts = f.read()

# ── Fields that look like rec.xxx but are JS/TS noise ────────────────────────
TS_NOISE = {
    "length", "map", "forEach", "filter", "find", "join", "toString",
    "toFixed", "includes", "sort", "slice", "push", "pop",
    "keys", "values", "entries", "split", "trim", "replace",
    "toLowerCase", "toUpperCase", "some", "every", "flat", "reduce",
    # Safe meta fields
    "not_implemented", "source", "calc_type", "calculation_source",
    "standard", "inputs_used", "narrative",
}


def extract_block_for_calc(ts_content, calc_type):
    """
    Extract the TypeScript if-block for a specific calc_type.
    Looks for: calc_type === "Calc Type Name" { ... }
    """
    escaped  = re.escape(calc_type)
    pattern  = rf'calc_type\s*===\s*["\']({escaped})["\']'
    m = re.search(pattern, ts_content)
    if not m:
        return ""
    # Walk forward to find the opening brace and match closing brace
    pos = m.end()
    # skip to first {
    while pos < len(ts_content) and ts_content[pos] != '{':
        pos += 1
    if pos >= len(ts_content):
        return ""
    depth = 0
    start = pos
    for i in range(pos, min(pos + 15000, len(ts_content))):
        c = ts_content[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return ts_content[start:i + 1]
    return ts_content[start:start + 5000]


def extract_rec_fields(block):
    """Extract all rec.fieldName patterns from a TS block."""
    patterns = [
        r'\brec\.([a-zA-Z_][a-zA-Z0-9_]*)',
        r'\brec\?\.\s*([a-zA-Z_][a-zA-Z0-9_]*)',
    ]
    fields = set()
    for pat in patterns:
        fields.update(re.findall(pat, block))
    return fields - TS_NOISE


# ── BOM/SOW dispatch discipline map ──────────────────────────────────────────
# calc_type → discipline (needed because BOM/SOW checks both)
DISCIPLINE_MAP = {
    "HVAC Cooling Load":                "Mechanical",
    "Ventilation / ACH":               "Mechanical",
    "Pump Sizing (TDH)":               "Mechanical",
    "Pipe Sizing":                      "Mechanical",
    "Compressed Air":                   "Mechanical",
    "Boiler System":                    "Mechanical",
    "Water Supply Pipe Sizing":         "Plumbing",
    "Hot Water Demand":                 "Plumbing",
    "Drainage Pipe Sizing":             "Plumbing",
    "Septic Tank Sizing":               "Plumbing",
    "Water Softener Sizing":            "Plumbing",
    "Water Treatment System":           "Plumbing",
    "Wastewater Treatment (STP)":       "Plumbing",
    "Storm Drain / Stormwater":         "Plumbing",
    "Grease Trap Sizing":               "Plumbing",
    "Roof Drain Sizing":                "Plumbing",
    "Load Estimation":                  "Electrical",
    "Voltage Drop":                     "Electrical",
    "Wire Sizing":                      "Electrical",
    "Short Circuit":                    "Electrical",
    "Lighting Design":                  "Electrical",
    "Solar PV System":                  "Electrical",
    "Power Factor Correction":          "Electrical",
    "Cable Tray Sizing":                "Electrical",
    "UPS Sizing":                       "Electrical",
    "Earthing / Grounding System":      "Electrical",
    "Lightning Protection System (LPS)":"Electrical",
    "Generator Sizing":                 "Electrical",
    "Fire Sprinkler Hydraulic":         "Fire Protection",
    "Fire Pump Sizing":                 "Fire Protection",
    "Stairwell Pressurization":         "Fire Protection",
    "Fire Alarm Battery":               "Fire Protection",
    "Elevator Traffic Analysis":        "Vertical Transportation",
    "Hoist Capacity":                   "Vertical Transportation",
    "Chiller System — Air Cooled":      "HVAC Systems",
    "Chiller System — Water Cooled":    "HVAC Systems",
    "AHU Sizing":                       "HVAC Systems",
    "Cooling Tower Sizing":             "HVAC Systems",
    "Duct Sizing (Equal Friction)":     "HVAC Systems",
    "Refrigerant Pipe Sizing":          "HVAC Systems",
    "FCU Selection":                    "HVAC Systems",
    "Expansion Tank Sizing":            "HVAC Systems",
    "Heat Exchanger":                   "HVAC Systems",
    "Shaft Design":                     "Machine Design",
    "V-Belt Drive Design":              "Machine Design",
    "Gear / Belt Drive":                "Machine Design",
    "Bearing Life (L10)":               "Machine Design",
    "Bolt Torque & Preload":            "Machine Design",
    "Beam / Column Design":             "Machine Design",
    "Pressure Vessel":                  "Machine Design",
    "Vibration Analysis":               "Machine Design",
    "Fluid Power":                      "Machine Design",
    "Noise / Acoustics":               "Machine Design",
}

print("\n" + "=" * 70)
print("LAYER 2b: BOM/SOW Contract Test")
print("=" * 70)

issues  = []
clean   = []
no_api  = []
no_block = []

for calc_type in DISCIPLINE_MAP:
    api = set(api_keys.get(calc_type, []))
    if not api:
        no_api.append(calc_type)
        continue

    block = extract_block_for_calc(ts, calc_type)
    if not block:
        no_block.append(calc_type)
        continue

    accessed = extract_rec_fields(block)
    missing  = accessed - api

    if missing:
        issues.append((calc_type, sorted(missing), sorted(api)))
    else:
        clean.append(calc_type)

for calc_type in clean:
    print(f"  PASS  {calc_type}")

for calc_type in no_block:
    print(f"  SKIP  {calc_type}: no BOM/SOW block found (calc type may not have BOM/SOW)")

for calc_type in no_api:
    print(f"  SKIP  {calc_type}: no API results (TypeScript-only or Layer 1 failed)")

print()
for calc, missing, api_list in issues:
    print(f"  FAIL  {calc}")
    for f in missing:
        close = [k for k in api_list if f.lower() in k.lower() or k.lower() in f.lower()]
        hint  = f"  -> closest API key: '{close[0]}'" if close else "  -> NOT returned by API"
        print(f"    rec.{f}{hint}")
    print()

print("=" * 70)
print(f"Result: {len(clean)} PASS  {len(issues)} FAIL  {len(no_block)} SKIP (no block)  {len(no_api)} SKIP (no API)")

report = {
    "mismatches": [
        {"calc_type": c, "missing_fields": mf, "api_keys": ak[:30]}
        for c, mf, ak in issues
    ],
    "clean":    clean,
    "no_block": no_block,
    "no_api":   no_api,
}
with open("bom_sow_mismatch_report.json", "w") as f:
    json.dump(report, f, indent=2)
print(f"Saved bom_sow_mismatch_report.json")

if issues:
    print("\nFIX REQUIRED: BOM/SOW will produce blank lines for these fields.")
    sys.exit(1)
print("\nNext: python validate_integration.py")
