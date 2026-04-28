"""
Digital Twin Schema Readiness Validator — WorkHive Platform
============================================================
A digital twin is a real-time virtual representation of a physical asset —
it knows the asset's location, current operational status, maintenance history,
and sensor readings. WorkHive's assets, pm_assets, and pm_knowledge tables
are the foundation. This validator ensures they're structurally ready to
become digital twins as IoT connectivity is added.

  Layer 1 — Asset model completeness
    1.  5 minimum DT fields in asset saves  — id/category/location/criticality/hive_id

  Layer 2 — IoT connectivity
    2.  sensor_readings schema              — required fields when table is built (forward guard)

  Layer 3 — Data quality
    3.  Status CHECK constraints            — controlled vocabulary on status fields
    4.  pm_knowledge asset_id FK            — orphaned knowledge records when assets deleted

  Layer 4 — Lifecycle and linkage
    5.  Asset lifecycle state field         — Active/Inactive/Decommissioned for DT health scoring
    6.  Logbook entries carry asset_ref_id  — maintenance history linkable to DT record

Usage:  python validate_digital_twin.py
Output: digital_twin_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

MIGRATIONS_DIR = os.path.join("supabase", "migrations")

ASSET_REQUIRED_DT_FIELDS = ["asset_id", "category", "location", "criticality", "hive_id"]
ASSET_WRITE_PAGES         = ["logbook.html"]
SENSOR_READINGS_REQUIRED  = [
    "asset_id", "sensor_type", "value", "unit", "recorded_at", "quality_flag",
]
STATUS_CONSTRAINED_TABLES = ["automation_log"]
KNOWLEDGE_TABLES_WITH_ASSET = ["pm_knowledge"]

# Pages that save logbook entries — must include asset_ref_id
LOGBOOK_WRITE_PAGES = ["logbook.html"]


def read_all_migrations():
    combined = ""
    if not os.path.isdir(MIGRATIONS_DIR):
        return combined
    for fname in sorted(os.listdir(MIGRATIONS_DIR)):
        if fname.endswith(".sql"):
            c = read_file(os.path.join(MIGRATIONS_DIR, fname))
            if c:
                combined += c
    return combined


# ── Layer 1: Asset model completeness ────────────────────────────────────────

def check_asset_dt_fields(pages, required_fields):
    """Every asset save must include the 5 minimum DT fields — without them
    the digital twin cannot answer WHERE, WHAT TYPE, HOW CRITICAL, or WHO OWNS IT."""
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        if not re.search(r"db\.from\(['\"]assets['\"]\)\.(upsert|insert)\s*\(", content):
            continue
        for field in required_fields:
            if not re.search(rf"\b{re.escape(field)}\s*:", content):
                issues.append({"check": "asset_dt_fields", "page": page,
                               "reason": (f"{page} asset save does not include DT field '{field}' — "
                                          f"digital twin cannot track this attribute")})
    return issues


# ── Layer 2: IoT connectivity ─────────────────────────────────────────────────

def check_sensor_readings_schema(migrations, required_cols):
    """Forward guard: PASS if sensor_readings not built yet.
    FAIL if built without required DT columns."""
    if not migrations:
        return []
    if not re.search(r"CREATE TABLE.*\bsensor_readings\b", migrations, re.IGNORECASE):
        return []
    table_m = re.search(
        r"CREATE TABLE.*\bsensor_readings\b([\s\S]+?)(?=CREATE TABLE|\Z)",
        migrations, re.IGNORECASE
    )
    if not table_m:
        return []
    table_body = table_m.group(1)
    issues = []
    for col in required_cols:
        if not re.search(rf"\b{re.escape(col)}\b", table_body):
            issues.append({"check": "sensor_readings_schema", "table": "sensor_readings",
                           "reason": (f"sensor_readings table missing column '{col}' — "
                                      f"digital twin cannot track this measurement attribute")})
    return issues


# ── Layer 3: Data quality ─────────────────────────────────────────────────────

def check_status_constraints(migrations, tables):
    """Status fields must have CHECK constraints — free-text status breaks MTBF
    grouping queries ('Running' vs 'running' = 2 separate buckets)."""
    if not migrations:
        return []
    issues = []
    for table in tables:
        table_m = re.search(
            rf"CREATE TABLE.*\b{re.escape(table)}\b([\s\S]+?)(?=CREATE TABLE|\Z)",
            migrations, re.IGNORECASE
        )
        if not table_m:
            continue
        table_body = table_m.group(1)
        if not re.search(r"\bstatus\b", table_body, re.IGNORECASE):
            continue
        if not re.search(r"CHECK\s*\([^)]*status[^)]*\)", table_body, re.IGNORECASE):
            issues.append({"check": "status_constraints", "table": table,
                           "reason": (f"Table '{table}' has a status column but no CHECK constraint — "
                                      f"free-text status values break MTBF grouping and ML features; "
                                      f"add: CHECK (status IN ('value1', 'value2', ...))")})
    return issues


def check_knowledge_fk(migrations, tables):
    """pm_knowledge.asset_id should have a FK reference to prevent orphaned
    knowledge records when assets are deleted."""
    if not migrations:
        return []
    issues = []
    for table in tables:
        table_m = re.search(
            rf"CREATE TABLE.*\b{re.escape(table)}\b([\s\S]+?)(?=CREATE TABLE|\Z)",
            migrations, re.IGNORECASE
        )
        if not table_m or "asset_id" not in table_m.group(1):
            continue
        if not re.search(
            r"asset_id\s+uuid\s+REFERENCES|asset_id.*REFERENCES\s+(pm_assets|assets)",
            table_m.group(1), re.IGNORECASE
        ):
            issues.append({"check": "knowledge_fk", "table": table,
                           "skip": True,
                           "reason": (f"Table '{table}' has asset_id but no FK REFERENCES — "
                                      f"orphaned knowledge records accumulate as assets are deleted, "
                                      f"causing semantic search to return stale DT snapshots")})
    return issues


# ── Layer 4: Lifecycle and linkage ────────────────────────────────────────────

def check_asset_lifecycle_state(pages):
    """
    The asset model must include a lifecycle state field (Active / Inactive /
    Decommissioned). Without it, the digital twin cannot distinguish between
    assets in active production, assets taken offline for repair, and assets
    permanently decommissioned. This means:

    - MTBF calculations include failure data from decommissioned assets
    - Maintenance scheduling sends PMs to assets no longer in service
    - Digital twin health scoring treats all assets as equally active
    - The predictive model cannot adjust failure probability for offline assets

    The fix: add a lifecycle or operational_status field to the assets table
    with a CHECK constraint (Active/Inactive/Decommissioned) and include it
    in the logbook.html asset save payload.
    Reported as WARN — functional but limits DT health scoring capability.
    """
    issues = []
    lifecycle_patterns = [
        r"\blifecycle\b", r"\boperational_status\b",
        r"Active.*Inactive.*Decommission",
        r"lifecycle_state", r"asset_status\b",
    ]
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        if not re.search(r"db\.from\(['\"]assets['\"]\)\.(upsert|insert)\s*\(", content):
            continue
        has_lifecycle = any(
            re.search(p, content, re.IGNORECASE) for p in lifecycle_patterns
        )
        if not has_lifecycle:
            issues.append({"check": "asset_lifecycle_state", "page": page,
                           "skip": True,
                           "reason": (f"{page} asset save payload has no lifecycle state field "
                                      f"(Active/Inactive/Decommissioned) — digital twin cannot "
                                      f"distinguish active assets from decommissioned ones; "
                                      f"MTBF and predictive models include stale asset data; "
                                      f"add 'lifecycle' field with CHECK constraint to the assets table")})
    return issues


def check_logbook_asset_linkage(pages):
    """
    Logbook entries must include asset_ref_id in the addEntry() insert payload.
    This UUID FK links the maintenance record to the digital twin asset record,
    enabling:
    - Direct DT query: 'show all maintenance history for this asset'
    - MTBF computation from linked entries (not just machine text matching)
    - Predictive model features tied to the specific physical asset

    Without asset_ref_id, the DT can only match entries by machine name string —
    which breaks when the machine name is inconsistent ('Pump A', 'pump-a', 'PUMP A').
    This is a regression guard — the field is currently included.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        # Find the addEntry function body
        m = re.search(r"async function addEntry\s*\(", content)
        if not m:
            continue
        body = content[m.start():m.start() + 1500]
        if "asset_ref_id" not in body:
            issues.append({"check": "logbook_asset_linkage", "page": page,
                           "reason": (f"{page} addEntry() insert payload does not include "
                                      f"asset_ref_id — logbook entries cannot be linked to the "
                                      f"digital twin asset record; MTBF and predictive models "
                                      f"fall back to unreliable machine name text matching")})
    return issues


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "asset_dt_fields",
    "sensor_readings_schema",
    "status_constraints",
    "knowledge_fk",
    "asset_lifecycle_state",
    "logbook_asset_linkage",
]

CHECK_LABELS = {
    "asset_dt_fields":         "L1  Core asset model has 5 minimum DT fields",
    "sensor_readings_schema":  "L2  sensor_readings table has required DT fields (forward guard)",
    "status_constraints":      "L3  Status fields on analytics tables use CHECK constraints",
    "knowledge_fk":            "L3  pm_knowledge asset_id has FK reference  [WARN]",
    "asset_lifecycle_state":   "L4  Asset model has lifecycle state field (Active/Inactive/Decommissioned)  [WARN]",
    "logbook_asset_linkage":   "L4  Logbook addEntry() carries asset_ref_id FK to DT record",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nDigital Twin Schema Readiness Validator (4-layer)"))
    print("=" * 55)

    migrations = read_all_migrations()

    all_issues = []
    all_issues += check_asset_dt_fields(ASSET_WRITE_PAGES, ASSET_REQUIRED_DT_FIELDS)
    all_issues += check_sensor_readings_schema(migrations, SENSOR_READINGS_REQUIRED)
    all_issues += check_status_constraints(migrations, STATUS_CONSTRAINED_TABLES)
    all_issues += check_knowledge_fk(migrations, KNOWLEDGE_TABLES_WITH_ASSET)
    all_issues += check_asset_lifecycle_state(ASSET_WRITE_PAGES)
    all_issues += check_logbook_asset_linkage(LOGBOOK_WRITE_PAGES)

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "digital_twin",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("digital_twin_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
