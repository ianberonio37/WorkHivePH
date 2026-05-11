"""
SQL Function Security Posture -- WorkHive Platform
====================================================
Catches the SECURITY DEFINER privilege-escalation class. Postgres
functions default to SECURITY INVOKER (run as the caller, RLS applies).
SECURITY DEFINER functions run as the owner (typically `postgres`),
which bypasses RLS entirely. When a DEFINER function's `search_path`
is NOT locked down (`SET search_path = pg_catalog, public` or
similar), an attacker who can create objects in a writeable schema
can shadow built-in names (`COUNT`, `TRIM`, etc.) and execute
arbitrary code with elevated privileges.

This is a documented Postgres CVE class (`CVE-2018-1058`-style
attacks). Supabase's default `public` schema is writable to
`authenticated` role by default — every DEFINER function without
search_path is a potential bypass.

Layer 1 -- SECURITY DEFINER without search_path lockdown                [FAIL]
  Any CREATE FUNCTION declared SECURITY DEFINER that does not include
  `SET search_path = ...` in the same definition. This is the
  exploitable shape; locking the search_path is the established fix.

Layer 2 -- No explicit security clause on RLS-sensitive table trigger    [WARN]
  Triggers attached to tables that hold sensitive data (audit logs,
  inventory transactions, marketplace_orders, hive_audit_log) should
  have an EXPLICIT `SECURITY` clause so the choice is visible at code
  review. Default INVOKER is OK; missing the clause is a code-smell.

Layer 3 -- Per-table function-security matrix (informational)            [INFO]
  Functions defined per migration + their security posture.

Layer 4 -- Security-posture distribution (informational)                 [INFO]
  Aggregate: how many DEFINER, INVOKER, default-unspecified, with vs
  without search_path. Tracks adoption of the lockdown pattern.

Skills consulted: security (Postgres function CVE class), data-engineer
(trigger semantics, RLS bypass surface), architect (function ownership
and the implicit-vs-explicit-clause discipline).
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

# Functions known-safe to keep as DEFINER WITHOUT search_path because
# they are Supabase-built-in stubs (auth.* triggers) or otherwise
# operate inside a controlled schema only. Each entry needs a
# one-line justification.
DEFINER_NO_SEARCH_PATH_OK: dict[tuple[str, str], str] = {
    # All 15 historical DEFINER fns without search_path are SUPERSEDED by
    # 20260511000002_db_hygiene_batch.sql which re-CREATE OR REPLACE'es
    # each fn with `SET search_path = pg_catalog, public`. Postgres last-
    # writer-wins per function name, so the lockdown is the live state.
    # The historical vulnerable definitions still exist in older migration
    # files (CREATE OR REPLACE can't be undone retroactively), so we keep
    # the allowlist entries flagged as SUPERSEDED for audit trail.
    ("20260420000000_baseline.sql", "handle_community_post_xp"):     "SUPERSEDED by 20260511000002 lockdown",
    ("20260420000000_baseline.sql", "handle_community_reaction_xp"): "SUPERSEDED by 20260511000002 lockdown",
    ("20260420000000_baseline.sql", "handle_community_reply_xp"):    "SUPERSEDED by 20260511000002 lockdown",
    ("20260420000000_baseline.sql", "increment_community_xp"):       "SUPERSEDED by 20260511000002 lockdown",
    ("20260420000000_baseline.sql", "increment_listing_view"):       "SUPERSEDED by 20260502000004 lockdown (already had search_path)",
    ("20260420000000_baseline.sql", "sync_auth_uid_on_signup"):      "SUPERSEDED by 20260511000002 lockdown",
    ("20260430000002_community_xp.sql", "increment_community_xp"):       "SUPERSEDED by 20260511000002",
    ("20260430000002_community_xp.sql", "handle_community_post_xp"):     "SUPERSEDED by 20260511000002",
    ("20260430000002_community_xp.sql", "handle_community_reply_xp"):    "SUPERSEDED by 20260511000002",
    ("20260430000002_community_xp.sql", "handle_community_reaction_xp"): "SUPERSEDED by 20260511000002",
    ("20260501000001_fix_auth_uid_backfill.sql", "sync_auth_uid_on_signup"): "SUPERSEDED by 20260511000002",
    ("20260501000003_missing_table_rls.sql", "sync_auth_uid_on_signup"):    "SUPERSEDED by 20260511000002",
    ("20260501000004_remaining_table_rls.sql", "sync_auth_uid_on_signup"):  "SUPERSEDED by 20260511000002",
    ("20260504000001_community_badge_auth_uid.sql", "handle_community_post_xp"): "SUPERSEDED by 20260511000002",
    ("20260508000009_asset_brain_foundation.sql", "sync_auth_uid_on_signup"):    "SUPERSEDED by 20260511000002",
}

# Sensitive tables for L2 trigger-clause checks.
SENSITIVE_TABLES = {
    "hive_audit_log",
    "cmms_audit_log",
    "automation_log",
    "inventory_transactions",
    "marketplace_orders",
    "marketplace_disputes",
    "ai_rate_limits",
    "auth.users",
}

# Trigger -> reason exemptions for L2 (explicit-clause check). Per-trigger
# justification preferred over disabling the check.
TRIGGER_EXPLICIT_OK: dict[tuple[str, str], str] = {
    # (migration, trigger_name): "reason"
    ("20260501000006_marketplace_scale.sql", "trg_seller_tier"):
        "DEFERRED -- baseline code-style; trigger executes update_seller_tier"
        " which is itself a pure-compute fn, not an RLS-bypass surface",
}

# Each CREATE FUNCTION block runs from `CREATE OR REPLACE FUNCTION ...` /
# `CREATE FUNCTION ...` to the matching `$$;` (or `LANGUAGE ... ;` /
# `LANGUAGE ...;` terminator). Parsing functions is non-trivial because
# the body uses `$$` quoting. We use a depth-aware split:
#   * Find each `CREATE FUNCTION` / `CREATE OR REPLACE FUNCTION` start
#   * Walk to the next `;` at quote-depth 0
#   * Quote depth: tracks `$$` (or `$tag$`) balanced pairs

CREATE_FN_RE = re.compile(
    r"""CREATE(?:\s+OR\s+REPLACE)?\s+FUNCTION\s+
        (?:(?:public|auth|"\w+")\.)?
        "?(?P<name>\w+)"?\s*\([^)]*\)""",
    re.IGNORECASE | re.VERBOSE,
)
DOLLAR_QUOTE_RE = re.compile(r"\$(?P<tag>\w*)\$")


def _walk_function_blocks(sql: str) -> list[dict]:
    """Yield {name, body_start, body_end, full_text} for each CREATE FUNCTION."""
    out: list[dict] = []
    pos = 0
    while True:
        m = CREATE_FN_RE.search(sql, pos)
        if not m:
            break
        start = m.start()
        # Walk forward looking for a `$$` open + close OR a `;` at top level.
        i = m.end()
        opened_tag: str | None = None
        end = -1
        while i < len(sql):
            if opened_tag is None:
                # Look for either `$tag$` (open) or `;` (function terminator).
                ch = sql[i]
                if ch == "$":
                    qm = DOLLAR_QUOTE_RE.match(sql, i)
                    if qm:
                        opened_tag = qm.group("tag")
                        i = qm.end()
                        continue
                if ch == ";":
                    end = i + 1
                    break
                i += 1
            else:
                # Walking inside a dollar-quoted body. Look for matching tag.
                tag_close = f"${opened_tag}$"
                idx = sql.find(tag_close, i)
                if idx == -1:
                    i = len(sql)
                else:
                    i = idx + len(tag_close)
                    opened_tag = None
        if end < 0:
            end = i
        out.append({
            "name":      m.group("name"),
            "full_text": sql[start:end],
            "start":     start,
            "end":       end,
        })
        pos = end
    return out


# -- Layer 1: DEFINER without search_path ---------------------------------

def check_definer_search_path() -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = re.sub(r"--[^\n]*", "", read_file(path) or "")
        fname = os.path.basename(path)
        for fn in _walk_function_blocks(sql):
            text = fn["full_text"]
            if not re.search(r"\bSECURITY\s+DEFINER\b", text, re.IGNORECASE):
                continue
            has_path = bool(re.search(
                r"\bSET\s+search_path\s*=", text, re.IGNORECASE,
            ))
            if has_path:
                continue
            if (fname, fn["name"]) in DEFINER_NO_SEARCH_PATH_OK:
                continue
            line_no = sql[:fn["start"]].count("\n") + 1
            report.append({
                "file":     fname,
                "fn":       fn["name"],
                "line":     line_no,
            })
            issues.append({
                "check": "definer_search_path", "skip": False,
                "reason": (
                    f"{fname}:{line_no}: function `{fn['name']}` is "
                    f"SECURITY DEFINER but has no `SET search_path = ...` "
                    f"clause. An attacker who can create objects in `public` "
                    f"can shadow built-in names and execute code as the "
                    f"function owner. Add `SET search_path = pg_catalog, "
                    f"public` to the function definition, or list "
                    f"(`{fname}`, `{fn['name']}`) in DEFINER_NO_SEARCH_PATH_OK "
                    f"with a justification."
                ),
            })
    return issues, report


# -- Layer 2: Trigger on sensitive table without explicit clause ----------

def check_trigger_explicit_clause() -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    trigger_re = re.compile(
        r"""CREATE\s+(?:OR\s+REPLACE\s+)?TRIGGER\s+(?P<tname>\w+)\s+
            (?:BEFORE|AFTER|INSTEAD\s+OF)[\s\S]*?
            ON\s+(?:(?:public|auth)\.)?"?(?P<table>\w+)"?
            [\s\S]*?EXECUTE\s+(?:PROCEDURE|FUNCTION)\s+
            (?:(?:public|auth)\.)?"?(?P<fn>\w+)""",
        re.IGNORECASE | re.VERBOSE,
    )
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = re.sub(r"--[^\n]*", "", read_file(path) or "")
        fname = os.path.basename(path)
        # Map fn name -> security posture across this migration's CREATE FN.
        fn_security: dict[str, str | None] = {}
        for f in _walk_function_blocks(sql):
            text = f["full_text"]
            if re.search(r"\bSECURITY\s+DEFINER\b", text, re.IGNORECASE):
                fn_security[f["name"]] = "DEFINER"
            elif re.search(r"\bSECURITY\s+INVOKER\b", text, re.IGNORECASE):
                fn_security[f["name"]] = "INVOKER"
            else:
                fn_security[f["name"]] = None
        for tm in trigger_re.finditer(sql):
            table = tm.group("table").lower()
            fn    = tm.group("fn")
            if table not in SENSITIVE_TABLES:
                continue
            posture = fn_security.get(fn)
            if posture in {"DEFINER", "INVOKER"}:
                continue
            # Function may be defined in a prior migration; only WARN if
            # it's in THIS migration with no explicit clause.
            if fn not in fn_security:
                continue
            if (fname, tm.group("tname")) in TRIGGER_EXPLICIT_OK:
                continue
            line_no = sql[:tm.start()].count("\n") + 1
            report.append({
                "file":  fname,
                "trigger": tm.group("tname"),
                "table": table,
                "fn":    fn,
                "line":  line_no,
            })
            issues.append({
                "check": "trigger_explicit_clause", "skip": True,
                "reason": (
                    f"{fname}:{line_no}: trigger `{tm.group('tname')}` on "
                    f"sensitive table `{table}` calls function `{fn}` "
                    f"defined in the same migration with NO explicit "
                    f"`SECURITY INVOKER` / `SECURITY DEFINER` clause. "
                    f"Postgres defaults to INVOKER which is usually fine "
                    f"— but make the choice EXPLICIT so reviewers see "
                    f"the security boundary."
                ),
            })
    return issues, report


# -- Layer 3: Per-migration function security matrix (informational) -----

def check_matrix() -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = re.sub(r"--[^\n]*", "", read_file(path) or "")
        fname = os.path.basename(path)
        counts: dict[str, int] = defaultdict(int)
        for f in _walk_function_blocks(sql):
            text = f["full_text"]
            if re.search(r"\bSECURITY\s+DEFINER\b", text, re.IGNORECASE):
                has_path = bool(re.search(
                    r"\bSET\s+search_path\s*=", text, re.IGNORECASE,
                ))
                counts["definer_with_path" if has_path else "definer_no_path"] += 1
            elif re.search(r"\bSECURITY\s+INVOKER\b", text, re.IGNORECASE):
                counts["invoker"] += 1
            else:
                counts["unspecified"] += 1
        if not counts:
            continue
        rows.append({"file": fname, "counts": dict(counts)})
    return [], rows


# -- Layer 4: Security-posture distribution (informational) --------------

def check_aggregate() -> tuple[list[dict], list[dict]]:
    agg: dict[str, int] = defaultdict(int)
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = re.sub(r"--[^\n]*", "", read_file(path) or "")
        for f in _walk_function_blocks(sql):
            text = f["full_text"]
            if re.search(r"\bSECURITY\s+DEFINER\b", text, re.IGNORECASE):
                has_path = bool(re.search(
                    r"\bSET\s+search_path\s*=", text, re.IGNORECASE,
                ))
                agg["definer_with_path" if has_path else "definer_no_path"] += 1
            elif re.search(r"\bSECURITY\s+INVOKER\b", text, re.IGNORECASE):
                agg["invoker"] += 1
            else:
                agg["unspecified"] += 1
    rows = [{"posture": k, "count": v} for k, v in sorted(agg.items())]
    return [], rows


# -- Runner ----------------------------------------------------------------

CHECK_NAMES = [
    "definer_search_path",
    "trigger_explicit_clause",
    "matrix",
    "aggregate",
]
CHECK_LABELS = {
    "definer_search_path":     "L1  Every SECURITY DEFINER fn sets search_path                 [FAIL]",
    "trigger_explicit_clause": "L2  Triggers on sensitive tables declare explicit SECURITY     [WARN]",
    "matrix":                  "L3  Per-migration function-security matrix (informational)    [INFO]",
    "aggregate":               "L4  Platform-wide security-posture distribution                [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nSQL Function Security Posture (4-layer)"))
    print("=" * 60)

    l1_issues, l1_report = check_definer_search_path()
    l2_issues, l2_report = check_trigger_explicit_clause()
    l3_issues, l3_report = check_matrix()
    l4_issues, l4_report = check_aggregate()

    all_issues = l1_issues + l2_issues + l3_issues + l4_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if l4_report:
        print(f"\n{bold('SECURITY POSTURE DISTRIBUTION (informational)')}")
        print("  " + "-" * 56)
        for r in l4_report:
            print(f"  {r['posture']:<28}  {r['count']}")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":           "function_security",
        "total_checks":        total,
        "passed":              n_pass,
        "warned":              n_warn,
        "failed":              n_fail,
        "definer_search_path": l1_report,
        "trigger_explicit":    l2_report,
        "matrix":              l3_report,
        "aggregate":           l4_report,
        "issues":              [i for i in all_issues if not i.get("skip")],
        "warnings":            [i for i in all_issues if i.get("skip")],
    }
    with open("function_security_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
