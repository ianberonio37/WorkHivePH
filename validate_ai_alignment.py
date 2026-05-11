"""
AI Alignment / Provenance -- WorkHive Platform
=================================================
Catches the unapproved-AI-output bug class. When an AI agent writes
into a worker-visible table without provenance metadata (source,
confidence, requires_approval), downstream UIs can't distinguish
human-entered ground truth from a hallucinated suggestion. A worker
sees "this asset is at high failure risk" with no way to tell that
the score came from an LLM that may have been wrong.

Layer 1 -- AI-source insert sites stamp `source` field                   [WARN]
  Edge fns that call callAI() AND insert into a worker-visible table
  should set `source` to a recognisable `ai_*` prefix so consumers can
  filter. Catches the silent provenance loss bug.

Layer 2 -- AI inserts include confidence + approval gate                 [WARN]
  Tables that receive AI inserts should ALSO carry either an
  `ai_confidence` numeric column OR a `requires_approval` boolean.
  Without one, a hallucinated row is indistinguishable from a vetted
  one. Forward-looking ratchet -- DEFERRED until columns ship.

Layer 3 -- Dashboard reads filter on approved provenance                 [WARN]
  Pages that read from AI-output tables should filter on
  `approved = true` or `requires_approval = false` OR display the
  confidence inline so a worker can decide. Pages in the worker view
  must not present AI rows as ground truth.

Layer 4 -- Per-table AI provenance inventory (informational)             [INFO]
  Per-table count of inserts originating from AI edge fns vs.
  human-entered. Helps spot tables drifting toward AI-dominated.

Skills consulted: ai-engineer (provenance metadata, confidence
exposure), security (untrusted data origin), designer (UX of
"this came from AI" visual treatment).
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


FUNCTIONS_DIR  = os.path.join("supabase", "functions")
MIGRATIONS_DIR = os.path.join("supabase", "migrations")

# AI-output tables that should carry provenance metadata. Discovered from
# the codebase; new entries land here when a fresh AI agent writes to
# a new table.
AI_OUTPUT_TABLES = {
    "ai_reports",
    "automation_log",
    "failure_signature_alerts",
    "asset_risk_scores",
    "parts_staging_recommendations",
    "fmea_entries",
    "intelligence_reports",
}

# Tables whose rows are exclusively AI-generated AND clearly labelled as
# such in their own filename. They don't need additional provenance
# (the table IS the provenance signal).
ALIGNMENT_OK_TABLES = {
    "ai_cost_log":       "Telemetry only — log of AI calls, not a worker-facing surface",
    "ai_quality_log":    "Eval scores — not surfaced to workers, governance internal",
    "agent_memory":      "Conversation memory — RLS-gated per worker; surface is the agent itself",
}

# Forward-looking ratchet — baseline 2026-05-11: 4 fns write to AI output
# tables without stamping source: 'ai_*', and 2 tables (ai_reports,
# asset_risk_scores) lack confidence/approval columns. Adoption is
# incremental; tracked in PRODUCTION_FIXES (AI alignment).
ALIGNMENT_DEFERRED = True

CALLAI_RE          = re.compile(r"\bcallAI\s*\(")
INSERT_RE          = re.compile(r"""\.from\(\s*['"](?P<table>\w+)['"]\s*\)\s*\.insert""")
SOURCE_FIELD_RE    = re.compile(r"""\bsource\s*:\s*['"](?P<v>[^'"]+)['"]""")


def list_edge_fns() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if os.path.isdir(FUNCTIONS_DIR):
        for d in sorted(os.listdir(FUNCTIONS_DIR)):
            idx = os.path.join(FUNCTIONS_DIR, d, "index.ts")
            if os.path.isfile(idx):
                out.append((d, idx))
    return out


def list_html_pages() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for path in sorted(glob.glob("*.html")):
        name = os.path.basename(path)
        if name.endswith(".html"):
            out.append((name, path))
    return out


def _strip_comments(src: str) -> str:
    src = re.sub(r"/\*[\s\S]*?\*/", "", src)
    src = re.sub(r"//[^\n]*", "", src)
    return src


def _table_columns_from_migrations() -> dict[str, set[str]]:
    """Crude: parse CREATE TABLE blocks and ALTER TABLE ADD COLUMN.
    Returns {table_name: {col1, col2, ...}}."""
    out: dict[str, set[str]] = defaultdict(set)
    if not os.path.isdir(MIGRATIONS_DIR):
        return out
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        src = read_file(path) or ""
        # CREATE TABLE blocks
        for m in re.finditer(
            r"""CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:public\.|"public"\.)?"?(?P<name>\w+)"?\s*\((?P<body>[^;]+)\)""",
            src, re.IGNORECASE | re.DOTALL,
        ):
            name = m.group("name")
            body = m.group("body")
            for col_m in re.finditer(r"^\s*\"?(\w+)\"?\s+[a-zA-Z][\w()\[\]]*", body, re.MULTILINE):
                out[name].add(col_m.group(1).lower())
        # ALTER TABLE ADD COLUMN
        for m in re.finditer(
            r"""ALTER\s+TABLE\s+(?:ONLY\s+)?(?:public\.|"public"\.)?"?(?P<name>\w+)"?\s+ADD\s+COLUMN\s+(?:IF\s+NOT\s+EXISTS\s+)?\"?(?P<col>\w+)\"?""",
            src, re.IGNORECASE,
        ):
            out[m.group("name")].add(m.group("col").lower())
    return out


# -- Layer 1: AI-source insert sites stamp `source` ------------------------

def check_source_stamp(fns) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for name, path in fns:
        src = _strip_comments(read_file(path) or "")
        if not CALLAI_RE.search(src):
            continue
        # Find every insert into a known AI_OUTPUT_TABLE
        for m in INSERT_RE.finditer(src):
            table = m.group("table")
            if table not in AI_OUTPUT_TABLES:
                continue
            # Look in a 600-char window after the insert for a `source:` field
            window = src[m.start(): m.start() + 600]
            sf = SOURCE_FIELD_RE.search(window)
            if not sf or not sf.group("v").startswith("ai_"):
                issues.append({
                    "check":  "source_stamp",
                    "reason": f"{name}: insert into AI-output table `{table}` does not stamp `source: 'ai_*'`",
                    "skip":   ALIGNMENT_DEFERRED,
                })
            report.append({
                "fn":     name,
                "table":  table,
                "source": sf.group("v") if sf else None,
            })
    return issues, report


# -- Layer 2: AI-output tables have confidence + approval columns --------

def check_provenance_columns(table_cols) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for table in sorted(AI_OUTPUT_TABLES):
        if table in ALIGNMENT_OK_TABLES:
            continue
        cols = table_cols.get(table, set())
        if not cols:
            continue  # table not declared in migrations — out of scope
        has_conf = any(c in cols for c in (
            "ai_confidence", "confidence", "confidence_score",
        ))
        has_appr = any(c in cols for c in (
            "requires_approval", "approved", "approved_at", "approved_by", "status",
        ))
        if not (has_conf or has_appr):
            issues.append({
                "check":  "provenance_columns",
                "reason": f"`{table}` carries AI inserts but has no confidence/approval column (existing cols: {', '.join(sorted(cols))[:120]})",
                "skip":   ALIGNMENT_DEFERRED,
            })
        report.append({"table": table, "has_confidence": has_conf, "has_approval": has_appr})
    return issues, report


# -- Layer 3: Dashboard reads filter on approved provenance ---------------

def check_dashboard_filters(pages, table_cols) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    approval_tables = set()
    for table in AI_OUTPUT_TABLES:
        cols = table_cols.get(table, set())
        if any(c in cols for c in ("requires_approval", "approved")):
            approval_tables.add(table)
    if not approval_tables:
        return issues, report
    SELECT_RE = re.compile(r"""\.from\(\s*['"](?P<table>\w+)['"]\s*\)\s*\.select""")
    for name, path in pages:
        src = read_file(path) or ""
        if not src:
            continue
        for m in SELECT_RE.finditer(src):
            table = m.group("table")
            if table not in approval_tables:
                continue
            # Look in a 600-char window after the select for an approval filter.
            window = src[m.start(): m.start() + 600]
            if re.search(r"""\.eq\(\s*['"](?:approved|requires_approval)['"]""", window):
                continue
            if "ai_confidence" in window:
                continue  # surfacing confidence inline is acceptable
            issues.append({
                "check":  "dashboard_filter",
                "reason": f"{name}: reads `{table}` without filtering on approved/requires_approval and no confidence shown",
            })
            report.append({"page": name, "table": table})
    return issues, report


# -- Layer 4: AI provenance inventory (informational) ---------------------

def check_inventory(fns) -> tuple[list[dict], list[dict]]:
    report = []
    by_table: dict[str, list[str]] = defaultdict(list)
    for name, path in fns:
        src = _strip_comments(read_file(path) or "")
        is_ai = bool(CALLAI_RE.search(src))
        if not is_ai:
            continue
        for m in INSERT_RE.finditer(src):
            table = m.group("table")
            by_table[table].append(name)
    for table, fns_list in by_table.items():
        report.append({
            "table":      table,
            "ai_fns":     sorted(set(fns_list)),
            "ai_fn_n":    len(set(fns_list)),
            "is_ai_out":  table in AI_OUTPUT_TABLES,
        })
    return [], sorted(report, key=lambda r: -r["ai_fn_n"])


# -- Runner -----------------------------------------------------------------

CHECK_NAMES = [
    "source_stamp",
    "provenance_columns",
    "dashboard_filter",
    "inventory",
]
CHECK_LABELS = {
    "source_stamp":        "L1  AI-source inserts stamp source: 'ai_*' on output tables       [WARN]",
    "provenance_columns":  "L2  AI-output tables have confidence and/or approval columns      [WARN]",
    "dashboard_filter":    "L3  Pages reading AI tables filter on approval or show confidence [WARN]",
    "inventory":           "L4  AI insert reach per table (informational)                     [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nAI Alignment / Provenance (4-layer)"))
    print("=" * 60)

    fns        = list_edge_fns()
    pages      = list_html_pages()
    table_cols = _table_columns_from_migrations()
    print(f"  {len(fns)} edge fn(s), {len(pages)} page(s), {len(table_cols)} table(s) parsed.")
    print(f"  AI_OUTPUT_TABLES={len(AI_OUTPUT_TABLES)}  ALIGNMENT_OK={len(ALIGNMENT_OK_TABLES)}.\n")

    l1_issues, l1_report = check_source_stamp(fns)
    l2_issues, l2_report = check_provenance_columns(table_cols)
    l3_issues, l3_report = check_dashboard_filters(pages, table_cols)
    l4_issues, l4_report = check_inventory(fns)

    all_issues = l1_issues + l2_issues + l3_issues + l4_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if l4_report:
        print(f"\n{bold('AI INSERT REACH PER TABLE (informational)')}")
        print("  " + "-" * 56)
        for r in l4_report[:10]:
            tag = "ai-output" if r["is_ai_out"] else "ai-write"
            print(f"  {r['table']:<32}  fns={r['ai_fn_n']:<2}  [{tag}]")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":          "ai_alignment",
        "total_checks":       total,
        "passed":             n_pass,
        "warned":             n_warn,
        "failed":             n_fail,
        "n_fns":              len(fns),
        "n_tables":           len(table_cols),
        "source_stamp":       l1_report,
        "provenance_columns": l2_report,
        "dashboard_filter":   l3_report,
        "inventory":          l4_report,
    }
    try:
        with open("ai_alignment_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    except Exception:
        pass

    sys.exit(0 if n_fail == 0 else 1)


if __name__ == "__main__":
    main()
