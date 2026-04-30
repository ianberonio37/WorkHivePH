"""
Webhook and Integration Idempotency Validator — WorkHive Platform
==================================================================
Idempotency means: running the same operation twice produces the same
result as running it once. This is critical for enterprise integrations:
SAP PM and IBM Maximo retry failed API calls. CMMS systems re-send
webhooks on timeout. pg_cron occasionally fires duplicate runs.

  Layer 0 — Migration SQL correctness
    1.  CREATE INDEX uses IF NOT EXISTS        — re-running supabase db push doesn't fail
    2.  CREATE POLICY preceded by DROP IF EXISTS — re-running supabase db push doesn't fail
    3.  Tables with RLS have GRANT statements  — missing GRANT = 401 despite valid RLS policies
    4.  UPDATE SET col references existing col — col not in ALTER TABLE ADD COLUMN = 42703 error
    5.  Backfill FROM identity tables warned   — no-op if worker_profiles empty at migration time

  Layer 1 — Schema foundations
    4.  external_sync UNIQUE constraint    — dedup anchor for all external system IDs

  Layer 2 — Webhook security
    5.  Webhook HMAC verified before payload read — spoofing + replay prevention

  Layer 3 — Upsert discipline
    6.  Shared table upserts specify onConflict   — explicit conflict resolution
    7.  Batch inserts in loops use upsert         — retry-safe bulk writes

  Layer 4 — Internal idempotency
    8.  PM completions have dedup protection      — no UNIQUE constraint = duplicate completions on retry
    9.  Scheduled report writes use upsert        — pg_cron double-fire creates duplicate reports

Usage:  python validate_idempotency.py
Output: idempotency_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

MIGRATIONS_DIR = os.path.join("supabase", "migrations")
FUNCTIONS_DIR  = os.path.join("supabase", "functions")
SCHEDULED_AGENTS = os.path.join(FUNCTIONS_DIR, "scheduled-agents", "index.ts")
PM_PAGE        = "pm-scheduler.html"

LIVE_PAGES = [
    "logbook.html", "inventory.html", "pm-scheduler.html",
    "hive.html", "skillmatrix.html", "dayplanner.html",
    "engineering-design.html", "assistant.html", "community.html",
]

SHARED_TABLES = [
    "inventory_items", "assets", "hive_members",
    "pm_assets", "skill_profiles", "schedule_items",
]


def read_all_migrations():
    content = ""
    if not os.path.isdir(MIGRATIONS_DIR):
        return content
    for fname in sorted(os.listdir(MIGRATIONS_DIR)):
        if fname.endswith(".sql"):
            c = read_file(os.path.join(MIGRATIONS_DIR, fname))
            if c:
                content += c
    return content


# ── Layer 0: Migration SQL correctness ────────────────────────────────────────

def check_migration_index_idempotency():
    """
    CREATE INDEX without IF NOT EXISTS fails when supabase db push re-runs the
    migration (e.g., on a fresh clone or after a failed push). The CLI shows a
    Y/n prompt which blocks CI pipelines and confuses developers.
    Every CREATE INDEX in migrations must use IF NOT EXISTS.
    """
    issues = []
    if not os.path.isdir(MIGRATIONS_DIR):
        return issues
    for fname in sorted(os.listdir(MIGRATIONS_DIR)):
        if not fname.endswith(".sql"):
            continue
        content = read_file(os.path.join(MIGRATIONS_DIR, fname))
        if not content:
            continue
        for m in re.finditer(r'\bCREATE\s+(?:UNIQUE\s+)?INDEX\s+', content, re.IGNORECASE):
            context = content[m.start():m.start() + 120]
            if re.search(r'IF\s+NOT\s+EXISTS', context, re.IGNORECASE):
                continue
            issues.append({
                "check": "migration_index_idempotency",
                "source": fname,
                "reason": f"{fname}: CREATE INDEX without IF NOT EXISTS — fails when supabase db push re-runs; use CREATE INDEX IF NOT EXISTS"
            })
            break  # one violation per file is enough
    return issues


def check_migration_policy_idempotency():
    """
    Every CREATE POLICY in a migration must have a matching DROP POLICY IF EXISTS
    somewhere in the same file. The safe pattern groups all DROPs before all
    CREATEs, or pairs them immediately — either way the count must match.
    Supabase returns "policy already exists" on re-run otherwise.
    """
    issues = []
    if not os.path.isdir(MIGRATIONS_DIR):
        return issues
    for fname in sorted(os.listdir(MIGRATIONS_DIR)):
        if not fname.endswith(".sql"):
            continue
        content = read_file(os.path.join(MIGRATIONS_DIR, fname))
        if not content:
            continue
        # Strip comment lines before counting
        non_comment = "\n".join(
            line for line in content.splitlines()
            if not line.strip().startswith("--")
        )
        create_count = len(re.findall(r'\bCREATE\s+POLICY\b', non_comment, re.IGNORECASE))
        drop_count   = len(re.findall(r'\bDROP\s+POLICY\s+IF\s+EXISTS\b', non_comment, re.IGNORECASE))
        if create_count > 0 and drop_count < create_count:
            issues.append({
                "check": "migration_policy_idempotency",
                "source": fname,
                "reason": (f"{fname}: {create_count} CREATE POLICY but only {drop_count} "
                           f"DROP POLICY IF EXISTS — missing {create_count - drop_count} DROP(s); "
                           f"add DROP POLICY IF EXISTS before each CREATE POLICY")
            })
    return issues


def check_migration_grant_coverage(migrations):
    """
    Supabase dashboard auto-grants SELECT/INSERT/UPDATE/DELETE to anon and
    authenticated roles when creating tables via the GUI. SQL migrations do NOT
    auto-grant. Any table created in a migration that also has RLS enabled needs
    explicit GRANT statements — without them, the anon role gets 401 on every
    query regardless of what the RLS policies allow.
    """
    issues = []
    if not migrations:
        return issues
    rls_tables = set(re.findall(
        r'ALTER\s+TABLE\s+(?:public\.)?(\w+)\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY',
        migrations, re.IGNORECASE
    ))
    for table in sorted(rls_tables):
        if not re.search(
            rf'GRANT\s+[^;]+ON\s+(?:public\.)?{re.escape(table)}\b',
            migrations, re.IGNORECASE
        ):
            issues.append({
                "check": "migration_grant_coverage",
                "reason": (f"Table '{table}' has RLS enabled in migrations but no GRANT statement — "
                           f"anon/authenticated roles get 401 despite valid RLS policies; "
                           f"add: GRANT SELECT,INSERT,UPDATE,DELETE ON {table} TO anon,authenticated")
            })
    return issues


def check_migration_update_column_exists():
    """
    UPDATE table SET col = X in a migration requires col to exist on table.
    If col was never added via ALTER TABLE ADD COLUMN, the migration fails with
    'ERROR: 42703: column does not exist'.

    Root cause of May 2026 incident: community_xp.auth_uid was referenced in a
    backfill UPDATE but never added via ALTER TABLE ADD COLUMN — backfill SQL
    crashed, leaving auth_uid NULL in community_xp rows.
    """
    issues = []
    if not os.path.isdir(MIGRATIONS_DIR):
        return issues

    # Build { table: set(cols) } from all ALTER TABLE ADD COLUMN across all migrations
    added_columns = {}
    all_files = sorted(os.listdir(MIGRATIONS_DIR))
    for fname in all_files:
        if not fname.endswith(".sql"):
            continue
        content = read_file(os.path.join(MIGRATIONS_DIR, fname))
        if not content:
            continue
        for m in re.finditer(
            r'ALTER\s+TABLE\s+(?:public\.)?(\w+)\s+ADD\s+COLUMN\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)',
            content, re.IGNORECASE
        ):
            added_columns.setdefault(m.group(1).lower(), set()).add(m.group(2).lower())

    # Columns that appear in ADD COLUMN somewhere — only flag these in UPDATE checks
    migration_added_cols = {c for cols in added_columns.values() for c in cols}

    for fname in all_files:
        if not fname.endswith(".sql"):
            continue
        content = read_file(os.path.join(MIGRATIONS_DIR, fname))
        if not content:
            continue
        # Strip comment lines before scanning UPDATE statements
        no_comments = "\n".join(
            line for line in content.splitlines()
            if not line.strip().startswith("--")
        )
        for m in re.finditer(
            r'\bUPDATE\s+(\w+)(?:\s+\w+)?\s+SET\s+(\w+)\s*=',
            no_comments, re.IGNORECASE
        ):
            table = m.group(1).lower()
            col   = m.group(2).lower()
            if col not in migration_added_cols:
                continue  # not a migration-added col, skip
            if col not in added_columns.get(table, set()):
                issues.append({
                    "check": "migration_update_column_exists",
                    "source": fname,
                    "reason": (f"{fname}: UPDATE {table} SET {col} — "
                               f"'{col}' was never added to '{table}' via ALTER TABLE ADD COLUMN; "
                               f"migration will fail with ERROR 42703 column does not exist")
                })
    return issues


def check_backfill_timing():
    """
    Migrations that UPDATE records FROM worker_profiles (or other auth identity tables)
    are silent no-ops if the source table is empty at deploy time. This happens when
    workers haven't signed up yet when the migration runs — leaving auth_uid = NULL
    in all existing records.

    After C4 enforces auth.uid() = auth_uid in RLS, NULL auth_uid records become
    invisible to all authenticated users — data loss symptom without actual deletion.

    Root cause of May 2026 incident: C3 backfill ran when worker_profiles was empty.
    Workers who signed up AFTER C3 had auth_uid = NULL in all their rows. C4 then
    blocked access because NULL != auth.uid() is always false in SQL.

    Fix: re-run the backfill after workers sign up, OR add a trigger on worker_profiles
    INSERT that immediately links all existing records (trg_sync_auth_uid_on_signup).
    """
    issues = []
    if not os.path.isdir(MIGRATIONS_DIR):
        return issues

    IDENTITY_TABLES = {"worker_profiles"}

    for fname in sorted(os.listdir(MIGRATIONS_DIR)):
        if not fname.endswith(".sql"):
            continue
        content = read_file(os.path.join(MIGRATIONS_DIR, fname))
        if not content:
            continue
        for table in IDENTITY_TABLES:
            if re.search(rf'\bFROM\s+{re.escape(table)}\b', content, re.IGNORECASE):
                issues.append({
                    "check": "backfill_timing_warning",
                    "source": fname,
                    "skip": True,  # WARN — valid pattern but timing-sensitive
                    "reason": (f"{fname} backfills FROM {table} — if {table} is empty at "
                               f"migration time (workers not yet signed up), auth_uid stays NULL "
                               f"in all rows; after C4 RLS enforcement this makes records "
                               f"invisible; ensure trg_sync_auth_uid_on_signup trigger exists "
                               f"or re-run backfill after workers create accounts")
                })
                break
    return issues


# ── Layer 1: Schema foundations ───────────────────────────────────────────────

def check_external_sync_schema(migrations):
    """Forward guard: if external_sync table exists, it must have
    UNIQUE(system_type, external_id, entity_type) or retries create duplicates."""
    if not migrations:
        return []
    if not re.search(r"CREATE TABLE.*\bexternal_sync\b", migrations, re.IGNORECASE):
        return []
    if not re.search(
        r"UNIQUE\s*\(\s*system_type\s*,\s*external_id\s*,\s*entity_type\s*\)"
        r"|UNIQUE\s*\(\s*external_id\s*,\s*system_type\s*,\s*entity_type\s*\)",
        migrations, re.IGNORECASE
    ):
        return [{"check": "external_sync_schema", "source": MIGRATIONS_DIR,
                 "reason": ("external_sync table exists but is missing "
                            "UNIQUE(system_type, external_id, entity_type) — "
                            "retried sync operations create duplicate mapping records")}]
    return []


# ── Layer 2: Webhook security ─────────────────────────────────────────────────

def check_webhook_hmac():
    """Webhook handlers must verify HMAC before reading req.json() — prevents
    spoofing and replay attacks."""
    issues = []
    if not os.path.isdir(FUNCTIONS_DIR):
        return []
    for func_name in os.listdir(FUNCTIONS_DIR):
        func_path = os.path.join(FUNCTIONS_DIR, func_name, "index.ts")
        content = read_file(func_path)
        if content is None:
            continue
        is_receiver = bool(re.search(
            r"X-WorkHive-Signature|webhook.*signature|hmac.*verify|verify.*hmac"
            r"|X-Hub-Signature|X-Shopify-Webhook",
            content, re.IGNORECASE
        ))
        if not is_receiver:
            continue
        hmac_pos = re.search(r"hmac|verifySignature|verify.*sign", content, re.IGNORECASE)
        json_pos  = re.search(r"req\.json\(\)", content)
        if hmac_pos and json_pos and hmac_pos.start() > json_pos.start():
            issues.append({"check": "webhook_hmac", "func": func_name,
                           "reason": (f"{func_name}/index.ts reads req.json() BEFORE "
                                      f"verifying HMAC — spoofed events bypass the signature check")})
        elif json_pos and not hmac_pos:
            issues.append({"check": "webhook_hmac", "func": func_name,
                           "reason": (f"{func_name}/index.ts has no HMAC verification — "
                                      f"any client can send fake events")})
    return issues


# ── Layer 3: Upsert discipline ────────────────────────────────────────────────

def check_upsert_conflict_spec(pages, tables):
    """.upsert() on shared tables must specify onConflict — bare upsert uses PK
    and may create instead of merge when only a unique column matches."""
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            table_match = next(
                (t for t in tables
                 if (f"from('{t}')" in line or f'from("{t}")' in line) and ".upsert(" in line),
                None
            )
            if not table_match:
                continue
            window = "\n".join(lines[i:min(len(lines), i + 8)])
            if "onConflict" not in window:
                issues.append({"check": "upsert_conflict_spec", "page": page,
                               "skip": True,
                               "reason": (f"{page}:{i + 1} .upsert() on '{table_match}' with no "
                                          f"onConflict — relies on primary key for deduplication; "
                                          f"add onConflict: 'unique_column' to make retry behavior explicit")})
    return issues


def check_batch_idempotency(pages, tables):
    """Batch inserts inside loops on shared tables should use upsert — raw insert
    in a loop creates duplicates on retry."""
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            table_match = next(
                (t for t in tables
                 if (f"from('{t}')" in line or f'from("{t}")' in line)
                 and ".insert(" in line and ".select(" not in line),
                None
            )
            if not table_match:
                continue
            window_back = "\n".join(lines[max(0, i - 8):i])
            if re.search(r"\bforEach\s*\(|\bfor\s*\(|\bfor\s+const\b|\bfor\s+let\b", window_back):
                issues.append({"check": "batch_idempotency", "page": page,
                               "skip": True,
                               "reason": (f"{page}:{i + 1} .insert() on '{table_match}' inside a loop — "
                                          f"not idempotent; use .upsert() with onConflict for retry safety")})
    return issues


# ── Layer 4: Internal idempotency ─────────────────────────────────────────────

def check_pm_completion_dedup(pm_page, migrations):
    """
    pm-scheduler.html submitCompletion() uses .insert() on pm_completions with
    no UNIQUE constraint in the migration files. If an enterprise system (SAP PM,
    Maximo) sends the completion event twice (network timeout, retry), or a
    worker taps Complete twice before the first request returns, two duplicate
    PM completion records are created.

    The fix is either:
    1. Add a UNIQUE(scope_item_id, worker_name, DATE(completed_at)) constraint
       to pm_completions so retries resolve to an upsert
    2. Change submitCompletion() to use .upsert() with onConflict

    Forward guard: this is WARN because no external integration exists yet.
    When SAP integration is built, this must become a FAIL.
    """
    issues = []
    # Check for UNIQUE constraint on pm_completions
    has_unique = bool(re.search(
        r"UNIQUE.*pm_completions|pm_completions.*UNIQUE"
        r"|unique.*scope_item_id.*worker_name|unique.*worker_name.*scope_item",
        migrations, re.IGNORECASE
    ))
    if has_unique:
        return []   # constraint exists — PASS

    # Check if pm-scheduler.html uses upsert on pm_completions
    content = read_file(pm_page)
    if content is None:
        return []
    has_upsert = bool(re.search(r"pm_completions.*upsert|upsert.*pm_completions", content))
    if has_upsert:
        return []

    # Neither constraint nor upsert — real gap
    issues.append({"check": "pm_completion_dedup", "page": pm_page, "skip": True,
                   "reason": (f"{pm_page} submitCompletion() uses .insert() on pm_completions "
                              f"with no UNIQUE constraint in migrations — enterprise system retry "
                              f"(SAP, Maximo) or network timeout creates a duplicate PM completion; "
                              f"add UNIQUE(scope_item_id, worker_name) or switch to .upsert()")})
    return issues


def check_scheduled_report_idempotency(func_path):
    """
    scheduled-agents writes ai_reports with .insert(). If pg_cron fires twice
    (edge case documented in Supabase pg_cron known issues), a duplicate weekly
    report is created for the same hive and report_type. Workers see two copies
    of the same digest report with no indication either is a duplicate.

    The fix: use .upsert() with onConflict on (hive_id, report_type) and a
    date-based period column, or add a UNIQUE constraint on ai_reports.
    """
    content = read_file(func_path)
    if content is None:
        return []
    # Check if ai_reports uses insert
    has_insert = bool(re.search(r'from\(["\']ai_reports["\'].*\.insert\(|\.insert.*ai_reports', content))
    if not has_insert:
        return []
    # Check if upsert is used instead
    has_upsert = bool(re.search(r'from\(["\']ai_reports["\'].*\.upsert\(|\.upsert.*ai_reports', content))
    if has_upsert:
        return []
    return [{"check": "scheduled_report_idempotency", "source": func_path, "skip": True,
             "reason": (f"{func_path} writes ai_reports with .insert() — if pg_cron fires "
                        f"twice (known edge case), duplicate weekly reports are created; "
                        f"use .upsert() with onConflict: 'hive_id,report_type' to dedup")}]


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    # L0
    "migration_index_idempotency",
    "migration_policy_idempotency",
    "migration_grant_coverage",
    "migration_update_column_exists",
    "backfill_timing_warning",
    # L1
    "external_sync_schema",
    # L2
    "webhook_hmac",
    # L3
    "upsert_conflict_spec",
    "batch_idempotency",
    # L4
    "pm_completion_dedup",
    "scheduled_report_idempotency",
]

CHECK_LABELS = {
    # L0
    "migration_index_idempotency":   "L0  CREATE INDEX uses IF NOT EXISTS in all migrations",
    "migration_policy_idempotency":  "L0  CREATE POLICY preceded by DROP POLICY IF EXISTS",
    "migration_grant_coverage":      "L0  RLS-enabled tables have GRANT statements in migrations",
    "migration_update_column_exists":"L0  UPDATE SET col references a col added via ALTER TABLE ADD COLUMN",
    "backfill_timing_warning":       "L0  Backfill FROM worker_profiles warned — no-op if table empty at deploy  [WARN]",
    # L1
    "external_sync_schema":          "L1  external_sync table has UNIQUE(system_type, external_id, entity_type)",
    # L2
    "webhook_hmac":                  "L2  Webhook handlers verify HMAC before reading payload",
    # L3
    "upsert_conflict_spec":          "L3  Shared table upserts specify onConflict  [WARN]",
    "batch_idempotency":             "L3  Batch loop inserts on shared tables use upsert  [WARN]",
    # L4
    "pm_completion_dedup":           "L4  pm_completions has dedup protection against double-submit  [WARN]",
    "scheduled_report_idempotency":  "L4  Scheduled ai_reports writes use upsert (pg_cron double-fire)  [WARN]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nWebhook and Integration Idempotency Validator (5-layer)"))
    print("=" * 55)

    migrations = read_all_migrations()

    all_issues = []
    all_issues += check_migration_index_idempotency()
    all_issues += check_migration_policy_idempotency()
    all_issues += check_migration_grant_coverage(migrations)
    all_issues += check_migration_update_column_exists()
    all_issues += check_backfill_timing()
    all_issues += check_external_sync_schema(migrations)
    all_issues += check_webhook_hmac()
    all_issues += check_upsert_conflict_spec(LIVE_PAGES, SHARED_TABLES)
    all_issues += check_batch_idempotency(LIVE_PAGES, SHARED_TABLES)
    all_issues += check_pm_completion_dedup(PM_PAGE, migrations)
    all_issues += check_scheduled_report_idempotency(SCHEDULED_AGENTS)

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "idempotency",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("idempotency_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
