"""
PDF Pipeline / Knowledge Ingestion -- WorkHive Platform
==========================================================
Catches the stalled-RAG bug class: knowledge tables that exist in the
schema but have no documented ingestion path. The naive seed (hand-
coded fixtures) is a ceiling on RAG quality; every *_knowledge table
should declare an ingestion source so the corpus can grow.

Layer 1 -- pdf_jobs table present                                        [FAIL]
  The migration set must declare the pdf_jobs ingestion-state table.
  Without it the pipeline has no queue to drain.

Layer 2 -- pdf-ingest edge fn exists                                     [FAIL]
  The edge fn that processes pdf_jobs rows must be present on disk
  and must write to at least one knowledge table.

Layer 3 -- Every knowledge table has an ingestion source                 [WARN]
  Each *_knowledge table should either:
    (a) be listed in KNOWLEDGE_INGESTION_OK with a justification
        ('seeded manually; intentionally curated'), OR
    (b) receive inserts from pdf-ingest or a seeder script.

Layer 4 -- Ingestion pipeline inventory (informational)                  [INFO]
  Lists each knowledge table + its known ingestion path. Helps spot
  tables drifting toward "exists but never grows".

Skills consulted: ai-engineer (RAG corpus quality), data-engineer
(ingestion queue + retry semantics), knowledge-manager (manual vs
automated knowledge capture).
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


MIGRATIONS_DIR    = os.path.join("supabase", "migrations")
FUNCTIONS_DIR     = os.path.join("supabase", "functions")
PDF_INGEST_FILE   = os.path.join(FUNCTIONS_DIR, "pdf-ingest", "index.ts")

# Tables exempt from the ingestion-path check. Each needs a justification.
KNOWLEDGE_INGESTION_OK = {
    "calc_knowledge":     "Seeded manually from PEC / NSCP / IEC fixtures; intentionally curated, no PDF pipeline",
}

KNOWLEDGE_TABLE_RE = re.compile(
    r"""CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?
        (?:public\.|"public"\.)?"?(?P<name>\w+_knowledge)"?""",
    re.IGNORECASE | re.VERBOSE,
)


def _all_migrations_sql() -> str:
    chunks: list[str] = []
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        chunks.append(read_file(path) or "")
    return "\n".join(chunks)


def _knowledge_tables() -> set[str]:
    sql = _all_migrations_sql()
    return {m.group("name") for m in KNOWLEDGE_TABLE_RE.finditer(sql)}


def _has_pdf_jobs_table() -> bool:
    sql = _all_migrations_sql()
    return bool(re.search(
        r"""CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?
            (?:public\.|"public"\.)?"?pdf_jobs"?""",
        sql, re.IGNORECASE | re.VERBOSE,
    ))


def _pdf_ingest_targets() -> set[str]:
    """Return the set of knowledge tables the pdf-ingest fn writes to,
    parsed from its target_table CHECK constraint OR from .insert() calls."""
    src = read_file(PDF_INGEST_FILE)
    if not src:
        return set()
    # Direct insert sites in the source.
    direct = set(re.findall(
        r"""\.from\(\s*['"`](\w+_knowledge)['"`]\s*\)\s*\.insert""",
        src,
    ))
    # Also pull the CHECK constraint from the migration since the
    # validator may run before the fn is fully wired.
    sql = _all_migrations_sql()
    check_m = re.search(
        r"""target_table\s+text\s+NOT\s+NULL\s+CHECK\s*\(\s*target_table\s+IN\s*\((?P<list>[^)]+)\)\s*\)""",
        sql, re.IGNORECASE,
    )
    if check_m:
        for vm in re.finditer(r"""['"]([^'"]+)['"]""", check_m.group("list")):
            direct.add(vm.group(1))
    return direct


def _seeded_tables() -> set[str]:
    """Best-effort: tables that have INSERT statements in any migration."""
    out: set[str] = set()
    sql = _all_migrations_sql()
    for m in re.finditer(
        r"""INSERT\s+INTO\s+(?:public\.)?"?(?P<name>\w+_knowledge)"?""",
        sql, re.IGNORECASE,
    ):
        out.add(m.group("name"))
    return out


# -- Layer 1: pdf_jobs table present --------------------------------------

def check_pdf_jobs_table() -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    present = _has_pdf_jobs_table()
    report = [{"pdf_jobs_table_present": present}]
    if not present:
        issues.append({
            "check": "pdf_jobs_table", "skip": False,
            "reason": (
                "pdf_jobs table not declared in any migration. The PDF "
                "ingestion pipeline has no queue surface. Apply migration "
                "20260511000011_pdf_jobs.sql."
            ),
        })
    return issues, report


# -- Layer 2: pdf-ingest edge fn exists ----------------------------------

def check_pdf_ingest_fn() -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    present = os.path.isfile(PDF_INGEST_FILE)
    targets = _pdf_ingest_targets() if present else set()
    report = [{
        "pdf_ingest_fn_present": present,
        "targets":               sorted(targets),
    }]
    if not present:
        issues.append({
            "check": "pdf_ingest_fn", "skip": False,
            "reason": f"pdf-ingest edge fn not found at {PDF_INGEST_FILE}",
        })
    elif not targets:
        issues.append({
            "check": "pdf_ingest_fn", "skip": True,
            "reason": (
                "pdf-ingest fn exists but writes to 0 knowledge tables. "
                "Verify the .insert() targets and target_table CHECK."
            ),
        })
    return issues, report


# -- Layer 3: Every knowledge table has an ingestion source --------------

def check_ingestion_coverage() -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    tables   = _knowledge_tables()
    targets  = _pdf_ingest_targets()
    seeded   = _seeded_tables()
    for table in sorted(tables):
        if table in KNOWLEDGE_INGESTION_OK:
            report.append({
                "table":   table,
                "source": f"OK ({KNOWLEDGE_INGESTION_OK[table]})",
            })
            continue
        has_source = (table in targets) or (table in seeded)
        report.append({
            "table":            table,
            "via_pdf_ingest":   table in targets,
            "via_migration":    table in seeded,
            "covered":          has_source,
        })
        if not has_source:
            issues.append({
                "check": "ingestion_coverage", "skip": True,
                "reason": (
                    f"Knowledge table '{table}' has no ingestion source -- "
                    f"not in pdf-ingest targets, no INSERTs in migrations. "
                    f"Either list it in KNOWLEDGE_INGESTION_OK with a "
                    f"justification or add it to the pdf-ingest CHECK list."
                ),
            })
    return issues, report


# -- Layer 4: Ingestion pipeline inventory (informational) ---------------

def check_inventory() -> tuple[list[dict], list[dict]]:
    report: list[dict] = []
    tables  = _knowledge_tables()
    targets = _pdf_ingest_targets()
    seeded  = _seeded_tables()
    for table in sorted(tables):
        report.append({
            "table":          table,
            "pdf_ingest_ok":  table in targets,
            "seeded_via_sql": table in seeded,
            "allowlisted":    table in KNOWLEDGE_INGESTION_OK,
        })
    return [], report


# -- Runner ---------------------------------------------------------------

CHECK_NAMES = [
    "pdf_jobs_table",
    "pdf_ingest_fn",
    "ingestion_coverage",
    "inventory",
]
CHECK_LABELS = {
    "pdf_jobs_table":     "L1  pdf_jobs ingestion queue table present                       [FAIL]",
    "pdf_ingest_fn":      "L2  pdf-ingest edge fn exists + writes knowledge tables          [FAIL]",
    "ingestion_coverage": "L3  Every *_knowledge table has a documented ingestion source   [WARN]",
    "inventory":          "L4  Knowledge table ingestion-path inventory                    [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nPDF Pipeline / Knowledge Ingestion (4-layer)"))
    print("=" * 60)

    tables  = _knowledge_tables()
    targets = _pdf_ingest_targets()
    print(f"  {len(tables)} *_knowledge table(s), pdf-ingest targets={len(targets)}.\n")

    l1_issues, l1_report = check_pdf_jobs_table()
    l2_issues, l2_report = check_pdf_ingest_fn()
    l3_issues, l3_report = check_ingestion_coverage()
    l4_issues, l4_report = check_inventory()

    all_issues = l1_issues + l2_issues + l3_issues + l4_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if l4_report:
        print(f"\n{bold('INGESTION PATH PER TABLE (informational)')}")
        print("  " + "-" * 56)
        for r in l4_report:
            tag = (
                "allowlisted" if r["allowlisted"]
                else "pdf-ingest" if r["pdf_ingest_ok"]
                else "seeded-sql" if r["seeded_via_sql"]
                else "uncovered"
            )
            print(f"  {r['table']:<32}  [{tag}]")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":          "pdf_pipeline",
        "total_checks":       total,
        "passed":             n_pass,
        "warned":             n_warn,
        "failed":             n_fail,
        "n_knowledge_tables": len(tables),
        "n_pdf_targets":      len(targets),
        "pdf_jobs_table":     l1_report,
        "pdf_ingest_fn":      l2_report,
        "ingestion_coverage": l3_report,
        "inventory":          l4_report,
    }
    try:
        with open("pdf_pipeline_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    except Exception:
        pass

    sys.exit(0 if n_fail == 0 else 1)


if __name__ == "__main__":
    main()
