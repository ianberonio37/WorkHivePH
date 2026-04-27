"""
Vector Knowledge Base Schema Validator — WorkHive Platform
==========================================================
WorkHive's Classic RAG pipeline (and future Graph/Agentic RAG) is built
on pgvector + nomic-embed-text-v1.5 (384 dimensions). Three knowledge
tables store embeddings: fault_knowledge, skill_knowledge, pm_knowledge.

If ANY of the structural rules below break, the semantic search pipeline
fails SILENTLY — the AI assistant returns generic answers instead of
contextual ones, and no error appears in the Guardian.

From the AI Engineer skill, RAG architecture images, and the
Predictive Analytics + Knowledge Manager skills.

Four things checked:

  1. pgvector extension enabled
     — CREATE EXTENSION IF NOT EXISTS vector must appear in a migration.
       Without it, the vector type doesn't exist and all knowledge tables
       fail to create. This is the foundation the entire RAG pipeline
       depends on.

  2. All knowledge tables declare vector(384)
     — fault_knowledge, skill_knowledge, pm_knowledge must each have
       an 'embedding vector(384)' column. The 384 dimension matches
       nomic-embed-text-v1.5 (the Groq free-tier embedding model).
       A mismatch — even 383 or 512 — causes every insert to fail with
       a silent dimension error.

  3. IVFFlat indexes on all embedding columns
     — Every embedding column must have an IVFFlat index using
       vector_cosine_ops. Without it, similarity search runs a full
       table scan — fine at 100 rows, takes minutes at 100,000 rows.
       The AI Engineer skill specifies IVFFlat (not HNSW) for this
       platform's access pattern.

  4. UNION ALL subqueries each have ORDER BY + LIMIT
     — The search_all_knowledge SQL function uses UNION ALL to merge
       results from all 3 tables. Each subquery MUST have its own
       ORDER BY + LIMIT BEFORE the UNION. If LIMIT is only on the
       outer query, Postgres processes ALL rows from all tables,
       then limits — defeating the purpose entirely.
       This is the UNION ALL bug the AI Engineer skill explicitly
       calls out as a known gotcha.

Usage:  python validate_vector_schema.py
Output: vector_schema_report.json
"""
import re, json, sys, os

MIGRATIONS_DIR   = os.path.join("supabase", "migrations")
FUNCTIONS_DIR    = os.path.join("supabase", "functions")
SEMANTIC_SEARCH  = os.path.join(FUNCTIONS_DIR, "semantic-search", "index.ts")

# The exact embedding model and its dimension
EMBEDDING_MODEL  = "nomic-embed-text-v1_5"
EMBEDDING_DIM    = 384

# Knowledge tables that must have vector columns and indexes
KNOWLEDGE_TABLES = ["fault_knowledge", "skill_knowledge", "pm_knowledge"]

# The unified search SQL function that uses UNION ALL
UNION_SEARCH_FN  = "search_all_knowledge"


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def read_all_migrations():
    """Return combined content of all migration SQL files."""
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


# ── Check 1: pgvector extension enabled ──────────────────────────────────────

def check_vector_extension(migrations):
    """
    CREATE EXTENSION IF NOT EXISTS vector must exist in a migration.
    This is the foundation — without it, the vector column type is
    not registered in PostgreSQL and every knowledge table fails to create.
    """
    issues = []
    if not migrations:
        return [{"source": MIGRATIONS_DIR, "reason": f"{MIGRATIONS_DIR} not found"}]

    if not re.search(r"CREATE\s+EXTENSION.*\bvector\b", migrations, re.IGNORECASE):
        issues.append({
            "source": MIGRATIONS_DIR,
            "reason": (
                "No 'CREATE EXTENSION IF NOT EXISTS vector' found in any "
                "migration file — the pgvector extension is not enabled, "
                "all knowledge tables and embedding columns will fail to create"
            ),
        })
    return issues


# ── Check 2: All knowledge tables have vector(384) ────────────────────────────

def check_vector_dimension(migrations, tables, dim):
    """
    Each knowledge table must declare 'embedding vector(DIM)' where DIM
    matches the embedding model dimension exactly.

    nomic-embed-text-v1.5 produces 384-dimensional vectors.
    A mismatch causes every INSERT to fail with a dimension error.
    The AI Assistant keeps working but returns no contextual knowledge.
    """
    issues = []
    if not migrations:
        return []

    for table in tables:
        # Find the CREATE TABLE block for this table
        table_m = re.search(
            rf"CREATE TABLE.*?\b{re.escape(table)}\b([\s\S]+?)(?=CREATE TABLE|CREATE INDEX|CREATE OR REPLACE|$)",
            migrations, re.IGNORECASE
        )
        if not table_m:
            issues.append({
                "table":  table,
                "reason": (
                    f"Table '{table}' not found in migration files — "
                    f"the knowledge table is missing, semantic search will "
                    f"return no results for this knowledge type"
                ),
            })
            continue

        table_body = table_m.group(1)
        # Check for embedding vector(DIM) declaration
        vec_m = re.search(
            r"\bembedding\s+vector\s*\(\s*(\d+)\s*\)",
            table_body
        )
        if not vec_m:
            issues.append({
                "table":  table,
                "reason": (
                    f"Table '{table}' has no 'embedding vector({dim})' column — "
                    f"embeddings cannot be stored for this knowledge type"
                ),
            })
        else:
            found_dim = int(vec_m.group(1))
            if found_dim != dim:
                issues.append({
                    "table":      table,
                    "found_dim":  found_dim,
                    "expected":   dim,
                    "reason": (
                        f"Table '{table}' uses vector({found_dim}) but model "
                        f"'{EMBEDDING_MODEL}' produces {dim}-dimensional vectors — "
                        f"dimension mismatch causes every embedding INSERT to fail"
                    ),
                })
    return issues


# ── Check 3: IVFFlat indexes on all embedding columns ────────────────────────

def check_ivfflat_indexes(migrations, tables):
    """
    Every embedding column must have an IVFFlat index with vector_cosine_ops.
    IVFFlat is the recommended index type for approximate nearest neighbor
    search on this platform's access pattern (medium dataset, high read).

    Without this index:
    - 100 rows: 2ms query (fine)
    - 10,000 rows: 200ms (slow)
    - 100,000 rows: 2+ seconds (unusable)
    The AI assistant would silently fall back to a full table scan.
    """
    issues = []
    if not migrations:
        return []

    for table in tables:
        # Find the IVFFlat index for this table
        ivfflat_m = re.search(
            rf"CREATE INDEX[\s\S]*?ON\s+{re.escape(table)}\s+USING\s+ivfflat\s*\([\s\S]*?vector_cosine_ops[\s\S]*?\)",
            migrations, re.IGNORECASE
        )
        if not ivfflat_m:
            issues.append({
                "table":  table,
                "reason": (
                    f"Table '{table}' has no IVFFlat index on the embedding column "
                    f"(USING ivfflat (embedding vector_cosine_ops)) — "
                    f"similarity search will full-scan the table, "
                    f"becoming unusably slow above 10,000 rows"
                ),
            })
    return issues


# ── Check 4: UNION ALL subqueries each have ORDER BY + LIMIT ─────────────────

def check_union_all_pattern(migrations):
    """
    The search_all_knowledge SQL function uses UNION ALL across 3 tables.
    Each subquery MUST have its own ORDER BY + LIMIT.

    Correct pattern (AI Engineer skill rule):
      SELECT ... FROM fault_knowledge
      WHERE ... ORDER BY embedding <=> query_embedding LIMIT N
      UNION ALL
      SELECT ... FROM skill_knowledge
      WHERE ... ORDER BY embedding <=> query_embedding LIMIT N

    Wrong pattern (common mistake):
      SELECT ... FROM fault_knowledge WHERE ...
      UNION ALL
      SELECT ... FROM skill_knowledge WHERE ...
      ORDER BY ... LIMIT N   ← applies AFTER the union (processes all rows)

    The wrong pattern makes Postgres retrieve ALL rows from all 3 tables,
    compute all similarities, then limit — defeating vector index use entirely
    and causing full table scans even with IVFFlat indexes.
    """
    issues = []
    if not migrations:
        return []

    # Find the search_all_knowledge function body
    fn_m = re.search(
        rf"CREATE OR REPLACE FUNCTION\s+{re.escape(UNION_SEARCH_FN)}[\s\S]+?(?=CREATE OR REPLACE FUNCTION|$$;)",
        migrations, re.IGNORECASE
    )
    if not fn_m:
        issues.append({
            "source": MIGRATIONS_DIR,
            "reason": (
                f"Function '{UNION_SEARCH_FN}' not found in migration files — "
                f"the unified cross-reference search is missing"
            ),
        })
        return issues

    fn_body = fn_m.group(0)

    # Each UNION ALL branch should have ORDER BY ... LIMIT inside a subquery
    # Count how many LIMIT clauses appear BEFORE UNION ALL
    subquery_blocks = re.findall(
        r"SELECT[\s\S]+?LIMIT\s+\w+[\s\S]*?(?=UNION ALL|\Z)",
        fn_body, re.IGNORECASE
    )

    # Count UNION ALL occurrences
    union_count = len(re.findall(r"UNION\s+ALL", fn_body, re.IGNORECASE))

    # There should be at least union_count + 1 subqueries with LIMIT
    if len(subquery_blocks) < union_count + 1:
        issues.append({
            "source":       MIGRATIONS_DIR,
            "union_count":  union_count,
            "limit_count":  len(subquery_blocks),
            "reason": (
                f"Function '{UNION_SEARCH_FN}' has {union_count} UNION ALL "
                f"but only {len(subquery_blocks)} subquery LIMIT clause(s) — "
                f"LIMIT must appear inside each subquery before the UNION, "
                f"not only on the outer query (AI Engineer skill: "
                f"'UNION ALL ORDER BY/LIMIT in subqueries')"
            ),
        })
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("\n" + "=" * 70)
print("Vector Knowledge Base Schema Validator")
print("=" * 70)

migrations = read_all_migrations()
print(f"\n  Checking {len(KNOWLEDGE_TABLES)} knowledge tables: "
      f"{', '.join(KNOWLEDGE_TABLES)}")
print(f"  Expected embedding model: {EMBEDDING_MODEL} ({EMBEDDING_DIM} dims)\n")

fail_count = 0
warn_count = 0
report     = {}

checks = [
    (
        "[1] pgvector extension enabled in migrations",
        check_vector_extension(migrations),
        "FAIL",
    ),
    (
        f"[2] All knowledge tables declare embedding vector({EMBEDDING_DIM})",
        check_vector_dimension(migrations, KNOWLEDGE_TABLES, EMBEDDING_DIM),
        "FAIL",
    ),
    (
        "[3] IVFFlat indexes on all knowledge table embedding columns",
        check_ivfflat_indexes(migrations, KNOWLEDGE_TABLES),
        "FAIL",
    ),
    (
        f"[4] {UNION_SEARCH_FN}() UNION ALL subqueries each have ORDER BY + LIMIT",
        check_union_all_pattern(migrations),
        "FAIL",
    ),
]

for label, issues, severity in checks:
    print(f"\n{label}\n")
    if not issues:
        print("  PASS")
    else:
        for iss in issues:
            print(f"  {severity}  {iss.get('table', iss.get('source', '?'))}")
            print(f"        {iss['reason']}")
        if severity == "FAIL":
            fail_count += len(issues)
        else:
            warn_count += len(issues)
    report[label] = issues

print(f"\n{'=' * 70}")
print(f"Result: {fail_count} FAIL  {warn_count} WARN")

with open("vector_schema_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved vector_schema_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll vector schema checks PASS.")
