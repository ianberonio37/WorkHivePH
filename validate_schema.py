"""
Schema Consistency Validator — WorkHive Platform
=================================================
Checks that the JavaScript code and Supabase schema stay in sync.
Schema drift happens silently — JS writes to a renamed column, a table
gets retired but code still references it, or a date is stored in the
wrong format and SQL queries break.

  Layer 1 — Table integrity
    1.  Retired tables not written  — no INSERT to parts_records / checklist_records
    2.  All db.from() names known   — no typos or undocumented tables
    3.  hive_audit_log NOT NULL cols — insert includes hive_id, actor, action

  Layer 2 — Column integrity
    4.  Timestamp format            — timestamp fields use .toISOString(), not locale strings
    5.  JSONB not stringified       — jsonb columns must not be wrapped in JSON.stringify()
    6.  Migration column coverage   — columns added by ALTER TABLE migrations are used in code

  Layer 3 — Scope completeness
    7.  All live pages in scope     — analytics.html and new pages included in LIVE_PAGES

Usage:  python validate_schema.py
Output: schema_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

MIGRATIONS_DIR = os.path.join("supabase", "migrations")

LIVE_PAGES = [
    "index.html",
    "logbook.html",
    "inventory.html",
    "pm-scheduler.html",
    "hive.html",
    "assistant.html",
    "skillmatrix.html",
    "dayplanner.html",
    "engineering-design.html",
    "analytics.html",
    "nav-hub.html",
    "floating-ai.js",
    "report-sender.html",
    "community.html",
]

RETIRED_TABLES = {"parts_records", "checklist_records"}

CORE_TABLES = {
    "logbook", "assets", "inventory_items", "inventory_transactions",
    "hives", "hive_members", "pm_assets", "pm_scope_items", "pm_completions",
    "report_contacts", "ai_reports", "automation_log",
    "skill_profiles", "skill_badges", "skill_exam_attempts", "schedule_items",
    "engineering_calcs",
    "community_posts", "community_replies", "community_reactions",
}

DATE_FIELDS = [
    "closed_at", "approved_at", "completed_at", "start_time", "end_time",
    "updated_at", "resolved_at",
]

AUDIT_LOG_REQUIRED = ["hive_id", "actor", "action"]

# jsonb columns that must NOT be wrapped in JSON.stringify() before DB insert
JSONB_COLUMNS = ["readings_json", "production_output", "parts_used", "meta", "results", "inputs"]


def read_migrations():
    tables = set()
    if not os.path.isdir(MIGRATIONS_DIR):
        return tables, []
    column_adds = []   # (table, column) pairs from ALTER TABLE ADD COLUMN
    for fname in sorted(os.listdir(MIGRATIONS_DIR)):
        if not fname.endswith(".sql"):
            continue
        content = read_file(os.path.join(MIGRATIONS_DIR, fname))
        if not content:
            continue
        for m in re.finditer(r"^CREATE TABLE(?:\s+IF NOT EXISTS)?\s+(\w+)", content, re.MULTILINE):
            tables.add(m.group(1))
        for m in re.finditer(
            r"ALTER TABLE\s+(\w+)\s+ADD COLUMN(?:\s+IF NOT EXISTS)?\s+(\w+)", content, re.MULTILINE
        ):
            column_adds.append((m.group(1), m.group(2), fname))
    return tables, column_adds


# ── Layer 1: Table integrity ──────────────────────────────────────────────────

def check_retired_tables(pages):
    issues = []
    for page in pages:
        content = read_file(page)
        if not content:
            continue
        for table in RETIRED_TABLES:
            for m in re.finditer(
                rf"db\.from\(['\"]({re.escape(table)})['\"].*?\)\s*\.(insert|upsert)\s*\(",
                content, re.DOTALL
            ):
                line = content[:m.start()].count("\n") + 1
                issues.append({"check": "retired_tables", "page": page, "table": table, "line": line,
                               "reason": f"{page}:{line} INSERT into retired table '{table}'"})
    return issues


def check_unknown_tables(pages, migration_tables):
    known = CORE_TABLES | migration_tables
    issues = []
    seen  = set()
    for page in pages:
        content = read_file(page)
        if not content:
            continue
        for m in re.finditer(r"db\.from\(['\"](\w+)['\"]\)", content):
            table = m.group(1)
            if table in known or table in RETIRED_TABLES or table in seen:
                continue
            seen.add(table)
            line = content[:m.start()].count("\n") + 1
            issues.append({"check": "unknown_tables", "page": page, "table": table, "line": line,
                           "skip": True,   # WARN — table may exist in DB without local migration
                           "reason": f"Table '{table}' in {page}:{line} not in any migration or CORE_TABLES — add a migration or register it"})
    return issues


def check_audit_log_columns(pages):
    issues = []
    for page in pages:
        content = read_file(page)
        if not content or "hive_audit_log" not in content:
            continue
        m = re.search(
            r"db\.from\(['\"]hive_audit_log['\"]\)\.insert\s*\(\s*\{([^}]+)\}",
            content, re.DOTALL
        )
        if not m:
            continue
        payload = m.group(1)
        for col in AUDIT_LOG_REQUIRED:
            if not re.search(r"\b" + re.escape(col) + r"\s*[:,\n}]", payload):
                issues.append({"check": "audit_log_columns", "page": page, "column": col,
                               "reason": f"{page} hive_audit_log insert missing NOT NULL column '{col}' — audit log entries will fail silently"})
    return issues


# ── Layer 2: Column integrity ─────────────────────────────────────────────────

def check_date_format(pages):
    issues = []
    for page in pages:
        content = read_file(page)
        if not content:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            for field in DATE_FIELDS:
                if re.search(rf"\b{re.escape(field)}\s*:\s*.*\.toLocaleDateString\s*\(", line):
                    issues.append({"check": "date_format", "page": page, "field": field, "line": i + 1,
                                   "reason": f"{page}:{i+1} '{field}' uses .toLocaleDateString() — SQL date queries will break, use .toISOString()"})
    return issues


def check_jsonb_not_stringified(pages):
    """
    jsonb columns in Supabase must receive a JS object, not JSON.stringify(obj).
    JSON.stringify wraps the object in a string, storing '"{\\"key\\":\\"val\\"}"'
    instead of {"key":"val"}. This silently breaks jsonb operators in SQL.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if not content:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            for col in JSONB_COLUMNS:
                if re.search(rf"\b{re.escape(col)}\s*:\s*JSON\.stringify\s*\(", line):
                    issues.append({"check": "jsonb_not_stringified", "page": page,
                                   "column": col, "line": i + 1,
                                   "reason": f"{page}:{i+1} jsonb column '{col}' wrapped in JSON.stringify() — pass the raw JS object directly; Supabase handles serialization"})
    return issues


def check_migration_column_coverage(pages, column_adds):
    """
    When a migration adds a column to a table (ALTER TABLE X ADD COLUMN Y),
    the corresponding frontend page should reference that column in at least
    one insert or update payload. If not, the migration ran but the data
    is never being saved — the feature is silently broken.
    """
    issues = []
    # Only check columns on tables that have a clear owning page
    TABLE_TO_PAGE = {
        "logbook":            "logbook.html",
        "inventory_items":    "inventory.html",
        "pm_assets":          "pm-scheduler.html",
        "hive_members":       "hive.html",
    }
    for table, column, migration_file in column_adds:
        page = TABLE_TO_PAGE.get(table)
        if not page:
            continue
        content = read_file(page)
        if not content:
            continue
        # Check if the column name appears anywhere in the file (as a field reference)
        if not re.search(rf"\b{re.escape(column)}\b", content):
            issues.append({"check": "migration_column_coverage",
                           "page": page, "table": table, "column": column,
                           "migration": migration_file,
                           "reason": f"Migration '{migration_file}' adds column '{column}' to '{table}' but {page} never references it — data from this migration is never saved"})
    return issues


def check_python_analytics_column_alignment():
    """
    Python descriptive.py references logbook columns by name using df["col"].
    If a column is referenced but was never added to the logbook schema
    (not in migrations), the analytics orchestrator never SELECTs it, so
    the Python DataFrame will never have that column — producing KeyError
    or always-null results.

    This check extracts every df["col"] reference from descriptive.py,
    then verifies it exists in either the analytics orchestrator SELECT
    (the definitive list of what Python receives) or in migration column adds.

    Problem 04 (Schema Drift): a renamed column in a migration breaks
    Python analytics silently — this guard catches the mismatch at code level.
    """
    import os as _os
    descriptive_path = _os.path.join("python-api", "analytics", "descriptive.py")
    orch_path        = _os.path.join("supabase", "functions", "analytics-orchestrator", "index.ts")

    py_content   = read_file(descriptive_path)
    orch_content = read_file(orch_path)
    if py_content is None or orch_content is None:
        return []

    # Extract column names Python reads from logbook-like DataFrames
    py_cols = set(re.findall(r'df\s*\[\s*["\']([^"\']+)["\']', py_content))
    # Also get df.get() patterns
    py_cols |= set(re.findall(r'df\.get\s*\(\s*["\']([^"\']+)["\']', py_content))

    # These columns are from inventory_transactions, not logbook — exempt
    TXN_COLS = {"type", "qty_change", "part_name", "created_at"}

    # What does the orchestrator SELECT from logbook? Find the logbook-specific select
    # (look for the select following a .from("logbook") reference)
    logbook_select_m = re.search(
        r'from\s*\(\s*["\']logbook["\'][\s\S]{0,200}?\.select\s*\(\s*["\']([^"\']+)["\']',
        orch_content
    )
    orch_cols = set()
    if logbook_select_m:
        orch_cols = {c.strip() for c in logbook_select_m.group(1).split(",")}

    issues = []
    for col in sorted(py_cols - TXN_COLS):
        if col in orch_cols:
            continue
        if col in ("created_at", "status"):  # universal audit columns
            continue
        issues.append({"check": "python_analytics_column_alignment",
                       "skip": True,
                       "reason": (f"descriptive.py references df['{col}'] but '{col}' is not in "
                                  f"the analytics-orchestrator logbook SELECT — Python may receive "
                                  f"an empty or missing column; verify the orchestrator SELECT includes "
                                  f"'{col}' or remove the reference from descriptive.py")})
    return issues


# ── Layer 3: Scope completeness ───────────────────────────────────────────────

def check_pages_in_scope():
    import glob
    live_set = set(LIVE_PAGES)
    issues   = []
    for path in glob.glob("*.html") + glob.glob("*.js"):
        fname = os.path.basename(path)
        if fname in live_set:
            continue
        if any(s in fname for s in ["-test", ".backup", "platform-health", "guardian",
                                     "parts-tracker", "symbol-gallery", "architecture"]):
            continue
        content = read_file(fname)
        if content and "db.from(" in content:
            issues.append({"check": "pages_in_scope", "page": fname,
                           "reason": f"{fname} uses db.from() but is not in validate_schema.py LIVE_PAGES — schema checks never run on it"})
    return issues


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    # L1
    "retired_tables", "unknown_tables", "audit_log_columns",
    # L2
    "date_format", "jsonb_not_stringified", "migration_column_coverage",
    # L3
    "pages_in_scope",
    "python_analytics_column_alignment",
]

CHECK_LABELS = {
    # L1
    "retired_tables":            "L1  No INSERT to retired tables",
    "unknown_tables":            "L1  All db.from() table names known  [WARN]",
    "audit_log_columns":         "L1  hive_audit_log NOT NULL columns present",
    # L2
    "date_format":               "L2  Timestamp fields use .toISOString()",
    "jsonb_not_stringified":     "L2  jsonb columns not wrapped in JSON.stringify()",
    "migration_column_coverage": "L2  New migration columns referenced in frontend",
    # L3
    "pages_in_scope":                        "L3  All DB-using pages in LIVE_PAGES",
    "python_analytics_column_alignment":     "L4  Python analytics df[] columns exist in orchestrator SELECT  [WARN]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nSchema Consistency Validator (4-layer)"))
    print("=" * 55)

    migration_tables, column_adds = read_migrations()
    print(f"  {len(migration_tables)} migration tables, {len(column_adds)} ADD COLUMN entries\n")

    all_issues = []
    all_issues += check_retired_tables(LIVE_PAGES)
    all_issues += check_unknown_tables(LIVE_PAGES, migration_tables)
    all_issues += check_audit_log_columns(LIVE_PAGES)
    all_issues += check_date_format(LIVE_PAGES)
    all_issues += check_jsonb_not_stringified(LIVE_PAGES)
    all_issues += check_migration_column_coverage(LIVE_PAGES, column_adds)
    all_issues += check_pages_in_scope()
    all_issues += check_python_analytics_column_alignment()

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":       "schema",
        "total_checks":    total,
        "passed":          n_pass,
        "warned":          n_warn,
        "failed":          n_fail,
        "migration_tables": sorted(migration_tables),
        "column_adds":     [(t, c, f) for t, c, f in column_adds],
        "issues":          [i for i in all_issues if not i.get("skip")],
        "warnings":        [i for i in all_issues if i.get("skip")],
    }
    with open("schema_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
