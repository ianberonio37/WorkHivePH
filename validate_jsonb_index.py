"""
JSONB Index Drift -- WorkHive Platform
========================================
JSONB columns queried via `@>`, `?`, `?|`, `?&`, `->>` operators
benefit from GIN indexes. Without them, every query falls back to
sequential scan and the table-size cliff is invisible until rows
pile up.

Layer 1 -- JSONB col queried by @> / ? but no GIN index                  [WARN]
  Find consumer-side JSONB containment / key-existence queries and
  check the migrations for a matching `CREATE INDEX ... USING gin`.

Layer 2 -- JSONB col with ->>'key' filter and high frequency             [WARN]
  Filter shape `col->>'key' = ...` benefits from a btree expression
  index. Surface high-frequency call sites without one.

Layer 3 -- GIN index inventory (informational)                            [INFO]
  Per-table count of GIN indexes that already exist.

Layer 4 -- JSONB op call frequency (informational)                        [INFO]
  Distribution of @>, ?, ?|, ->>'...' usage across the codebase.

Skills consulted: data-engineer (JSONB indexing semantics),
performance (sequential scan on JSONB at 100k+ rows = page hang).
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
EXCLUDED_HTML_PATTERNS = ("-test.html", ".backup.html", "_backup.html", ".backup")

JSONB_INDEX_OK: dict[tuple[str, str], str] = {
    # external_sync.sync_payload GIN index SHIPPED in 20260511000007_db_hygiene_wave2.sql.
    # Closed: PRODUCTION_FIXES #58. Allowlist empty -- gate ratchets cleanly.
}

CREATE_TABLE_RE = re.compile(
    r"""CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?
        (?:public\.|"public"\.)?"?(?P<name>\w+)"?\s*\(
        (?P<body>[\s\S]*?)\n\s*\);""",
    re.IGNORECASE | re.VERBOSE,
)
JSONB_COL_RE = re.compile(
    r"""^\s*"?(?P<col>\w+)"?\s+(?:"jsonb"|jsonb)\b""",
    re.IGNORECASE | re.MULTILINE | re.VERBOSE,
)
GIN_INDEX_RE = re.compile(
    r"""CREATE\s+(?:UNIQUE\s+)?INDEX[\s\S]*?ON\s+
        (?:public\.|"public"\.)?"?(?P<table>\w+)"?\s*
        USING\s+"?gin"?\s*\(\s*"?(?P<col>\w+)"?""",
    re.IGNORECASE | re.VERBOSE,
)
CONSUMER_JSONB_RE = re.compile(
    r"""\.from\s*\(\s*['"`](?P<table>\w+)['"`]\s*\)
        [\s\S]{0,200}?
        \.(?P<op>contains|containedBy)\s*\(\s*['"`](?P<col>\w+)['"`]""",
    re.VERBOSE,
)
DOUBLE_ARROW_RE = re.compile(
    r"""['"`](?P<col>\w+)->>['"`](?P<key>\w+)['"`]""",
)


def collect_jsonb_cols() -> set[tuple[str, str]]:
    out = set()
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = re.sub(r"--[^\n]*", "", read_file(path) or "")
        for tm in CREATE_TABLE_RE.finditer(sql):
            for cm in JSONB_COL_RE.finditer(tm.group("body")):
                col = cm.group("col").lower()
                if col in {"constraint", "primary", "foreign", "check"}:
                    continue
                out.add((tm.group("name").lower(), col))
    return out


def collect_gin_indexes() -> set[tuple[str, str]]:
    out = set()
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = re.sub(r"--[^\n]*", "", read_file(path) or "")
        for m in GIN_INDEX_RE.finditer(sql):
            out.add((m.group("table").lower(), m.group("col").lower()))
    return out


def list_consumer_files() -> list[str]:
    out: list[str] = []
    for p in sorted(glob.glob("*.html")):
        if any(x in p.lower() for x in EXCLUDED_HTML_PATTERNS):
            continue
        out.append(p)
    for p in sorted(glob.glob("*.js")):
        if p.endswith(".min.js"):
            continue
        out.append(p)
    for p in sorted(glob.glob("supabase/functions/**/*.ts", recursive=True)):
        out.append(p)
    return out


def collect_consumer_jsonb_ops() -> dict[tuple[str, str], int]:
    """Return {(table, col): n_usages} for .contains() / .containedBy() calls."""
    counter: dict[tuple[str, str], int] = defaultdict(int)
    for path in list_consumer_files():
        src = read_file(path) or ""
        for m in CONSUMER_JSONB_RE.finditer(src):
            counter[(m.group("table").lower(), m.group("col").lower())] += 1
    return counter


def check_missing_gin(jsonb_cols, gin_cols, consumer_ops):
    issues, report = [], []
    for (table, col), n in consumer_ops.items():
        if (table, col) not in jsonb_cols:
            continue
        if (table, col) in gin_cols:
            continue
        if (table, col) in JSONB_INDEX_OK:
            continue
        report.append({"table": table, "col": col, "n_usages": n})
        issues.append({
            "check": "missing_gin", "skip": True,
            "reason": (
                f"{table}.{col}: {n} consumer-side JSONB containment "
                f"query (.contains() / .containedBy()) but no "
                f"`CREATE INDEX ... USING gin` exists. Add: "
                f"`CREATE INDEX idx_{table}_{col}_gin ON {table} "
                f"USING gin ({col});`"
            ),
        })
    return issues, report


def check_double_arrow_freq(jsonb_cols):
    """Just count call sites; informational only since expression indexes
    are case-by-case."""
    counter: dict[tuple[str, str], int] = defaultdict(int)
    for path in list_consumer_files():
        src = read_file(path) or ""
        for m in DOUBLE_ARROW_RE.finditer(src):
            col = m.group("col").lower()
            key = m.group("key").lower()
            # We can't know which table without surrounding context.
            counter[(col, key)] += 1
    rows = [{"col": c, "key": k, "n": n}
            for (c, k), n in sorted(counter.items(), key=lambda kv: -kv[1])][:10]
    issues = []   # no L2 issues, informational
    return issues, rows


def check_gin_inventory(gin_cols):
    by_table: dict[str, list[str]] = defaultdict(list)
    for (t, c) in gin_cols:
        by_table[t].append(c)
    rows = [{"table": t, "n_gin": len(cs), "cols": cs}
            for t, cs in sorted(by_table.items(), key=lambda kv: -len(kv[1]))]
    return [], rows


def check_jsonb_op_distribution(jsonb_cols):
    op_counter: dict[str, int] = defaultdict(int)
    op_patterns = {
        "contains":   re.compile(r"\.contains\s*\("),
        "containedBy": re.compile(r"\.containedBy\s*\("),
        "double_arrow": re.compile(r"['\"`]\w+->>['\"]"),
        "single_arrow": re.compile(r"->"),
    }
    for path in list_consumer_files():
        src = read_file(path) or ""
        for op, rx in op_patterns.items():
            op_counter[op] += len(rx.findall(src))
    return [], [{"op": k, "count": v} for k, v in op_counter.items()]


CHECK_NAMES = ["missing_gin", "double_arrow_freq", "gin_inventory", "op_distribution"]
CHECK_LABELS = {
    "missing_gin":       "L1  Consumer JSONB containment queries have a GIN index           [WARN]",
    "double_arrow_freq": "L2  ->> key-extraction frequency surfaces (informational)         [INFO]",
    "gin_inventory":     "L3  GIN index inventory per table (informational)                 [INFO]",
    "op_distribution":   "L4  JSONB op distribution (informational)                          [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nJSONB Index Drift (4-layer)"))
    print("=" * 60)
    jsonb_cols    = collect_jsonb_cols()
    gin_cols      = collect_gin_indexes()
    consumer_ops  = collect_consumer_jsonb_ops()
    print(f"  {len(jsonb_cols)} jsonb cols, {len(gin_cols)} GIN indexes, "
          f"{sum(consumer_ops.values())} consumer JSONB ops.\n")
    l1_i, l1_r = check_missing_gin(jsonb_cols, gin_cols, consumer_ops)
    l2_i, l2_r = check_double_arrow_freq(jsonb_cols)
    l3_i, l3_r = check_gin_inventory(gin_cols)
    l4_i, l4_r = check_jsonb_op_distribution(jsonb_cols)
    all_issues = l1_i + l2_i + l3_i + l4_i
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)
    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")
    report = {"validator": "jsonb_index", "total_checks": total,
              "passed": n_pass, "warned": n_warn, "failed": n_fail,
              "missing_gin": l1_r, "double_arrow_freq": l2_r,
              "gin_inventory": l3_r, "op_distribution": l4_r,
              "issues": [i for i in all_issues if not i.get("skip")],
              "warnings": [i for i in all_issues if i.get("skip")]}
    with open("jsonb_index_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
