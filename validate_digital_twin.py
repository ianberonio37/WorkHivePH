"""
Digital Twin Schema Readiness Validator — WorkHive Platform
============================================================
A digital twin is a real-time virtual representation of a physical asset —
it knows the asset's location, current operational status, maintenance history,
and sensor readings. WorkHive's `assets`, `pm_assets`, and `pm_knowledge`
tables are the foundation. This validator ensures they're structurally ready
to become digital twins as IoT connectivity is added.

From the Integration Engineer skill (MQTT pattern, sensor_readings),
Research Topic 5 (ISO 23247 digital twin), Predictive Analytics skill.

Four things checked:

  1. Core asset model has the 5 minimum digital twin fields
     — Every asset must carry: a stable identifier (asset_id), a category
       (type grouping), a location (spatial context), a criticality level
       (maintenance priority), and a hive_id (ownership/tenant scoping).
       Without these 5 fields, the digital twin cannot answer the most
       basic questions: "Where is this asset?", "How critical is it?",
       and "Who owns it?"

  2. sensor_readings table schema includes DT required fields
     — When IoT sensors are connected via MQTT/OPC-UA, a sensor_readings
       table will store telemetry. It must have: asset_id (FK to asset),
       sensor_type (what's being measured), value (the reading), unit
       (dimensional units), recorded_at (UTC timestamp), and quality_flag
       (Good/Uncertain/Bad — marks stale or invalid readings).
       Forward guard: PASS if table not built yet. FAIL if built without
       required fields.

  3. Status fields on knowledge/analytics tables use CHECK constraints
     — Tables that track state (automation_log, any operational status)
       must use CHECK constraints to enforce a controlled vocabulary.
       Free-text status fields break MTBF grouping queries: 'Running'
       and 'running' and 'RUNNING' produce three separate buckets instead
       of one. Forward guard for when operational_status is added.

  4. pm_knowledge.asset_id has a FK reference to the assets table
     — The pm_knowledge knowledge base table stores asset health snapshots
       for semantic search. Its asset_id column is currently a bare uuid
       with no FK constraint — records can reference deleted or nonexistent
       assets silently. For digital twin integrity, asset references must
       be enforced at the DB level.

Usage:  python validate_digital_twin.py
Output: digital_twin_report.json
"""
import re, json, sys, os

MIGRATIONS_DIR = os.path.join("supabase", "migrations")

# The 5 minimum fields every asset record must carry for digital twin use
ASSET_REQUIRED_DT_FIELDS = ["asset_id", "category", "location", "criticality", "hive_id"]

# Pages that save to the assets table — all must include DT fields
ASSET_WRITE_PAGES = ["logbook.html"]  # primary asset creation page

# Required columns for a sensor_readings table (when built)
SENSOR_READINGS_REQUIRED = [
    "asset_id",      # FK to the asset being monitored
    "sensor_type",   # what parameter is being measured
    "value",         # the numeric reading
    "unit",          # dimensional unit (°C, bar, Hz, mm/s)
    "recorded_at",   # UTC timestamp of the reading
    "quality_flag",  # Good / Uncertain / Bad data quality marker
]

# Tables that have status fields — must use CHECK constraints or enum
STATUS_CONSTRAINED_TABLES = ["automation_log"]

# Knowledge tables where asset_id should reference the assets table
KNOWLEDGE_TABLES_WITH_ASSET = ["pm_knowledge"]


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


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


# ── Check 1: Core asset model has the 5 minimum DT fields ────────────────────

def check_asset_dt_fields(pages, required_fields):
    """
    When a worker saves an asset, it must include all 5 minimum digital twin
    fields. The save operation in logbook.html and inventory.html constructs
    the asset payload — each required field must appear in the save payload.

    Missing fields mean the digital twin cannot:
    - Answer WHERE questions (no location)
    - Answer WHAT TYPE questions (no category)
    - Prioritise maintenance (no criticality)
    - Scope to the right team (no hive_id)
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue

        # Check if this page saves to assets at all
        has_assets_upsert = bool(re.search(
            r"db\.from\(['\"]assets['\"]\)\.(upsert|insert)\s*\(",
            content
        ))
        if not has_assets_upsert:
            continue

        # The asset payload often uses spread syntax ({ ...asset, ... }) so
        # fields are defined in an object built before the upsert call.
        # Scan the entire file for field declarations near asset data.
        for field in required_fields:
            # Field should appear somewhere as a key in the code
            if not re.search(rf"\b{re.escape(field)}\s*:", content):
                issues.append({
                    "page":  page,
                    "field": field,
                    "reason": (
                        f"{page} — assets save operations do not include "
                        f"DT field '{field}' anywhere in the file — "
                        f"digital twin cannot track this attribute for the asset"
                    ),
                })
    return issues


# ── Check 2: sensor_readings table has required DT fields ────────────────────

def check_sensor_readings_schema(migrations, required_cols):
    """
    When IoT sensors are connected (via MQTT or OPC-UA), a sensor_readings
    table will store the telemetry. For digital twin integrity, it must have
    all required fields at creation time.

    Forward guard: PASS if table not yet built.
    FAIL if it exists but is missing required columns.
    """
    issues = []
    if not migrations:
        return []

    has_table = bool(re.search(
        r"CREATE TABLE.*\bsensor_readings\b",
        migrations, re.IGNORECASE
    ))
    if not has_table:
        return []   # forward guard — table not built yet

    # Table exists — find its CREATE TABLE block
    table_m = re.search(
        r"CREATE TABLE.*\bsensor_readings\b([\s\S]+?)(?=CREATE TABLE|\Z)",
        migrations, re.IGNORECASE
    )
    if not table_m:
        return []

    table_body = table_m.group(1)
    for col in required_cols:
        if not re.search(rf"\b{re.escape(col)}\b", table_body):
            issues.append({
                "table": "sensor_readings",
                "col":   col,
                "reason": (
                    f"sensor_readings table is missing column '{col}' — "
                    f"digital twin cannot track this measurement attribute"
                ),
            })
    return issues


# ── Check 3: Status fields use CHECK constraints ──────────────────────────────

def check_status_constraints(migrations, tables):
    """
    Tables that track operational state must use CHECK constraints to enforce
    a controlled vocabulary on their status fields.

    Without constraints:
    - 'Running' and 'running' and 'RUNNING' are 3 different values
    - MTBF queries group by status and get fragmented buckets
    - ML models trained on the data learn incorrect feature boundaries

    The automation_log table already has:
      CHECK (status IN ('success', 'failed', 'skipped'))
    This is the pattern to follow for any new operational status field.
    """
    issues = []
    if not migrations:
        return []

    for table in tables:
        # Find the CREATE TABLE block for this table
        table_m = re.search(
            rf"CREATE TABLE.*\b{re.escape(table)}\b([\s\S]+?)(?=CREATE TABLE|\Z)",
            migrations, re.IGNORECASE
        )
        if not table_m:
            continue

        table_body = table_m.group(1)

        # Does it have a status column?
        if not re.search(r"\bstatus\b", table_body, re.IGNORECASE):
            continue

        # Does it have a CHECK constraint on status?
        has_check = bool(re.search(
            r"CHECK\s*\([^)]*status[^)]*\)",
            table_body, re.IGNORECASE
        ))
        if not has_check:
            issues.append({
                "table": table,
                "reason": (
                    f"Table '{table}' has a status column but no "
                    f"CHECK constraint — free-text status values break "
                    f"MTBF grouping queries and ML feature consistency. "
                    f"Add: CHECK (status IN ('value1', 'value2', ...))"
                ),
            })
    return issues


# ── Check 4: pm_knowledge.asset_id has FK reference ──────────────────────────

def check_knowledge_fk(migrations, tables):
    """
    Knowledge base tables that reference assets by asset_id must use a
    proper FK constraint (REFERENCES pm_assets(id) or REFERENCES assets).

    Without FK:
    - pm_knowledge can accumulate rows referencing deleted assets
    - Semantic search returns orphaned records with no physical asset
    - Digital twin queries join on a UUID with no referential guarantee

    Note: pm_knowledge uses asset_id (uuid) not an FK — this is flagged
    as a WARN (orphaned records are a data quality risk, not a crash).
    """
    issues = []
    if not migrations:
        return []

    for table in tables:
        table_m = re.search(
            rf"CREATE TABLE.*\b{re.escape(table)}\b([\s\S]+?)(?=CREATE TABLE|\Z)",
            migrations, re.IGNORECASE
        )
        if not table_m:
            continue

        table_body = table_m.group(1)

        # Does it have an asset_id column?
        if "asset_id" not in table_body:
            continue

        # Does it have a FK reference for asset_id?
        has_fk = bool(re.search(
            r"asset_id\s+uuid\s+REFERENCES|asset_id.*REFERENCES\s+(pm_assets|assets)",
            table_body, re.IGNORECASE
        ))
        if not has_fk:
            issues.append({
                "table": table,
                "reason": (
                    f"Table '{table}' has an asset_id column but no FK "
                    f"REFERENCES constraint — orphaned knowledge records "
                    f"will accumulate as assets are deleted, causing semantic "
                    f"search to return stale digital twin snapshots"
                ),
            })
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("\n" + "=" * 70)
print("Digital Twin Schema Readiness Validator")
print("=" * 70)

migrations = read_all_migrations()
fail_count = 0
warn_count = 0
report     = {}

checks = [
    (
        "[1] Core asset model has 5 minimum DT fields (id/category/location/criticality/hive)",
        check_asset_dt_fields(ASSET_WRITE_PAGES, ASSET_REQUIRED_DT_FIELDS),
        "FAIL",
    ),
    (
        "[2] sensor_readings table has required DT fields (when built)",
        check_sensor_readings_schema(migrations, SENSOR_READINGS_REQUIRED),
        "FAIL",
    ),
    (
        "[3] Status fields on analytics/automation tables use CHECK constraints",
        check_status_constraints(migrations, STATUS_CONSTRAINED_TABLES),
        "FAIL",
    ),
    (
        "[4] Knowledge tables with asset_id have FK reference (DT data integrity)",
        check_knowledge_fk(migrations, KNOWLEDGE_TABLES_WITH_ASSET),
        "WARN",
    ),
]

for label, issues, severity in checks:
    print(f"\n{label}\n")
    if not issues:
        print("  PASS")
    else:
        for iss in issues:
            print(f"  {severity}  {iss.get('page', iss.get('table', '?'))}")
            print(f"        {iss['reason']}")
        if severity == "FAIL":
            fail_count += len(issues)
        else:
            warn_count += len(issues)
    report[label] = issues

print(f"\n{'=' * 70}")
print(f"Result: {fail_count} FAIL  {warn_count} WARN")

with open("digital_twin_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved digital_twin_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll digital twin readiness checks PASS.")
