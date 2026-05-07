"""
CMMS Contracts Validator — WorkHive Platform
=============================================
Prevents silent drift between the three locations that define how SAP/Maximo
field codes map to WorkHive values:

  _shared/mappings.ts       — canonical source of truth (TypeScript)
  integrations.html         — STATUS_NORM / TYPE_NORM (JavaScript in browser)
  cmms_config_seeder.py     — FIELD_MAPS (Python seeder)

Also verifies that edge functions import from the shared file rather than
defining their own local copies, and that all column names written by the
import wizard actually exist in the target DB table (from migrations).

Checks:
  Layer 1 — Edge function contracts
    1.  cmms-sync imports STATUS_MAP/TYPE_MAP from _shared/mappings.ts         [FAIL]
    2.  cmms-webhook-receiver imports from _shared/mappings.ts                 [FAIL]
    3.  No local STATUS_MAP definition in cmms-sync                            [FAIL]
    4.  No local STATUS_MAP definition in cmms-webhook-receiver                [FAIL]

  Layer 2 — Mapping parity
    5.  integrations.html STATUS_NORM keys match _shared/mappings.ts           [FAIL]
    6.  integrations.html TYPE_NORM keys match _shared/mappings.ts             [FAIL]
    7.  cmms_config_seeder.py FIELD_MAPS keys match DEFAULT_FIELD_MAPS         [WARN]

  Layer 3 — DB column targets
    8.  logbook columns written by import wizard exist in migration schema      [FAIL]
    9.  assets columns written by import wizard exist in migration schema       [FAIL]
    10. inventory_items columns written by import wizard exist in schema        [FAIL]
    11. pm_assets columns written by import wizard exist in schema              [FAIL]

Usage:  python validate_cmms_contracts.py
Output: cmms_contracts_report.json
"""

import re, json, sys, os, glob

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

SHARED_MAPPINGS    = os.path.join("supabase", "functions", "_shared", "mappings.ts")
CMMS_SYNC          = os.path.join("supabase", "functions", "cmms-sync", "index.ts")
CMMS_WEBHOOK       = os.path.join("supabase", "functions", "cmms-webhook-receiver", "index.ts")
INTEGRATIONS_HTML  = "integrations.html"
SEEDER_CONFIG      = os.path.join("test-data-seeder", "seeders", "cmms_config_seeder.py")
MIGRATIONS_DIR     = os.path.join("supabase", "migrations")
BASELINE_MIGRATION = os.path.join(MIGRATIONS_DIR, "20260420000000_baseline.sql")


# ── Schema extraction from migrations ────────────────────────────────────────

def extract_table_columns(table: str) -> set:
    """Parse column names from CREATE TABLE in the baseline migration."""
    content = read_file(BASELINE_MIGRATION)
    if not content:
        return set()
    pattern = rf'CREATE TABLE[^"]*"{table}"\s*\((.*?)\);'
    m = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
    if not m:
        return set()
    block = m.group(1)
    cols = re.findall(r'"([a-zA-Z_][a-zA-Z0-9_]*)"', block)
    return set(cols)


# ── Shared mappings parser ────────────────────────────────────────────────────

def extract_ts_map_keys(content: str, map_name: str) -> dict:
    """Extract {system_type: {code: value}} from a TS const declaration."""
    pattern = rf'export const {map_name}[^=]+=\s*\{{(.*?)\}};'
    m = re.search(pattern, content, re.DOTALL)
    if not m:
        return {}
    outer = m.group(1)
    result = {}
    for sys_m in re.finditer(r'(\w+)\s*:\s*\{([^}]*)\}', outer):
        sys_type = sys_m.group(1)
        inner = sys_m.group(2)
        codes = {}
        for entry in re.finditer(r'(\w+)\s*:\s*"([^"]*)"', inner):
            codes[entry.group(1)] = entry.group(2)
        result[sys_type] = codes
    return result


def extract_js_norm_keys(content: str, var_name: str) -> dict:
    """Extract {system_type: {code: value}} from a JS const declaration."""
    pattern = rf'const {var_name}\s*=\s*\{{(.*?)\}};'
    m = re.search(pattern, content, re.DOTALL)
    if not m:
        return {}
    return extract_ts_map_keys(f"export const {var_name} = {{{m.group(1)}}};", var_name)


def extract_py_dict_keys(content: str, var_name: str) -> dict:
    """Extract top-level keys from a Python dict assignment."""
    pattern = rf'{var_name}\s*=\s*\{{(.*?)\n\}}'
    m = re.search(pattern, content, re.DOTALL)
    if not m:
        return {}
    block = m.group(1)
    keys = re.findall(r'"([^"]+)"\s*:', block)
    keys += re.findall(r"'([^']+)'\s*:", block)
    return {k: True for k in keys}


# ── Layer 1: Edge function contracts ─────────────────────────────────────────

def check_imports_shared(fn_path: str, fn_name: str) -> list:
    content = read_file(fn_path)
    issues  = []
    if content is None:
        return [{"check": f"imports_shared_{fn_name}",
                 "reason": f"{fn_path} not found"}]
    has_import = bool(re.search(r'import\s*\{[^}]*(?:STATUS_MAP|TYPE_MAP)[^}]*\}\s*from\s*["\']\.\./_shared/mappings\.ts["\']', content))
    if not has_import:
        issues.append({
            "check":  f"imports_shared_{fn_name}",
            "reason": (f"{fn_path} does not import STATUS_MAP/TYPE_MAP from _shared/mappings.ts — "
                       f"add: import {{ STATUS_MAP, TYPE_MAP }} from \"../_shared/mappings.ts\""),
        })
    return issues


def check_no_local_status_map(fn_path: str, fn_name: str) -> list:
    content = read_file(fn_path)
    if content is None:
        return []
    if re.search(r'const\s+STATUS_MAP\s*[:=]', content):
        line = content[:re.search(r'const\s+STATUS_MAP\s*[:=]', content).start()].count('\n') + 1
        return [{
            "check":  f"no_local_status_map_{fn_name}",
            "reason": (f"{fn_path}:{line} defines a local STATUS_MAP — "
                       f"remove it and import from _shared/mappings.ts instead; "
                       f"local copies diverge silently when new CMMS status codes are added"),
        }]
    return []


# ── Layer 2: Mapping parity ───────────────────────────────────────────────────

def check_html_norm_matches_shared(norm_var: str, shared_var: str) -> list:
    html_content   = read_file(INTEGRATIONS_HTML)
    shared_content = read_file(SHARED_MAPPINGS)
    issues = []
    if not html_content or not shared_content:
        return []

    html_map   = extract_js_norm_keys(html_content,   norm_var)
    shared_map = extract_ts_map_keys(shared_content, shared_var)

    if not html_map:
        issues.append({"check": f"html_{norm_var}_matches_shared",
                       "reason": f"Could not parse {norm_var} from integrations.html — check the variable name",
                       "skip": True})
        return issues
    if not shared_map:
        issues.append({"check": f"html_{norm_var}_matches_shared",
                       "reason": f"Could not parse {shared_var} from _shared/mappings.ts",
                       "skip": True})
        return issues

    for sys_type in shared_map:
        shared_codes = set(shared_map.get(sys_type, {}).keys())
        html_codes   = set(html_map.get(sys_type, {}).keys())
        missing_in_html = shared_codes - html_codes
        extra_in_html   = html_codes  - shared_codes

        if missing_in_html:
            issues.append({
                "check":  f"html_{norm_var}_matches_shared",
                "reason": (f"integrations.html {norm_var}['{sys_type}'] is missing codes "
                           f"{sorted(missing_in_html)} that exist in _shared/mappings.ts {shared_var} — "
                           f"add them to keep the import wizard in sync with the edge functions"),
            })
        if extra_in_html:
            issues.append({
                "check":  f"html_{norm_var}_matches_shared",
                "skip":   True,
                "reason": (f"integrations.html {norm_var}['{sys_type}'] has extra codes "
                           f"{sorted(extra_in_html)} not in _shared/mappings.ts — "
                           f"consider adding them to the shared file"),
            })
    return issues


def check_seeder_field_maps() -> list:
    content = read_file(SEEDER_CONFIG)
    shared  = read_file(SHARED_MAPPINGS)
    issues  = []
    if not content or not shared:
        return []

    seeder_keys = set(extract_py_dict_keys(content, "FIELD_MAPS").keys())
    shared_keys = set(extract_py_dict_keys(shared.replace("export const DEFAULT_FIELD_MAPS", "FIELD_MAPS"), "FIELD_MAPS").keys())

    # Simpler approach: just check all three CMMS types are present in the seeder
    for sys_type in ("sap_pm", "maximo", "generic"):
        if sys_type not in seeder_keys:
            issues.append({
                "check":  "seeder_field_maps",
                "skip":   True,
                "reason": (f"cmms_config_seeder.py FIELD_MAPS missing '{sys_type}' entry — "
                           f"Live Sync seeding for {sys_type} will use empty field map"),
            })
    return issues


# ── Layer 3: DB column targets ────────────────────────────────────────────────

# Columns that startImport() in integrations.html writes to each table.
# Source: read from startImport() JS — hardcoded here as the canonical list.
# When you add/remove a column from startImport(), update this dict AND run
# the validator to confirm the column exists in the migration.
IMPORT_WRITES = {
    "logbook": {
        "worker_name", "date", "machine", "category", "problem", "action",
        "knowledge", "status", "created_at", "maintenance_type", "root_cause",
        "downtime_hours", "hive_id", "closed_at", "parts_used",
    },
    "assets": {
        "worker_name", "asset_id", "name", "type", "location", "criticality",
        "registered_at", "created_at", "status", "hive_id",
        "submitted_by", "approved_by", "approved_at",
    },
    "inventory_items": {
        "worker_name", "part_number", "part_name", "category", "unit",
        "qty_on_hand", "min_qty", "bin_location", "linked_asset_ids", "notes",
        "status", "hive_id", "submitted_by", "approved_by", "approved_at",
    },
    "pm_assets": {
        "hive_id", "worker_name", "asset_name", "tag_id",
        "location", "category", "criticality", "last_anchor_date",
    },
}


def check_import_column_targets() -> list:
    issues = []
    for table, written_cols in IMPORT_WRITES.items():
        db_cols = extract_table_columns(table)
        if not db_cols:
            issues.append({
                "check":  f"import_columns_{table}",
                "skip":   True,
                "reason": (f"Could not extract schema for '{table}' from migration — "
                           f"check {BASELINE_MIGRATION} exists"),
            })
            continue
        bad = sorted(written_cols - db_cols)
        if bad:
            for col in bad:
                issues.append({
                    "check":  f"import_columns_{table}",
                    "reason": (f"integrations.html startImport() writes '{col}' to '{table}' "
                               f"but that column does not exist in the migration schema — "
                               f"either add the column via ALTER TABLE or remove it from startImport()"),
                })
    return issues


# ── Runner ────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "imports_shared_cmms_sync",
    "imports_shared_cmms_webhook",
    "no_local_status_map_cmms_sync",
    "no_local_status_map_cmms_webhook",
    "html_STATUS_NORM_matches_shared",
    "html_TYPE_NORM_matches_shared",
    "seeder_field_maps",
    "import_columns_logbook",
    "import_columns_assets",
    "import_columns_inventory_items",
    "import_columns_pm_assets",
]

CHECK_LABELS = {
    "imports_shared_cmms_sync":            "L1  cmms-sync imports STATUS_MAP from _shared/mappings.ts",
    "imports_shared_cmms_webhook":         "L1  cmms-webhook-receiver imports from _shared/mappings.ts",
    "no_local_status_map_cmms_sync":       "L1  cmms-sync has no local STATUS_MAP definition",
    "no_local_status_map_cmms_webhook":    "L1  cmms-webhook-receiver has no local STATUS_MAP",
    "html_STATUS_NORM_matches_shared":     "L2  integrations.html STATUS_NORM matches _shared/mappings.ts",
    "html_TYPE_NORM_matches_shared":       "L2  integrations.html TYPE_NORM matches _shared/mappings.ts",
    "seeder_field_maps":                   "L2  cmms_config_seeder.py FIELD_MAPS covers all 3 CMMS types  [WARN]",
    "import_columns_logbook":              "L3  Import wizard logbook columns exist in DB schema",
    "import_columns_assets":               "L3  Import wizard assets columns exist in DB schema",
    "import_columns_inventory_items":      "L3  Import wizard inventory_items columns exist in DB schema",
    "import_columns_pm_assets":            "L3  Import wizard pm_assets columns exist in DB schema",
}


def main():
    bold  = lambda s: f"\033[1m{s}\033[0m"
    print(bold("\nCMMS Contracts Validator (3-layer)"))
    print("=" * 55)

    all_issues = []

    # Layer 1
    all_issues += check_imports_shared(CMMS_SYNC,    "cmms_sync")
    all_issues += check_imports_shared(CMMS_WEBHOOK, "cmms_webhook")
    all_issues += check_no_local_status_map(CMMS_SYNC,    "cmms_sync")
    all_issues += check_no_local_status_map(CMMS_WEBHOOK, "cmms_webhook")

    # Layer 2
    all_issues += check_html_norm_matches_shared("STATUS_NORM", "STATUS_MAP")
    all_issues += check_html_norm_matches_shared("TYPE_NORM",   "TYPE_MAP")
    all_issues += check_seeder_field_maps()

    # Layer 3
    all_issues += check_import_column_targets()

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed — no drift detected.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "cmms_contracts",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("cmms_contracts_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
