"""
Auth Migration Readiness Validator — WorkHive Platform (Phase A audit)
======================================================================
Phase A of the Supabase Auth migration. Static-only audit that confirms
the platform is ready to drop the L3 permissive policies (PRODUCTION_FIXES
#36) without locking out workers. Three-layer audit + a SQL output for
the data-side straggler check (run live, not part of the gate).

  Layer 1 — Auth-gated sibling completeness on permissive tables
    1.  Every L3 table (permissive USING(true) on hive-scoped) has an
        auth.uid()-using policy covering each of SELECT/INSERT/UPDATE/DELETE.
        FOR ALL counts as all four. Without a sibling, dropping the
        permissive policy in Phase E locks workers out of that verb.
    [FAIL] severity — concrete blocker for Phase E.

  Layer 2 — auth_uid column coverage on user-data tables
    2.  Every hive-scoped writer table has an auth_uid column declared.
        The auth-gated policies all reference auth_uid; missing column
        means the policy can never grant access.
    [FAIL] severity — same blocker class as L1.

  Layer 3 — Identity gate strength on Phase B pages
    3.  Every page that already reads _authUid hardens its gate
        (`if (!_authUid) redirect → signin`). Currently most pages
        gate only on WORKER_NAME and treat _authUid as optional —
        a worker with stale localStorage but no Supabase Auth session
        gets in, then 401s when policies flip.
    [WARN] severity — Phase B fix; soft today.

  Output also includes ready-to-run SQL counts for "straggler rows"
  (auth_uid IS NULL but worker_name maps to a worker_profiles match)
  so the data-side gap can be quantified before Phase C ships the backfill.

Usage:  python validate_auth_migration_readiness.py
Output: auth_migration_readiness_report.json
"""
import json
import os
import re
import sys
from collections import defaultdict

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT           = os.path.dirname(os.path.abspath(__file__))
MIGRATIONS_DIR = os.path.join(ROOT, "supabase", "migrations")


# Tables that ride the L3 permissive-policy catalog from validate_rls_readiness.
# Hardcoded here rather than dynamically derived so Phase A is reviewable as a
# punch list independent of the readiness validator's runtime state.
L3_PERMISSIVE_TABLES = [
    "logbook",
    "inventory_transactions",
    "community_posts",
    "community_replies",
    "community_xp",
]

# Hive-scoped writer tables that should carry an auth_uid column. Drawn from
# the project_supabase_auth_migration backfill set + everything users write to.
USER_DATA_TABLES = [
    "logbook",
    "inventory_items",
    "inventory_transactions",
    "assets",
    "pm_assets",
    "pm_completions",
    "pm_scope_items",
    "hive_members",
    "skill_profiles",
    "schedule_items",
    "community_posts",
    "community_replies",
    "community_xp",
    "marketplace_listings",
    "marketplace_sellers",
    "asset_nodes",
    "rcm_fmea_modes",
    "rcm_strategies",
    "weibull_fits",
]

# Pages that already read _authUid (per Grep survey). Phase B hardens these.
PHASE_B_PAGES = [
    "marketplace.html",
    "pm-scheduler.html",
    "inventory.html",
    "logbook.html",
    "project-manager.html",
    "hive.html",
    "dayplanner.html",
    "community.html",
    "skillmatrix.html",
    # index.html handles the auth flow itself; not in this list.
]


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def _strip_block_comments(sql: str) -> str:
    return re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)


def _strip_line_comments(sql: str) -> str:
    out: list[str] = []
    for line in sql.splitlines():
        if line.lstrip().startswith("--"):
            continue
        out.append(line)
    return "\n".join(out)


def _list_migration_files() -> list[str]:
    if not os.path.isdir(MIGRATIONS_DIR):
        return []
    return [
        os.path.join(MIGRATIONS_DIR, f)
        for f in sorted(os.listdir(MIGRATIONS_DIR))
        if f.endswith(".sql")
    ]


def _read_all_migrations() -> str:
    out: list[str] = []
    for p in _list_migration_files():
        out.append(_strip_line_comments(_strip_block_comments(_read(p))))
    return "\n".join(out)


# ─── Layer 1: Auth-gated sibling completeness ────────────────────────────────

# Capture each CREATE POLICY's table, FOR clause, and full USING/WITH CHECK
# tail so we can detect auth.uid() usage.
POLICY_RE = re.compile(
    r"""
    CREATE\s+POLICY\s+
    "?(?P<name>[\w\-\s]+?)"?\s+
    ON\s+
    (?:"?public"?\.)?"?(?P<table>[\w]+)"?\s+
    (?:FOR\s+(?P<verb>SELECT|INSERT|UPDATE|DELETE|ALL)\s+)?
    (?:TO\s+[\w,\s]+\s+)?
    (?P<tail>.*?);
    """,
    re.IGNORECASE | re.DOTALL | re.VERBOSE,
)


def _auth_gated_verbs_per_table(migrations: str) -> dict:
    """Returns {table: set(verbs)} of verbs covered by an auth.uid()-using
    policy. FOR ALL is exploded into the four CRUD verbs."""
    out: dict[str, set[str]] = defaultdict(set)
    for m in POLICY_RE.finditer(migrations):
        table = m.group("table")
        verb  = (m.group("verb") or "ALL").upper()
        tail  = m.group("tail")
        if "auth.uid()" not in tail and 'auth"."uid"()' not in tail:
            continue
        if verb == "ALL":
            out[table].update({"SELECT", "INSERT", "UPDATE", "DELETE"})
        else:
            out[table].add(verb)
    return out


def check_auth_gated_siblings(migrations: str) -> list[dict]:
    issues: list[dict] = []
    coverage = _auth_gated_verbs_per_table(migrations)
    for table in L3_PERMISSIVE_TABLES:
        verbs = coverage.get(table, set())
        missing = {"SELECT", "INSERT", "UPDATE", "DELETE"} - verbs
        if not missing:
            continue
        issues.append({
            "check":   "auth_gated_sibling_coverage",
            "table":   table,
            "missing": sorted(missing),
            "reason": (
                f"L3 permissive table '{table}' is missing auth.uid()-using "
                f"sibling policies for verbs {sorted(missing)}. Dropping the "
                f"USING(true) policy in Phase E would 401 every authed "
                f"worker on those operations. Add a per-verb auth-gated "
                f"policy (or a FOR ALL policy) to '{table}' before Phase E."
            ),
        })
    return issues


# ─── Layer 2: auth_uid column coverage on user-data tables ───────────────────

AUTH_UID_COL_RE = re.compile(
    # Match `auth_uid` declared as a column anywhere — CREATE TABLE body or
    # ALTER TABLE ADD COLUMN. Both forms produce the same downstream effect.
    r"""
    (?:
       \b(?P<t1>\w+)\s*\([^)]*\bauth_uid\b
       |
       ALTER\s+TABLE\s+(?:\"?public\"?\.)?\"?(?P<t2>\w+)\"?\s+
         ADD\s+COLUMN(?:\s+IF\s+NOT\s+EXISTS)?\s+auth_uid
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _tables_with_auth_uid(migrations: str) -> set[str]:
    out: set[str] = set()
    for m in AUTH_UID_COL_RE.finditer(migrations):
        t = (m.group("t2") or m.group("t1") or "").strip()
        if t:
            out.add(t)
    return out


_QUALIFIED_AUTH_UID_RE = re.compile(r'"\w+"\."auth_uid"|\b\w+\.auth_uid\b')


def _tables_whose_policies_reference_auth_uid(migrations: str) -> set[str]:
    """A table needs an auth_uid column ONLY when at least one of its existing
    policies references `auth_uid` UNQUALIFIED (i.e., the polled-table's own
    column). Membership-chain JOINs that reference another table's auth_uid
    (e.g. `hm.auth_uid = auth.uid()` reading hive_members.auth_uid) do NOT
    require auth_uid on the polled table itself.

    Strategy: strip all alias-qualified forms (`"alias"."auth_uid"`,
    `alias.auth_uid`) from the policy tail, then check if `auth_uid` still
    appears. If yes, the column is referenced unqualified → polled table needs
    its own auth_uid column."""
    out: set[str] = set()
    for m in POLICY_RE.finditer(migrations):
        table = m.group("table")
        tail  = m.group("tail")
        stripped = _QUALIFIED_AUTH_UID_RE.sub("", tail)
        if "auth_uid" in stripped:
            out.add(table)
    return out


def check_auth_uid_coverage(migrations: str) -> list[dict]:
    issues: list[dict] = []
    have   = _tables_with_auth_uid(migrations)
    needed = _tables_whose_policies_reference_auth_uid(migrations)
    for table in USER_DATA_TABLES:
        if table in have:
            continue
        if table not in needed:
            # Auth-gated policies on this table use membership-only predicates,
            # not auth_uid comparisons. Column is optional.
            continue
        issues.append({
            "check": "auth_uid_column_coverage",
            "table": table,
            "reason": (
                f"User-data table '{table}' has policies that reference "
                f"`auth_uid` in their predicate, but the column is NOT "
                f"declared in any migration. Auth-gated access cannot be "
                f"granted without the column. Add `ALTER TABLE {table} ADD "
                f"COLUMN IF NOT EXISTS auth_uid uuid REFERENCES auth.users(id) "
                f"ON DELETE SET NULL` in a migration, plus a backfill from "
                f"worker_profiles."
            ),
        })
    return issues


# ─── Layer 3: Identity gate strength on Phase B pages ────────────────────────

def check_identity_gate_strength() -> list[dict]:
    issues: list[dict] = []
    for page in PHASE_B_PAGES:
        path = os.path.join(ROOT, page)
        src = _read(path)
        if not src:
            continue
        # Page reads _authUid (precondition for the check)
        if "_authUid" not in src:
            continue
        # Two valid gate patterns:
        #   (a) Strong:  `if (!_authUid) { ...signin... }`
        #       — used by pages that already require WORKER_NAME first
        #   (b) Softer:  `if (WORKER_NAME && !_authUid) { ...signin... }`
        #       — used by pages with intentional anon-browsing surface (e.g.,
        #         marketplace listings); blocks stale-localStorage workers
        #         without blocking true anon visitors
        # Either pattern satisfies Phase B. Search the entire file rather than
        # a head window — gate may be in DOMContentLoaded handler near EOF.
        has_strong_gate = bool(re.search(
            r"if\s*\(\s*!\s*_authUid\s*\)[^{]*\{[^}]*(?:signin|location\.href|redirect)",
            src, re.IGNORECASE | re.DOTALL,
        ))
        has_softer_gate = bool(re.search(
            r"if\s*\(\s*WORKER_NAME\s*&&\s*!\s*_authUid\s*\)[^{]*\{[^}]*(?:signin|location\.href|redirect)",
            src, re.IGNORECASE | re.DOTALL,
        ))
        if has_strong_gate or has_softer_gate:
            continue
        issues.append({
            "check": "identity_gate_strength", "skip": True,
            "page":  page,
            "reason": (
                f"{page} reads `_authUid` from db.auth.getSession() but does "
                f"not require it as a gate. Workers with stale localStorage "
                f"WORKER_NAME but no Supabase Auth session can still load "
                f"the page; their inserts go through with auth_uid=null and "
                f"will 401 the moment Phase E drops permissive policies. Add "
                f"`if (!_authUid) {{ window.location.href='index.html?signin=1'; "
                f"return; }}` near the top of the script init."
            ),
        })
    return issues


# ─── Straggler-row SQL queries (informational, run live) ─────────────────────

def straggler_queries() -> list[dict]:
    """Generate ready-to-run SQL counts per user-data table. The user runs
    these in Supabase Dashboard SQL Editor to quantify the Phase C backfill
    scope. Static-only validators don't have DB access."""
    queries: list[dict] = []
    for table in USER_DATA_TABLES:
        sql = (
            f"-- Stragglers in {table}: rows with worker_name but no auth_uid\n"
            f"SELECT COUNT(*) AS straggler_count, COUNT(DISTINCT worker_name) AS distinct_workers\n"
            f"FROM public.{table} t\n"
            f"WHERE t.auth_uid IS NULL\n"
            f"  AND t.worker_name IN (SELECT display_name FROM public.worker_profiles);"
        )
        queries.append({"table": table, "sql": sql})
    return queries


# ─── Runner ────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "auth_gated_sibling_coverage",
    "auth_uid_column_coverage",
    "identity_gate_strength",
]
CHECK_LABELS = {
    "auth_gated_sibling_coverage": "L1  Every L3 permissive table has auth-gated siblings for all 4 CRUD verbs",
    "auth_uid_column_coverage":    "L2  Every user-data table has an auth_uid column declared",
    "identity_gate_strength":      "L3  Every Phase B page hardens `if (!_authUid) redirect` as a gate  [WARN]",
}


def main() -> None:
    def bold(s: str) -> str:
        return f"\033[1m{s}\033[0m"
    print(bold("\nAuth Migration Readiness Validator (Phase A audit, 3-layer)"))
    print("=" * 65)

    migrations = _read_all_migrations()

    all_issues: list[dict] = []
    all_issues += check_auth_gated_siblings(migrations)
    all_issues += check_auth_uid_coverage(migrations)
    all_issues += check_identity_gate_strength()

    by_check: dict = defaultdict(list)
    for i in all_issues:
        by_check[i["check"]].append(i)

    n_pass = n_warn = n_fail = 0
    for name in CHECK_NAMES:
        items = by_check.get(name, [])
        warns = [i for i in items if i.get("skip")]
        fails = [i for i in items if not i.get("skip")]
        label = CHECK_LABELS[name]
        if not items:
            print(f"  \033[92mPASS\033[0m  {label}")
            n_pass += 1
        elif not fails:
            print(f"  \033[93mSKIP\033[0m  {label}")
            n_warn += 1
        else:
            print(f"  \033[91mFAIL\033[0m  {label}")
            n_fail += 1

    if all_issues:
        print(f"\n\033[91mIssues:\033[0m")
        for i in all_issues:
            tag = "\033[93mSKIP\033[0m" if i.get("skip") else "\033[91mFAIL\033[0m"
            print(f"  [{tag}] [{i['check']}]  {i['reason']}")

    print(f"\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL")
    print(f"\n  See auth_migration_readiness_report.json for the live SQL")
    print(f"  straggler-count queries (Phase C scoping).")

    report = {
        "validator":          "auth_migration_readiness",
        "phase":              "A_audit",
        "summary":            {"pass": n_pass, "warn": n_warn, "fail": n_fail},
        "issues":             [i for i in all_issues if not i.get("skip")],
        "warnings":           [i for i in all_issues if i.get("skip")],
        "straggler_queries":  straggler_queries(),
    }
    with open(os.path.join(ROOT, "auth_migration_readiness_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
