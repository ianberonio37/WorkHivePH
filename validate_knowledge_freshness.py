"""
Knowledge Base Freshness Validator — WorkHive Platform
=======================================================
WorkHive's AI assistant answers from a live knowledge base: fault history
from logbook saves, skill profiles from exam results, PM health from
completions. Every save triggers an embed-entry function call that creates
a vector embedding and stores it in the knowledge tables.

If ANY link in this pipeline breaks, the knowledge base goes stale
SILENTLY — the AI assistant keeps responding but answers from outdated
data.

  Layer 1 — Pipeline coverage
    1.  embed-entry handles all 3 types  — fault / skill / pm handlers must exist
    2.  All 3 embed functions present     — embedFaultEntry, embedSkillEntry, embedPMEntry

  Layer 2 — Type routing
    3.  Correct type parameter per page   — wrong type routes data to wrong table

  Layer 3 — Query safety
    4.  IS NOT NULL guard on search fns   — null embeddings crash cosine distance operator

  Layer 4 — Pipeline resilience
    5.  Embed is fire-and-forget          — embed call must NOT be awaited at the call site
    6.  Embed function has try/catch      — network errors must not throw and block saves

Usage:  python validate_knowledge_freshness.py
Output: knowledge_freshness_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

MIGRATIONS_DIR = os.path.join("supabase", "migrations")
EMBED_FUNCTION = os.path.join("supabase", "functions", "embed-entry", "index.ts")

KNOWLEDGE_TYPES = {
    "fault": "logbook.html",
    "skill": "skillmatrix.html",
    "pm":    "pm-scheduler.html",
}

EMBED_FUNCTIONS = {
    "logbook.html":      "embedFaultEntry",
    "skillmatrix.html":  "embedSkillEntry",
    "pm-scheduler.html": "embedPMEntry",
}

SEARCH_FUNCTIONS = [
    "search_fault_knowledge",
    "search_skill_knowledge",
    "search_pm_knowledge",
]


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


def extract_function_body(content, func_name, max_chars=2000):
    m = re.search(rf"(?:async\s+)?function\s+{re.escape(func_name)}\s*\(", content)
    if not m:
        return None
    return content[m.start():m.start() + max_chars]


# ── Layer 1: Pipeline coverage ────────────────────────────────────────────────

def check_embed_type_handlers(func_path, types):
    """embed-entry must handle all 3 types. A missing handler silently drops that
    entire data category — the AI has no memory of those events."""
    content = read_file(func_path)
    if content is None:
        return [{"check": "embed_type_handlers", "source": func_path,
                 "reason": f"{func_path} not found — embed-entry function missing entirely"}]
    issues = []
    for knowledge_type, source_page in types.items():
        if not re.search(rf"['\"]({re.escape(knowledge_type)})['\"]", content):
            issues.append({"check": "embed_type_handlers", "type": knowledge_type,
                           "reason": (f"{func_path} has no handler for type='{knowledge_type}' — "
                                      f"data from {source_page} will never be embedded")})
    return issues


def check_embed_functions_present(embed_map):
    """Each knowledge source page must define its embed function. Removing it
    during a refactor silently stops that knowledge source from updating."""
    issues = []
    for page, func_name in embed_map.items():
        content = read_file(page)
        if content is None:
            issues.append({"check": "embed_functions_present", "page": page,
                           "reason": f"{page} not found — cannot verify embed function"})
            continue
        if not re.search(rf"(?:async\s+)?function\s+{re.escape(func_name)}\s*\(", content):
            issues.append({"check": "embed_functions_present", "page": page,
                           "reason": (f"{page} does not define {func_name}() — "
                                      f"this knowledge source will never be embedded")})
    return issues


# ── Layer 2: Type routing ─────────────────────────────────────────────────────

def check_embed_type_params(type_to_page):
    """Each embed call must pass the correct type string — wrong type routes data
    to the wrong knowledge table (fault data in skill_knowledge etc.)."""
    issues = []
    for knowledge_type, page in type_to_page.items():
        content = read_file(page)
        if content is None:
            continue
        embed_m = re.search(r"embed-entry[\s\S]{0,500}?type\s*:\s*['\"](\w+)['\"]", content)
        if not embed_m:
            issues.append({"check": "embed_type_params", "page": page,
                           "reason": (f"{page} calls embed-entry but no type parameter found — "
                                      f"embed-entry cannot route to the correct knowledge table")})
            continue
        found_type = embed_m.group(1)
        if found_type != knowledge_type:
            issues.append({"check": "embed_type_params", "page": page,
                           "reason": (f"{page} passes type='{found_type}' to embed-entry but "
                                      f"should pass type='{knowledge_type}'")})
    return issues


# ── Layer 3: Query safety ─────────────────────────────────────────────────────

def check_null_embedding_guard(migrations, search_funcs):
    """SQL similarity search functions must filter embedding IS NOT NULL — null
    embeddings cause the cosine distance operator to throw a runtime error."""
    if not migrations:
        return [{"check": "null_embedding_guard", "source": MIGRATIONS_DIR,
                 "reason": f"{MIGRATIONS_DIR} not found"}]
    issues = []
    for func_name in search_funcs:
        fn_m = re.search(
            rf"FUNCTION\s+{re.escape(func_name)}\s*\([\s\S]+?(?=CREATE OR REPLACE FUNCTION|\Z)",
            migrations, re.IGNORECASE
        )
        if not fn_m:
            issues.append({"check": "null_embedding_guard", "func": func_name,
                           "reason": f"SQL function '{func_name}' not found in migrations"})
            continue
        if not re.search(r"embedding\s+IS\s+NOT\s+NULL", fn_m.group(0), re.IGNORECASE):
            issues.append({"check": "null_embedding_guard", "func": func_name,
                           "reason": (f"'{func_name}' has no 'embedding IS NOT NULL' filter — "
                                      f"null embeddings crash cosine distance search")})
    return issues


# ── Layer 4: Pipeline resilience ─────────────────────────────────────────────

def check_embed_fire_and_forget(embed_map):
    """
    Embed function calls must NOT be prefixed with await at the call site.
    The embed pipeline updates the knowledge base asynchronously — the main
    save (logbook entry, PM completion, skill badge) must complete and confirm
    to the worker regardless of embed success or failure.

    If someone adds await before embedFaultEntry(...), a Groq API timeout or
    rate limit on the embed call would make the logbook save appear to hang —
    the worker sees a spinning loader for 60 seconds before their entry saves.

    Correct:   embedFaultEntry(entry);           ← fire-and-forget
    Incorrect: await embedFaultEntry(entry);     ← blocks the save confirmation
    """
    issues = []
    for page, func_name in embed_map.items():
        content = read_file(page)
        if content is None:
            continue
        # Find the call site (not the function definition)
        for m in re.finditer(rf"\bawait\s+{re.escape(func_name)}\s*\(", content):
            line_no = content[:m.start()].count("\n") + 1
            issues.append({"check": "embed_fire_and_forget", "page": page, "line": line_no,
                           "reason": (f"{page}:{line_no} uses 'await {func_name}()' — "
                                      f"embed call must be fire-and-forget (no await); "
                                      f"embedding failure will block the save confirmation "
                                      f"and leave the worker staring at a spinner for 60 seconds")})
    return issues


def check_embed_has_try_catch(embed_map):
    """
    Every embed function body must contain a try/catch that does NOT rethrow.
    Without it, a network error (Groq down, Supabase edge function cold start)
    throws an unhandled promise rejection. In the browser this produces a cryptic
    console error. In the worst case (if the function is accidentally awaited)
    it crashes the entire save path and the logbook entry is lost.

    The correct pattern: try { ... } catch (e) { console.warn(...); }
    The dangerous pattern: try { ... } catch (e) { throw e; }  ← rethrows
    """
    issues = []
    for page, func_name in embed_map.items():
        content = read_file(page)
        if content is None:
            continue
        body = extract_function_body(content, func_name)
        if body is None:
            continue
        # Must have a catch clause
        if "catch" not in body:
            issues.append({"check": "embed_has_try_catch", "page": page,
                           "reason": (f"{page} {func_name}() has no try/catch — "
                                      f"a network error throws an unhandled rejection; "
                                      f"add try/catch with console.warn to suppress silently")})
            continue
        # Must not rethrow — catch must not contain 'throw e' or 'throw err'
        catch_m = re.search(r"catch\s*\([^)]*\)\s*\{([^}]+)\}", body)
        if catch_m and re.search(r"\bthrow\b", catch_m.group(1)):
            issues.append({"check": "embed_has_try_catch", "page": page,
                           "reason": (f"{page} {func_name}() catch block rethrows the error — "
                                      f"embed failures will propagate and may block the save path; "
                                      f"use console.warn to swallow embed errors silently")})
    return issues


# ── Runner ─────────────────────────────────────────────────────────────────────

def check_pipeline_coverage_ratio(logbook_pages, embed_map):
    """
    The embed pipeline runs fire-and-forget after each logbook save, but there
    is no mechanism anywhere in the codebase that compares logbook entry count
    against fault_knowledge row count to detect pipeline lag.

    Problem 02 (Stale Data) + Problem 11 (Data Latency): if 100 logbook entries
    exist but only 10 fault_knowledge rows, the AI answers from 10% of available
    history — silently, with no indication to the worker.

    A pipeline health check should exist somewhere in the platform:
      SELECT COUNT(*) FROM logbook WHERE worker_name = $worker
      vs
      SELECT COUNT(*) FROM fault_knowledge WHERE hive_id = $hive

    If the ratio is below 30%, surface a warning to the worker or the Guardian.
    This check verifies that such a count-comparison pattern exists in the
    assistant.html sidebar, the Guardian dashboard, or the AI orchestrator.
    Reported as WARN — the pipeline works but has no health monitoring.
    """
    all_content = ""
    for page in logbook_pages:
        content = read_file(page)
        if content:
            all_content += content

    has_coverage_check = bool(re.search(
        r"fault_knowledge.*count|count.*fault_knowledge"
        r"|knowledge.*coverage|pipeline.*ratio|logbook.*vs.*knowledge"
        r"|knowledge.*logbook.*ratio",
        all_content, re.IGNORECASE
    ))
    if not has_coverage_check:
        return [{"check": "pipeline_coverage_ratio", "skip": True,
                 "reason": ("No code compares logbook entry count against fault_knowledge row count — "
                            "pipeline lag (100 logbook entries but only 10 embeddings) is invisible; "
                            "add a count-comparison in assistant.html sidebar or Guardian dashboard: "
                            "SELECT COUNT(*) FROM fault_knowledge WHERE hive_id = $hive")}]
    return []


CHECK_NAMES = [
    "embed_type_handlers",
    "embed_functions_present",
    "embed_type_params",
    "null_embedding_guard",
    "embed_fire_and_forget",
    "embed_has_try_catch",
    "pipeline_coverage_ratio",
]

CHECK_LABELS = {
    "embed_type_handlers":     "L1  embed-entry handles all 3 knowledge types (fault/skill/pm)",
    "embed_functions_present": "L1  All 3 embed functions defined in their source pages",
    "embed_type_params":       "L2  Each embed call passes the correct type parameter",
    "null_embedding_guard":    "L3  SQL search functions filter embedding IS NOT NULL",
    "embed_fire_and_forget":   "L4  Embed calls are fire-and-forget (no await at call site)",
    "embed_has_try_catch":     "L4  Embed functions have try/catch that does not rethrow",
    "pipeline_coverage_ratio": "L5  Knowledge base coverage ratio monitored (logbook vs embeddings)  [WARN]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nKnowledge Base Freshness Validator (4-layer)"))
    print("=" * 55)

    migrations = read_all_migrations()
    print(f"  Knowledge types: {', '.join(KNOWLEDGE_TYPES.keys())}\n")

    all_issues = []
    all_issues += check_embed_type_handlers(EMBED_FUNCTION, KNOWLEDGE_TYPES)
    all_issues += check_embed_functions_present(EMBED_FUNCTIONS)
    all_issues += check_embed_type_params(KNOWLEDGE_TYPES)
    all_issues += check_null_embedding_guard(migrations, SEARCH_FUNCTIONS)
    all_issues += check_embed_fire_and_forget(EMBED_FUNCTIONS)
    all_issues += check_embed_has_try_catch(EMBED_FUNCTIONS)
    all_issues += check_pipeline_coverage_ratio(list(EMBED_FUNCTIONS.keys()), EMBED_FUNCTIONS)

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "knowledge_freshness",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("knowledge_freshness_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
