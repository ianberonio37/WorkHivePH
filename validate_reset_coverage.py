"""
Reset Coverage Validator -- WorkHive Platform Guardian
======================================================
Auto-derives the production table set from supabase/migrations/*.sql and
verifies every table is covered by reset.py (RESET_TABLES + RESET_TABLES_NON_ID).

Catches the recurring bug where a feature ships a new table but reset.py
isn't updated -- so 'Reset' leaves stale rows behind across reseeds.
Surfaced 2026-05-09 when 322 projects + 2365 project_items + 318
project_links + 1345 project_progress_logs survived a Reset across the
multiple Project Manager phases.

Two checks:
  1. Every CREATE TABLE found in migrations is in reset.py
  2. Every reset.py entry points to a real table in migrations
     (catches typos and stale entries after a table is dropped)

Skips:
  - Views (CREATE VIEW)
  - System schemas (auth.*, storage.*, pg_*)
  - The 'public' schema prefix is ignored

Usage:  python validate_reset_coverage.py
Output: reset_coverage_report.json
"""
import re, json, sys, os
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result  # noqa: E402

ROOT = Path(__file__).resolve().parent
MIGRATIONS_DIR = ROOT / "supabase" / "migrations"
RESET_PY = ROOT / "test-data-seeder" / "seeders" / "reset.py"

CHECK_NAMES = ["all_tables_in_reset", "no_phantom_reset_entries"]
CHECK_LABELS = {
    "all_tables_in_reset":     "L1  Every migration table is in reset.py RESET_TABLES",
    "no_phantom_reset_entries": "L2  Every reset.py entry points to a real migration table",
}

# CREATE TABLE -- captures both 'public.tbl' and 'tbl' shapes.
RE_CREATE_TABLE = re.compile(
    r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?'
    r'(?:"?(?:public|auth|storage)"?\.)?'
    r'"?(\w+)"?\s*\(',
    re.IGNORECASE,
)
# CREATE VIEW -- exclude views from coverage requirements.
RE_CREATE_VIEW = re.compile(
    r'CREATE\s+(?:OR\s+REPLACE\s+)?(?:MATERIALIZED\s+)?VIEW\s+'
    r'(?:"?\w+"?\.)?"?(\w+)"?\s+AS\b',
    re.IGNORECASE,
)
# DROP TABLE -- when a table is dropped, remove from production set.
RE_DROP_TABLE = re.compile(
    r'DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?'
    r'(?:"?\w+"?\.)?"?(\w+)"?',
    re.IGNORECASE,
)

# Tables we never expect reset.py to clear (managed by Supabase, internal infra).
SYSTEM_TABLES_IGNORED = {
    # Supabase internal
    "schema_migrations", "supabase_functions", "supabase_migrations",
    # Auth schema (cleared via auth.admin API, not table delete)
    "users", "identities", "sessions", "refresh_tokens", "audit_log_entries",
    "instances", "schema_migrations", "mfa_factors", "mfa_challenges",
    "mfa_amr_claims", "saml_providers", "saml_relay_states", "sso_providers",
    "sso_domains", "flow_state", "one_time_tokens",
    # Storage schema
    "buckets", "objects", "migrations",
    # pgbouncer / realtime / extensions infra
    "messages", "subscription", "tenants", "extensions",
}

# Catalog / reference tables populated only by migration INSERTs (no Python
# seeder). Wiping them breaks FK-using DB triggers on the next user action.
# Reset.py must NOT clear these; this validator must NOT flag them as missing.
# Surfaced 2026-05-09 when achievement_definitions wipe broke PM completion
# triggers (FK violation on worker_achievements_achievement_id_fkey).
CATALOG_TABLES_IGNORED = {
    "achievement_definitions",
    "equipment_reading_templates",
    # Platform metadata: seeded only by migrations (canonical_sources
    # foundation + per-truth registration migrations). Wiping it loses the
    # registry that AI agents read to find canonical truth sources.
    "canonical_sources",
}


def _strip_sql_comments(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", "", sql)
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    return sql


def parse_migrations() -> set:
    """Return set of public-schema table names CREATE TABLEd in migrations,
    minus any subsequently DROPped, minus the system-table ignore list."""
    if not MIGRATIONS_DIR.is_dir():
        return set()

    tables = set()
    views = set()
    for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
        # Some baseline migrations have non-UTF-8 bytes; read with replace.
        try:
            content = sql_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        content = _strip_sql_comments(content)

        # Track views to exclude from CREATE TABLE matches if a regex picks both up.
        for m in RE_CREATE_VIEW.finditer(content):
            views.add(m.group(1).lower())

        for m in RE_CREATE_TABLE.finditer(content):
            name = m.group(1).lower()
            # Skip if this is actually a view per the same name match
            if name in views:
                continue
            tables.add(name)

        for m in RE_DROP_TABLE.finditer(content):
            name = m.group(1).lower()
            tables.discard(name)

    return tables - SYSTEM_TABLES_IGNORED - CATALOG_TABLES_IGNORED


def parse_reset_py() -> tuple[set, set]:
    """Return (RESET_TABLES_set, RESET_TABLES_NON_ID_keys_set) from reset.py.
    Reads the source as text rather than importing, so the validator works
    even if test-data-seeder dependencies aren't on sys.path."""
    src = read_file(str(RESET_PY))
    if not src:
        return set(), set()

    main_set: set = set()
    non_id_set: set = set()

    # Match the RESET_TABLES = [ ... ] block
    m = re.search(r"RESET_TABLES\s*=\s*\[(.*?)\]", src, re.DOTALL)
    if m:
        for entry in re.findall(r'"([^"]+)"|\'([^\']+)\'', m.group(1)):
            name = (entry[0] or entry[1]).strip().lower()
            if name:
                main_set.add(name)

    # Match the RESET_TABLES_NON_ID = { "tbl": (...), ... } block
    m2 = re.search(r"RESET_TABLES_NON_ID\s*=\s*\{(.*?)\}", src, re.DOTALL)
    if m2:
        # Keys in the dict literal
        for k in re.findall(r'"([^"]+)"\s*:|\'([^\']+)\'\s*:', m2.group(1)):
            name = (k[0] or k[1]).strip().lower()
            if name:
                non_id_set.add(name)

    return main_set, non_id_set


def check_all_tables_in_reset(prod_tables, reset_set, non_id_set):
    issues = []
    covered = reset_set | non_id_set
    missing = sorted(prod_tables - covered)
    for table in missing:
        issues.append({
            "check": "all_tables_in_reset",
            "reason": (
                f"Migration creates table '{table}' but reset.py doesn't clear it. "
                "Add to RESET_TABLES (children before parents) or RESET_TABLES_NON_ID "
                "if its PK is not 'id'."
            ),
        })
    return issues


def check_no_phantom_reset_entries(prod_tables, reset_set, non_id_set):
    issues = []
    all_reset = reset_set | non_id_set
    phantoms = sorted(all_reset - prod_tables)
    for table in phantoms:
        # System tables in the ignore list are also "phantom" but expected.
        if table in SYSTEM_TABLES_IGNORED:
            continue
        issues.append({
            "check": "no_phantom_reset_entries",
            "reason": (
                f"reset.py references table '{table}' but no migration creates it. "
                "Likely a typo or a stale entry after the table was dropped. Remove it."
            ),
        })
    return issues


def main():
    print("Reset Coverage Validator")
    print("========================")

    prod_tables = parse_migrations()
    reset_set, non_id_set = parse_reset_py()

    print(f"  {len(prod_tables)} production tables in migrations")
    print(f"  {len(reset_set)} entries in RESET_TABLES")
    print(f"  {len(non_id_set)} entries in RESET_TABLES_NON_ID")
    print()

    all_issues = []
    all_issues += check_all_tables_in_reset(prod_tables, reset_set, non_id_set)
    all_issues += check_no_phantom_reset_entries(prod_tables, reset_set, non_id_set)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    print(f"\nReset coverage: {n_pass} PASS, {n_fail} FAIL, {n_skip} SKIP")

    report = {
        "production_tables_count": len(prod_tables),
        "reset_tables_count":      len(reset_set),
        "non_id_tables_count":     len(non_id_set),
        "missing_from_reset":      sorted(prod_tables - reset_set - non_id_set),
        "phantom_in_reset":        sorted((reset_set | non_id_set) - prod_tables - SYSTEM_TABLES_IGNORED),
        "issues":                  all_issues,
        "n_pass":                  n_pass,
        "n_fail":                  n_fail,
    }
    with open("reset_coverage_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
