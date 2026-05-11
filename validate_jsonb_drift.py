"""
JSONB Schema Drift Detector -- WorkHive Platform
=================================================
JSONB columns are typed only by convention. When the writer and reader
disagree on the key set -- writer stores `{notes, value}` but reader
asks for `obj.note` (no `s`) -- the read returns `undefined` silently.
The page renders blank or rounds NaN to 0; nobody sees an error.

This gate inventories every JSONB column declared in migrations,
finds the keys read by consumer files, and flags drift shapes.

Layer 1 -- JSONB column never read via dotted/bracket access            [WARN]
  Column is declared as `jsonb` in CREATE TABLE but no consumer file
  ever accesses `row.<col>.<key>` or `row.<col>['key']`. Either the
  column is orphaned (candidate for removal) or every reader uses
  `JSON.stringify(row.<col>)` which makes audit impossible.

Layer 2 -- Reader key without object-literal writer                     [WARN]
  Reader file accesses `row.<col>.foo` for a column whose writers all
  pass a variable (no object literal anywhere). Static analysis can't
  prove `foo` is always present; the consumer may render undefined.
  Surfaces as a watch-list, not a hard fail.

Layer 3 -- Reader-key vs writer-key inventory (informational)           [INFO]
  Per-column matrix: keys observed in writes vs keys observed in
  reads. Helps spot one-letter typos, abandoned keys, or asymmetric
  shapes between the writer fn and the reader UI.

Layer 4 -- JSONB column census (informational)                          [INFO]
  Per-table count of JSONB columns. High counts can signal that a
  proper relational shape was skipped in favour of JSONB blobs.

Skills consulted: data-engineer (schema/query alignment, JSONB-as-
escape-hatch tradeoff), architect (when to normalize vs JSONB), AI
engineer (AI-generated payloads land in JSONB columns; key-set drift
between fn versions is a common bug).
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

# JSONB columns we know are intentionally treated as opaque blobs (AI
# response cache, vector embeddings, etc.). Each entry needs a one-line
# justification.
OPAQUE_JSONB = {
    ("ai_reports", "report_json"):       "AI report cache; structure varies per report_type",
    ("ai_reports", "summary"):            "free text",
    ("hive_analytics_cache", "mtbf_by_machine"):  "dynamic per-machine map; no fixed key set",
    ("hive_analytics_cache", "mttr_by_machine"):  "dynamic per-machine map",
    ("hive_audit_log", "meta"):           "audit metadata; per-event shape varies",
    ("cmms_audit_log", "meta"):           "audit metadata; per-event shape varies",
    ("automation_log", "detail"):         "free-form per-job detail",
    ("logbook", "readings_json"):         "telemetry payload; equipment-specific shape",
    ("logbook", "production_output"):     "production data; varies by line type",
    ("skill_exam_attempts", "answers"):   "per-exam answer map keyed by question id",
    ("hive_benchmarks", "targets"):       "per-hive KPI target map; user-defined keys",
    ("network_benchmarks", "sample_hives"): "anonymised list of hive ids",
    ("engineering_calc_history", "key_inputs"):  "per-calc-type input map",
    ("engineering_calc_history", "key_outputs"): "per-calc-type output map",
    ("engineering_calcs", "inputs"):       "per-calc-type input map",
    ("engineering_calcs", "results"):      "per-calc-type result map",
    ("engineering_calcs", "narrative"):    "AI-generated narrative paragraphs",
    ("engineering_calcs", "bom_data"):     "BOM/SOW structure varies by discipline",
    ("ph_intelligence_reports", "report_json"): "snapshot blob",
    ("parts_staging_recommendations", "parts"): "AI part recommendation array; per-recommendation shape",
    ("asset_edges", "properties"):                "graph edge properties; per-edge schema varies",
    ("asset_nodes", "external_ids"):              "CMMS sync IDs map; per-system shape",
    ("asset_risk_scores", "components"):          "risk-model component scores; consumed as a unit",
    ("asset_risk_scores", "top_factors"):         "risk-model top contributing factors array",
    ("calc_knowledge", "key_inputs"):             "calc-history knowledge inputs",
    ("calc_knowledge", "key_outputs"):            "calc-history knowledge outputs",
    ("canonical_sources", "contract"):            "registry contract spec",
    ("cmms_audit_log", "quality_score"):          "AI quality scores per audit row",
    ("external_sync", "sync_payload"):            "CMMS sync payload; per-system schema",
    ("failure_signature_alerts", "evidence"):     "pattern-alert evidence blob",
    ("integration_configs", "field_map"):         "CMMS field mapping; per-integration shape",
    ("ph_intelligence_reports", "narrative"):     "AI narrative paragraphs",
    ("project_items", "predecessors"):            "task-graph predecessor refs",
}


CREATE_TABLE_RE = re.compile(
    r"""CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?
        (?:public\.|"public"\.)?
        "?(?P<name>\w+)"?\s*\(
        (?P<body>[\s\S]*?)\n\s*\);""",
    re.IGNORECASE | re.VERBOSE,
)
JSONB_COL_RE = re.compile(
    r"""^\s*"?(?P<col>\w+)"?\s+(?:"jsonb"|jsonb)\b""",
    re.IGNORECASE | re.MULTILINE | re.VERBOSE,
)
ALTER_JSONB_RE = re.compile(
    r"""ALTER\s+TABLE\s+(?:ONLY\s+)?(?:public\.|"public"\.|IF\s+EXISTS\s+)?
        "?(?P<table>\w+)"?\s+ADD\s+COLUMN(?:\s+IF\s+NOT\s+EXISTS)?\s+
        "?(?P<col>\w+)"?\s+(?:"jsonb"|jsonb)\b""",
    re.IGNORECASE | re.VERBOSE,
)


def collect_jsonb_columns() -> set[tuple[str, str]]:
    cols: set[tuple[str, str]] = set()
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = re.sub(r"--[^\n]*", "", read_file(path) or "")
        for tm in CREATE_TABLE_RE.finditer(sql):
            table = tm.group("name").lower()
            for cm in JSONB_COL_RE.finditer(tm.group("body")):
                col = cm.group("col").lower()
                if col not in {"constraint", "primary", "foreign", "check"}:
                    cols.add((table, col))
        for am in ALTER_JSONB_RE.finditer(sql):
            cols.add((am.group("table").lower(), am.group("col").lower()))
    return cols


def list_consumer_files() -> list[str]:
    out: list[str] = []
    for path in sorted(glob.glob("*.html")):
        if any(p in path.lower() for p in EXCLUDED_HTML_PATTERNS):
            continue
        out.append(path)
    for path in sorted(glob.glob("*.js")):
        if path.endswith(".min.js"):
            continue
        out.append(path)
    if os.path.isdir(FUNCTIONS_DIR):
        for d in sorted(os.listdir(FUNCTIONS_DIR)):
            idx = os.path.join(FUNCTIONS_DIR, d, "index.ts")
            if os.path.isfile(idx):
                out.append(idx)
    for path in sorted(glob.glob(os.path.join(PYTHON_API_DIR, "**", "*.py"), recursive=True)):
        if "__init__" in path:
            continue
        out.append(path)
    return out


def _strip_comments(src: str) -> str:
    src = re.sub(r"<!--[\s\S]*?-->", "", src)
    src = re.sub(r"/\*[\s\S]*?\*/", "", src)
    src = re.sub(r"//[^\n]*", "", src)
    return src


def find_reader_keys(src: str, col: str) -> set[str]:
    """Find `<anything>.<col>.<key>` and `<anything>.<col>['key']` patterns."""
    keys: set[str] = set()
    # `obj.col.key`  -- key must be alpha first; no chained method calls
    rx_dot = re.compile(rf"""\.{re.escape(col)}\s*\.\s*(?P<key>[a-zA-Z_]\w{{0,40}})""")
    for m in rx_dot.finditer(src):
        k = m.group("key")
        # Filter out method calls: a key followed by `(` is a function.
        end = m.end()
        if end < len(src) and src[end] == "(":
            continue
        keys.add(k)
    rx_brk = re.compile(rf"""\.{re.escape(col)}\s*\[\s*['"`](?P<key>[^'"`]+)['"`]\s*\]""")
    for m in rx_brk.finditer(src):
        keys.add(m.group("key"))
    return keys


def find_writer_keys(src: str, col: str) -> set[str]:
    """Find `.insert({col: {k:..., k2:...}})` / `.update({col: {...}})` keys."""
    keys: set[str] = set()
    # Match `col:` or `"col":` or `'col':` followed by `{ ... }` literal.
    rx = re.compile(
        rf"""['"`]?{re.escape(col)}['"`]?\s*:\s*\{{(?P<body>[^{{}}]*)\}}""",
        re.DOTALL,
    )
    for m in rx.finditer(src):
        body = m.group("body")
        for km in re.finditer(r"['\"`]?([a-zA-Z_]\w*)['\"`]?\s*:", body):
            keys.add(km.group(1))
    return keys


# -- Layer 1: JSONB column never read --------------------------------------

def check_unread_jsonb(
    cols: set[tuple[str, str]],
    files: list[str],
) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    # Build aggregate reader keys per column.
    reader_keys: dict[tuple[str, str], set[str]] = defaultdict(set)
    for path in files:
        src = _strip_comments(read_file(path) or "")
        for (table, col) in cols:
            reader_keys[(table, col)] |= find_reader_keys(src, col)
    for (table, col) in sorted(cols):
        if (table, col) in OPAQUE_JSONB:
            continue
        if reader_keys[(table, col)]:
            continue
        report.append({"table": table, "column": col})
        issues.append({
            "check": "unread_jsonb", "skip": True,
            "reason": (
                f"Column {table}.{col} is jsonb in schema but no source "
                f"file accesses any key of it (`row.{col}.<key>` or "
                f"`row.{col}['<key>']`). Either the column is orphaned "
                f"(candidate for removal) or readers always pass it as an "
                f"opaque blob (consider adding {table}.{col} to OPAQUE_JSONB "
                f"with a justification)."
            ),
        })
    return issues, report


# -- Layer 2: Reader key without object-literal writer --------------------

def check_reader_without_writer_literal(
    cols: set[tuple[str, str]],
    files: list[str],
) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    reader_keys: dict[tuple[str, str], set[str]] = defaultdict(set)
    writer_keys: dict[tuple[str, str], set[str]] = defaultdict(set)
    for path in files:
        src = _strip_comments(read_file(path) or "")
        for (table, col) in cols:
            reader_keys[(table, col)] |= find_reader_keys(src, col)
            writer_keys[(table, col)] |= find_writer_keys(src, col)
    for (table, col) in sorted(cols):
        if (table, col) in OPAQUE_JSONB:
            continue
        rk = reader_keys[(table, col)]
        wk = writer_keys[(table, col)]
        # Only complain if there ARE readers AND there ARE NO matching
        # writer literals. If writers exist but use a variable shape
        # (no literal), wk will be empty -- that's the bug pattern we
        # want to catch.
        if not rk:
            continue
        if wk:
            continue
        report.append({
            "table":       table,
            "column":      col,
            "reader_keys": sorted(rk)[:8],
        })
        issues.append({
            "check": "reader_without_writer", "skip": True,
            "reason": (
                f"Column {table}.{col}: readers reference keys "
                f"{sorted(rk)[:5]} but no source file writes the column "
                f"with an object literal -- writers all pass a variable. "
                f"Static analysis can't prove the keys are always present; "
                f"consider adding a TypeScript / Python typed shape OR "
                f"add to OPAQUE_JSONB if the reader handles undefined."
            ),
        })
    return issues, report


# -- Layer 3: Reader vs writer key inventory (informational) --------------

def check_key_inventory(
    cols: set[tuple[str, str]],
    files: list[str],
) -> tuple[list[dict], list[dict]]:
    reader_keys: dict[tuple[str, str], set[str]] = defaultdict(set)
    writer_keys: dict[tuple[str, str], set[str]] = defaultdict(set)
    for path in files:
        src = _strip_comments(read_file(path) or "")
        for (table, col) in cols:
            reader_keys[(table, col)] |= find_reader_keys(src, col)
            writer_keys[(table, col)] |= find_writer_keys(src, col)
    rows: list[dict] = []
    for (table, col) in sorted(cols):
        rows.append({
            "table":         table,
            "column":        col,
            "n_reader_keys": len(reader_keys[(table, col)]),
            "n_writer_keys": len(writer_keys[(table, col)]),
            "writer_keys":   sorted(writer_keys[(table, col)])[:6],
            "reader_keys":   sorted(reader_keys[(table, col)])[:6],
        })
    rows.sort(key=lambda r: -(r["n_reader_keys"] + r["n_writer_keys"]))
    return [], rows


# -- Layer 4: JSONB column census (informational) -------------------------

def check_census(cols: set[tuple[str, str]]) -> tuple[list[dict], list[dict]]:
    by_table: dict[str, int] = defaultdict(int)
    for (table, _col) in cols:
        by_table[table] += 1
    rows = [
        {"table": t, "n_jsonb_cols": n}
        for t, n in sorted(by_table.items(), key=lambda kv: -kv[1])
    ]
    return [], rows


# -- Runner --------------------------------------------------------------

CHECK_NAMES = [
    "unread_jsonb",
    "reader_without_writer",
    "key_inventory",
    "census",
]
CHECK_LABELS = {
    "unread_jsonb":          "L1  Every JSONB column has a reader (or is allowlisted opaque)  [WARN]",
    "reader_without_writer": "L2  Every reader key has a matching object-literal writer       [WARN]",
    "key_inventory":         "L3  Per-column reader/writer key inventory (informational)      [INFO]",
    "census":                "L4  JSONB column count by table (informational)                 [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nJSONB Schema Drift Detector (4-layer)"))
    print("=" * 60)

    cols  = collect_jsonb_columns()
    files = list_consumer_files()
    print(f"  {len(cols)} JSONB column(s) across "
          f"{len({t for t, _ in cols})} table(s); "
          f"{len(files)} consumer files scanned.\n")

    l1_issues, l1_report = check_unread_jsonb(cols, files)
    l2_issues, l2_report = check_reader_without_writer_literal(cols, files)
    l3_issues, l3_report = check_key_inventory(cols, files)
    l4_issues, l4_report = check_census(cols)

    all_issues = l1_issues + l2_issues + l3_issues + l4_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if l3_report:
        print(f"\n{bold('JSONB KEY INVENTORY (top by total keys)')}")
        print("  " + "-" * 56)
        for r in l3_report[:8]:
            print(f"  {r['table']:<22} . {r['column']:<22}  "
                  f"R={r['n_reader_keys']:<2} W={r['n_writer_keys']}")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":             "jsonb_drift",
        "total_checks":          total,
        "passed":                n_pass,
        "warned":                n_warn,
        "failed":                n_fail,
        "n_jsonb_cols":          len(cols),
        "unread_jsonb":          l1_report,
        "reader_without_writer": l2_report,
        "key_inventory":         l3_report,
        "census":                l4_report,
        "issues":                [i for i in all_issues if not i.get("skip")],
        "warnings":              [i for i in all_issues if i.get("skip")],
    }
    with open("jsonb_drift_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
