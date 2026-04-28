"""
Data Governance Validator — WorkHive Platform
==============================================
WorkHive's three knowledge tables (fault_knowledge, skill_knowledge,
pm_knowledge) are the memory of the AI assistant. Without proper governance:
- Unknown workers can inject fake fault histories (no ownership)
- Semantic search returns unfiltered noise (no metadata)
- Any client with the anon key can write to knowledge tables (weak governance)
- If the embedding model changes, old rows become silently incompatible (no versioning)

  Layer 1 — Data ownership                                  [Problem 07]
    1.  All knowledge tables have worker_name attribution — pm_knowledge
        currently lacks worker_name: PM health snapshots cannot be attributed
        to the worker who triggered the update.

  Layer 2 — Metadata for semantic filtering                 [Problem 10]
    2.  fault_knowledge must include maintenance_type — without it, RAG
        cannot answer "show Breakdown failures only" or distinguish between
        corrective and preventive entries in the knowledge base.

  Layer 3 — Write path integrity                            [Problem 15]
    3.  Knowledge tables must NOT be written directly by client-side HTML/JS.
        Only the embed-entry edge function (server-side, HMAC-signed) should
        insert knowledge rows. Direct client writes bypass validation.

  Layer 4 — Access control on knowledge tables              [Problem 15]
    4.  Knowledge tables must have RLS policies or at least explicit SELECT
        policies. Without them, any client with the anon Supabase key can
        read another hive's fault history or inject malicious knowledge.

  Layer 5 — Embedding model version tracking                [Problem 19]
    5.  Knowledge tables have no embedding_model_version column. If the
        embedding model changes from nomic-embed-text-v1.5 to a different
        model, old rows become silently incompatible — cosine similarity
        between old and new embeddings is meaningless but returns no error.

  Layer 6 — Knowledge write consistency via embed-entry     [Problem 15, 07]
    6.  embed-entry must pass worker attribution fields for all 3 knowledge
        types. The pm type currently derives worker context from asset data
        but does not pass the worker_name who triggered the embed call.

Usage:  python validate_data_governance.py
Output: data_governance_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

MIGRATIONS_DIR    = os.path.join("supabase", "migrations")
EMBED_ENTRY       = os.path.join("supabase", "functions", "embed-entry", "index.ts")
KNOWLEDGE_TABLES  = ["fault_knowledge", "skill_knowledge", "pm_knowledge"]

CLIENT_PAGES = [
    "logbook.html", "inventory.html", "pm-scheduler.html", "hive.html",
    "assistant.html", "skillmatrix.html", "dayplanner.html",
    "engineering-design.html", "analytics.html", "nav-hub.html",
    "platform-health.html",
]


def read_all_migrations():
    combined = ""
    if not os.path.isdir(MIGRATIONS_DIR):
        return combined
    for fname in sorted(os.listdir(MIGRATIONS_DIR)):
        if fname.endswith(".sql"):
            c = read_file(os.path.join(MIGRATIONS_DIR, fname))
            if c:
                combined += f"\n-- FILE: {fname}\n" + c
    return combined


def get_table_definition(migrations, table_name):
    """Extract CREATE TABLE block for the given table name."""
    m = re.search(
        rf"CREATE TABLE.*?\b{re.escape(table_name)}\b([\s\S]+?)(?=CREATE TABLE|CREATE INDEX|CREATE OR REPLACE|\Z)",
        migrations, re.IGNORECASE
    )
    return m.group(1) if m else None


# ── Layer 1: Data ownership ───────────────────────────────────────────────────

def check_worker_attribution(migrations):
    """
    Every knowledge table must have a worker_name column so that:
    1. AI responses can be attributed ("based on entries from Worker A")
    2. Data quality issues can be traced to their source
    3. Hive supervisors can audit whose knowledge is in the base

    fault_knowledge: has worker_name ✓
    skill_knowledge: has worker_name ✓
    pm_knowledge:    MISSING worker_name — PM health snapshots cannot be
                     attributed. When the AI says "Asset X is overdue", there
                     is no record of which worker's view triggered the snapshot.
    """
    issues = []
    for table in KNOWLEDGE_TABLES:
        body = get_table_definition(migrations, table)
        if body is None:
            issues.append({"check": "worker_attribution", "table": table,
                           "reason": f"Table '{table}' definition not found in migrations"})
            continue
        # Also check ALTER TABLE ADD COLUMN (column may have been added in a later migration)
        has_via_create = "worker_name" in body
        has_via_alter  = bool(re.search(
            rf"ALTER TABLE\s+{re.escape(table)}\s*ADD COLUMN.*worker_name",
            migrations, re.IGNORECASE
        ))
        if not has_via_create and not has_via_alter:
            issues.append({"check": "worker_attribution", "table": table,
                           "reason": (f"Table '{table}' has no worker_name column — "
                                      f"knowledge rows cannot be attributed to the worker who created them; "
                                      f"add: worker_name text to the CREATE TABLE definition and pass it "
                                      f"through the embed-entry function for all 3 knowledge types")})
    return issues


# ── Layer 2: Metadata for semantic filtering ──────────────────────────────────

def check_fault_knowledge_maintenance_type(migrations):
    """
    fault_knowledge stores machine, category, problem, root_cause, action —
    but NOT maintenance_type. Without it, semantic search cannot answer:
      - "Show me only Breakdown failures" (vs Preventive, Inspection)
      - "How many corrective entries mention Pump failures?"
      - Filter RAG results to only the relevant work type

    The search_all_knowledge function currently returns ALL fault entries
    regardless of maintenance_type. A Preventive Maintenance entry about
    "checked oil levels" may rank higher than an actual Breakdown entry
    about "pump seized" for some queries.

    Fix: add maintenance_type to fault_knowledge and filter in embed-entry.
    """
    body = get_table_definition(migrations, "fault_knowledge")
    if body is None:
        return []
    has_via_alter = bool(re.search(
        r"ALTER TABLE\s+fault_knowledge\s*ADD COLUMN.*maintenance_type",
        migrations, re.IGNORECASE
    ))
    if "maintenance_type" not in body and not has_via_alter:
        return [{"check": "fault_knowledge_maintenance_type",
                 "table": "fault_knowledge",
                 "skip": True,
                 "reason": ("fault_knowledge table has no maintenance_type column — "
                            "semantic search cannot filter by work type; Preventive entries "
                            "pollute the Breakdown failure knowledge base; "
                            "add: maintenance_type text to the schema and pass it from embed-entry")}]
    return []


# ── Layer 3: Write path integrity ─────────────────────────────────────────────

def check_no_direct_client_writes(client_pages, knowledge_tables):
    """
    Knowledge tables must only be written by the embed-entry edge function
    (server-side, authenticated with the service role key). If any client-side
    HTML/JS file directly inserts into knowledge tables, a malicious worker
    could inject fake fault histories or false skill levels — the AI would
    then answer from poisoned data.

    The correct write path:
      Worker action → page JS calls embed-entry via fetch()
      → embed-entry generates embedding + inserts with SERVICE_ROLE_KEY
      → knowledge table row created with validation

    Any direct .from('fault_knowledge').insert() in a client page bypasses
    the embedding generation, hive_id validation, and content quality checks
    in the edge function.
    """
    issues = []
    for page in client_pages:
        content = read_file(page)
        if content is None:
            continue
        for table in knowledge_tables:
            if re.search(
                rf"from\(['\"]({re.escape(table)})['\"].*\.(?:insert|upsert|update|delete)\(",
                content, re.IGNORECASE
            ):
                issues.append({"check": "no_direct_client_writes", "page": page,
                               "table": table,
                               "reason": (f"{page} writes directly to '{table}' — "
                                          f"knowledge tables must only be written by the embed-entry "
                                          f"edge function to ensure valid embeddings and hive scoping; "
                                          f"remove this direct DB write and route through embed-entry")})
    return issues


# ── Layer 4: Access control on knowledge tables ───────────────────────────────

def check_knowledge_table_policies(migrations):
    """
    Knowledge tables should have explicit Row Level Security policies.
    Without RLS:
    - Any browser client with the Supabase anon key can SELECT all rows
      from all hives (reads another hive's fault history)
    - Any browser client can INSERT rows directly, bypassing the embedding
      pipeline entirely (inject fake knowledge)

    Note: WorkHive's RLS is currently deferred pending Supabase Auth migration.
    This check verifies that at minimum, an explicit CREATE POLICY or
    ENABLE ROW LEVEL SECURITY exists for each knowledge table in migrations.
    Reported as WARN — the Auth migration must come first before RLS is safe.
    """
    issues = []
    for table in KNOWLEDGE_TABLES:
        has_rls = bool(re.search(
            rf"ENABLE ROW LEVEL SECURITY.*{re.escape(table)}"
            rf"|ALTER TABLE.*{re.escape(table)}.*ENABLE ROW LEVEL SECURITY"
            rf"|CREATE POLICY.*ON\s+{re.escape(table)}",
            migrations, re.IGNORECASE
        ))
        if not has_rls:
            issues.append({"check": "knowledge_table_policies", "table": table,
                           "skip": True,
                           "reason": (f"Table '{table}' has no RLS policies in migrations — "
                                      f"any browser client with the anon key can read all hives' "
                                      f"knowledge base or inject fake entries; "
                                      f"add ENABLE ROW LEVEL SECURITY + SELECT policy scoped to hive_id "
                                      f"once Supabase Auth migration is complete")})
    return issues


# ── Layer 5: Embedding model version tracking ─────────────────────────────────

def check_embedding_model_version(migrations, embed_path):
    """
    The embedding model name (nomic-embed-text-v1.5) is only in code comments
    and hardcoded in the embed-entry function. None of the knowledge tables
    have an embedding_model or model_version column.

    Why this matters (Problem 19 — No Version Control):
    If the embedding model is ever changed (Groq deprecates nomic, a better
    free-tier model becomes available), all existing rows become silently
    incompatible. Cosine similarity between nomic and a different model's
    embeddings produces meaningless scores — queries return the wrong rows
    with confident similarity scores. There is no way to identify which
    rows used the old model and need re-embedding.

    Fix: add embedding_model text DEFAULT 'nomic-embed-text-v1_5' to all
    knowledge tables, and set it explicitly in embed-entry when inserting.
    Then a migration that changes models can identify and re-embed old rows:
      UPDATE fault_knowledge SET embedding = new_embedding
      WHERE embedding_model != 'new-model-name'
    """
    # Check if any knowledge table has an embedding_model column
    has_version = bool(re.search(
        r"embedding_model\b|model_version\b|embed_model\b"
        r"|ADD COLUMN.*embedding_model",
        migrations, re.IGNORECASE
    ))

    # Also check embed-entry for model version being stored
    embed_content = read_file(embed_path) or ""
    has_version_in_insert = bool(re.search(
        r"embedding_model\s*:|model_version\s*:|model_name\s*:",
        embed_content
    ))

    if not has_version and not has_version_in_insert:
        return [{"check": "embedding_model_version", "source": embed_path,
                 "skip": True,
                 "reason": ("Knowledge tables have no embedding_model column — if the embedding "
                            "model changes, old rows produce wrong similarity scores with no way to "
                            "identify which rows need re-embedding; "
                            "add: embedding_model text DEFAULT 'nomic-embed-text-v1_5' to all 3 "
                            "knowledge tables and set it explicitly in embed-entry on insert")}]
    return []


# ── Layer 6: Worker attribution passed through embed-entry ───────────────────

def check_embed_entry_worker_attribution(embed_path):
    """
    The embed-entry function must pass worker attribution for all 3 knowledge
    types so that knowledge rows always know who generated them.

    Current state:
    - fault: worker_name comes from logbook record.worker_name ✓
    - skill: worker_name comes from skill_badges record.worker_name ✓
    - pm:    worker_name is NOT passed — the PM entry derives context from
             the pm_asset (asset_name, category) but never stores who
             called the embed. When a supervisor views PM health and the
             snapshot is created, no worker_name is recorded.

    This is the root cause of the missing worker_name in pm_knowledge:
    the column exists in fault/skill but not in pm because it was never
    wired through the function.
    """
    content = read_file(embed_path)
    if content is None:
        return [{"check": "embed_worker_attribution", "source": embed_path,
                 "reason": f"{embed_path} not found"}]

    # Find the pm knowledge insert block
    pm_insert_m = re.search(
        r"pm_knowledge[\s\S]{0,500}?\.insert\s*\(\s*\{",
        content
    )
    if not pm_insert_m:
        return []

    pm_insert_block = content[pm_insert_m.start():pm_insert_m.start() + 600]
    if "worker_name" not in pm_insert_block:
        return [{"check": "embed_worker_attribution", "source": embed_path,
                 "skip": True,
                 "reason": (f"{embed_path} pm_knowledge insert does not include worker_name — "
                            f"PM knowledge snapshots cannot be attributed to the worker who triggered them; "
                            f"extract worker_name from the request body or the pm_completions record "
                            f"and pass it through to the pm_knowledge insert")}]
    return []


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "worker_attribution",
    "fault_knowledge_maintenance_type",
    "no_direct_client_writes",
    "knowledge_table_policies",
    "embedding_model_version",
    "embed_worker_attribution",
]

CHECK_LABELS = {
    "worker_attribution":               "L1  All knowledge tables have worker_name attribution",
    "fault_knowledge_maintenance_type": "L2  fault_knowledge includes maintenance_type for filtering  [WARN]",
    "no_direct_client_writes":          "L3  No client-side HTML/JS writes directly to knowledge tables",
    "knowledge_table_policies":         "L4  Knowledge tables have RLS policies  [WARN]",
    "embedding_model_version":          "L5  Embedding model version tracked per knowledge row  [WARN]",
    "embed_worker_attribution":         "L6  embed-entry passes worker_name for all 3 knowledge types  [WARN]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nData Governance Validator (6-layer)"))
    print("=" * 55)
    print("  Addresses: no data ownership, lack of metadata,")
    print("  weak governance, no version control\n")

    migrations = read_all_migrations()

    all_issues = []
    all_issues += check_worker_attribution(migrations)
    all_issues += check_fault_knowledge_maintenance_type(migrations)
    all_issues += check_no_direct_client_writes(CLIENT_PAGES, KNOWLEDGE_TABLES)
    all_issues += check_knowledge_table_policies(migrations)
    all_issues += check_embedding_model_version(migrations, EMBED_ENTRY)
    all_issues += check_embed_entry_worker_attribution(EMBED_ENTRY)

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "data_governance",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("data_governance_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
