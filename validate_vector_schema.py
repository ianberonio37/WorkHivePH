"""
Vector Knowledge Base Schema Validator — WorkHive Platform
==========================================================
WorkHive's Classic RAG pipeline (and future Graph/Agentic RAG) is built
on pgvector + nomic-embed-text-v1.5 (384 dimensions). Three knowledge
tables store embeddings: fault_knowledge, skill_knowledge, pm_knowledge.

If ANY of the structural rules below break, the semantic search pipeline
fails SILENTLY — the AI assistant returns generic answers instead of
contextual ones, and no error appears in the Guardian.

  Layer 1 — Foundation
    1.  pgvector extension enabled     — CREATE EXTENSION vector in migrations

  Layer 2 — Schema integrity
    2.  All tables declare vector(384) — dimension must match embedding model exactly
    3.  IVFFlat indexes on embeddings  — full table scan above 10k rows is unusable

  Layer 3 — Query correctness
    4.  UNION ALL subquery LIMIT       — each subquery must LIMIT before the UNION
    5.  hive_id scoping in search fn   — search_all_knowledge must filter by hive_id

  Layer 4 — Result quality
    6.  Similarity threshold guard     — low-relevance results must be filtered out  [WARN]

Usage:  python validate_vector_schema.py
Output: vector_schema_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

MIGRATIONS_DIR  = os.path.join("supabase", "migrations")
FUNCTIONS_DIR   = os.path.join("supabase", "functions")
SEMANTIC_SEARCH = os.path.join(FUNCTIONS_DIR, "semantic-search", "index.ts")

EMBEDDING_MODEL  = "nomic-embed-text-v1_5"
EMBEDDING_DIM    = 384
KNOWLEDGE_TABLES = ["fault_knowledge", "skill_knowledge", "pm_knowledge"]
UNION_SEARCH_FN  = "search_all_knowledge"
MIN_SIMILARITY   = 0.5   # minimum acceptable similarity score


def read_all_migrations():
    combined = ""
    if not os.path.isdir(MIGRATIONS_DIR):
        return combined
    for fname in sorted(os.listdir(MIGRATIONS_DIR)):
        if not fname.endswith(".sql"):
            continue
        content = read_file(os.path.join(MIGRATIONS_DIR, fname))
        if content:
            combined += f"\n-- FILE: {fname}\n" + content
    return combined


# ── Layer 1: Foundation ───────────────────────────────────────────────────────

def check_vector_extension(migrations):
    if not migrations:
        return [{"check": "vector_extension", "source": MIGRATIONS_DIR,
                 "reason": f"{MIGRATIONS_DIR} not found"}]
    if not re.search(r"CREATE\s+EXTENSION.*\bvector\b", migrations, re.IGNORECASE):
        return [{"check": "vector_extension", "source": MIGRATIONS_DIR,
                 "reason": ("No 'CREATE EXTENSION IF NOT EXISTS vector' found — "
                            "pgvector not enabled, all knowledge tables will fail to create")}]
    return []


# ── Layer 2: Schema integrity ─────────────────────────────────────────────────

def check_vector_dimension(migrations, tables, dim):
    """Each knowledge table must declare embedding vector(384) — dimension must
    match nomic-embed-text-v1.5 exactly. A mismatch causes every INSERT to fail."""
    issues = []
    if not migrations:
        return []
    for table in tables:
        table_m = re.search(
            rf"CREATE TABLE.*?\b{re.escape(table)}\b([\s\S]+?)(?=CREATE TABLE|CREATE INDEX|CREATE OR REPLACE|$)",
            migrations, re.IGNORECASE
        )
        if not table_m:
            issues.append({"check": "vector_dimension", "table": table,
                           "reason": (f"Table '{table}' not found in migrations — "
                                      f"knowledge table missing, semantic search returns no results")})
            continue
        vec_m = re.search(r"\bembedding\s+vector\s*\(\s*(\d+)\s*\)", table_m.group(1))
        if not vec_m:
            issues.append({"check": "vector_dimension", "table": table,
                           "reason": f"Table '{table}' has no embedding vector({dim}) column"})
        elif int(vec_m.group(1)) != dim:
            issues.append({"check": "vector_dimension", "table": table,
                           "reason": (f"Table '{table}' uses vector({vec_m.group(1)}) but model "
                                      f"produces {dim}-dim vectors — dimension mismatch on every INSERT")})
    return issues


def check_ivfflat_indexes(migrations, tables):
    """Every embedding column must have an IVFFlat index with vector_cosine_ops.
    Without it, similarity search full-scans the table — unusable above 10k rows."""
    issues = []
    if not migrations:
        return []
    for table in tables:
        if not re.search(
            rf"CREATE INDEX[\s\S]*?ON\s+{re.escape(table)}\s+USING\s+ivfflat\s*\([\s\S]*?vector_cosine_ops[\s\S]*?\)",
            migrations, re.IGNORECASE
        ):
            issues.append({"check": "ivfflat_indexes", "table": table,
                           "reason": (f"Table '{table}' has no IVFFlat index on embedding — "
                                      f"similarity search will full-scan, unusable above 10,000 rows")})
    return issues


# ── Layer 3: Query correctness ────────────────────────────────────────────────

def check_union_all_pattern(migrations):
    """search_all_knowledge must have ORDER BY + LIMIT inside each UNION ALL subquery.
    Outer-only LIMIT makes Postgres process all rows before limiting — defeats the index."""
    if not migrations:
        return []
    fn_m = re.search(
        rf"CREATE OR REPLACE FUNCTION\s+{re.escape(UNION_SEARCH_FN)}[\s\S]+?(?=CREATE OR REPLACE FUNCTION|\$\$;)",
        migrations, re.IGNORECASE
    )
    if not fn_m:
        return [{"check": "union_all_pattern", "source": MIGRATIONS_DIR,
                 "reason": f"Function '{UNION_SEARCH_FN}' not found in migrations"}]
    fn_body     = fn_m.group(0)
    union_count = len(re.findall(r"UNION\s+ALL", fn_body, re.IGNORECASE))
    sub_limits  = re.findall(r"SELECT[\s\S]+?LIMIT\s+\w+[\s\S]*?(?=UNION ALL|\Z)", fn_body, re.IGNORECASE)
    if len(sub_limits) < union_count + 1:
        return [{"check": "union_all_pattern", "source": MIGRATIONS_DIR,
                 "reason": (f"'{UNION_SEARCH_FN}' has {union_count} UNION ALL but only "
                            f"{len(sub_limits)} subquery LIMIT(s) — LIMIT must be inside each "
                            f"subquery before the UNION, not only on the outer query")}]
    return []


def check_hive_id_scoping(migrations, tables):
    """
    search_all_knowledge must filter by hive_id so each tenant's AI assistant
    only searches their own knowledge base. Without hive_id scoping, Worker A's
    logbook faults appear as context in Worker B's AI responses — cross-tenant
    data leakage through the semantic search pipeline.
    """
    if not migrations:
        return []
    fn_m = re.search(
        rf"CREATE OR REPLACE FUNCTION\s+{re.escape(UNION_SEARCH_FN)}[\s\S]+?(?=CREATE OR REPLACE FUNCTION|\$\$;)",
        migrations, re.IGNORECASE
    )
    if not fn_m:
        return []
    fn_body = fn_m.group(0)
    issues  = []
    for table in tables:
        # Find the subquery that references this table
        table_block = re.search(
            rf"FROM\s+{re.escape(table)}[\s\S]*?(?=UNION ALL|\Z)",
            fn_body, re.IGNORECASE
        )
        if not table_block:
            continue
        block = table_block.group(0)
        if "hive_id" not in block and "match_hive_id" not in block:
            issues.append({"check": "hive_id_scoping", "table": table,
                           "reason": (f"search_all_knowledge subquery for '{table}' has no "
                                      f"hive_id filter — semantic search crosses tenant boundaries, "
                                      f"exposing other hives' knowledge to this worker's AI assistant")})
    return issues


# ── Layer 4: Result quality ───────────────────────────────────────────────────

def check_similarity_threshold(migrations, semantic_search_path):
    """
    The search_all_knowledge function and the semantic-search edge function must
    filter results by a minimum similarity score (e.g. similarity > 0.5).
    Without a threshold, the AI receives results from completely unrelated records
    whenever the knowledge base is small or the query is on an unfamiliar topic.
    A worker asking 'what's our most common pump failure?' gets an answer from
    their only logbook entry — a compressor fault with 0.2 similarity — presented
    as if it were relevant context. The fix: add WHERE similarity > 0.5 to the
    outer query, or filter in the edge function before injecting into the prompt.
    Reported as WARN — functional but degrades AI answer quality on sparse data.
    """
    issues = []
    # Check SQL function
    if migrations:
        fn_m = re.search(
            rf"CREATE OR REPLACE FUNCTION\s+{re.escape(UNION_SEARCH_FN)}[\s\S]+?(?=CREATE OR REPLACE FUNCTION|\$\$;)",
            migrations, re.IGNORECASE
        )
        if fn_m:
            fn_body = fn_m.group(0)
            has_threshold = bool(re.search(
                r"similarity\s*[><=]+\s*0\.\d+|match_threshold|min_similarity|\bWHERE\b.*similarity",
                fn_body, re.IGNORECASE
            ))
            if not has_threshold:
                issues.append({"check": "similarity_threshold", "source": "migrations",
                               "skip": True,
                               "reason": (f"'{UNION_SEARCH_FN}' has no similarity threshold filter — "
                                          f"low-relevance results (similarity < {MIN_SIMILARITY}) are "
                                          f"injected into the AI prompt when the knowledge base is sparse; "
                                          f"add WHERE similarity > {MIN_SIMILARITY} to the outer query")})

    # Check edge function
    ef_content = read_file(semantic_search_path)
    if ef_content:
        has_threshold = bool(re.search(
            r"similarity\s*[><=]+\s*0\.\d+|match_threshold|min_similarity|filter.*similarity",
            ef_content, re.IGNORECASE
        ))
        if not has_threshold and issues:
            # Both SQL and edge function lack thresholds — strengthen the WARN message
            issues[-1]["reason"] += (f"; the semantic-search edge function also has no "
                                     f"threshold filter before injecting results into the prompt")
    return issues


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "vector_extension",
    "vector_dimension",
    "ivfflat_indexes",
    "union_all_pattern",
    "hive_id_scoping",
    "similarity_threshold",
]

CHECK_LABELS = {
    "vector_extension":    "L1  pgvector extension enabled in migrations",
    "vector_dimension":    "L2  All knowledge tables declare embedding vector(384)",
    "ivfflat_indexes":     "L2  IVFFlat indexes on all embedding columns",
    "union_all_pattern":   "L3  search_all_knowledge UNION ALL subqueries each have LIMIT",
    "hive_id_scoping":     "L3  search_all_knowledge filters by hive_id (tenant isolation)",
    "similarity_threshold":"L4  Similarity threshold filters low-relevance results  [WARN]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nVector Knowledge Base Schema Validator (4-layer)"))
    print("=" * 55)

    migrations = read_all_migrations()
    print(f"  {len(KNOWLEDGE_TABLES)} knowledge tables: {', '.join(KNOWLEDGE_TABLES)}")
    print(f"  Embedding model: {EMBEDDING_MODEL} ({EMBEDDING_DIM} dims)\n")

    all_issues = []
    all_issues += check_vector_extension(migrations)
    all_issues += check_vector_dimension(migrations, KNOWLEDGE_TABLES, EMBEDDING_DIM)
    all_issues += check_ivfflat_indexes(migrations, KNOWLEDGE_TABLES)
    all_issues += check_union_all_pattern(migrations)
    all_issues += check_hive_id_scoping(migrations, KNOWLEDGE_TABLES)
    all_issues += check_similarity_threshold(migrations, SEMANTIC_SEARCH)

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "vector_schema",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("vector_schema_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
