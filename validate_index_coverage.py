"""
Index Coverage Detector -- WorkHive Platform
=============================================
Catches the silent perf cliff: queries that filter on columns lacking any
index. At 1k rows the table scan is invisible; at 100k rows the page
hangs. This validator inventories every `.eq()` / `.gte()` / `.lte()` /
`.in()` / `.match()` / `.filter()` filter target across the codebase,
crosses against indexed columns from migrations, and flags concentrations
of high-frequency unindexed reads.

Layer 1 -- High-frequency unindexed filter                              [WARN]
  Any (table, column) pair filtered in 3+ source files AND 5+ total
  usages where the column lacks any covering index. These are the
  urgent perf wins -- adding `CREATE INDEX idx_<table>_<col>` removes
  the table scan everywhere.

Layer 2 -- Medium-frequency unindexed filter                            [WARN]
  Same shape, lower threshold (2+ files, 3+ uses). Surfaces growing
  hotspots before they become L1.

Layer 3 -- Filter coverage matrix (informational)                       [INFO]
  Per-table breakdown: total filter columns vs indexed columns. Helps
  spot tables with low coverage ratio.

Layer 4 -- Tables with no non-PK index (informational)                  [INFO]
  Inventory of tables whose only index is the primary key. Often
  intentional for tiny config tables, but a leading indicator on
  high-write-volume tables.

Skills consulted: performance (query optimization, index hit/miss),
data-engineer (schema/query alignment, batch over loops, narrow selects),
analytics-engineer (large dashboard reads must hit indexes).
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
FUNCTIONS_DIR  = os.path.join("supabase", "functions")
PYTHON_API_DIR = "python-api"

EXCLUDED_HTML_PATTERNS = ("-test.html", ".backup.html", "_backup.html", ".backup")

# Tables we treat as opaque (no DDL we can analyse).
OPAQUE_TABLES = {
    "auth", "users", "objects",
    "pg_publication_tables", "information_schema",
}

# Columns that are always considered "implicitly indexed" because Supabase
# / Postgres handles them specially. `id` is the convention PK; `auth_uid`
# nearly always has an index added in companion migrations; `created_at`
# is high-cardinality monotonic so even a partial scan is acceptable.
ALWAYS_COVERED = {"id"}

# Tier thresholds.
L1_FILES = 3
L1_USES  = 5
L2_FILES = 2
L2_USES  = 3

# (table, column) pairs that are known un-indexed perf debt. Each entry
# pins the existing state so the gate runs green; remove the entry once
# the corresponding `CREATE INDEX` migration ships. Logged in
# PRODUCTION_FIXES.md under the "index coverage" perf-debt entry.
INDEX_DEFERRED = {
    # All L1 (13) + L2 (12) historical indexes SHIPPED across
    # 20260511000002_db_hygiene_batch.sql and 20260511000007_db_hygiene_wave2.sql.
    # Allowlist intentionally empty -- the gate now ratchets cleanly:
    # any NEW filter that crosses thresholds without an index surfaces
    # immediately. Closed: PRODUCTION_FIXES #42 L1+L2.
}


# -- Schema discovery: indexed columns ---------------------------------------

# CREATE INDEX [UNIQUE] [IF NOT EXISTS] name ON [public.]table (col [, col2])
CREATE_INDEX_RE = re.compile(
    r"""CREATE\s+(?:UNIQUE\s+)?INDEX\s+
        (?:CONCURRENTLY\s+)?
        (?:IF\s+NOT\s+EXISTS\s+)?
        "?\w+"?\s+ON\s+
        (?:(?:public|"public")\.)?"?(?P<table>\w+)"?\s*
        (?:USING\s+"?\w+"?\s*)?
        \(\s*(?P<cols>[^)]+)\)""",
    re.IGNORECASE | re.VERBOSE,
)

# Inline PRIMARY KEY: `id uuid PRIMARY KEY`
INLINE_PK_RE = re.compile(
    r"""\b(?P<col>\w+)\s+\w+(?:\s+\w+)*?\s+PRIMARY\s+KEY\b""",
    re.IGNORECASE | re.VERBOSE,
)
# Constraint-level PRIMARY KEY: `PRIMARY KEY (col1, col2)`
CONSTRAINT_PK_RE = re.compile(
    r"""(?:CONSTRAINT\s+\w+\s+)?PRIMARY\s+KEY\s*\(\s*(?P<cols>[^)]+)\)""",
    re.IGNORECASE | re.VERBOSE,
)
# Inline UNIQUE: `email text UNIQUE`
INLINE_UNIQUE_RE = re.compile(
    r"""^\s*"?(?P<col>\w+)"?\s+\w[^,;\n]*\bUNIQUE\b""",
    re.IGNORECASE | re.MULTILINE | re.VERBOSE,
)
# Constraint-level UNIQUE
CONSTRAINT_UNIQUE_RE = re.compile(
    r"""(?:CONSTRAINT\s+\w+\s+)?UNIQUE\s*\(\s*(?P<cols>[^)]+)\)""",
    re.IGNORECASE | re.VERBOSE,
)

CREATE_TABLE_RE = re.compile(
    r"""CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?
        (?:public\.|"public"\.)?
        "?(?P<name>\w+)"?\s*\(
        (?P<body>[\s\S]*?)\n\s*\);""",
    re.IGNORECASE | re.VERBOSE,
)


def load_indexed_columns() -> dict[str, set[str]]:
    """Return {table: set of columns covered by ANY index (PK, UNIQUE, or
    explicit CREATE INDEX). For composite indexes, we register the LEADING
    column only -- Postgres can use a composite for a prefix match but
    not for non-leading columns."""
    indexed: dict[str, set[str]] = defaultdict(set)
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = re.sub(r"--[^\n]*", "", read_file(path) or "")

        # CREATE INDEX statements
        for m in CREATE_INDEX_RE.finditer(sql):
            table = m.group("table").lower()
            cols  = m.group("cols").split(",")
            if cols:
                # Leading column of a composite index covers prefix matches
                first = cols[0].strip().strip('"').lower()
                # Strip function wrappers like lower(name) -> name
                fn_m = re.match(r"^\w+\s*\(\s*(\w+)\s*\)$", first)
                if fn_m:
                    # Functional index doesn't cover plain .eq() -- skip
                    continue
                # Strip any DESC/ASC/NULLS FIRST/etc.
                first = first.split()[0]
                indexed[table].add(first)

        # CREATE TABLE bodies for inline PRIMARY KEY / UNIQUE
        for m in CREATE_TABLE_RE.finditer(sql):
            table = m.group("name").lower()
            body  = m.group("body")

            for pk in INLINE_PK_RE.finditer(body):
                indexed[table].add(pk.group("col").lower())
            for pk in CONSTRAINT_PK_RE.finditer(body):
                cols = pk.group("cols").split(",")
                if cols:
                    first = cols[0].strip().strip('"').lower()
                    indexed[table].add(first)
            for uq in INLINE_UNIQUE_RE.finditer(body):
                col = uq.group("col").lower()
                if col not in {"constraint", "primary", "foreign", "check"}:
                    indexed[table].add(col)
            for uq in CONSTRAINT_UNIQUE_RE.finditer(body):
                cols = uq.group("cols").split(",")
                if cols:
                    first = cols[0].strip().strip('"').lower()
                    indexed[table].add(first)
    return dict(indexed)


# -- Filter call discovery ---------------------------------------------------

# Match `db.from('TABLE').<chain>.eq('col', x)` -- we collect every filter
# operator (eq, gt, gte, lt, lte, in, ilike, like, neq) on a column.
FROM_CALL_RE = re.compile(
    r"""\.from\s*\(\s*['"`](?P<table>[a-z_][a-z0-9_]*)['"`]\s*\)
        (?P<chain>(?:\s*\.\s*\w+\s*\([^)]*\))+)""",
    re.IGNORECASE | re.VERBOSE,
)
PY_FROM_CALL_RE = re.compile(
    r"""\.table\s*\(\s*['"](?P<table>[a-z_][a-z0-9_]*)['"]\s*\)
        (?P<chain>(?:\s*\.\s*\w+\s*\([^)]*\))+)""",
    re.IGNORECASE | re.VERBOSE,
)
FILTER_OP_RE = re.compile(
    r"""\.(?P<op>eq|gt|gte|lt|lte|in|ilike|like|neq|contains)\s*\(
        \s*['"`](?P<col>[a-zA-Z_]\w*)['"`]""",
    re.VERBOSE,
)
MATCH_OP_RE = re.compile(r"""\.match\s*\(\s*\{([^}]+)\}""")


def list_consumer_files() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for path in sorted(glob.glob("*.html")):
        if any(p in path.lower() for p in EXCLUDED_HTML_PATTERNS):
            continue
        out.append((path, "html"))
    for path in sorted(glob.glob("*.js")):
        if path.endswith(".min.js"):
            continue
        out.append((path, "shared_js"))
    if os.path.isdir(FUNCTIONS_DIR):
        for d in sorted(os.listdir(FUNCTIONS_DIR)):
            idx = os.path.join(FUNCTIONS_DIR, d, "index.ts")
            if os.path.isfile(idx):
                out.append((idx, "edge"))
    for path in sorted(glob.glob(os.path.join(PYTHON_API_DIR, "**", "*.py"), recursive=True)):
        if "__init__" in path:
            continue
        out.append((path, "python_api"))
    return out


def find_filters(consumer_files: list[tuple[str, str]]) -> list[dict]:
    """Return list of {table, column, op, path, layer} for every filter call."""
    out: list[dict] = []
    for path, layer in consumer_files:
        src = read_file(path) or ""
        rx = PY_FROM_CALL_RE if path.endswith(".py") else FROM_CALL_RE
        for m in rx.finditer(src):
            table = m.group("table").lower()
            chain = m.group("chain")
            for fm in FILTER_OP_RE.finditer(chain):
                out.append({
                    "table": table,
                    "column": fm.group("col").lower(),
                    "op":    fm.group("op").lower(),
                    "path":  path,
                    "layer": layer,
                })
            for mm in MATCH_OP_RE.finditer(chain):
                for piece in mm.group(1).split(","):
                    if ":" in piece:
                        col = piece.split(":", 1)[0].strip().strip("'\"`").lower()
                        if col and re.match(r"^\w+$", col):
                            out.append({
                                "table": table,
                                "column": col,
                                "op": "match",
                                "path": path,
                                "layer": layer,
                            })
    return out


# -- Layer 1+2: Unindexed filter analysis -----------------------------------

def analyse_unindexed(
    filters: list[dict],
    indexed: dict[str, set[str]],
) -> tuple[list[dict], list[dict]]:
    """Return (l1_findings, l2_findings) for high/medium frequency.

    Each finding: {table, column, n_files, n_uses, layers, sample}
    """
    # group filters by (table, column)
    bucket: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for f in filters:
        if f["table"] in OPAQUE_TABLES:
            continue
        if f["column"] in ALWAYS_COVERED:
            continue
        # Skip views (start with v_) -- indexes apply to underlying tables.
        if f["table"].startswith("v_"):
            continue
        # Skip if no DDL for this table (table_cols would be empty -> skip).
        bucket[(f["table"], f["column"])].append(f)

    l1: list[dict] = []
    l2: list[dict] = []
    for (table, col), uses in bucket.items():
        if col in indexed.get(table, set()):
            continue
        if (table, col) in INDEX_DEFERRED:
            continue
        n_files = len({u["path"] for u in uses})
        n_uses  = len(uses)
        layers  = sorted({u["layer"] for u in uses})
        sample  = sorted({u["path"] for u in uses})[:5]
        finding = {
            "table":   table,
            "column":  col,
            "n_files": n_files,
            "n_uses":  n_uses,
            "layers":  layers,
            "sample":  sample,
        }
        if n_files >= L1_FILES and n_uses >= L1_USES:
            l1.append(finding)
        elif n_files >= L2_FILES and n_uses >= L2_USES:
            l2.append(finding)
    l1.sort(key=lambda f: (-f["n_uses"], -f["n_files"]))
    l2.sort(key=lambda f: (-f["n_uses"], -f["n_files"]))
    return l1, l2


def check_l1(findings: list[dict]) -> list[dict]:
    issues: list[dict] = []
    for f in findings:
        issues.append({
            "check": "high_freq_unindexed", "skip": True,
            "reason": (
                f"{f['table']}.{f['column']}: filtered in {f['n_files']} files "
                f"({f['n_uses']} total usages, layers={f['layers']}) but no "
                f"index covers this column. Add: "
                f"`CREATE INDEX IF NOT EXISTS idx_{f['table']}_{f['column']} "
                f"ON {f['table']} ({f['column']});`"
            ),
        })
    return issues


def check_l2(findings: list[dict]) -> list[dict]:
    issues: list[dict] = []
    for f in findings:
        issues.append({
            "check": "med_freq_unindexed", "skip": True,
            "reason": (
                f"{f['table']}.{f['column']}: filtered in {f['n_files']} files "
                f"({f['n_uses']} total usages) but no index covers this column. "
                f"Growing hotspot -- add an index when this rises to L1 "
                f"thresholds (3+ files, 5+ uses)."
            ),
        })
    return issues


# -- Layer 3: Per-table coverage matrix (informational) --------------------

def check_coverage_matrix(
    filters: list[dict],
    indexed: dict[str, set[str]],
) -> tuple[list[dict], list[dict]]:
    cols_per_table: dict[str, set[str]] = defaultdict(set)
    for f in filters:
        if f["table"] in OPAQUE_TABLES:
            continue
        if f["table"].startswith("v_"):
            continue
        cols_per_table[f["table"]].add(f["column"])
    rows: list[dict] = []
    for table, cols in cols_per_table.items():
        idx = indexed.get(table, set())
        rows.append({
            "table":     table,
            "filtered":  len(cols),
            "indexed":   len(cols & idx),
            "uncovered": sorted(cols - idx - ALWAYS_COVERED)[:8],
            "ratio":     (len(cols & idx) / len(cols)) if cols else 0,
        })
    rows.sort(key=lambda r: r["ratio"])
    return [], rows


# -- Layer 4: Tables with no non-PK index (informational) ------------------

def check_no_index_tables(indexed: dict[str, set[str]]) -> tuple[list[dict], list[dict]]:
    """Tables that exist in some sense but have only `id` as their indexed
    set. We pull table names from the filter universe to keep the noise
    low (lookup-only catalog tables get excluded if nobody filters them).
    """
    rows: list[dict] = []
    for table, cols in indexed.items():
        if cols == {"id"}:
            rows.append({"table": table})
    rows.sort(key=lambda r: r["table"])
    return [], rows


# -- Runner -----------------------------------------------------------------

CHECK_NAMES = [
    "high_freq_unindexed",
    "med_freq_unindexed",
    "coverage_matrix",
    "no_index_tables",
]
CHECK_LABELS = {
    "high_freq_unindexed": "L1  No high-frequency filter (3+ files, 5+ uses) on un-indexed col [WARN]",
    "med_freq_unindexed":  "L2  No medium-frequency filter (2+ files, 3+ uses) on un-indexed col [WARN]",
    "coverage_matrix":     "L3  Per-table filter-vs-index coverage matrix (informational)    [INFO]",
    "no_index_tables":     "L4  Tables with only PK index (informational)                    [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nIndex Coverage Detector (4-layer)"))
    print("=" * 60)

    indexed        = load_indexed_columns()
    consumer_files = list_consumer_files()
    filters        = find_filters(consumer_files)

    print(f"  {sum(len(s) for s in indexed.values())} indexed columns across "
          f"{len(indexed)} tables; "
          f"{len(filters)} filter calls in {len(consumer_files)} files.\n")

    l1_findings, l2_findings = analyse_unindexed(filters, indexed)
    l1_issues = check_l1(l1_findings)
    l2_issues = check_l2(l2_findings)
    _, matrix_report = check_coverage_matrix(filters, indexed)
    _, no_idx_report = check_no_index_tables(indexed)

    all_issues = l1_issues + l2_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if matrix_report:
        print(f"\n{bold('FILTER-vs-INDEX COVERAGE (lowest ratio first)')}")
        print("  " + "-" * 56)
        for r in matrix_report[:10]:
            uncovered = ", ".join(r["uncovered"][:4])
            tail = f"  uncovered: {uncovered}" if uncovered else ""
            print(f"  {r['table']:<28}  {r['indexed']}/{r['filtered']:<3}  "
                  f"({r['ratio']*100:5.1f}%){tail}")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":          "index_coverage",
        "total_checks":       total,
        "passed":             n_pass,
        "warned":             n_warn,
        "failed":             n_fail,
        "n_indexed_tables":   len(indexed),
        "n_filter_calls":     len(filters),
        "l1_findings":        l1_findings,
        "l2_findings":        l2_findings,
        "coverage_matrix":    matrix_report,
        "no_index_tables":    no_idx_report,
        "issues":             [i for i in all_issues if not i.get("skip")],
        "warnings":           [i for i in all_issues if i.get("skip")],
    }
    with open("index_coverage_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
