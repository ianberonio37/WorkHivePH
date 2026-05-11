"""
Embedding Coverage & Freshness -- WorkHive Platform
=====================================================
Catches the silent vector-search-returns-zero bug. WorkHive uses
embeddings for asset graph search + calc knowledge RAG. If asset_nodes
gets new rows but the embedding pipeline doesn't backfill, semantic
search misses them entirely.

Layer 1 -- Every embedding table has a backfill cron / fn               [WARN]
  Tables ending in `_embeddings` should have a refresh fn registered
  (e.g., `embed-entry`) AND a cron schedule that backfills new rows.

Layer 2 -- Embedding table has vector index                             [WARN]
  Each `*_embeddings.embedding` column should have a `USING ivfflat`
  or `USING hnsw` index. Without it, similarity queries do full scan.

Layer 3 -- Embedding adoption per source table (informational)          [INFO]
  Map of (source_table -> embedding_table) coverage. Helps spot
  source tables that have RAG potential but no embedding pipeline.

Layer 4 -- Embedding model dimension distribution (informational)       [INFO]
  Inventory of vector(N) declarations across the schema.

Skills consulted: ai-engineer (RAG pipelines, vector index choice),
data-engineer (backfill cron discipline), realtime-engineer (new-row
embedding triggers vs cron backfill).
"""
from __future__ import annotations

import re
import json
import sys
import os
import glob

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


MIGRATIONS_DIR = os.path.join("supabase", "migrations")
FUNCTIONS_DIR  = os.path.join("supabase", "functions")

EMBEDDING_OK: dict[str, str] = {
    # "embedding_table": "reason"
}

EMBED_TABLE_RE = re.compile(
    r"""CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?
        (?:public\.|"public"\.)?"?(?P<name>\w+_embeddings|\w+_knowledge)"?\s*\(""",
    re.IGNORECASE | re.VERBOSE,
)
VECTOR_COL_RE = re.compile(
    r"""\b(?:vector|public\."vector")\s*\((?P<dim>\d+)\)""",
    re.IGNORECASE | re.VERBOSE,
)
VECTOR_INDEX_RE = re.compile(
    r"""CREATE\s+INDEX[\s\S]*?ON\s+(?:public\.|"public"\.)?"?(?P<table>\w+)"?\s*
        USING\s+"?(?:ivfflat|hnsw)"?""",
    re.IGNORECASE | re.VERBOSE,
)
REFRESH_FN_RE = re.compile(r"""embed-entry|embed_entry|generate_embedding""")


def _read_all_migrations() -> str:
    return "\n".join(read_file(p) or "" for p in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))))


def collect_embedding_tables() -> list[str]:
    sql = re.sub(r"--[^\n]*", "", _read_all_migrations())
    return sorted(set(m.group("name").lower() for m in EMBED_TABLE_RE.finditer(sql)))


def has_refresh_fn() -> bool:
    return any(os.path.isfile(os.path.join(FUNCTIONS_DIR, fn, "index.ts"))
               for fn in ("embed-entry", "embedding-refresh"))


def has_backfill_cron() -> bool:
    sql = _read_all_migrations()
    return bool(re.search(
        r"""cron\.schedule\s*\([^)]*embed""",
        sql, re.IGNORECASE,
    ))


def has_vector_index(table: str) -> bool:
    sql = re.sub(r"--[^\n]*", "", _read_all_migrations())
    for m in VECTOR_INDEX_RE.finditer(sql):
        if m.group("table").lower() == table:
            return True
    return False


def check_refresh_pipeline(tables):
    issues, report = [], []
    has_fn   = has_refresh_fn()
    has_cron = has_backfill_cron()
    report.append({"refresh_fn_present": has_fn, "backfill_cron_present": has_cron})
    if not tables:
        return issues, report
    if not has_fn:
        issues.append({
            "check": "refresh_pipeline", "skip": True,
            "reason": (
                "Embedding tables exist but no refresh edge fn (`embed-entry` "
                "or similar) is present. New rows won't get embedded; vector "
                "search results are stale by design. Add or restore the "
                "refresh fn."
            ),
        })
    if not has_cron:
        issues.append({
            "check": "refresh_pipeline", "skip": True,
            "reason": (
                "Embedding tables exist but no `cron.schedule` job mentions "
                "'embed'. The refresh fn is decorative without a recurring "
                "trigger -- schedule a daily / hourly backfill."
            ),
        })
    return issues, report


def check_vector_index(tables):
    issues, report = [], []
    for t in tables:
        if t in EMBEDDING_OK:
            continue
        if has_vector_index(t):
            continue
        report.append({"table": t})
        issues.append({
            "check": "vector_index", "skip": True,
            "reason": (
                f"{t}: no `USING ivfflat` / `USING hnsw` index on the "
                f"vector column. Similarity queries fall back to "
                f"sequential scan. Add: `CREATE INDEX idx_{t}_embedding "
                f"ON {t} USING ivfflat (embedding vector_cosine_ops);`"
            ),
        })
    return issues, report


def check_source_coverage(tables):
    """Heuristic: each *_embeddings table should have a source table
    without the suffix. Surface coverage gaps."""
    rows = []
    sql = re.sub(r"--[^\n]*", "", _read_all_migrations())
    # All non-view tables
    all_tables = set(re.findall(
        r"""CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:public\.|"public"\.)?"?(\w+)"?\s*\(""",
        sql, re.IGNORECASE,
    ))
    all_tables = {t.lower() for t in all_tables}
    for emb in tables:
        if emb.endswith("_embeddings"):
            src = emb.removesuffix("_embeddings")
            rows.append({"embedding_table": emb, "source_table": src,
                         "source_exists": src in all_tables})
        elif emb.endswith("_knowledge"):
            rows.append({"embedding_table": emb, "source_table": "(internal RAG store)",
                         "source_exists": True})
    return [], rows


def check_dim_inventory():
    rows = []
    sql = re.sub(r"--[^\n]*", "", _read_all_migrations())
    from collections import Counter
    counter: Counter = Counter()
    for m in VECTOR_COL_RE.finditer(sql):
        counter[int(m.group("dim"))] += 1
    for dim, n in counter.most_common():
        rows.append({"dim": dim, "count": n})
    return [], rows


CHECK_NAMES = ["refresh_pipeline", "vector_index", "source_coverage", "dim_inventory"]
CHECK_LABELS = {
    "refresh_pipeline": "L1  Embedding refresh fn + backfill cron present                [WARN]",
    "vector_index":     "L2  Every embedding table has a vector index                    [WARN]",
    "source_coverage":  "L3  Embedding table -> source table coverage (informational)    [INFO]",
    "dim_inventory":    "L4  Vector dimension distribution (informational)               [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nEmbedding Coverage & Freshness (4-layer)"))
    print("=" * 60)
    tables = collect_embedding_tables()
    print(f"  {len(tables)} embedding/knowledge table(s) in schema.\n")
    l1_i, l1_r = check_refresh_pipeline(tables)
    l2_i, l2_r = check_vector_index(tables)
    l3_i, l3_r = check_source_coverage(tables)
    l4_i, l4_r = check_dim_inventory()
    all_issues = l1_i + l2_i + l3_i + l4_i
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)
    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")
    report = {"validator": "embedding_coverage", "total_checks": total,
              "passed": n_pass, "warned": n_warn, "failed": n_fail,
              "refresh_pipeline": l1_r, "vector_index": l2_r,
              "source_coverage": l3_r, "dim_inventory": l4_r,
              "issues": [i for i in all_issues if not i.get("skip")],
              "warnings": [i for i in all_issues if i.get("skip")]}
    with open("embedding_coverage_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
