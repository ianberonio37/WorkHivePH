"""
Layer 2c — Diagram Inputs Contract Validator
=============================================
Checks that inp.xxx references inside every buildXxxSVG() function match
the actual property keys returned by collectInputs() for that calc type.

Root cause of bug class discovered in April 2026 visual testing:
  10 out of 12 diagram builders used wrong inp.xxx property names.
  The || fallback silently produced hardcoded defaults — no error, wrong value.
  Examples:
    inp.hot_T_in_c        → actual: hot_inlet_C      (Heat Exchanger)
    inp.shell_id_mm       → actual: inner_diameter_mm (Pressure Vessel)
    inp.radial_load_kN    → actual: Fr_kN             (Bearing Life)
    inp.num_parts_line    → actual: n_parts            (Hoist Capacity)
    inp.center_distance_mm→ actual: center_dist_mm    (V-Belt Drive)

Also checks inputs.xxx in the BOM/SOW edge function against the same
collectInputs() keys — caught 3 SOW "0 RPM" / blank field bugs.

Reports WARN (not FAIL) since some mismatched names are dead-code fallbacks
that don't break the diagram. Visual testing remains the final gate.

Usage:  python validate_diagram_inputs.py
Output: diagram_inputs_report.json
"""
import re, json, sys

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DRAWING_FILE  = "engineering-design.html"
EDGE_FUNC     = "supabase/functions/engineering-bom-sow/index.ts"

# ── Builder → calc type mapping ───────────────────────────────────────────────
BUILDER_TO_CALC = {
    "buildHeatExchangerSVG":    "Heat Exchanger",
    "buildPressureVesselSVG":   "Pressure Vessel",
    "buildFluidPowerSVG":       "Fluid Power",
    "buildVBeltDriveSVG":       "V-Belt Drive Design",
    "buildVibrationSVG":        "Vibration Analysis",
    "buildNoiseAcousticsSVG":   "Noise / Acoustics",
    "buildShaftDesignSVG":      "Shaft Design",
    "buildBeamColumnSVG":       "Beam / Column Design",
    "buildBearingLifeSVG":      "Bearing Life (L10)",
    "buildBoltTorqueSVG":       "Bolt Torque & Preload",
    "buildElevatorTrafficSVG":  "Elevator Traffic Analysis",
    "buildHoistCapacitySVG":    "Hoist Capacity",
    "buildPipeSizingSVG":       "Pipe Sizing",
    "buildCompressedAirSVG":    "Compressed Air",
    "buildBoilerSystemSVG":     "Boiler / Steam System",
    "buildAHUSizingSVG":        "AHU Sizing",
    "buildDuctSizingSVG":       "Duct Sizing (Equal Friction)",
    "buildSolarPVSVG":          "Solar PV System",
    "buildPFCSVG":              "Power Factor Correction",
    "buildUPSSVG":              "UPS Sizing",
    "buildEarthingSVG":         "Earthing / Grounding System",
    "buildStairwellPressSVG":   "Stairwell Pressurization",
    "buildFireAlarmBatterySVG": "Fire Alarm Battery",
    "buildExpansionTankSVG":    "Expansion Tank Sizing",
    "buildVentilationSVG":      "Ventilation / ACH",
    "buildFCUSVG":              "FCU Selection",
    "buildRefrigPipeSVG":       "Refrigerant Pipe Sizing",
    "buildCoolingTowerSVG":     "Cooling Tower Sizing",
    "buildChillerSVG":          "Chiller System — Water Cooled",
    "buildWaterSupplyPipeSVG":  "Water Supply Pipe Sizing",
    "buildHotWaterDemandSVG":   "Hot Water Demand",
    "buildDrainagePipeSVG":     "Drainage Pipe Sizing",
    "buildSepticTankSVG":       "Septic Tank Sizing",
    "buildGreaseTrapSVG":       "Grease Trap Sizing",
    "buildRoofDrainSVG":        "Roof Drain Sizing",
    "buildWaterSoftenerSVG":    "Water Softener Sizing",
    "buildWaterTreatmentSVG":   "Water Treatment System",
    "buildWastewaterSTPSVG":    "Wastewater Treatment (STP)",
    "buildStormDrainSVG":       "Storm Drain / Stormwater",
    "buildPumpPIDSvg":          "Pump Sizing (TDH)",
    "buildFireSprinklerSvg":    "Fire Sprinkler Hydraulic",
    "buildFirePumpPIDSvg":      "Fire Pump Sizing",
    "buildHVACSvg":             "HVAC Cooling Load",
    "buildLightingLayoutSvg":   "Lighting Design",
    "buildCleanAgentSVG":       "Clean Agent Suppression",
    "buildLPSZoneSvg":          "Lightning Protection System (LPS)",
    "buildGeneratorConnectionSvg": "Generator Sizing",
    "buildTransformerSLDSvg":   "Transformer Sizing",
    # Electrical SLD uses shared display logic — skip inputs check
    "buildElectricalSLDSvg":    None,
}

# Keys that appear in every collectInputs() return — not calc-specific
UNIVERSAL_KEYS = {"project_name", "calc_type", "floor_area", "occupancy_type"}

# JS/object method names that appear after inp. but aren't input keys
INP_NOISE = {
    "constructor", "toString", "valueOf", "length", "prototype",
    "hasOwnProperty", "isPrototypeOf", "propertyIsEnumerable",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def read_file(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def extract_function_body(content, func_name, max_chars=60000):
    m = re.search(rf"function\s+{re.escape(func_name)}\s*\(", content)
    if not m:
        return None
    brace = content.find("{", m.end())
    if brace == -1:
        return None
    depth, i = 0, brace
    limit = min(brace + max_chars, len(content))
    while i < limit:
        if content[i] == "{":
            depth += 1
        elif content[i] == "}":
            depth -= 1
            if depth == 0:
                return content[brace:i + 1]
        i += 1
    return content[brace:brace + max_chars]


def extract_collector_keys(content, calc_type):
    """Parse collectInputs() in engineering-design.html for a given calc type
    and return the set of property keys in the return object."""
    escaped = re.escape(calc_type)
    m = re.search(rf"_calcType\s*===\s*['\"]({escaped})['\"]", content)
    if not m:
        return set()

    # Find 'return {' within 600 chars of the match
    seg = content[m.end(): m.end() + 600]
    rm = re.search(r"return\s*\{", seg)
    if not rm:
        return set()

    start = m.end() + rm.end()
    depth, pos = 1, start
    while pos < len(content) and depth > 0:
        if content[pos] == "{":
            depth += 1
        elif content[pos] == "}":
            depth -= 1
        pos += 1
    block = content[start: pos - 1]

    # Extract `key:` at start of line (handles both `key: value` and `key :value`)
    keys = re.findall(r"^\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*:", block, re.MULTILINE)
    return set(keys) | UNIVERSAL_KEYS


def extract_inp_refs(body):
    """Return all unique inp.xxx property names from a builder body."""
    refs = set()
    for m in re.finditer(r"\binp(?:\?)?\s*\.\s*([a-zA-Z_][a-zA-Z0-9_]*)", body):
        refs.add(m.group(1))
    return refs - INP_NOISE


def extract_inputs_refs_ts(block):
    """Return all unique inputs.xxx property names from a TS agent block."""
    refs = set()
    for m in re.finditer(r"\binputs(?:\?)?\s*\.\s*([a-zA-Z_][a-zA-Z0-9_]*)", block):
        refs.add(m.group(1))
    # Filter TS noise
    ts_noise = {
        "length", "map", "forEach", "filter", "find", "join", "toString",
        "toFixed", "includes", "split", "trim", "replace", "toLowerCase",
        "project_name",  # universal — present in all collectors
    }
    return refs - ts_noise


def extract_ts_agent_block(ts_content, calc_type):
    """Extract the agent function body for a calc_type from the BOM/SOW edge function."""
    escaped = re.escape(calc_type)
    m = re.search(rf'calc_type\s*===\s*["\']({escaped})["\']', ts_content)
    if not m:
        return ""
    pos = m.end()
    while pos < len(ts_content) and ts_content[pos] != "{":
        pos += 1
    if pos >= len(ts_content):
        return ""
    depth, start = 0, pos
    for i in range(pos, min(pos + 20000, len(ts_content))):
        if ts_content[i] == "{":
            depth += 1
        elif ts_content[i] == "}":
            depth -= 1
            if depth == 0:
                return ts_content[start: i + 1]
    return ts_content[start: start + 5000]


# ── Layer 2c-A: Builder inp.xxx check ────────────────────────────────────────

def check_builder_inp_keys(html, builders_map):
    clean, warns, skipped = [], [], []

    for func, calc_type in builders_map.items():
        if calc_type is None:
            skipped.append((func, "no calc type mapping"))
            continue

        body = extract_function_body(html, func)
        if body is None:
            skipped.append((func, "function not found"))
            continue

        known_keys = extract_collector_keys(html, calc_type)
        if not known_keys:
            skipped.append((func, f"no collectInputs() block for '{calc_type}'"))
            continue

        inp_refs = extract_inp_refs(body)
        mismatches = inp_refs - known_keys

        if mismatches:
            warns.append({
                "func": func,
                "calc_type": calc_type,
                "mismatched": sorted(mismatches),
                "known_keys": sorted(known_keys),
            })
        else:
            clean.append(func)

    return clean, warns, skipped


# ── Layer 2c-B: Edge function inputs.xxx check ───────────────────────────────

def check_edge_inputs_keys(html, ts_content, calc_types):
    clean, warns, skipped = [], [], []

    for calc_type in calc_types:
        block = extract_ts_agent_block(ts_content, calc_type)
        if not block:
            skipped.append((calc_type, "no agent block in edge function"))
            continue

        known_keys = extract_collector_keys(html, calc_type)
        if not known_keys:
            skipped.append((calc_type, f"no collectInputs() block"))
            continue

        refs = extract_inputs_refs_ts(block)
        mismatches = refs - known_keys

        if mismatches:
            warns.append({
                "calc_type": calc_type,
                "mismatched": sorted(mismatches),
                "known_keys": sorted(known_keys),
            })
        else:
            clean.append(calc_type)

    return clean, warns, skipped


# ── Runner ────────────────────────────────────────────────────────────────────

def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    def green(s): return f"\033[92m{s}\033[0m"
    def yellow(s): return f"\033[93m{s}\033[0m"
    def red(s): return f"\033[91m{s}\033[0m"

    print(bold("\nDiagram Inputs Contract Validator (Layer 2c)"))
    print("=" * 58)

    html = read_file(DRAWING_FILE)
    if not html:
        print(f"  ERROR: {DRAWING_FILE} not found")
        sys.exit(1)

    ts = read_file(EDGE_FUNC)
    if not ts:
        print(f"  WARN: {EDGE_FUNC} not found — skipping edge function check")

    # ── Part A: Builder inp.xxx ───────────────────────────────────────────────
    print(bold("\n  Part A — buildXxxSVG() inp.xxx vs collectInputs() keys"))
    print("  " + "-" * 54)

    clean_a, warns_a, skip_a = check_builder_inp_keys(html, BUILDER_TO_CALC)

    for func in clean_a:
        print(f"  PASS  {func}")
    for item in skip_a:
        print(f"  SKIP  {item[0]}: {item[1]}")
    for item in warns_a:
        print(yellow(f"  WARN  {item['func']} ({item['calc_type']})"))
        for key in item["mismatched"]:
            close = [k for k in item["known_keys"]
                     if key.lower() in k.lower() or k.lower() in key.lower()]
            hint = f"  -> closest: '{close[0]}'" if close else "  -> no close match in collectInputs()"
            print(f"         inp.{key}{hint}")

    total_a = len(clean_a) + len(warns_a)
    print(f"\n  Part A: {len(clean_a)} PASS  {len(warns_a)} WARN  {len(skip_a)} SKIP  "
          f"(of {total_a} checked builders)")

    # ── Part B: Edge function inputs.xxx ─────────────────────────────────────
    if ts:
        print(bold("\n  Part B — BOM/SOW edge function inputs.xxx vs collectInputs() keys"))
        print("  " + "-" * 54)

        edge_calc_types = list(BUILDER_TO_CALC.values())
        edge_calc_types = [ct for ct in edge_calc_types if ct is not None]
        # Deduplicate, preserve order
        seen = set()
        edge_calc_types = [ct for ct in edge_calc_types
                           if not (ct in seen or seen.add(ct))]

        clean_b, warns_b, skip_b = check_edge_inputs_keys(html, ts, edge_calc_types)

        for ct in clean_b:
            print(f"  PASS  {ct}")
        for item in skip_b:
            print(f"  SKIP  {item[0]}: {item[1]}")
        for item in warns_b:
            print(yellow(f"  WARN  {item['calc_type']}"))
            for key in item["mismatched"]:
                close = [k for k in item["known_keys"]
                         if key.lower() in k.lower() or k.lower() in key.lower()]
                hint = f"  -> closest: '{close[0]}'" if close else "  -> no close match"
                print(f"         inputs.{key}{hint}")

        total_b = len(clean_b) + len(warns_b)
        print(f"\n  Part B: {len(clean_b)} PASS  {len(warns_b)} WARN  {len(skip_b)} SKIP  "
              f"(of {total_b} checked)")
    else:
        warns_b, skip_b, clean_b = [], [], []

    # ── Summary ───────────────────────────────────────────────────────────────
    total_warns = len(warns_a) + len(warns_b)
    print("\n" + "=" * 58)
    if total_warns == 0:
        print(green("  All inp.xxx / inputs.xxx checks PASS — no stale property names."))
    else:
        print(yellow(f"  {total_warns} WARN — mismatched property names found."))
        print("  These silently fall back to hardcoded defaults in diagrams.")
        print("  Fix: align inp.xxx names with collectInputs() return keys.")

    report = {
        "validator": "diagram_inputs",
        "part_a_builder_checks": {
            "pass": clean_a, "warn": warns_a, "skip": [s[0] for s in skip_a]
        },
        "part_b_edge_checks": {
            "pass": clean_b,
            "warn": warns_b,
            "skip": [s[0] for s in skip_b] if ts else ["edge function not found"],
        },
        "total_warns": total_warns,
    }
    with open("diagram_inputs_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print("  Saved diagram_inputs_report.json")

    # WARNs do not fail the build — they are advisory
    sys.exit(0)


if __name__ == "__main__":
    main()
