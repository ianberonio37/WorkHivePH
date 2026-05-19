"""
Schema Migration Order Safety -- WorkHive Platform
====================================================
Catches the "works on dev, breaks on fresh clone" migration class.
Supabase applies migrations in lexicographic filename order. A
migration that references a table / column / function from a LATER
migration silently succeeds locally (where everything's been applied
already) but fails when a fresh environment applies them in order.

The classic shape:
  20260420_baseline.sql      CREATE TABLE assets (id, ...)
  20260415_pre_assets.sql    ALTER TABLE assets ADD COLUMN ...
                             # ^ 04-15 runs BEFORE 04-20; assets doesn't exist yet

Layer 1 -- Reference to a table not yet declared                        [FAIL]
  Any ALTER TABLE / CREATE INDEX / CREATE POLICY / CREATE TRIGGER that
  references a table whose CREATE TABLE comes in a LATER migration
  (or doesn't exist at all in the migration set).

Layer 2 -- Reference to a column not yet added                          [WARN]
  Any DDL/policy/RPC that references column `t.c` where `c` was added
  to `t` by an ALTER TABLE in a later migration. The Postgres apply
  fails immediately on fresh clones.

Layer 3 -- Reference to a function not yet declared                     [WARN]
  Triggers / RPC references / view definitions that name a function
  declared in a later migration.

Layer 4 -- Cross-migration dependency matrix (informational)            [INFO]
  Inventory of (migration_file, referenced_objects) pairs. Surfaces
  migrations with the heaviest cross-file dependencies — those are
  the highest-risk if order changes.

Skills consulted: data-engineer (migration order semantics, supabase
db push behaviour), architect (schema dependency review).
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

# Per (referencing_file, referenced_object) exemptions.
ORDER_OK: dict[tuple[str, str], str] = {
    # ("20260501_x.sql", "table_y"): "reason"
}

# Tables we treat as always-present (Supabase / Postgres built-ins).
# Stored both as single token (matches our regex capture) and schema-qualified.
ALWAYS_PRESENT_TABLES = {
    "users", "objects", "buckets",
    "auth.users", "auth.identities", "auth.sessions",
    "auth.mfa_factors", "auth.mfa_challenges",
    "storage", "storage.objects", "storage.buckets",
    # pg system catalogs commonly referenced
    "pg_publication", "pg_publication_tables",
    "information_schema",
    # Supabase canonical extensions
    "vault.secrets", "vault",
    "schema_migrations",   # supabase migration history
}

CREATE_TABLE_RE = re.compile(
    # Matches CREATE TABLE and CREATE [MATERIALIZED] VIEW. Materialised views
    # are first-class declared objects too: indexes can reference them,
    # REFRESH statements name them, and the dependency-order check needs to
    # see them in the first-seen registry.
    r"""CREATE\s+
        (?:TABLE|(?:MATERIALIZED\s+)?VIEW)
        \s+(?:IF\s+NOT\s+EXISTS\s+)?
        (?:(?P<schema>public|auth)\.|"(?P<schema_q>public|auth)"\.)?
        "?(?P<name>\w+)"?\s*(?:\(|AS\b)""",
    re.IGNORECASE | re.VERBOSE,
)
ALTER_ADD_COLUMN_RE = re.compile(
    r"""ALTER\s+TABLE\s+(?:ONLY\s+)?(?:public\.|"public"\.|IF\s+EXISTS\s+)?
        "?(?P<name>\w+)"?\s+ADD\s+COLUMN(?:\s+IF\s+NOT\s+EXISTS)?\s+
        "?(?P<col>\w+)"?""",
    re.IGNORECASE | re.VERBOSE,
)
CREATE_FN_RE = re.compile(
    r"""CREATE(?:\s+OR\s+REPLACE)?\s+FUNCTION\s+
        (?:(?:public|auth)\.)?
        "?(?P<name>\w+)"?\s*\(""",
    re.IGNORECASE | re.VERBOSE,
)

# References to validate.
ALTER_REF_RE = re.compile(
    r"""ALTER\s+TABLE\s+
        (?:ONLY\s+)?
        (?:IF\s+EXISTS\s+)?           # optional, can precede the schema prefix
        (?:(?:public|auth)\.|"public"\.)?
        "?(?P<name>\w+)"?""",
    re.IGNORECASE | re.VERBOSE,
)
INDEX_REF_RE = re.compile(
    r"""CREATE\s+(?:UNIQUE\s+)?INDEX\s+
        (?:CONCURRENTLY\s+)?
        (?:IF\s+NOT\s+EXISTS\s+)?
        "?\w+"?\s+ON\s+(?:(?:public|auth)\.|"public"\.)?
        "?(?P<name>\w+)"?""",
    re.IGNORECASE | re.VERBOSE,
)
POLICY_REF_RE = re.compile(
    r"""CREATE\s+POLICY\s+"?[\w\s-]+"?\s+ON\s+
        (?:(?:public|auth)\.|"public"\.)?
        "?(?P<name>\w+)"?""",
    re.IGNORECASE | re.VERBOSE,
)
TRIGGER_REF_RE = re.compile(
    r"""CREATE\s+(?:OR\s+REPLACE\s+)?TRIGGER\s+\w+\s+
        (?:BEFORE|AFTER|INSTEAD\s+OF)[\s\S]*?
        ON\s+(?:(?:public|auth)\.)?"?(?P<table>\w+)"?
        [\s\S]*?EXECUTE\s+(?:PROCEDURE|FUNCTION)\s+
        (?:(?:public|auth)\.)?"?(?P<fn>\w+)""",
    re.IGNORECASE | re.VERBOSE,
)


def list_migrations_ordered() -> list[str]:
    return sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql")))


def _strip_comments(sql: str) -> str:
    sql = re.sub(r"/\*[\s\S]*?\*/", "", sql)
    return re.sub(r"--[^\n]*", "", sql)


def build_table_first_seen() -> dict[str, str]:
    """{table_name: first_migration_filename_that_creates_it}"""
    out: dict[str, str] = {}
    for path in list_migrations_ordered():
        sql = _strip_comments(read_file(path) or "")
        fname = os.path.basename(path)
        for m in CREATE_TABLE_RE.finditer(sql):
            name = m.group("name").lower()
            if name in out:
                continue
            out[name] = fname
    return out


def build_column_first_seen() -> dict[tuple[str, str], str]:
    """{(table, column): first migration filename}"""
    out: dict[tuple[str, str], str] = {}
    for path in list_migrations_ordered():
        sql = _strip_comments(read_file(path) or "")
        fname = os.path.basename(path)
        # Inline columns from CREATE TABLE bodies
        for tm in re.finditer(
            r"""CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?
                (?:(?:public|auth)\.|"public"\.)?
                "?(?P<name>\w+)"?\s*\(
                (?P<body>[\s\S]*?)\n\s*\);""",
            sql, re.IGNORECASE | re.VERBOSE,
        ):
            table = tm.group("name").lower()
            for cm in re.finditer(
                r"""^\s*"?(?P<col>\w+)"?\s+["a-zA-Z]""",
                tm.group("body"), re.MULTILINE,
            ):
                col = cm.group("col").lower()
                if col in {"constraint", "primary", "unique", "foreign", "check"}:
                    continue
                key = (table, col)
                if key not in out:
                    out[key] = fname
        # ALTER TABLE ADD COLUMN
        for m in ALTER_ADD_COLUMN_RE.finditer(sql):
            key = (m.group("name").lower(), m.group("col").lower())
            if key not in out:
                out[key] = fname
    return out


def build_function_first_seen() -> dict[str, str]:
    """{fn_name: first migration filename}"""
    out: dict[str, str] = {}
    for path in list_migrations_ordered():
        sql = _strip_comments(read_file(path) or "")
        fname = os.path.basename(path)
        for m in CREATE_FN_RE.finditer(sql):
            name = m.group("name").lower()
            if name not in out:
                out[name] = fname
    return out


# -- Layer 1: Reference to a table not yet declared ----------------------

def check_table_order(table_first_seen: dict[str, str]) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for path in list_migrations_ordered():
        sql = _strip_comments(read_file(path) or "")
        fname = os.path.basename(path)
        for rx in (ALTER_REF_RE, INDEX_REF_RE, POLICY_REF_RE):
            for m in rx.finditer(sql):
                tbl = m.group("name").lower()
                if tbl in ALWAYS_PRESENT_TABLES:
                    continue
                if (fname, tbl) in ORDER_OK:
                    continue
                first = table_first_seen.get(tbl)
                if first is None:
                    # Referenced but no CREATE TABLE found anywhere.
                    line_no = sql[:m.start()].count("\n") + 1
                    report.append({
                        "ref_file":   fname,
                        "ref_table":  tbl,
                        "line":       line_no,
                        "kind":       "no_create_table",
                    })
                    issues.append({
                        "check": "table_order", "skip": False,
                        "reason": (
                            f"{fname}:{line_no}: references table `{tbl}` "
                            f"but NO `CREATE TABLE {tbl}` is found in any "
                            f"migration. The migration will fail on apply. "
                            f"Either add the CREATE TABLE or list "
                            f"(`{fname}`, `{tbl}`) in ORDER_OK if the table "
                            f"is created outside the migration set."
                        ),
                    })
                    continue
                if first > fname:
                    line_no = sql[:m.start()].count("\n") + 1
                    report.append({
                        "ref_file":   fname,
                        "ref_table":  tbl,
                        "first_seen": first,
                        "line":       line_no,
                        "kind":       "out_of_order",
                    })
                    issues.append({
                        "check": "table_order", "skip": False,
                        "reason": (
                            f"{fname}:{line_no}: references table `{tbl}` "
                            f"but its CREATE TABLE lives in `{first}` "
                            f"(applied AFTER this migration). Fresh-clone "
                            f"apply fails. Reorder or merge migrations."
                        ),
                    })
    return issues, report


# -- Layer 2: Reference to a column not yet added ----------------------

def check_column_order(
    col_first_seen: dict[tuple[str, str], str],
) -> tuple[list[dict], list[dict]]:
    """Match `<table>.<column>` references and check column-first-seen <= migration."""
    issues: list[dict] = []
    report: list[dict] = []
    col_ref_re = re.compile(
        r"\b(?P<table>\w+)\.(?P<col>\w+)\b",
    )
    SKIP_NAMESPACES = {
        "auth", "storage", "public", "extensions", "vault",
        "pg_catalog", "information_schema", "graphql",
    }
    for path in list_migrations_ordered():
        sql = _strip_comments(read_file(path) or "")
        fname = os.path.basename(path)
        # Only look at the body OUTSIDE of CREATE TABLE / CREATE FUNCTION
        # bodies (those are declarations, not references). To keep this
        # bounded, scan POLICY / TRIGGER WHEN / INDEX expressions for
        # the table.col pattern. As a tighter signal, look at
        # CREATE INDEX / CREATE POLICY USING/WITH CHECK clauses only.
        scope_pattern = re.compile(
            r"""CREATE\s+(?:POLICY|INDEX|VIEW|MATERIALIZED\s+VIEW)[\s\S]*?;""",
            re.IGNORECASE | re.VERBOSE,
        )
        for sm in scope_pattern.finditer(sql):
            chunk = sm.group(0)
            for m in col_ref_re.finditer(chunk):
                tbl = m.group("table").lower()
                col = m.group("col").lower()
                if tbl in SKIP_NAMESPACES:
                    continue
                if (fname, f"{tbl}.{col}") in ORDER_OK:
                    continue
                key = (tbl, col)
                first = col_first_seen.get(key)
                if first is None:
                    continue   # likely not a column at all (NEW.x in WHEN clause etc.)
                if first > fname:
                    line_no = sql.count("\n", 0, sm.start() + m.start()) + 1
                    report.append({
                        "ref_file":   fname,
                        "ref_col":    f"{tbl}.{col}",
                        "first_seen": first,
                        "line":       line_no,
                    })
                    issues.append({
                        "check": "column_order", "skip": True,
                        "reason": (
                            f"{fname}:{line_no}: references column "
                            f"`{tbl}.{col}` but it's first added in `{first}` "
                            f"(applied AFTER this migration). May fail on "
                            f"fresh-clone apply."
                        ),
                    })
    return issues, report


# -- Layer 3: Reference to a function not yet declared ----------------

def check_function_order(
    fn_first_seen: dict[str, str],
) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for path in list_migrations_ordered():
        sql = _strip_comments(read_file(path) or "")
        fname = os.path.basename(path)
        for tm in TRIGGER_REF_RE.finditer(sql):
            fn = tm.group("fn").lower()
            if (fname, fn) in ORDER_OK:
                continue
            first = fn_first_seen.get(fn)
            if first is None:
                continue
            if first > fname:
                line_no = sql[:tm.start()].count("\n") + 1
                report.append({
                    "ref_file":   fname,
                    "ref_fn":     fn,
                    "first_seen": first,
                    "line":       line_no,
                })
                issues.append({
                    "check": "function_order", "skip": True,
                    "reason": (
                        f"{fname}:{line_no}: trigger references function "
                        f"`{fn}` but its CREATE FUNCTION is in `{first}` "
                        f"(applied AFTER this migration). Fresh-clone "
                        f"apply fails on this trigger."
                    ),
                })
    return issues, report


# -- Layer 4: Cross-migration dependency matrix -----------------------

def check_dependency_matrix(
    table_first_seen: dict[str, str],
) -> tuple[list[dict], list[dict]]:
    by_file: dict[str, set[str]] = defaultdict(set)
    for path in list_migrations_ordered():
        sql = _strip_comments(read_file(path) or "")
        fname = os.path.basename(path)
        # Tables this migration creates locally.
        local: set[str] = set()
        for m in CREATE_TABLE_RE.finditer(sql):
            local.add(m.group("name").lower())
        # All tables this migration references.
        for rx in (ALTER_REF_RE, INDEX_REF_RE, POLICY_REF_RE):
            for m in rx.finditer(sql):
                tbl = m.group("name").lower()
                if tbl in local or tbl in ALWAYS_PRESENT_TABLES:
                    continue
                if tbl in table_first_seen and table_first_seen[tbl] != fname:
                    by_file[fname].add(tbl)
    rows: list[dict] = []
    for fname, deps in sorted(by_file.items(), key=lambda kv: -len(kv[1])):
        rows.append({
            "file":  fname,
            "n_deps": len(deps),
            "deps":   sorted(deps)[:5],
        })
    return [], rows


# -- Runner -----------------------------------------------------------

CHECK_NAMES = [
    "table_order",
    "column_order",
    "function_order",
    "dependency_matrix",
]
CHECK_LABELS = {
    "table_order":       "L1  No migration references a table declared later                [FAIL]",
    "column_order":      "L2  No migration references a column added later                  [WARN]",
    "function_order":    "L3  No trigger references a function declared later               [WARN]",
    "dependency_matrix": "L4  Cross-migration dependency matrix (informational)             [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nSchema Migration Order Safety (4-layer)"))
    print("=" * 60)

    table_first_seen = build_table_first_seen()
    col_first_seen   = build_column_first_seen()
    fn_first_seen    = build_function_first_seen()

    print(f"  {len(table_first_seen)} tables, "
          f"{len(col_first_seen)} (table,col) pairs, "
          f"{len(fn_first_seen)} functions in declaration history.\n")

    l1_issues, l1_report = check_table_order(table_first_seen)
    l2_issues, l2_report = check_column_order(col_first_seen)
    l3_issues, l3_report = check_function_order(fn_first_seen)
    l4_issues, l4_report = check_dependency_matrix(table_first_seen)

    all_issues = l1_issues + l2_issues + l3_issues + l4_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if l4_report:
        print(f"\n{bold('TOP DEPENDENT MIGRATIONS (informational)')}")
        print("  " + "-" * 56)
        for r in l4_report[:8]:
            sample = ", ".join(r["deps"][:3])
            print(f"  {r['file']:<48}  deps={r['n_deps']:<3} ({sample})")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":          "migration_order",
        "total_checks":       total,
        "passed":             n_pass,
        "warned":             n_warn,
        "failed":             n_fail,
        "n_tables":           len(table_first_seen),
        "n_columns":          len(col_first_seen),
        "n_functions":        len(fn_first_seen),
        "table_order":        l1_report,
        "column_order":       l2_report,
        "function_order":     l3_report,
        "dependency_matrix":  l4_report,
        "issues":             [i for i in all_issues if not i.get("skip")],
        "warnings":           [i for i in all_issues if i.get("skip")],
    }
    with open("migration_order_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
