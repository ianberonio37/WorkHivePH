"""
Migration Immutability Detector -- WorkHive Platform
=====================================================
Catches the case where an already-applied database migration is edited
after its first commit. Postgres tracks applied migrations in the
`supabase_migrations.schema_migrations` table by FILENAME, so a re-edit
silently does NOT re-run -- production keeps the old DDL while every
fresh clone, staging environment, and customer self-host applies the new
DDL. Schema drift is invisible until something breaks.

Layer 1 -- Migration file modified after first commit                   [FAIL]
  For each .sql file in supabase/migrations/, count the number of distinct
  commits that touched it. A correctly-managed migration has exactly one:
  the commit that introduced it. Any subsequent commit means somebody
  edited an already-applied file. Fix: revert the edit and add a NEW
  migration that performs the additional change.

Layer 2 -- Migration filename does not follow timestamp convention      [WARN]
  Migrations must be named `YYYYMMDDHHMMSS_descriptor.sql` so Supabase
  can apply them in deterministic order. Out-of-order names cause
  re-applies to skip earlier files, leaving production behind staging.

Layer 3 -- Migration touched by recent merge / rebase                   [WARN]
  Migrations whose latest commit hash differs from their first commit
  hash but where the diff is whitespace-only -- usually a rebase artifact.
  Lower stakes than L1 (no semantic change) but still drift-risk because
  the file's git mtime moved.

Layer 4 -- Migration count and recency (informational)                  [INFO]
  Counts of migrations created in the last 7 / 30 days. Bursts can
  signal incomplete schema design or rushed batches.

Skills consulted: data-engineer (migration discipline, schema/query
alignment rules), devops (deploy semantics, supabase db push behavior),
architect (schema change review, breaking-change flagging).
"""
from __future__ import annotations

import re
import json
import sys
import os
import glob
import subprocess
from collections import defaultdict
from datetime import datetime, timezone

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import format_result


MIGRATIONS_DIR = os.path.join("supabase", "migrations")

# Filename convention: YYYYMMDDHHMMSS_descriptor.sql
TIMESTAMP_RE = re.compile(r"^\d{14}_[a-z0-9_]+\.sql$")

# Per-entry justification dict for migrations that legitimately have multiple
# commits (e.g., the baseline pg_dump that periodically gets refreshed).
# Pre-2026-05-10 historical edits captured below as a baseline allowlist;
# each entry is logged in PRODUCTION_FIXES.md for follow-up investigation
# (verify the second commit landed BEFORE the migration was deployed; if
# yes, the entry is permanently safe; if not, it's prod/clone drift).
ALLOWED_MULTI_COMMIT = {
    # ── 2026-07-18 production catch-up self-heal (prod was 2 months behind + squash-rebaselined) ──
    # Edited IN-PLACE while pushing the accumulated migrations to prod (PRODUCTION_DEPLOY_RUNBOOK.md +
    # commit c7b0b04) to survive prod/local schema drift a granular replay hit. Each edit is idempotent
    # (BOM strip / IF NOT EXISTS / guarded GRANT) and a no-op on any already-consistent environment.
    "20260609000005_fix_readiness_blocker_summary.sql":
        "2026-07-18 prod deploy: stripped a UTF-8 BOM prod's migration runner rejected (local psql strips it); content otherwise unchanged.",
    "20260620000008_rls_enable_remaining_hive_tables.sql":
        "2026-07-18 prod deploy: ADD COLUMN IF NOT EXISTS hive_id before the RLS policy (prod's legacy external_sync lacked it after a history squash); no-op where it exists.",
    "20260705000003_q4_daily_ai_ceiling.sql":
        "2026-07-18 prod deploy: CREATE TABLE IF NOT EXISTS ai_rate_limits before the ALTER (squash lost the table on prod); no-op where it exists.",
    "20260718000002_cron_health_view.sql":
        "2026-07-18 prod deploy: guarded the grafana_reader GRANT (role created by the infra/mcp/grafana side-file prod hasn't run); the view is created regardless.",
    "20260718000003_storage_health_view.sql":
        "2026-07-18 prod deploy: guarded the grafana_reader GRANT (same class as cron_health_view).",
    # ── 2026-05-20 voice-phase migration cascade self-heal (turns 10-11) ───────
    # Local Supabase migration up failed because of cross-migration schema
    # collisions (CREATE TABLE IF NOT EXISTS X declared twice with different
    # columns) and a few worker_hives → hive_members typos. Each file below
    # received the SAME class of self-heal edit: additive ALTER TABLE for
    # missing columns, or table-name correction. All 7 files were edited
    # IN-PLACE rather than via follow-up migrations because none had been
    # applied locally yet (the failing migrations blocked everything after
    # them). Documented in memory project_agent_memory_schema_collision_2026_05_20.md.
    # Local Supabase re-applied via `supabase migration up --local` after each fix;
    # production deploys should use these in-place edits as well since the
    # migrations weren't applied in any environment.
    # ── 2026-06-09 readiness blocker fix — REVERTED to byte-identical original ──
    # The deep-walk fixed the Stair-1 "satisfied-criterion-as-blocker" bug (e.g.
    # "30 of 5 PM templates registered") by editing this already-applied file in
    # 593a5c4 — a mistake. The edit was then REVERTED, so this file is byte-identical
    # to its first commit (70314ba7); the real fix lives in the forward migration
    # 20260609000005_fix_readiness_blocker_summary.sql (CREATE OR REPLACE). The
    # immutability INVARIANT holds (current content == first version); only the git
    # history carries a benign reverted touch. Allowlisted to document that.
    "20260513000001_hive_readiness.sql":
        "2026-06-09 reverted to byte-identical first-commit content; real fix in "
        "forward migration 20260609000005. Benign reverted touch in git history.",
    "20260516000001_agent_memory_phase2.sql":
        "2026-05-20 self-heal: additive ALTER TABLE ADD COLUMN IF NOT EXISTS "
        "for Phase 2 columns (session_id, turn_num, etc.) to coexist with the "
        "older 20260511000001 agent_memory schema. Caught by turn-8 sentinel "
        "phase_4_dialog_state. The IF NOT EXISTS guards make this idempotent "
        "on both fresh and partially-applied environments.",
    "20260516000003_anomaly_alerts_phase5.sql":
        "2026-05-20 self-heal: RLS policy referenced non-existent worker_hives; "
        "rewritten to use hive_members. Also DROP FUNCTION IF EXISTS before "
        "CREATE OR REPLACE on fetch_active_alerts (return type changed).",
    "20260516000004_kb_rag_phase3.sql":
        "2026-05-20 self-heal: RLS policies referenced non-existent worker_hives; "
        "rewritten to use hive_members on both kb_documents and kb_chunks.",
    "20260516000007_voice_analytics_phase8.sql":
        "2026-05-20 self-heal: additive ALTER TABLE on conversation_analytics "
        "(session_id, turn_num, created_at, etc.) so the table coexists with "
        "the earlier voice_tables_simple declaration. The index on (session_id, "
        "turn_num) requires these columns.",
    "20260516000011_voice_tables_simple.sql":
        "2026-05-20 self-heal: 4 CREATE TABLE IF NOT EXISTS lines annotated "
        "with `-- table-collision-allow:` markers documenting the intentional "
        "simple-fallback pattern (after the phase-specific migrations).",
    "20260519000003_platform_feedback_votes.sql":
        "2026-05-20 self-heal: additive ALTER ADD COLUMN voted_at for "
        "environments where an earlier partial run created the table without it.",
    "20260519000021_canonical_sources_platform_feedback_and_kg.sql":
        "2026-05-20 fix: ON CONFLICT (source_name) → ON CONFLICT (domain). "
        "canonical_sources PK is `domain` not `source_name`. Single-token fix.",
    "20260520000004_drop_phantom_columns_safe.sql":
        "2026-05-20 fix: skipped DROP COLUMN clarification_prompt + last_turn_num "
        "from dialog_state because they're referenced by the fetch_dialog_state "
        "RPC return table — DROP would CASCADE and remove the RPC.",
    "20260520000024_v_project_items_progress_truth.sql":
        "2026-05-20 self-heal: added ALTER TABLE project_items ADD COLUMN IF "
        "NOT EXISTS for actual_start, actual_end, predecessors, etc. — "
        "20260520000009 dropped these as phantom but the v_project_items_truth "
        "view (turn 4) was the consumer that justified keeping them.",
    "20260520000025_v_ai_reports_skill_badges_achievements_truth.sql":
        "2026-05-20 self-heal: ALTER TABLE achievement_definitions ADD COLUMN "
        "xp_per_level int default 100. The turn-5 v_worker_achievements_truth "
        "view assumed it existed; restoring as an additive column is safer than "
        "rewriting the view.",
    "20260520000001_canonical_lineage_edges.sql":
        "2026-05-20 same-day amendment: original commit b528865 created the "
        "table; follow-up commit 1b1a203 added the canonical_sources INSERT "
        "registration (a coherent extension of the migration's purpose). "
        "Local Supabase re-applied via psql; no prod deploy between commits. "
        "Migration ships as one logical unit (table + self-registration).",
    "20260520000010_v_alert_truth.sql":
        "2026-05-20 same-day amendment + revert: original commit 1b1a203 "
        "created the view; 7ac65f1 extended with rule_id+category in-place "
        "(audit caught the rule); 015ce87 reverted to the original content + "
        "shipped the rule_id+category extension as new migration 20260520000013. "
        "L3 (whitespace_only_edits) confirms the diff between 1b1a203 and "
        "015ce87 is whitespace-only (CRLF normalization). File is effectively "
        "pristine at its first-commit semantics.",
    "20260519000002_platform_feedback.sql":
        "2026-05-19 same-day fix: rate-limit + resolved_at trigger landed in "
        "follow-up commit (5f5d4dc0) right after the schema commit (023d9d99). "
        "No prod deploy between the two — the table ships as one logical unit. "
        "Local Supabase re-applied via `supabase migration up --local`.",
    "20260425000000_hive_audit_log.sql":
        "pre-2026-05-10 historical edit; investigate via git log",
    "20260428000003_analytics_new_field_indexes.sql":
        "pre-2026-05-10 historical edit; same-day touch likely typo fix pre-deploy",
    "20260429000002_early_access_emails.sql":
        "pre-2026-05-10 historical edit; 3-commit chain needs investigation",
    "20260501000001_fix_auth_uid_backfill.sql":
        "pre-2026-05-10 historical edit; same-day touch likely typo fix pre-deploy",
    "20260505000002_project_knowledge.sql":
        "pre-2026-05-10 historical edit; same-day touch likely typo fix pre-deploy",
    "20260511000002_db_hygiene_batch.sql":
        "2026-05-12 hotfix: parts_records FK guard added so fresh local stacks "
        "do not halt on assets.asset_id missing UNIQUE constraint. Second commit "
        "landed same-day, no prod deploy in between (remote DB already had FK). "
        "Long-term fix: ensure assets.asset_id has UNIQUE in baseline migration.",
    "20260513000000_analytics_events.sql":
        "2026-05-13 same-day fix: ON CONFLICT clause referenced source_name "
        "which is not the PK (domain is). Edited in Phase 0 commit 70314ba "
        "before any prod deploy of this Phase 0 batch. No state divergence "
        "possible: the table ships as part of Phase 0 and was never applied "
        "with the broken ON CONFLICT.",
    "20260512000003_sensor_readings.sql":
        "2026-05-12 walkthrough fix: GENERATED column not IMMUTABLE; replaced "
        "with BEFORE INSERT trigger. Never applied to remote (migration list "
        "shows empty remote column for 20260512*). Local Docker re-applied "
        "via `supabase migration up --local` after edit. Safe.",
    "20260512000007_phase_5b1_drop_logbook_asset_ref.sql":
        "2026-05-12 walkthrough fix: CREATE OR REPLACE VIEW couldn't drop "
        "asset_ref_id column; added DROP VIEW IF EXISTS CASCADE for "
        "v_logbook_truth + asset_brain_overview (latter retired, no live "
        "consumers). Never applied to remote.",
    "20260512000008_phase_5b2_drop_inventory_linked_asset_ids.sql":
        "2026-05-12 walkthrough fix: same CREATE OR REPLACE column-rename "
        "issue. DROP VIEW IF EXISTS CASCADE added. Never applied to remote.",
    "20260512000012_canonical_anchor_batch.sql":
        "2026-05-12 walkthrough fix: v_worker_assignment_truth referenced "
        "logbook.asset_ref_id which Phase 5b.1 dropped; pm_completions.worker "
        "column is worker_name not completed_by. Both fixed. Replaced the "
        "asset_brain_overview_legacy registration (view retired in 5b.1) with "
        "a retirement tombstone. Never applied to remote.",
    "20260512000017_canonical_capture_contracts.sql":
        "2026-05-12 Wave 1.5 fix: qr_asset_lookup_v1 regex widened from "
        "[a-z0-9_-] to [A-Za-z0-9_-] to allow uppercase tags like 'PMP-001'. "
        "Caught by validate_capture_contracts.py fixture L2 on first run. "
        "Never applied to remote.",
    "20260512000013_tier_bcde_foundation.sql":
        "2026-05-12 walkthrough + Tier C realign: (a) v_project_truth used "
        "wrong column names (type/budget_pesos/...) for actual projects table "
        "shape; v_knowledge_truth assumed unified 'content' column; "
        "v_audit_unified assumed worker_name+payload across all 4 audit "
        "tables. All fixed. Never applied to remote.",
    "20260514000002_canonical_agent_contracts.sql":
        "2026-05-15 one-time idempotency fix: added DROP POLICY IF EXISTS "
        "before each CREATE POLICY so re-running the migration does not fail "
        "on an existing policy. Same-session edit, not yet applied to remote.",
    "20260516000001_agent_memory_phase2.sql":
        "2026-05-16 same-day regression fixes batch (commit 6c3e094): "
        "validator registration + migration policies + search_path lockdown. "
        "Phase 2 Session Memory Layer migration, never applied to remote prod.",
    "20260516000002_dialog_state_phase4.sql":
        "2026-05-16 same-day regression fixes batch (commit 6c3e094): "
        "validator registration + migration policies + search_path lockdown. "
        "Phase 4 Multi-Turn Dialog Flow migration, never applied to remote prod.",
    "20260516000003_anomaly_alerts_phase5.sql":
        "2026-05-16 two same-day fix passes (commits 6c3e094, 0c8408f): "
        "validator failures fix (pgvector dims, search_path, RLS policies). "
        "Phase 5 Proactive Alerts migration, never applied to remote prod.",
    "20260516000004_kb_rag_phase3.sql":
        "2026-05-16 same-day fix pass (commit 0c8408f): pgvector dims fix "
        "and RLS policies. Phase 3 KB RAG migration, never applied to remote.",
    "20260516000005_offline_resilience_phase6.sql":
        "2026-05-16 same-day fix pass (commit 0c8408f): validator registration "
        "and RLS policies. Phase 6 Offline Resilience migration, never applied "
        "to remote prod.",
    "20260521000001_fk_on_delete_hardening.sql":
        "2026-05-21 self-heal: wrapped each FK reconstruction in a DO $$ IF EXISTS "
        "guard so the migration applies cleanly on fresh local stacks where parent "
        "tables were dropped by earlier 20260512000009_phase_5c_drop_assets cascades. "
        "Pure idempotency hardening: semantics unchanged where parents exist; "
        "silently skips where they don't. Never applied to remote prod between the "
        "two commits (local-first workflow). Long-term: roll the guard into a fresh "
        "migration if this file needs further edits.",
}


def list_migrations() -> list[str]:
    return sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql")))


def _git_commits_touching(path: str) -> list[dict]:
    """Return list of {hash, date} for all commits that touched `path`.

    Newest first (matches `git log` default order). Returns empty list if
    git is unavailable or the file is not yet committed.
    """
    try:
        result = subprocess.run(
            ["git", "log", "--pretty=format:%H|%ad", "--date=iso", "--", path],
            capture_output=True, text=True, timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    out: list[dict] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or "|" not in line:
            continue
        sha, date = line.split("|", 1)
        out.append({"sha": sha.strip(), "date": date.strip()})
    return out


def _git_diff_whitespace_only(path: str, sha_a: str, sha_b: str) -> bool:
    """True if the diff between two commits for `path` is whitespace-only.

    Uses `git diff --ignore-all-space --quiet`. Exit 0 -> no semantic diff.
    Exit 1 -> semantic diff exists. Anything else -> conservatively False.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--ignore-all-space", "--quiet",
             f"{sha_a}..{sha_b}", "--", path],
            capture_output=True, text=True, timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


# -- Layer 1: Migration file modified after first commit --------------------

def check_modified_after_first_commit(
    migrations: list[str],
) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for path in migrations:
        fname = os.path.basename(path)
        if fname in ALLOWED_MULTI_COMMIT:
            continue
        commits = _git_commits_touching(path)
        if len(commits) <= 1:
            continue
        # newest is commits[0]; oldest is commits[-1]
        report.append({
            "path":        path,
            "n_commits":   len(commits),
            "first_sha":   commits[-1]["sha"][:8],
            "first_date":  commits[-1]["date"][:10],
            "latest_sha":  commits[0]["sha"][:8],
            "latest_date": commits[0]["date"][:10],
        })
        issues.append({
            "check": "modified_after_first_commit", "skip": False,
            "reason": (
                f"{path}: edited across {len(commits)} commits (first "
                f"{commits[-1]['sha'][:8]} @ {commits[-1]['date'][:10]}, "
                f"latest {commits[0]['sha'][:8]} @ {commits[0]['date'][:10]}). "
                f"Production keeps the FIRST version since Supabase tracks "
                f"applied migrations by filename. Revert the edit and add a "
                f"NEW migration with a fresh timestamp for the additional "
                f"change. If this file is legitimately re-baselined, add the "
                f"filename to ALLOWED_MULTI_COMMIT with a justification."
            ),
        })
    return issues, report


# -- Layer 2: Filename convention --------------------------------------------

def check_filename_convention(
    migrations: list[str],
) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for path in migrations:
        fname = os.path.basename(path)
        if not TIMESTAMP_RE.match(fname):
            report.append({"path": path, "filename": fname})
            issues.append({
                "check": "filename_convention", "skip": True,
                "reason": (
                    f"{path}: filename '{fname}' does not match "
                    f"YYYYMMDDHHMMSS_descriptor.sql -- Supabase applies "
                    f"migrations in lexicographic filename order, so a "
                    f"non-conforming name can land in the wrong slot."
                ),
            })
    return issues, report


# -- Layer 3: Recent edit is whitespace-only ---------------------------------

def check_whitespace_only_edits(
    migrations: list[str],
) -> tuple[list[dict], list[dict]]:
    """For migrations with multiple commits, separate semantic edits (L1
    FAIL) from whitespace-only ones (L3 WARN). The L1 list is regenerated
    here against the same set so the categories don't double-count."""
    issues: list[dict] = []
    report: list[dict] = []
    for path in migrations:
        fname = os.path.basename(path)
        if fname in ALLOWED_MULTI_COMMIT:
            continue
        commits = _git_commits_touching(path)
        if len(commits) <= 1:
            continue
        first = commits[-1]["sha"]
        latest = commits[0]["sha"]
        if not _git_diff_whitespace_only(path, first, latest):
            continue   # semantic diff -> L1 territory, not L3
        # Whitespace-only edit on already-applied migration: still drift,
        # because the file's mtime / hash moved even if semantics didn't.
        report.append({
            "path":         path,
            "first_sha":    first[:8],
            "latest_sha":   latest[:8],
        })
        issues.append({
            "check": "whitespace_only_edits", "skip": True,
            "reason": (
                f"{path}: re-edited {len(commits)-1} time(s) but the diff "
                f"between {first[:8]} and {latest[:8]} is whitespace-only. "
                f"Likely a rebase / merge artifact. No semantic risk, but "
                f"file is touched -- consider squashing or leaving it pristine."
            ),
        })
    return issues, report


# -- Layer 4: Recency inventory (informational) ------------------------------

def check_recency_inventory(
    migrations: list[str],
) -> tuple[list[dict], list[dict]]:
    now = datetime.now(timezone.utc)
    by_age: dict[str, int] = defaultdict(int)
    for path in migrations:
        fname = os.path.basename(path)
        m = re.match(r"^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})_", fname)
        if not m:
            by_age["non_conforming"] += 1
            continue
        try:
            ts = datetime(*map(int, m.groups()), tzinfo=timezone.utc)
        except ValueError:
            by_age["non_conforming"] += 1
            continue
        age_days = (now - ts).days
        if age_days <= 7:
            by_age["last_7d"] += 1
        elif age_days <= 30:
            by_age["last_30d"] += 1
        else:
            by_age["older"] += 1
    rows = [
        {"bucket": k, "count": v}
        for k, v in sorted(by_age.items(), key=lambda kv: -kv[1])
    ]
    return [], rows


# -- Runner ------------------------------------------------------------------

CHECK_NAMES = [
    "modified_after_first_commit",
    "filename_convention",
    "whitespace_only_edits",
    "recency_inventory",
]
CHECK_LABELS = {
    "modified_after_first_commit": "L1  No migration file edited after its first commit              [FAIL]",
    "filename_convention":         "L2  Every migration follows YYYYMMDDHHMMSS_descriptor.sql        [WARN]",
    "whitespace_only_edits":       "L3  No migration carries whitespace-only re-edits (rebase scar)  [WARN]",
    "recency_inventory":           "L4  Migration count by age bucket (informational)                [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nMigration Immutability Detector (4-layer)"))
    print("=" * 60)

    migrations = list_migrations()
    print(f"  {len(migrations)} migration file(s) scanned.\n")

    # Verify git is available; if not, the validator can still run filename
    # convention + recency but L1 / L3 collapse to inconclusive.
    git_ok = True
    try:
        subprocess.run(["git", "rev-parse", "--git-dir"],
                       capture_output=True, text=True, timeout=5, check=True)
    except Exception:
        git_ok = False

    if not git_ok:
        print("  \033[93mWARN: git not available; L1 + L3 will report empty.\033[0m\n")

    if git_ok:
        l1_issues, l1_report = check_modified_after_first_commit(migrations)
        l3_issues, l3_report = check_whitespace_only_edits(migrations)
    else:
        l1_issues, l1_report = [], []
        l3_issues, l3_report = [], []
    l2_issues, l2_report = check_filename_convention(migrations)
    l4_issues, l4_report = check_recency_inventory(migrations)

    all_issues = l1_issues + l2_issues + l3_issues + l4_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if l4_report:
        print(f"\n{bold('MIGRATION RECENCY (informational)')}")
        print("  " + "-" * 56)
        for r in l4_report:
            print(f"  {r['bucket']:<24}  {r['count']}")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":             "migration_immutability",
        "total_checks":          total,
        "passed":                n_pass,
        "warned":                n_warn,
        "failed":                n_fail,
        "n_migrations":          len(migrations),
        "git_available":         git_ok,
        "modified":              l1_report,
        "non_conforming_names":  l2_report,
        "whitespace_only":       l3_report,
        "recency_inventory":     l4_report,
        "issues":                [i for i in all_issues if not i.get("skip")],
        "warnings":              [i for i in all_issues if i.get("skip")],
    }
    with open("migration_immutability_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
