"""
Schema Consistency Validator — WorkHive Platform
=================================================
Checks that the JavaScript code and Supabase schema stay in sync.
Schema drift happens silently — JS writes to a renamed column, a table
gets retired but code still references it, or a date is stored in the
wrong format and SQL queries break.

Checks:
  1. Retired table guard     — INSERT calls to retired tables must not exist
                               in live pages (parts_records, checklist_records)

  2. Migration column align  — hive_audit_log inserts must include all 3
                               NOT NULL columns defined in the migration file

  3. Unknown table names     — every db.from('X') in live pages must reference
                               a known table (catches typos and undocumented tables)

  4. Date format in DB writes — timestamp fields (closed_at, approved_at, etc.)
                               must use .toISOString(), not .toLocaleDateString()
                               A locale string like "4/27/2026" breaks SQL date queries

Usage:  python validate_schema.py
Output: schema_report.json
"""
import re, json, sys, os

MIGRATIONS_DIR = os.path.join("supabase", "migrations")

# Live pages to scan — test files and retired pages are excluded
LIVE_PAGES = [
    "logbook.html",
    "inventory.html",
    "pm-scheduler.html",
    "hive.html",
    "assistant.html",
    "skillmatrix.html",
    "dayplanner.html",
    "engineering-design.html",
    "nav-hub.html",
    "floating-ai.js",
]

# Tables that are retired — must not appear in INSERT calls in live pages
RETIRED_TABLES = {"parts_records", "checklist_records"}

# Core platform tables (exist in Supabase from initial setup, no local migration needed)
CORE_TABLES = {
    "logbook", "assets", "inventory_items", "inventory_transactions",
    "hives", "hive_members", "pm_assets", "pm_scope_items", "pm_completions",
    "skill_profiles", "skill_badges", "skill_exam_attempts", "schedule_items",
    "engineering_calcs",   # exists in live DB, migration pending
}

# Timestamp fields that must always store ISO 8601 (toISOString), not locale strings
DATE_FIELDS = [
    "closed_at", "approved_at", "completed_at", "start_time", "end_time",
    "updated_at", "resolved_at",
]

# hive_audit_log: NOT NULL columns from 20260425000000_hive_audit_log.sql
AUDIT_LOG_REQUIRED = ["hive_id", "actor", "action"]


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def read_migrations():
    """Return set of table names defined in any migration file."""
    tables = set()
    if not os.path.isdir(MIGRATIONS_DIR):
        return tables
    for fname in os.listdir(MIGRATIONS_DIR):
        if not fname.endswith(".sql"):
            continue
        content = read_file(os.path.join(MIGRATIONS_DIR, fname))
        if content:
            for m in re.finditer(r"^CREATE TABLE(?:\s+IF NOT EXISTS)?\s+(\w+)", content, re.MULTILINE):
                tables.add(m.group(1))
    return tables


# ── Check 1: No retired table INSERT calls in live pages ─────────────────────

def check_retired_tables(pages):
    """
    Retired tables (parts_records, checklist_records) must not appear in
    active INSERT statements in live pages. Reading or commenting about
    a retired table is OK — writing to it is not.
    If this fires, it means a live page is still writing to a table that
    no longer exists or is no longer maintained.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        for table in RETIRED_TABLES:
            # Only flag actual .insert( or .upsert( calls, not comments or reads
            pattern = rf"db\.from\(['\"]({re.escape(table)})['\"][^)]*\)\s*\.(insert|upsert)\s*\("
            matches = re.finditer(pattern, content)
            for m in matches:
                line_no = content[:m.start()].count("\n") + 1
                issues.append({
                    "page":  page,
                    "table": table,
                    "line":  line_no,
                    "reason": (
                        f"{page}:{line_no} — INSERT into retired table "
                        f"'{table}' — this table is no longer maintained"
                    ),
                })
    return issues


# ── Check 2: hive_audit_log inserts include required columns ─────────────────

def check_audit_log_columns(pages):
    """
    The migration file defines hive_id, actor, and action as NOT NULL.
    The writeAuditLog() function must include all three in its insert payload.
    If any are missing, audit log entries will fail silently.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        if "hive_audit_log" not in content:
            continue

        # Find the hive_audit_log insert block
        m = re.search(
            r"db\.from\(['\"]hive_audit_log['\"]\)\.insert\s*\(\s*\{([^}]+)\}",
            content, re.DOTALL
        )
        if not m:
            continue

        payload = m.group(1)
        for col in AUDIT_LOG_REQUIRED:
            # Match both:  col: value  (explicit)  AND  col,  /  col\n  (ES6 shorthand)
            pat = r"\b" + re.escape(col) + r"\s*[:,\n}]"
            if not re.search(pat, payload):
                issues.append({
                    "page":   page,
                    "column": col,
                    "reason": (
                        f"{page} — hive_audit_log insert missing required column "
                        f"'{col}' (NOT NULL in migration 20260425000000) — "
                        f"audit log entries will fail silently"
                    ),
                })
    return issues


# ── Check 3: No unknown table names in live pages ────────────────────────────

def check_unknown_tables(pages, migration_tables):
    """
    Every db.from('X') call in live pages must reference a table that is
    either a core platform table or defined in a migration file.
    Unknown names are likely typos or undocumented tables that have no
    migration — if the database is recreated, these tables won't exist.
    """
    known = CORE_TABLES | migration_tables
    issues = []
    seen = set()   # avoid duplicate reports for the same table

    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        for m in re.finditer(r"db\.from\(['\"](\w+)['\"]\)", content):
            table = m.group(1)
            if table in known or table in RETIRED_TABLES or table in seen:
                continue
            seen.add(table)
            line_no = content[:m.start()].count("\n") + 1
            issues.append({
                "page":  page,
                "table": table,
                "line":  line_no,
                "reason": (
                    f"Table '{table}' used in {page}:{line_no} is not defined "
                    f"in any migration file and is not a known core table — "
                    f"add a migration or add it to CORE_TABLES if it already exists"
                ),
            })
    return issues


# ── Check 4: Date fields use toISOString(), not toLocaleDateString() ─────────

def check_date_format(pages):
    """
    Timestamp columns in Supabase (closed_at, approved_at, etc.) must be
    stored as ISO 8601 strings via .toISOString().
    Using .toLocaleDateString() stores a locale-specific string like "4/27/2026"
    which breaks SQL date comparisons, ORDER BY, and BETWEEN queries.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            for field in DATE_FIELDS:
                # Pattern: the date field is assigned a toLocaleDateString() value
                if re.search(
                    rf"\b{re.escape(field)}\s*:\s*.*\.toLocaleDateString\s*\(",
                    line
                ):
                    issues.append({
                        "page":  page,
                        "field": field,
                        "line":  i + 1,
                        "reason": (
                            f"{page}:{i + 1} — '{field}' uses .toLocaleDateString() "
                            f"(stores locale string) — use .toISOString() instead "
                            f"so SQL date queries work correctly"
                        ),
                    })
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("\n" + "=" * 70)
print("Schema Consistency Validator")
print("=" * 70)

migration_tables = read_migrations()
print(f"\n  Loaded {len(migration_tables)} table(s) from migration files: "
      f"{', '.join(sorted(migration_tables))}\n")

fail_count = 0
warn_count = 0
report     = {}

checks = [
    (
        "[1] No INSERT calls to retired tables in live pages",
        check_retired_tables(LIVE_PAGES),
        "FAIL",
    ),
    (
        "[2] hive_audit_log insert includes all NOT NULL migration columns",
        check_audit_log_columns(LIVE_PAGES),
        "FAIL",
    ),
    (
        "[3] All db.from() table names are known (no undocumented tables)",
        check_unknown_tables(LIVE_PAGES, migration_tables),
        "WARN",   # warn only — table may exist in DB without a local migration
    ),
    (
        "[4] Timestamp fields use .toISOString() not .toLocaleDateString()",
        check_date_format(LIVE_PAGES),
        "FAIL",
    ),
]

for label, issues, severity in checks:
    print(f"\n{label}\n")
    if not issues:
        print("  PASS")
    else:
        for iss in issues:
            print(f"  {severity}  {iss.get('page', '?')}")
            print(f"        {iss['reason']}")
        if severity == "FAIL":
            fail_count += len(issues)
        else:
            warn_count += len(issues)
    report[label] = issues

print(f"\n{'=' * 70}")
print(f"Result: {fail_count} FAIL  {warn_count} WARN")

with open("schema_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved schema_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll schema checks PASS (warnings may need review).")
