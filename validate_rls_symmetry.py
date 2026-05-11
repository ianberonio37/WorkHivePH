"""
RLS Policy Symmetry Detector -- WorkHive Platform
==================================================
Catches asymmetric RLS policy coverage. The risk: a table with an INSERT
policy but no SELECT policy lets workers WRITE rows they then cannot READ
back -- the page renders as if the save silently failed. The opposite
shape (SELECT-only on a table that needs writes from the UI) is the
read-only-by-mistake bug.

Layer 1 -- Write without read                                            [WARN]
  Any user-writable table (INSERT, UPDATE, or DELETE policy present) must
  also have a SELECT policy. Without it, a worker who writes a row cannot
  see it -- the UI looks broken even though the write succeeded.

Layer 2 -- Read without create on user-data tables                       [WARN]
  Tables clearly intended for user data (FK-rich, high-write-frequency)
  with SELECT but no INSERT policy are usually misconfigured. Catalog
  tables (achievement_definitions, equipment_reading_templates) are
  legitimately read-only and exempt by allowlist.

Layer 3 -- Update gap                                                    [WARN]
  Tables with INSERT but no UPDATE policy let workers create rows but
  never fix mistakes. Frequently a missed gap when a feature ships.

Layer 4 -- CRUD coverage matrix (informational)                          [INFO]
  Per-table breakdown of which verbs have policies. Helps spot patterns:
  full CRUD on user data, INSERT-only on event/log tables, SELECT-only
  on catalogs.

Skills consulted: security (auth boundaries, RLS as primary access
control), data-engineer (RLS from day one rule), multitenant-engineer
(hive isolation, role/permission edge cases).
"""
from __future__ import annotations

import re
import json
import sys
import os
import glob
from collections import defaultdict

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


MIGRATIONS_DIR = os.path.join("supabase", "migrations")

# Tables we know are intentionally read-only (catalog data, seeded once).
# Each entry needs a one-line justification.
READ_ONLY_OK = {
    "achievement_definitions":     "platform-seeded catalog of achievements; never user-writable",
    "equipment_reading_templates": "platform-seeded catalog of telemetry templates",
    "canonical_sources":           "service-role-only domain registry",
    "schedule_items":              "internal scheduler config; not user-writable from UI",
    "asset_brain_overview":        "view-like rollup of asset_nodes; read-only",
    # Service-role-writes-with-anon-reads pattern: edge fns write via the
    # service-role key (which bypasses RLS), UI only reads. The lack of an
    # INSERT policy is correct for these tables -- no anon path can create
    # rows, only a server-authored fn.
    "ai_reports":                  "service-role-only writes (intelligence-report fn); anon reads",
    "automation_log":              "service-role-only writes (cron + edge fns); anon reads for monitoring",
}

# Tables we know are intentionally insert-only (audit logs, event sinks).
INSERT_ONLY_OK = {
    "hive_audit_log":              "audit log; rows immutable post-insert",
    "cmms_audit_log":              "CMMS audit trail; rows immutable post-insert",
    "automation_log":              "scheduled-job results; rows immutable post-insert",
    "ai_rate_limits":              "rate-limit counters; INSERT-only with retention",
    "engineering_calc_history":    "calc-history append-only log",
    "early_access_emails":         "lead capture; admin-only read",
}

# Tables that are append-only event records (similar to insert-only but
# rows can be marked acknowledged via UPDATE).
APPEND_WITH_UPDATE_OK = {
    "failure_signature_alerts":    "pattern alerts; UPDATE used for acknowledge",
    "asset_risk_scores":           "risk-score history; INSERT-only emit, no UPDATE",
    "weibull_fits":                "stats history; INSERT-only emit",
    "pf_intervals":                "PF interval history; INSERT-only emit",
    "ph_intelligence_reports":     "intelligence-report history; INSERT-only emit",
    "ai_reports":                  "AI report cache; INSERT/UPDATE for refresh",
    "hive_benchmarks":             "benchmark snapshots; INSERT-only",
    "network_benchmarks":          "network benchmark snapshots; INSERT-only",
    "parts_staging_recommendations": "AI recommendations; UPDATE for accept/dismiss",
    "parts_staged_reservations":   "reservation events; UPDATE for state transitions",
}


# Reuse the same parser shape as validate_rls_readiness.py.
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


def _strip_comments(sql: str) -> str:
    sql = re.sub(r"/\*[\s\S]*?\*/", "", sql)
    return "\n".join(l for l in sql.split("\n") if not l.lstrip().startswith("--"))


def parse_policies() -> dict[str, set[str]]:
    """Return {table: set of verbs that have at least one live CREATE POLICY}.

    Last-writer-wins per (table, policy_name) -- a DROP after a CREATE
    retracts the verb, matching Postgres semantics.
    """
    # {(table, name): verb}
    live: dict[tuple[str, str], str] = {}
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = _strip_comments(read_file(path) or "")
        events: list[tuple[int, str, tuple[str, str], str]] = []
        for m in CREATE_POLICY_RE.finditer(sql):
            verb = (m.group("verb") or "ALL").upper()
            events.append((m.start(), "CREATE",
                           (m.group("table").strip(), m.group("name").strip()),
                           verb))
        for m in DROP_POLICY_RE.finditer(sql):
            events.append((m.start(), "DROP",
                           (m.group("table").strip(), m.group("name").strip()),
                           ""))
        events.sort(key=lambda e: e[0])
        for _pos, kind, key, verb in events:
            if kind == "CREATE":
                live[key] = verb
            else:
                live.pop(key, None)
    by_table: dict[str, set[str]] = defaultdict(set)
    for (table, _name), verb in live.items():
        if verb == "ALL":
            for v in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                by_table[table].add(v)
        else:
            by_table[table].add(verb)
    return by_table


def parse_rls_enabled_tables() -> set[str]:
    enabled: set[str] = set()
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = _strip_comments(read_file(path) or "")
        for m in ENABLE_RLS_RE.finditer(sql):
            enabled.add(m.group(1))
    return enabled


# -- Layer 1: Write without read --------------------------------------------

def check_write_without_read(
    by_table: dict[str, set[str]],
) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for table, verbs in sorted(by_table.items()):
        if "SELECT" in verbs:
            continue
        write_verbs = verbs & {"INSERT", "UPDATE", "DELETE"}
        if not write_verbs:
            continue
        if table in INSERT_ONLY_OK:
            continue
        if table in APPEND_WITH_UPDATE_OK:
            continue
        # Audit log shape: write-only tables that intentionally have no
        # SELECT policy (anon role can write, supervisors read via
        # service-role API). Tracked via INSERT_ONLY_OK above; raise WARN
        # for unrecognized cases so somebody decides explicitly.
        report.append({
            "table":   table,
            "verbs":   sorted(verbs),
            "missing": "SELECT",
        })
        issues.append({
            "check": "write_without_read", "skip": True,
            "reason": (
                f"Table '{table}' has {sorted(write_verbs)} policy but no "
                f"SELECT policy. Workers who write rows cannot read them "
                f"back -- the UI looks broken. Either add a SELECT policy "
                f"or list the table in INSERT_ONLY_OK / APPEND_WITH_UPDATE_OK "
                f"with a justification."
            ),
        })
    return issues, report


# -- Layer 2: Read without create on user-data tables -----------------------

def check_read_without_create(
    by_table: dict[str, set[str]],
) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for table, verbs in sorted(by_table.items()):
        if "INSERT" in verbs:
            continue
        if "SELECT" not in verbs:
            continue
        if table in READ_ONLY_OK:
            continue
        # Skip tables that already have UPDATE-only or DELETE-only writers
        # (these are legitimate "edit existing seeded rows" patterns).
        if "UPDATE" in verbs or "DELETE" in verbs:
            continue
        report.append({
            "table":   table,
            "verbs":   sorted(verbs),
            "missing": "INSERT",
        })
        issues.append({
            "check": "read_without_create", "skip": True,
            "reason": (
                f"Table '{table}' has SELECT policy but no INSERT/UPDATE/DELETE. "
                f"Likely accidentally read-only -- if intentional, add to "
                f"READ_ONLY_OK with a justification."
            ),
        })
    return issues, report


# -- Layer 3: Update gap ----------------------------------------------------

def check_update_gap(
    by_table: dict[str, set[str]],
) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for table, verbs in sorted(by_table.items()):
        if "INSERT" not in verbs:
            continue
        if "UPDATE" in verbs:
            continue
        if table in INSERT_ONLY_OK:
            continue
        # Tables for which UPDATE-less is intentional (event records).
        report.append({
            "table":   table,
            "verbs":   sorted(verbs),
            "missing": "UPDATE",
        })
        issues.append({
            "check": "update_gap", "skip": True,
            "reason": (
                f"Table '{table}' has INSERT policy but no UPDATE policy. "
                f"Workers can create rows but never edit mistakes. Add an "
                f"UPDATE policy or list the table in INSERT_ONLY_OK as "
                f"intentional."
            ),
        })
    return issues, report


# -- Layer 4: CRUD coverage matrix (informational) --------------------------

def check_crud_matrix(
    by_table: dict[str, set[str]],
) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    for table, verbs in sorted(by_table.items()):
        rows.append({
            "table":  table,
            "select": "SELECT" in verbs,
            "insert": "INSERT" in verbs,
            "update": "UPDATE" in verbs,
            "delete": "DELETE" in verbs,
            "verbs_count": len(verbs & {"SELECT", "INSERT", "UPDATE", "DELETE"}),
        })
    rows.sort(key=lambda r: (-r["verbs_count"], r["table"]))
    return [], rows


# -- Runner ------------------------------------------------------------------

CHECK_NAMES = [
    "write_without_read",
    "read_without_create",
    "update_gap",
    "crud_matrix",
]
CHECK_LABELS = {
    "write_without_read":  "L1  Tables with write policy also have SELECT policy             [WARN]",
    "read_without_create": "L2  Tables with SELECT policy also have INSERT (unless catalog)  [WARN]",
    "update_gap":          "L3  Tables with INSERT policy also have UPDATE (unless event)    [WARN]",
    "crud_matrix":         "L4  Per-table CRUD coverage matrix (informational)               [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nRLS Policy Symmetry Detector (4-layer)"))
    print("=" * 60)

    by_table     = parse_policies()
    rls_enabled  = parse_rls_enabled_tables()
    print(f"  {len(by_table)} tables with policies, "
          f"{len(rls_enabled)} tables with RLS enabled.\n")

    l1_issues, l1_report = check_write_without_read(by_table)
    l2_issues, l2_report = check_read_without_create(by_table)
    l3_issues, l3_report = check_update_gap(by_table)
    l4_issues, l4_report = check_crud_matrix(by_table)

    all_issues = l1_issues + l2_issues + l3_issues + l4_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if l4_report:
        print(f"\n{bold('CRUD COVERAGE MATRIX (informational)')}")
        print("  " + "-" * 56)
        print(f"  {'table':<32}  S  I  U  D")
        for r in l4_report[:15]:
            ck = lambda b: "✓" if b else "·"
            print(f"  {r['table']:<32}  {ck(r['select'])}  {ck(r['insert'])}  {ck(r['update'])}  {ck(r['delete'])}")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":            "rls_symmetry",
        "total_checks":         total,
        "passed":               n_pass,
        "warned":               n_warn,
        "failed":               n_fail,
        "n_tables_with_policy": len(by_table),
        "n_rls_enabled":        len(rls_enabled),
        "write_without_read":   l1_report,
        "read_without_create":  l2_report,
        "update_gap":           l3_report,
        "crud_matrix":          l4_report,
        "issues":               [i for i in all_issues if not i.get("skip")],
        "warnings":             [i for i in all_issues if i.get("skip")],
    }
    with open("rls_symmetry_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
