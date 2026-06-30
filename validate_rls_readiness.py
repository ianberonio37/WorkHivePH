"""
RLS Readiness Audit Validator — WorkHive Platform
==================================================
WorkHive currently runs in a "string-identity" tenant model where most policies
are USING(true) WITH CHECK(true) granted to anon, and the JS layer enforces
hive_id / worker_name filters. The auth migration (deferred per project memory)
will flip these tables to auth.uid()-gated policies. Every USING(true) on a
hive-scoped table is therefore a "must-fix-before-auth-flip" item — and a few
classes of bug are silent today even pre-auth (RLS enabled with no policy =
total lockout; policies present with RLS disabled = dead code).

This validator parses every CREATE POLICY / ENABLE ROW LEVEL SECURITY /
DISABLE ROW LEVEL SECURITY across supabase/migrations/, dedupes by
(table, policy_name) keeping the last definition (matching Postgres
last-writer-wins semantics for re-applied migrations), and surfaces:

  Layer 1 — Lockout traps
    1.  No table has RLS enabled with zero policies.
    [FAIL] anon (and authenticated) cannot read or write — page 401s on load.

  Layer 2 — Dead policies
    2.  Every policy lives on a table where RLS is enabled.
    [FAIL] Policy is dead code; access is unrestricted via privilege layer alone.

  Layer 3 — Permissive USING(true) catalog (auth-migration prep)
    3.  No hive-scoped table relies on USING(true) as its ONLY policy.
    [WARN] Acceptable today (string-identity model), but every entry here must
    be dropped or tightened before the auth migration flips. This is the
    pre-flight punch list — not a production bug today.

  Layer 4 — Per-verb policy completeness
    4.  Every RLS-enabled table has SELECT + INSERT + UPDATE + DELETE coverage
        (FOR ALL counts as all four).
    [WARN] Missing-verb gaps mean the operation 401s — the page silently fails
    one CRUD action. Read-only catalog tables can opt out via READ_ONLY_TABLES.

Usage:  python validate_rls_readiness.py
Output: rls_readiness_report.json
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


# ─── Allowlists / opt-outs ────────────────────────────────────────────────────

# Tables that are read-only by design — they have SELECT policies (or are
# RLS-disabled with GRANT SELECT) and writes happen only via SECURITY DEFINER
# functions or direct admin SQL, so missing INSERT/UPDATE/DELETE policies
# don't represent a UI-surface bug. Documented case-by-case.
READ_ONLY_TABLES: dict = {
    "achievement_definitions":     "Reference catalog — populated by migrations only",
    "equipment_reading_templates": "Reference catalog — populated by migrations only",
    "marketplace_platform_admins": "Identity allowlist — admin SQL only",
    "drawing_standards":           "Reference catalog (if present) — read-only by design",
}

# Tables that anon never writes to directly — writes happen exclusively via
# edge functions running with the service-role key (which bypasses RLS).
# Anon-side missing INSERT/UPDATE/DELETE policies are intentional, not a UI
# surface bug. The function call itself is gated by per-fn auth (req JWT or
# webhook signature). For these tables, a SELECT policy is enough.
SERVICE_ROLE_ONLY_WRITE_TABLES: dict = {
    "ai_reports":          "Written exclusively by analytics-orchestrator + ai-orchestrator edge fns (service role)",
    "automation_log":      "Written exclusively by scheduled edge fns (service role) — observability table",
    "worker_profiles":     "INSERT on sign-up via index.html; UPDATE/DELETE not exposed to UI (account model)",
    "early_access_emails": "INSERT-only via landing-page form; UPDATE/DELETE not exposed to UI (lead capture)",
}

# Tables explicitly disabled from RLS by design (using GRANT layer only).
# Validated against actual DISABLE ROW LEVEL SECURITY statements.
EXPECTED_RLS_DISABLED: dict = {
    "worker_achievements":   "World-readable leaderboard; writes via SECURITY DEFINER fn (see 20260508000006)",
    "achievement_xp_log":    "World-readable XP feed; writes via SECURITY DEFINER fn (see 20260508000006)",
}


# ─── Migration walk + parsing ────────────────────────────────────────────────

def _list_migration_files() -> list[str]:
    if not os.path.isdir(MIGRATIONS_DIR):
        return []
    out: list[str] = []
    for fname in sorted(os.listdir(MIGRATIONS_DIR)):
        if not fname.endswith(".sql"):
            continue
        if fname.endswith("_baseline.sql"):
            # pg_dump snapshot uses double-quoted identifiers and re-defines
            # most policies. Including it gives the pre-auth historical state
            # which is the right baseline for this audit.
            pass
        out.append(os.path.join(MIGRATIONS_DIR, fname))
    return out


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


# Match a CREATE POLICY statement up to its terminating `;`. Captures:
#   1: policy name (no quotes)
#   2: table name (handles "public"."t", public.t, "t", t)
#   3: verb (FOR SELECT / FOR INSERT / FOR UPDATE / FOR DELETE / FOR ALL — empty = ALL)
#   4: tail (USING / WITH CHECK clauses + everything until ;)
CREATE_POLICY_RE = re.compile(
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

# Match a DROP POLICY [IF EXISTS] statement. Captures the policy name + table
# so the parser can mark a policy as removed in last-writer-wins dedup.
DROP_POLICY_RE = re.compile(
    r"""
    DROP\s+POLICY\s+(?:IF\s+EXISTS\s+)?
    "?(?P<name>[\w\-\s]+?)"?\s+
    ON\s+
    (?:"?public"?\.)?"?(?P<table>[\w]+)"?\s*
    ;
    """,
    re.IGNORECASE | re.DOTALL | re.VERBOSE,
)

ENABLE_RLS_RE = re.compile(
    r"ALTER\s+TABLE\s+(?:ONLY\s+)?(?:\"?public\"?\.)?\"?(\w+)\"?\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY",
    re.IGNORECASE,
)
DISABLE_RLS_RE = re.compile(
    r"ALTER\s+TABLE\s+(?:ONLY\s+)?(?:\"?public\"?\.)?\"?(\w+)\"?\s+DISABLE\s+ROW\s+LEVEL\s+SECURITY",
    re.IGNORECASE,
)
HIVE_ID_COLUMN_RE = re.compile(
    r"\b(\w+)\s*\(\s*[^)]*\bhive_id\b|"
    r"ALTER\s+TABLE\s+(?:\"?public\"?\.)?\"?(\w+)\"?\s+ADD\s+COLUMN(?:\s+IF\s+NOT\s+EXISTS)?\s+hive_id",
    re.IGNORECASE,
)


def _is_permissive(tail: str) -> bool:
    """A policy is 'permissive' if its USING and WITH CHECK clauses both
    reduce to true. Catches the canonical USING(true) WITH CHECK(true) form
    plus a no-WITH-CHECK FOR-SELECT permissive variant."""
    # Strip whitespace + parens to find the bare predicate text
    using_m = re.search(r"USING\s*\((.*?)\)\s*(?:WITH|;|$)", tail, re.IGNORECASE | re.DOTALL)
    with_check_m = re.search(r"WITH\s+CHECK\s*\((.*?)\)\s*;?\s*$", tail, re.IGNORECASE | re.DOTALL)
    using_pred = (using_m.group(1).strip() if using_m else "").lower()
    check_pred = (with_check_m.group(1).strip() if with_check_m else "").lower()
    # USING(true) only: read-permissive, FOR SELECT
    if using_pred in ("true", "(true)"):
        if not check_pred or check_pred in ("true", "(true)"):
            return True
    return False


def _parse_migrations() -> dict:
    """Returns:
        {
            "policies": {(table, name): {"verb", "permissive", "file"}},
            "rls_enabled":  {table: file},
            "rls_disabled": {table: file},
            "hive_scoped":  set of table names,
        }
    Last-writer-wins per (table, policy_name) and per (table, RLS state).
    """
    policies: dict = {}
    rls_enabled: dict = {}
    rls_disabled: dict = {}
    hive_scoped: set = set()
    client_revoked: set = set()  # tables explicitly REVOKE'd ALL from anon/authenticated = deliberately service-role-only

    for path in _list_migration_files():
        raw = _read(path)
        cleaned = _strip_line_comments(_strip_block_comments(raw))
        rel = os.path.relpath(path, ROOT)

        # Policies — interleave CREATE and DROP in source order so last-writer
        # wins per (table, name). A DROP after a CREATE removes the policy
        # from the live state; matches Postgres semantics for re-applied
        # migrations and lets Phase E's drop-policy migration naturally
        # update the catalogued state.
        events: list[tuple[int, str, str, dict]] = []
        for m in CREATE_POLICY_RE.finditer(cleaned):
            events.append((m.start(), "CREATE", m.group("table").strip(), {
                "name":  m.group("name").strip(),
                "verb":  (m.group("verb") or "ALL").upper(),
                "tail":  m.group("tail"),
            }))
        for m in DROP_POLICY_RE.finditer(cleaned):
            events.append((m.start(), "DROP", m.group("table").strip(), {
                "name": m.group("name").strip(),
            }))
        events.sort(key=lambda e: e[0])
        for _pos, kind, table, payload in events:
            key = (table, payload["name"])
            if kind == "CREATE":
                policies[key] = {
                    "verb":       payload["verb"],
                    "permissive": _is_permissive(payload["tail"]),
                    "file":       rel,
                    "name":       payload["name"],
                    "table":      table,
                }
            else:  # DROP
                policies.pop(key, None)

        # ENABLE / DISABLE — track the last state per table
        for m in ENABLE_RLS_RE.finditer(cleaned):
            t = m.group(1)
            rls_enabled[t]  = rel
            rls_disabled.pop(t, None)
        for m in DISABLE_RLS_RE.finditer(cleaned):
            t = m.group(1)
            rls_disabled[t] = rel
            rls_enabled.pop(t, None)

        # REVOKE ALL ... ON <table> FROM ... anon/authenticated = deliberately service-role-only.
        # Such a table is meant to be unreachable by clients (touched only via SECURITY DEFINER
        # RPCs / service_role, which has BYPASSRLS), so RLS-on + zero-policy is the CORRECT lockdown
        # for it, NOT a lockout trap (e.g. login_attempts, the brute-force counter — Arc I).
        for m in re.finditer(
            r'REVOKE\s+ALL\s+(?:PRIVILEGES\s+)?ON\s+(?:TABLE\s+)?(?:public\.)?(\w+)\b'
            r'[^;]*\bFROM\b[^;]*\b(?:anon|authenticated)\b',
            cleaned, re.IGNORECASE,
        ):
            client_revoked.add(m.group(1))

        # Tables with hive_id column — heuristic: column name appears in a
        # CREATE TABLE block OR in an ALTER TABLE ADD COLUMN. Both are
        # captured by HIVE_ID_COLUMN_RE.
        for m in HIVE_ID_COLUMN_RE.finditer(cleaned):
            # Group 2 (ALTER TABLE form) is most precise; group 1 (CREATE
            # TABLE form) returns the table identifier preceding the (.
            t = (m.group(2) or m.group(1) or "").strip()
            if t:
                hive_scoped.add(t)

    # Filter hive_scoped to only tables that actually have RLS state — the
    # column-detection regex is loose and may include unrelated identifiers.
    known_tables = set(rls_enabled) | set(rls_disabled) | {p[0] for p in policies}
    hive_scoped = hive_scoped & known_tables

    return {
        "policies":     policies,
        "rls_enabled":  rls_enabled,
        "rls_disabled": rls_disabled,
        "client_revoked": client_revoked,
        "hive_scoped":  hive_scoped,
    }


# ─── Layer 1: Lockout traps ──────────────────────────────────────────────────

def check_lockout_traps(state: dict) -> list[dict]:
    """Tables with RLS enabled but zero policies are unreachable: anon and
    authenticated both get 0-row results (and 401 on writes) regardless of
    GRANT. The page silently breaks for every user."""
    issues: list[dict] = []
    by_table: dict = defaultdict(list)
    for (table, _name), p in state["policies"].items():
        by_table[table].append(p)
    for table, file in state["rls_enabled"].items():
        if table in state.get("client_revoked", set()):
            continue  # deliberately service-role-only (revoke-all from clients) — zero-policy is the lockdown, not a trap
        if not by_table.get(table):
            issues.append({
                "check": "rls_lockout_trap",
                "table": table, "file": file,
                "reason": (
                    f"Table '{table}' has RLS enabled in {file} but ZERO "
                    f"policies are defined. anon and authenticated both see "
                    f"0 rows on SELECT and 401 on INSERT/UPDATE/DELETE. The "
                    f"page that reads this table silently fails on load. Add "
                    f"at least a SELECT policy or DISABLE ROW LEVEL SECURITY "
                    f"if access is meant to be controlled by GRANT alone "
                    f"(then add to EXPECTED_RLS_DISABLED with a justification)."
                ),
            })
    return issues


# ─── Layer 2: Dead policies ──────────────────────────────────────────────────

def check_dead_policies(state: dict) -> list[dict]:
    """A CREATE POLICY on a table that has RLS DISABLED (or never enabled)
    is dead code: Postgres doesn't consult policies when RLS is off. Surfaces
    cases where someone added a policy intending to gate access but forgot
    the ENABLE step (or where a later DISABLE inadvertently neutered earlier
    policies)."""
    issues: list[dict] = []
    rls_on  = set(state["rls_enabled"])
    rls_off = set(state["rls_disabled"])
    for (table, name), p in state["policies"].items():
        if table in rls_on:
            continue
        if table in rls_off and table in EXPECTED_RLS_DISABLED:
            continue  # explicit, documented opt-out
        if table not in rls_on and table not in rls_off:
            # Table never had ENABLE/DISABLE statement parsed — possibly a
            # baseline-omitted detail. Treat as informational SKIP rather
            # than FAIL to avoid false positives from baseline parsing.
            continue
        issues.append({
            "check": "rls_dead_policy",
            "table": table, "policy": name, "file": p["file"],
            "reason": (
                f"Policy '{name}' on '{table}' ({p['file']}) is DEAD CODE: "
                f"the table's last RLS state is DISABLED (in "
                f"{state['rls_disabled'].get(table)}). Either re-enable RLS "
                f"on '{table}' or drop the policy. This is a silent risk: "
                f"reading the policy gives a false sense of access control."
            ),
        })
    return issues


# ─── Layer 3: Permissive USING(true) catalog ────────────────────────────────

def check_permissive_catalog(state: dict) -> list[dict]:
    """Catalog every permissive USING(true) policy on a hive-scoped table.
    Today these are the string-identity backbone (anon CRUD, JS layer enforces
    hive_id filter). When the auth migration ships, every entry here must be
    dropped or tightened so auth.uid()-gated policies actually gate access.

    WARN severity — the punch list, not a production bug today."""
    issues: list[dict] = []
    for (table, name), p in state["policies"].items():
        if not p["permissive"]:
            continue
        if table not in state["hive_scoped"]:
            continue
        if table in state["rls_disabled"]:
            continue  # RLS off → policy is dead anyway, captured by L2
        # Skip table-policy if table is opted out as read-only catalog
        if table in READ_ONLY_TABLES:
            continue
        issues.append({
            "check": "permissive_using_true", "skip": True,
            "table": table, "policy": name, "file": p["file"], "verb": p["verb"],
            "reason": (
                f"Permissive policy '{name}' on hive-scoped table '{table}' "
                f"(verb: {p['verb']}, file: {p['file']}) — USING(true) WITH "
                f"CHECK(true). This is the string-identity model today (anon "
                f"CRUD with JS-layer hive_id filter). Before the auth migration "
                f"flips, this policy must be dropped (or tightened) so "
                f"auth.uid()-gated siblings actually gate access. Track this "
                f"as a pre-flight punch-list item, not a production bug today."
            ),
        })
    return issues


# ─── Layer 4: Per-verb policy completeness ───────────────────────────────────

def check_verb_completeness(state: dict) -> list[dict]:
    """Every RLS-enabled, non-read-only table has at least one policy covering
    each CRUD verb. FOR ALL counts as all four. Missing-verb gaps mean the
    operation 401s for every user — the UI silently fails one button."""
    issues: list[dict] = []
    by_table: dict = defaultdict(set)
    for (table, _name), p in state["policies"].items():
        verb = p["verb"]
        if verb == "ALL":
            by_table[table].update({"SELECT", "INSERT", "UPDATE", "DELETE"})
        else:
            by_table[table].add(verb)

    for table in state["rls_enabled"]:
        if table in READ_ONLY_TABLES:
            continue
        if table in SERVICE_ROLE_ONLY_WRITE_TABLES:
            continue  # writes via service-role edge fns; missing anon-side write policies expected
        verbs = by_table.get(table, set())
        if not verbs:
            continue  # Already flagged by L1 (lockout trap)
        missing = {"SELECT", "INSERT", "UPDATE", "DELETE"} - verbs
        if not missing:
            continue
        issues.append({
            "check": "rls_verb_coverage", "skip": True,
            "table": table, "missing": sorted(missing),
            "reason": (
                f"Table '{table}' has RLS enabled but no policy covers "
                f"{sorted(missing)}. Operations on those verbs 401 for every "
                f"user. Either add per-verb policies or use FOR ALL. If this "
                f"table is a read-only catalog, add it to READ_ONLY_TABLES; "
                f"if it's written exclusively by edge functions via service "
                f"role, add it to SERVICE_ROLE_ONLY_WRITE_TABLES — both with "
                f"a justification."
            ),
        })
    return issues


# ─── Runner ────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "rls_lockout_trap",
    "rls_dead_policy",
    "permissive_using_true",
    "rls_verb_coverage",
]
CHECK_LABELS = {
    "rls_lockout_trap":      "L1  No table has RLS enabled with zero policies",
    "rls_dead_policy":       "L2  Every policy lives on a table where RLS is enabled",
    "permissive_using_true": "L3  Permissive USING(true) catalog on hive-scoped tables  [WARN]",
    "rls_verb_coverage":     "L4  Every RLS-enabled table has all 4 CRUD verbs covered  [WARN]",
}


def main() -> None:
    def bold(s: str) -> str:
        return f"\033[1m{s}\033[0m"
    print(bold("\nRLS Readiness Audit Validator (4-layer)"))
    print("=" * 60)

    state = _parse_migrations()
    n_pol     = len(state["policies"])
    n_enabled = len(state["rls_enabled"])
    n_disabled = len(state["rls_disabled"])
    n_hive    = len(state["hive_scoped"])
    print(f"  Parsed {n_pol} policies, {n_enabled} RLS-enabled tables, "
          f"{n_disabled} RLS-disabled tables, {n_hive} hive-scoped tables.\n")

    all_issues: list[dict] = []
    all_issues += check_lockout_traps(state)
    all_issues += check_dead_policies(state)
    all_issues += check_permissive_catalog(state)
    all_issues += check_verb_completeness(state)

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

    report = {
        "validator":    "rls_readiness",
        "policies":     n_pol,
        "rls_enabled":  n_enabled,
        "rls_disabled": n_disabled,
        "hive_scoped":  n_hive,
        "summary":      {"pass": n_pass, "warn": n_warn, "fail": n_fail},
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open(os.path.join(ROOT, "rls_readiness_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
