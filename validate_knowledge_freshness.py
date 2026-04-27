"""
Knowledge Base Freshness Validator — WorkHive Platform
=======================================================
WorkHive's AI assistant answers from a live knowledge base: fault history
from logbook saves, skill profiles from exam results, PM health from
completions. Every save triggers an embed-entry function call that creates
a vector embedding and stores it in the knowledge tables.

If ANY link in this pipeline breaks, the knowledge base goes stale
SILENTLY — the AI assistant keeps responding but answers from outdated
data. Workers ask "what's our most common pump failure?" and the AI
answers from data that's weeks old with no indication it's stale.

From the Graph/Agentic RAG images, Knowledge Engineer role (Gartner),
and Knowledge Manager skill file.

Four things checked:

  1. embed-entry handles all 3 knowledge types
     — The function must accept and process: 'fault' (logbook entries),
       'skill' (skill badge/level updates), 'pm' (PM completions).
       A missing type handler means that knowledge source never gets
       embedded — the AI has no memory of that data category.

  2. All 3 embed functions defined in respective pages
     — embedFaultEntry in logbook.html, embedPMEntry in pm-scheduler.html,
       embedSkillEntry in skillmatrix.html. If any embed function is
       removed during a refactor, that knowledge source stops updating.
       This is the most common way the RAG pipeline breaks silently.

  3. Each embed call passes the correct type parameter
     — logbook.html must pass type:'fault', pm-scheduler.html type:'pm',
       skillmatrix.html type:'skill'. A wrong type routes the data to
       the wrong knowledge table — fault data goes into skill_knowledge,
       skill data is silently dropped, etc.

  4. Search SQL functions filter embedding IS NOT NULL
     — The Postgres similarity search functions must filter out rows
       where embedding IS NULL before computing cosine distance. Without
       this filter, rows with null embeddings (failed or pending embeds)
       cause the vector comparison to throw a runtime error, crashing
       the search entirely for that query.

Usage:  python validate_knowledge_freshness.py
Output: knowledge_freshness_report.json
"""
import re, json, sys, os

MIGRATIONS_DIR = os.path.join("supabase", "migrations")
EMBED_FUNCTION = os.path.join("supabase", "functions", "embed-entry", "index.ts")

# Knowledge types the embed-entry function must handle
KNOWLEDGE_TYPES = {
    "fault": "logbook.html",
    "skill": "skillmatrix.html",
    "pm":    "pm-scheduler.html",
}

# Embed function names expected in each page
EMBED_FUNCTIONS = {
    "logbook.html":     "embedFaultEntry",
    "skillmatrix.html": "embedSkillEntry",
    "pm-scheduler.html":"embedPMEntry",
}

# SQL functions that must have IS NOT NULL guard
SEARCH_FUNCTIONS = [
    "search_fault_knowledge",
    "search_skill_knowledge",
    "search_pm_knowledge",
]


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def read_all_migrations():
    combined = ""
    if not os.path.isdir(MIGRATIONS_DIR):
        return combined
    for fname in sorted(os.listdir(MIGRATIONS_DIR)):
        if not fname.endswith(".sql"):
            continue
        c = read_file(os.path.join(MIGRATIONS_DIR, fname))
        if c:
            combined += c
    return combined


# ── Check 1: embed-entry handles all 3 knowledge types ───────────────────────

def check_embed_type_handlers(func_path, types):
    """
    The embed-entry function must handle all 3 knowledge types.
    A missing handler silently drops that data category — the embedding
    is never created, the knowledge table never grows, and the AI
    has no memory of events from that source.

    Required handlers:
    - type === 'fault'  → writes to fault_knowledge
    - type === 'skill'  → writes to skill_knowledge
    - type === 'pm'     → writes to pm_knowledge
    """
    issues = []
    content = read_file(func_path)
    if content is None:
        return [{
            "source": func_path,
            "reason": f"{func_path} not found — embed-entry function is missing entirely",
        }]

    for knowledge_type, source_page in types.items():
        if not re.search(
            rf"['\"]({re.escape(knowledge_type)})['\"]",
            content
        ):
            issues.append({
                "type":   knowledge_type,
                "source": func_path,
                "reason": (
                    f"{func_path} has no handler for type='{knowledge_type}' — "
                    f"data from {source_page} will never be embedded into the "
                    f"knowledge base, making the AI blind to that data source"
                ),
            })
    return issues


# ── Check 2: All 3 embed functions present in respective pages ────────────────

def check_embed_functions_present(embed_map):
    """
    Each page that generates knowledge must define its embed function.
    If the function is removed during a refactor (e.g., someone cleans
    up 'unused' functions), that knowledge source silently stops updating.

    Required:
    - logbook.html:     async function embedFaultEntry(entry)
    - skillmatrix.html: async function embedSkillEntry(entry)
    - pm-scheduler.html:async function embedPMEntry(entry)
    """
    issues = []
    for page, func_name in embed_map.items():
        content = read_file(page)
        if content is None:
            issues.append({
                "page": page,
                "func": func_name,
                "reason": f"{page} not found — cannot verify embed function",
            })
            continue

        if not re.search(
            rf"(?:async\s+)?function\s+{re.escape(func_name)}\s*\(",
            content
        ):
            issues.append({
                "page": page,
                "func": func_name,
                "reason": (
                    f"{page} does not define {func_name}() — "
                    f"this knowledge source will never be embedded; "
                    f"the AI will have no memory of this data type"
                ),
            })
    return issues


# ── Check 3: Embed calls pass correct type parameter ─────────────────────────

def check_embed_type_params(type_to_page):
    """
    Each embed call must pass the correct type string to embed-entry.
    A wrong type routes data to the wrong knowledge table:
    - type:'fault' sent from skill update → skill data in fault_knowledge
    - type:'skill' sent from logbook → fault data silently dropped

    Correct mapping:
    - logbook.html     → type: 'fault'
    - pm-scheduler.html → type: 'pm'
    - skillmatrix.html  → type: 'skill'
    """
    issues = []
    for knowledge_type, page in type_to_page.items():
        content = read_file(page)
        if content is None:
            continue

        # Find the embed-entry fetch call in this page
        embed_call_m = re.search(
            r"embed-entry[\s\S]{0,500}?type\s*:\s*['\"](\w+)['\"]",
            content
        )
        if not embed_call_m:
            issues.append({
                "page":            page,
                "expected_type":   knowledge_type,
                "reason": (
                    f"{page} calls embed-entry but no type parameter found — "
                    f"embed-entry cannot route the data to the correct knowledge table"
                ),
            })
            continue

        found_type = embed_call_m.group(1)
        if found_type != knowledge_type:
            issues.append({
                "page":          page,
                "found_type":    found_type,
                "expected_type": knowledge_type,
                "reason": (
                    f"{page} passes type='{found_type}' to embed-entry but "
                    f"should pass type='{knowledge_type}' — data will be routed "
                    f"to the wrong knowledge table"
                ),
            })
    return issues


# ── Check 4: Search SQL functions filter embedding IS NOT NULL ────────────────

def check_null_embedding_guard(migrations, search_funcs):
    """
    Each SQL similarity search function must include 'embedding IS NOT NULL'
    in its WHERE clause. Without this:
    - Rows inserted before embeddings were generated have null embeddings
    - The vector cosine distance operator (<=>) throws a runtime error
      on null inputs, crashing the search for that query
    - Workers ask questions and get no results instead of partial results

    The guard also ensures the IVFFlat index is used efficiently —
    the index skips null rows automatically.
    """
    issues = []
    if not migrations:
        return [{"source": MIGRATIONS_DIR, "reason": f"{MIGRATIONS_DIR} not found"}]

    for func_name in search_funcs:
        # Find the function body
        fn_m = re.search(
            rf"FUNCTION\s+{re.escape(func_name)}\s*\([\s\S]+?(?=CREATE OR REPLACE FUNCTION|\Z)",
            migrations, re.IGNORECASE
        )
        if not fn_m:
            issues.append({
                "func":   func_name,
                "reason": f"SQL function '{func_name}' not found in migration files",
            })
            continue

        fn_body = fn_m.group(0)
        has_null_guard = bool(re.search(
            r"embedding\s+IS\s+NOT\s+NULL",
            fn_body, re.IGNORECASE
        ))
        if not has_null_guard:
            issues.append({
                "func":   func_name,
                "reason": (
                    f"SQL function '{func_name}' has no 'embedding IS NOT NULL' "
                    f"filter — null embeddings cause a runtime error on the vector "
                    f"cosine distance operator, crashing similarity search for that query"
                ),
            })
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("\n" + "=" * 70)
print("Knowledge Base Freshness Validator")
print("=" * 70)

migrations = read_all_migrations()
print(f"\n  Knowledge types: {', '.join(KNOWLEDGE_TYPES.keys())}")
print(f"  Source pages:    {', '.join(KNOWLEDGE_TYPES.values())}\n")

fail_count = 0
warn_count = 0
report     = {}

checks = [
    (
        "[1] embed-entry handles all 3 knowledge types (fault / skill / pm)",
        check_embed_type_handlers(EMBED_FUNCTION, KNOWLEDGE_TYPES),
        "FAIL",
    ),
    (
        "[2] All 3 embed functions defined in respective pages",
        check_embed_functions_present(EMBED_FUNCTIONS),
        "FAIL",
    ),
    (
        "[3] Each embed call passes the correct type parameter",
        check_embed_type_params(KNOWLEDGE_TYPES),
        "FAIL",
    ),
    (
        "[4] SQL search functions filter embedding IS NOT NULL",
        check_null_embedding_guard(migrations, SEARCH_FUNCTIONS),
        "FAIL",
    ),
]

for label, issues, severity in checks:
    print(f"\n{label}\n")
    if not issues:
        print("  PASS")
    else:
        for iss in issues:
            print(f"  {severity}  {iss.get('page', iss.get('func', iss.get('type', iss.get('source', '?'))))}")
            print(f"        {iss['reason']}")
        if severity == "FAIL":
            fail_count += len(issues)
        else:
            warn_count += len(issues)
    report[label] = issues

print(f"\n{'=' * 70}")
print(f"Result: {fail_count} FAIL  {warn_count} WARN")

with open("knowledge_freshness_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved knowledge_freshness_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll knowledge freshness checks PASS.")
