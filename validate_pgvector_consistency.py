"""
pgvector Consistency -- WorkHive Platform
=============================================
Catches the vector-dim-mismatch class of bugs. WorkHive's RAG layer
relies on `embedding-chain.ts` producing 384-dim vectors and the
schema declaring `vector(384)` on every embedding column. A drift in
either direction (chain outputs 1536-dim, column is vector(384), or
vice versa) silently returns zero matches on `cosine_distance` queries
-- no error, just empty results.

Layer 1 -- Every vector(N) column matches embedding TARGET_DIM           [FAIL]
  Parses `_shared/embedding-chain.ts` for TARGET_DIM, parses every
  `vector(N)` column in migrations, fails on any mismatch.

Layer 2 -- Every search RPC filters by hive_id                           [WARN]
  PL/pgSQL functions using the `<=>` operator must include `hive_id`
  in their WHERE clause. Without it, cross-hive bleed is possible
  through pgvector search.

Layer 3 -- Embedding tables have hive RLS policy                         [WARN]
  Every `*_embeddings` / `*_knowledge` table must have an RLS policy
  that scopes by hive_id. Belt-and-braces with L2.

Layer 4 -- Vector dim distribution (informational)                       [INFO]
  Inventory of every vector(N) column declared in migrations grouped
  by dim. Surfaces tables that pre-date the 384 standard.

Skills consulted: ai-engineer (embedding model dims, RAG indexing),
data-engineer (pg_vector index choice, ivfflat vs hnsw, distance
operators), multitenant-engineer (hive_id RLS).
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
EMBED_CHAIN    = os.path.join("supabase", "functions", "_shared", "embedding-chain.ts")

# Tables exempt from L1 dim check (legitimate non-384 dim, e.g. archival).
DIM_OK = {
    # "table.column": "reason"
}

# Tables exempt from L2 hive filter (legitimate global, e.g. catalog).
HIVE_FILTER_OK = {
    "calc_knowledge":  "Engineering calc knowledge is platform-wide, not hive-scoped",
    "industry_standards_chunks":  "Industry standards (ISO/ASHRAE/NFPA) are platform-wide reference corpus, mirrors kb_chunks pattern but not hive-scoped",
    "platform_knowledge_graph_facts":  "Platform-wide KG facts (2026-05-19), hive-agnostic by design — mirrors industry_standards / kb_chunks pattern. Powers semantic_search_platform_kg_facts RPC.",
    "persona_knowledge":  "Global persona RAG corpus (companion W10-W13) — NO hive_id column by design; match_persona_knowledge searches the shared corpus, so it correctly does not (cannot) filter by hive_id. Same class as calc_knowledge / industry_standards.",
}

# Tables exempt from L3 RLS check.
RLS_OK = {
    "calc_knowledge":     "Global catalog — granted SELECT to anon",
    "fault_knowledge":    "DEFERRED — RAG knowledge table, RLS migration tracked in PRODUCTION_FIXES",
    "skill_knowledge":    "DEFERRED — RAG knowledge table, RLS migration tracked in PRODUCTION_FIXES",
    "pm_knowledge":       "DEFERRED — RAG knowledge table, RLS migration tracked in PRODUCTION_FIXES",
    "bom_knowledge":      "DEFERRED — RAG knowledge table, RLS migration tracked in PRODUCTION_FIXES",
    "project_knowledge":  "DEFERRED — RAG knowledge table, RLS migration tracked in PRODUCTION_FIXES",
    "persona_knowledge":  "Global persona RAG corpus (companion W10-W13) — NO tenant column (cannot leak cross-tenant); read edge-only via service_role (ai-gateway / persona-knowledge.ts). Same class as the other RAG knowledge tables above.",
    "embedding_cache":    "Global embedding cache keyed by text hash — NO tenant column (cannot leak cross-tenant); read/write edge-only via service_role (embedding-chain.ts). Not user data.",
}

VECTOR_COL_RE = re.compile(
    r"""\b\"?(?P<col>\w+)\"?\s+(?:public\.)?\"?vector\"?\s*\(\s*(?P<dim>\d+)\s*\)""",
    re.IGNORECASE,
)
CREATE_TABLE_RE = re.compile(
    r"""CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:public\.|"public"\.)?\"?(?P<name>\w+)\"?\s*\((?P<body>[^;]+?)\)\s*;""",
    re.IGNORECASE | re.DOTALL,
)
CREATE_FN_RE = re.compile(
    r"""CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+(?:public\.|"public"\.)?\"?(?P<name>\w+)\"?\s*\([^)]*\)[\s\S]+?\$\$(?P<body>[\s\S]+?)\$\$""",
    re.IGNORECASE,
)
COSINE_OP_RE = re.compile(r"""<=>""")
RLS_POLICY_RE = re.compile(
    r"""CREATE\s+POLICY[\s\S]+?ON\s+(?:public\.|"public"\.)?\"?(?P<table>\w+)\"?""",
    re.IGNORECASE,
)


def parse_target_dim() -> int | None:
    src = read_file(EMBED_CHAIN)
    if not src:
        return None
    m = re.search(r"const\s+TARGET_DIM\s*=\s*(\d+)", src)
    return int(m.group(1)) if m else None


def parse_vector_columns() -> list[dict]:
    """Returns list of {table, column, dim, file}."""
    out: list[dict] = []
    if not os.path.isdir(MIGRATIONS_DIR):
        return out
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        src = read_file(path) or ""
        for m in CREATE_TABLE_RE.finditer(src):
            table = m.group("name")
            body  = m.group("body")
            for cm in VECTOR_COL_RE.finditer(body):
                out.append({
                    "table": table,
                    "column": cm.group("col"),
                    "dim":   int(cm.group("dim")),
                    "file":  os.path.basename(path),
                })
        # Also handle ALTER TABLE ADD COLUMN ... vector(N)
        for cm in re.finditer(
            r"""ALTER\s+TABLE\s+(?:ONLY\s+)?(?:public\.|"public"\.)?\"?(?P<table>\w+)\"?\s+ADD\s+COLUMN\s+(?:IF\s+NOT\s+EXISTS\s+)?(?P<rest>[^;]+)""",
            src, re.IGNORECASE,
        ):
            rest = cm.group("rest")
            vm = VECTOR_COL_RE.search(rest)
            if vm:
                out.append({
                    "table":  cm.group("table"),
                    "column": vm.group("col"),
                    "dim":    int(vm.group("dim")),
                    "file":   os.path.basename(path),
                })
    return out


def parse_search_fns() -> list[dict]:
    """Functions that use the <=> operator. Returns list of {name, body, file}."""
    out: list[dict] = []
    if not os.path.isdir(MIGRATIONS_DIR):
        return out
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        src = read_file(path) or ""
        for m in CREATE_FN_RE.finditer(src):
            body = m.group("body")
            if not COSINE_OP_RE.search(body):
                continue
            out.append({
                "name": m.group("name"),
                "body": body,
                "file": os.path.basename(path),
            })
    return out


def parse_rls_tables() -> set[str]:
    out: set[str] = set()
    if not os.path.isdir(MIGRATIONS_DIR):
        return out
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        src = read_file(path) or ""
        for m in RLS_POLICY_RE.finditer(src):
            out.add(m.group("table"))
    return out


# -- Layer 1: Vector dim matches TARGET_DIM ------------------------------

def check_dim_consistency(target_dim, vec_cols) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    if target_dim is None:
        issues.append({
            "check":  "dim_consistency",
            "reason": f"_shared/embedding-chain.ts: TARGET_DIM not declared — cannot verify column dims",
        })
        return issues, report
    for vc in vec_cols:
        key = f"{vc['table']}.{vc['column']}"
        if key in DIM_OK:
            continue
        if vc["dim"] != target_dim:
            issues.append({
                "check":  "dim_consistency",
                "reason": f"{key} declared vector({vc['dim']}) but TARGET_DIM={target_dim} (file: {vc['file']})",
            })
        report.append({
            "table":  vc["table"],
            "column": vc["column"],
            "dim":    vc["dim"],
            "match":  vc["dim"] == target_dim,
        })
    return issues, report


# -- Layer 2: Search RPCs filter by hive_id ------------------------------

def check_hive_filter(search_fns) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for fn in search_fns:
        has_hive = re.search(r"\bhive_id\b", fn["body"])
        report.append({
            "fn":       fn["name"],
            "has_hive": bool(has_hive),
            "file":     fn["file"],
        })
        if not has_hive:
            # Check if it's exempt by looking at the tables it references.
            # Match either bare 'tablename' or schema-prefixed 'public.tablename'.
            referenced = re.findall(r"\bFROM\s+(?:\w+\.)?(\w+)", fn["body"], re.IGNORECASE)
            exempt = any(t in HIVE_FILTER_OK for t in referenced)
            if exempt:
                continue
            issues.append({
                "check":  "hive_filter",
                "reason": f"Search fn `{fn['name']}` uses <=> but does not reference hive_id — cross-hive bleed risk",
            })
    return issues, report


# -- Layer 3: Embedding tables have RLS policy ---------------------------

def check_embedding_rls(vec_cols, rls_tables) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    seen = set()
    for vc in vec_cols:
        if vc["table"] in seen:
            continue
        seen.add(vc["table"])
        if vc["table"] in RLS_OK:
            continue
        has_rls = vc["table"] in rls_tables
        if not has_rls:
            issues.append({
                "check":  "embedding_rls",
                "reason": f"`{vc['table']}` carries vector data but has no RLS policy",
            })
        report.append({"table": vc["table"], "has_rls": has_rls})
    return issues, report


# -- Layer 4: Vector dim distribution (informational) -------------------

def check_distribution(vec_cols) -> tuple[list[dict], list[dict]]:
    by_dim: dict[int, list[str]] = defaultdict(list)
    for vc in vec_cols:
        by_dim[vc["dim"]].append(f"{vc['table']}.{vc['column']}")
    return [], [{"dim": d, "n": len(cols), "cols": sorted(cols)} for d, cols in sorted(by_dim.items())]


# -- Runner -----------------------------------------------------------------

CHECK_NAMES = [
    "dim_consistency",
    "hive_filter",
    "embedding_rls",
    "vector_distribution",
]
CHECK_LABELS = {
    "dim_consistency":     "L1  Every vector(N) column matches embedding TARGET_DIM           [FAIL]",
    "hive_filter":         "L2  Every search RPC filters by hive_id                           [WARN]",
    "embedding_rls":       "L3  Every embedding table has an RLS policy                       [WARN]",
    "vector_distribution": "L4  Vector dim distribution (informational)                       [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\npgvector Consistency (4-layer)"))
    print("=" * 60)

    target_dim  = parse_target_dim()
    vec_cols    = parse_vector_columns()
    search_fns  = parse_search_fns()
    rls_tables  = parse_rls_tables()

    print(f"  TARGET_DIM={target_dim}  vector columns={len(vec_cols)}")
    print(f"  Search fns (<=>): {len(search_fns)}  RLS-policied tables: {len(rls_tables)}.")
    print(f"  DIM_OK={len(DIM_OK)}  HIVE_FILTER_OK={len(HIVE_FILTER_OK)}  RLS_OK={len(RLS_OK)}.\n")

    l1_issues, l1_report = check_dim_consistency(target_dim, vec_cols)
    l2_issues, l2_report = check_hive_filter(search_fns)
    l3_issues, l3_report = check_embedding_rls(vec_cols, rls_tables)
    l4_issues, l4_report = check_distribution(vec_cols)

    all_issues = l1_issues + l2_issues + l3_issues + l4_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if l4_report:
        print(f"\n{bold('VECTOR DIM DISTRIBUTION (informational)')}")
        print("  " + "-" * 56)
        for r in l4_report:
            print(f"  vector({r['dim']})  count={r['n']}  cols={', '.join(r['cols'])}")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":           "pgvector_consistency",
        "total_checks":        total,
        "passed":              n_pass,
        "warned":              n_warn,
        "failed":              n_fail,
        "target_dim":          target_dim,
        "n_vector_columns":    len(vec_cols),
        "n_search_fns":        len(search_fns),
        "dim_consistency":     l1_report,
        "hive_filter":         l2_report,
        "embedding_rls":       l3_report,
        "vector_distribution": l4_report,
    }
    try:
        with open("pgvector_consistency_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    except Exception:
        pass

    sys.exit(0 if n_fail == 0 else 1)


if __name__ == "__main__":
    main()
