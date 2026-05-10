"""
Canonical Sources Validator - WorkHive Platform
================================================
Foundation validator for the Canonical Sources initiative (Phase A.1+).
Every domain concept on the platform should have one entry in the
`canonical_sources` registry. AI agents read from the registry first when
asked about a registered domain so the answer is consistent across
orchestrators, edge functions, and UI pages.

Layer 1 - Registry health
  1.  Migration declares the canonical_sources table        [FAIL]
  2.  Migration locks writes to service role only           [FAIL]
  3.  Migration grants SELECT to anon and authenticated     [FAIL]
  4.  Initial seed registers at least the 6 ALIGNED truths  [FAIL]

Layer 2 - Drift detection (active when consumers refactor to canonicals)
  5.  No edge function reads underlying table directly when
      a canonical view exists for that domain                [WARN]
  6.  No HTML page reads underlying table directly when a
      canonical view exists for that domain                  [WARN]

Layer 3 - Contract integrity (active when v_*_truth views land)
  7.  Every registered view/table exists in migrations       [FAIL]
  8.  Contract JSONB declares non-empty 'key' array          [WARN]

Phase A.1 only enforces Layer 1. Layers 2 and 3 activate progressively
as v_asset_truth, v_risk_truth, v_pm_compliance_truth, and the rest land.

Skills consulted: architect (registry pattern, contract metadata),
data-engineer (immutable schema, narrow lookups), security (locked write
policy, anon read for AI lookup), multitenant-engineer (no hive_id on
registry - this is platform metadata).

Usage:  python validate_canonical_sources.py
Output: canonical_sources_report.json
"""
import re
import json
import sys
import os
import glob

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

MIGRATION_PATH = os.path.join(
    "supabase", "migrations", "20260509000001_canonical_sources_foundation.sql"
)
MIGRATIONS_DIR = os.path.join("supabase", "migrations")

# Tier 3 from CANONICAL_SOURCES_AUDIT.md: domains that are already aligned
# and just need registration. Phase A.1 seeds these into the registry.
ALIGNED_TRUTHS = [
    "shift_state",
    "asset_graph_edges",
    "community_thread",
    "engineering_calc_history",
    "cmms_external_link",
    "ai_rate_limit",
    # Three audit logs (D5 from the audit, kept separate as different domains
    # but registered so AI agents know which one to query)
    "automation_log",
    "hive_audit_log",
    "cmms_audit_log",
]

CHECK_NAMES = [
    "registry_table_declared",
    "registry_writes_locked",
    "registry_select_granted",
    "registry_seeded_aligned",
    "registry_sources_exist",
]

CHECK_LABELS = {
    "registry_table_declared":  "L1  canonical_sources table declared in migration              [FAIL]",
    "registry_writes_locked":   "L1  Write policy locked (USING false WITH CHECK false)         [FAIL]",
    "registry_select_granted":  "L1  GRANT SELECT to anon and authenticated                     [FAIL]",
    "registry_seeded_aligned":  "L1  Initial seed registers all aligned truths from the audit   [FAIL]",
    "registry_sources_exist":   "L3  Every registered source_name exists in migrations          [FAIL]",
}


def _read_migration():
    return read_file(MIGRATION_PATH) or ""


# ── Layer 1: Registry health ─────────────────────────────────────────────────

def check_registry_table_declared(text):
    if not text:
        return [{
            "check": "registry_table_declared",
            "reason": (
                f"{MIGRATION_PATH} missing. The canonical_sources registry is "
                f"the foundation of the truth-scattering fix; nothing else can "
                f"register without it."
            ),
        }]
    if "CREATE TABLE IF NOT EXISTS public.canonical_sources" not in text:
        return [{
            "check": "registry_table_declared",
            "reason": "canonical_sources table is not declared. Migration must CREATE TABLE IF NOT EXISTS public.canonical_sources.",
        }]
    required_cols = ["domain", "source_kind", "source_name", "owner_skill", "freshness", "contract"]
    missing = [c for c in required_cols if not re.search(rf"\b{c}\b", text)]
    if missing:
        return [{
            "check": "registry_table_declared",
            "reason": f"canonical_sources missing required columns: {missing}",
        }]
    return []


def check_registry_writes_locked(text):
    if not text:
        return [{"check": "registry_writes_locked", "reason": f"{MIGRATION_PATH} missing."}]
    # Need a FOR ALL policy with USING (false) WITH CHECK (false) to block writes
    pat = re.compile(
        r"CREATE POLICY[^;]+canonical_sources[^;]+FOR ALL[^;]+USING\s*\(\s*false\s*\)[^;]+WITH CHECK\s*\(\s*false\s*\)",
        re.IGNORECASE | re.DOTALL,
    )
    if not pat.search(text):
        return [{
            "check": "registry_writes_locked",
            "reason": (
                "canonical_sources needs a FOR ALL policy with USING (false) WITH CHECK (false) "
                "so anon and authenticated cannot write to the registry. Service role bypasses RLS "
                "and is the only legitimate writer."
            ),
        }]
    return []


def check_registry_select_granted(text):
    if not text:
        return [{"check": "registry_select_granted", "reason": f"{MIGRATION_PATH} missing."}]
    pat = re.compile(
        r"GRANT[^;]*SELECT[^;]*ON\s+public\.canonical_sources[^;]*TO[^;]*authenticated",
        re.IGNORECASE | re.DOTALL,
    )
    if not pat.search(text):
        return [{
            "check": "registry_select_granted",
            "reason": (
                "GRANT SELECT to anon and authenticated is required so AI agents (running with "
                "anon key from edge functions) can look up canonicals. Without GRANT, every "
                "lookup returns 401 even though RLS allows reads."
            ),
        }]
    return []


def check_registry_seeded_aligned(text):
    if not text:
        return [{"check": "registry_seeded_aligned", "reason": f"{MIGRATION_PATH} missing."}]
    issues = []
    for domain in ALIGNED_TRUTHS:
        if not re.search(rf"'\s*{re.escape(domain)}\s*'", text):
            issues.append({
                "check": "registry_seeded_aligned",
                "reason": (
                    f"Aligned truth '{domain}' is not seeded in the migration. The audit "
                    f"identified it as already-canonical and ready to register on day one."
                ),
            })
    return issues


# ── Layer 3: Source existence (active for views as they land) ─────────────────

def _registered_sources_from_migration(text):
    """Extract (domain, source_kind, source_name) tuples from INSERT VALUES."""
    sources = []
    if not text:
        return sources
    # Crude parser: find INSERT INTO public.canonical_sources blocks and
    # extract the first three columns of each VALUES row.
    insert_blocks = re.findall(
        r"INSERT INTO public\.canonical_sources[\s\S]+?ON CONFLICT",
        text,
        re.IGNORECASE,
    )
    for block in insert_blocks:
        # Find ('domain', 'source_kind', 'source_name', ...)
        rows = re.findall(
            r"\(\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*'([^']+)'",
            block,
        )
        for d, k, n in rows:
            sources.append((d, k, n))
    return sources


def check_registry_sources_exist(text):
    """For every (kind=table) registration, the table must exist in some migration.
    For (kind=view), the view must exist (parsed by validate_schema_coverage's logic).
    Phase A.1 only checks tables; views are covered when v_*_truth lands."""
    if not text:
        return [{"check": "registry_sources_exist", "reason": f"{MIGRATION_PATH} missing."}]

    sources = _registered_sources_from_migration(text)
    if not sources:
        # Nothing seeded yet; not a fail at A.1 if we already passed seeded_aligned
        return []

    # Build set of all CREATE TABLE names across migrations
    all_tables = set()
    for path in glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql")):
        sql = read_file(path) or ""
        # strip line comments
        sql = re.sub(r"--[^\n]*", "", sql)
        for m in re.finditer(
            r'CREATE TABLE (?:IF NOT EXISTS )?(?:"?\w+"?\.)?"?(\w+)"?\s*\(',
            sql,
            re.IGNORECASE,
        ):
            all_tables.add(m.group(1))
        for m in re.finditer(
            r'CREATE (?:OR REPLACE )?(?:MATERIALIZED )?VIEW\s+(?:"?\w+"?\.)?"?(\w+)"?',
            sql,
            re.IGNORECASE,
        ):
            all_tables.add(m.group(1))

    issues = []
    for domain, kind, name in sources:
        if kind in ("table", "view") and name not in all_tables:
            issues.append({
                "check": "registry_sources_exist",
                "reason": (
                    f"Domain '{domain}' registers source '{name}' (kind={kind}) but no migration "
                    f"declares a table or view with that name. Either the source is a typo or "
                    f"the migration that creates it has not landed yet."
                ),
            })
    return issues


# ── Runner ────────────────────────────────────────────────────────────────────

def main():
    def bold(s):
        return f"\033[1m{s}\033[0m"

    print(bold("\nCanonical Sources Validator"))
    print("=" * 50)

    text = _read_migration()

    all_issues = []
    all_issues += check_registry_table_declared(text)
    all_issues += check_registry_writes_locked(text)
    all_issues += check_registry_select_granted(text)
    all_issues += check_registry_seeded_aligned(text)
    all_issues += check_registry_sources_exist(text)

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "canonical_sources",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("canonical_sources_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
