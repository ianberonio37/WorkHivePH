"""Generate the Engineering Design Wave 3 capture-contracts migration.

For each python-api/calcs/<name>.py, scans the file for `inputs.get("...")`
calls (and a few other access patterns) to extract the expected input
field names. Emits one capture_id per calc (eng_calc_<name>_v1) registered
in canonical_capture_contracts with surface=form and target_table=
engineering_calcs.

Output:
  supabase/migrations/20260512000019_capture_contracts_wave3_eng.sql
"""
import re, os, sys, glob, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

CALCS_DIR = "python-api/calcs"
OUTPUT    = "supabase/migrations/20260512000019_capture_contracts_wave3_eng.sql"

# Patterns we recognise as input-field reads in calc handlers
INPUT_PATTERNS = [
    re.compile(r'inputs\.get\(\s*["\']([a-z_][a-z0-9_]*)["\']'),
    re.compile(r'inputs\[\s*["\']([a-z_][a-z0-9_]*)["\']'),
]

# Type hint per field-name pattern. Best-effort; falls back to "number".
def type_for_field(name: str) -> str:
    n = name.lower()
    if n.endswith(("_id", "uid", "_uuid", "_node_id")): return "string"
    if n in ("worker_name", "project_name", "discipline", "machine", "model",
             "manufacturer", "tag", "notes", "category", "location"):
        return "string"
    if n.endswith(("_count", "_n", "_qty")) or n.startswith("n_"):
        return "integer"
    if n.endswith(("_flag", "_enabled", "_is", "is_", "has_")) or n.startswith(("is_", "has_")):
        return "boolean"
    return "number"   # default for engineering inputs (kpa, lpm, mm, etc.)


def short_name(p): return os.path.splitext(os.path.basename(p))[0]
def calc_title(n): return " ".join(w.capitalize() for w in n.split("_"))


def primary_discipline(name: str) -> str:
    if any(k in name for k in ("ahu_","chiller","cooling_tower","fcu_","duct_","ventilation",
                               "refrigerant","heat_exchanger","expansion_tank","hvac_","stairwell_")):
        return "hvac"
    if any(k in name for k in ("fire_","sprinkler","clean_agent")):
        return "fire"
    if any(k in name for k in ("water_","drainage","drain","sewer_","septic","grease_trap",
                               "hot_water","domestic_water","wastewater","boiler","pipe_sizing",
                               "roof_drain","storm_drain")):
        return "plumbing"
    if any(k in name for k in ("cable","wire","voltage","transformer","generator","ups",
                               "load_","short_circuit","earthing","harmonic","power_factor")):
        return "electrical"
    if any(k in name for k in ("lightning",)):
        return "lightning_protection"
    if any(k in name for k in ("solar_pv",)):
        return "solar_pv"
    if "lighting" in name:
        return "lighting"
    if "noise" in name:
        return "acoustics"
    if any(k in name for k in ("compressed_air",)):
        return "pneumatic"
    if any(k in name for k in ("fluid_power","hydraulic")):
        return "hydraulic"
    if any(k in name for k in ("bearing","shaft","gear","beam","pressure_vessel","bolt",
                               "pump","fan","vibration","hoist","elevator")):
        return "mechanical"
    return "general"


def main():
    rows = []
    for path in sorted(glob.glob(os.path.join(CALCS_DIR, "*.py"))):
        name = short_name(path)
        if name == "__init__": continue
        content = open(path, encoding="utf-8").read()
        if not re.search(r"^def calculate", content, re.MULTILINE): continue
        fields = set()
        for pat in INPUT_PATTERNS:
            for m in pat.finditer(content):
                fields.add(m.group(1))
        if not fields:
            # Fall back: skip calcs that have no inputs.get() pattern. Some
            # use direct args. They get covered by an umbrella allowlist.
            continue

        capture_id = f"eng_calc_{name}_v1"
        title = calc_title(name)
        disc  = primary_discipline(name)

        # Build the contract_schema. Required: anything that's clearly a
        # number/integer (engineering inputs almost always required). Type:
        # inferred from field name.
        properties = {}
        required = []
        for f in sorted(fields):
            ftype = type_for_field(f)
            properties[f] = ftype
            if ftype in ("number", "integer"):
                required.append(f)

        # Build SQL row. JSON Schema as compact JSON string.
        import json as _json
        schema_obj = {
            "type": "object",
            "required": required[:8],   # cap required at 8 to keep schema readable
            "properties": {k: {"type": ["number", "null"]} if v == "number" else
                              {"type": ["integer", "null"]} if v == "integer" else
                              {"type": ["string", "null"]} if v == "string" else
                              {"type": ["boolean", "null"]} for k, v in properties.items()},
        }
        fields_arr = [{"name": f, "type": type_for_field(f), "required": f in required[:8]}
                      for f in sorted(fields)]

        schema_json = _json.dumps(schema_obj).replace("'", "''")
        fields_json = _json.dumps(fields_arr).replace("'", "''")

        consumers = f"ARRAY['engineering-design.html','engineering-bom-sow','engineering-calc-agent']"
        target_cols = "ARRAY['calc_type','project_name','inputs','results','worker_name','hive_id']"

        rows.append(
            f"('{capture_id}', 'form', 'engineering-design.html', "
            f"'{fields_json}'::jsonb, "
            f"'engineering_calcs', {target_cols}, 'edge', "
            f"'{schema_json}'::jsonb, "
            f"{consumers}, "
            f"'Engineering Design {disc} calc. Fields auto-extracted from python-api/calcs/{name}.py inputs.get() calls. Wave 3 batch.')"
        )

    values_sql = ",\n  ".join(rows)
    migration = f"""-- Tier F / Layer 0 — Capture Contracts Wave 3: Engineering Design
-- ({len(rows)} calc-input contracts, 2026-05-12).
--
-- One capture per python-api/calcs/<name>.py handler. Fields extracted
-- from `inputs.get("...")` calls in the calc body. surface=form,
-- target_table=engineering_calcs (every calc writes a row carrying its
-- inputs+results+narrative into that single table).
--
-- Generated by tools/gen_eng_captures.py — re-run that script to refresh
-- after editing any calc handler's input shape.

BEGIN;

INSERT INTO public.canonical_capture_contracts
  (capture_id, surface, source_page, fields, target_table, target_columns, validates_at, contract_schema, consumers, notes)
VALUES
  {values_sql}
ON CONFLICT (capture_id) DO UPDATE
  SET surface         = EXCLUDED.surface,
      source_page     = EXCLUDED.source_page,
      fields          = EXCLUDED.fields,
      target_table    = EXCLUDED.target_table,
      target_columns  = EXCLUDED.target_columns,
      validates_at    = EXCLUDED.validates_at,
      contract_schema = EXCLUDED.contract_schema,
      consumers       = EXCLUDED.consumers,
      notes           = EXCLUDED.notes,
      registered_at   = now();

COMMIT;
"""
    with open(OUTPUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(migration)
    print(f"Wrote {OUTPUT} ({len(rows)} captures)")


if __name__ == "__main__":
    main()
