"""
AI Data Pipeline Validator — WorkHive Platform
===============================================
WorkHive's AI assistant is only as good as the data pipeline feeding it.
If the pipeline is silently broken, the AI keeps answering — but from
stale, incomplete, or fragmented context the worker cannot verify.

This validator checks the health of every layer of the AI data pipeline:
from scheduled jobs writing to automation_log, to the context assembled
in the system prompt, to whether the worker can see how fresh the AI's
knowledge actually is.

  Layer 1 — Pipeline monitoring                             [Problem 13]
    1.  automation_log queried for pipeline health — no code reads the
        log to detect silent failures in scheduled jobs.

  Layer 2 — Context integration coverage                   [Problem 03, 18]
    2.  buildSystemPrompt queries only logbook + schedule — skill badges,
        inventory stock, and PM health are silently omitted, fragmenting
        the worker's context across disconnected data silos.

  Layer 3 — Semantic context on all AI paths               [Problem 14]
    3.  getSemanticContext() is only called in the personal assistant
        fallback path, NOT the orchestrator path. Team-intelligence
        answers get no semantic enrichment from the knowledge base.

  Layer 4 — Data quality transparency                      [Problem 20]
    4.  logbookCount is tracked in the sidebar but never injected into
        the AI system prompt — the AI cannot calibrate confidence or
        tell the worker how many entries it is reasoning from.

  Layer 5 — Stale data signal                              [Problem 02]
    5.  No freshness indicator in the system prompt. The AI answers as
        if the knowledge base is current even when the last embedding
        is months old. Workers have no visibility into knowledge age.

  Layer 6 — Empty knowledge base handling                  [Problem 03, 20]
    6.  getSemanticContext() silently returns empty string when the
        knowledge base is empty. The AI then answers from general
        knowledge without telling the worker it has no team history.

Usage:  python validate_ai_data_pipeline.py
Output: ai_data_pipeline_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

ASSISTANT_PAGE   = "assistant.html"
SCHEDULED_AGENTS = os.path.join("supabase", "functions", "scheduled-agents", "index.ts")
AI_ORCH          = os.path.join("supabase", "functions", "ai-orchestrator", "index.ts")


# ── Layer 1: Pipeline monitoring ──────────────────────────────────────────────

def check_automation_log_monitored(scheduled_path):
    """
    scheduled-agents writes to automation_log on success and failure.
    This is the heartbeat of the AI pipeline (weekly digests, failure reports,
    shift handover summaries). If a cron job fails for 3 days nobody knows.

    For monitoring to work, some part of the system must READ automation_log
    and surface failures. Currently:
    - validate_compliance.py confirms the log IS written to (write path ok)
    - But NO code anywhere reads automation_log to check for recent failures

    The fix: add a check in the Guardian dashboard or a new cron job that
    queries automation_log for 'failed' status entries within the last 48h
    and surfaces them as alerts. Example:
      SELECT * FROM automation_log WHERE status = 'failed'
        AND created_at > NOW() - INTERVAL '48 hours'
    """
    content = read_file(scheduled_path)
    if content is None:
        return [{"check": "automation_log_monitored", "source": scheduled_path,
                 "reason": f"{scheduled_path} not found"}]

    # Check if automation_log is READ anywhere (not just written)
    assistant_content  = read_file(ASSISTANT_PAGE) or ""
    platform_content   = read_file("platform-health.html") or ""

    all_content = content + assistant_content + platform_content

    has_read_query = bool(re.search(
        r"from\(['\"]automation_log['\"].*select|automation_log.*\.select\("
        r"|automation_log.*status.*failed|failed.*automation_log",
        all_content, re.IGNORECASE | re.DOTALL
    ))
    if not has_read_query:
        return [{"check": "automation_log_monitored", "source": scheduled_path,
                 "reason": ("automation_log is written to by scheduled-agents but never READ for "
                            "health monitoring — a cron job that fails silently for days is invisible; "
                            "add a query to check for 'failed' entries within the last 48h and surface "
                            "them in the Guardian dashboard or as a hive notification")}]
    return []


# ── Layer 2: Context integration coverage ────────────────────────────────────

def check_context_data_sources(page):
    """
    buildSystemPrompt() queries only logbook (last 10) and schedule_items
    (17-day window). The worker's full operational picture is fragmented:

    What IS included:     logbook entries, schedule items
    What is MISSING:      skill badges (competency level), inventory stock
                          levels (which parts are running low), PM health
                          (which assets are overdue)

    Why this matters: A worker asking "what should I prioritize today?" gets
    an answer based only on their schedule and past logbook — without knowing
    that Pump A's spare seal is out of stock, that their Electrical badge
    expires next month, or that 3 PM tasks are overdue.

    This is a fragmented context problem (Problem 18) — the AI has access to
    5 personal data sources but only uses 2 of them.
    """
    content = read_file(page)
    if content is None:
        return [{"check": "context_data_sources", "page": page,
                 "reason": f"{page} not found"}]

    build_m = re.search(r"async function buildSystemPrompt\s*\(", content)
    if not build_m:
        return [{"check": "context_data_sources", "page": page,
                 "reason": f"{page} buildSystemPrompt() not found"}]

    body = content[build_m.start():build_m.start() + 3000]
    issues = []

    if not re.search(r"skill_badge\b|skill_badges\b", body):
        issues.append({"check": "context_data_sources", "page": page, "skip": True,
                       "reason": (f"{page} buildSystemPrompt() does not query skill_badges — "
                                  f"the AI cannot answer competency questions or recommend training; "
                                  f"add: db.from('skill_badges').select('discipline,level,badge_type')"
                                  f".eq('worker_name', name).order('awarded_at', {{ascending:false}}).limit(5)")})

    if not re.search(r"inventory_items\b|inventory.*stock\b|stock.*level", body):
        issues.append({"check": "context_data_sources", "page": page, "skip": True,
                       "reason": (f"{page} buildSystemPrompt() does not include inventory context — "
                                  f"the AI cannot warn about low-stock critical parts or suggest "
                                  f"parts before a planned maintenance; add inventory summary to prompt")})

    if not re.search(r"pm_completion\b|pm_asset\b|overdue.*pm\b|pm.*overdue\b|pm.*health", body):
        issues.append({"check": "context_data_sources", "page": page, "skip": True,
                       "reason": (f"{page} buildSystemPrompt() does not include PM health context — "
                                  f"the AI cannot answer 'what PM tasks are overdue?' or prioritize "
                                  f"maintenance based on schedule; add overdue PM count to prompt")})

    return issues


# ── Layer 3: Semantic context on all AI paths ─────────────────────────────────

def check_semantic_context_on_all_paths(page):
    """
    getSemanticContext() is only called in the personal assistant fallback
    path (Step 2 in sendMessage()). When the orchestrator answers successfully
    (Step 1), it returns the answer WITHOUT semantic enrichment from the
    team knowledge base.

    Result: the orchestrator path — which handles the majority of requests
    for hive members — never benefits from team fault history, skill profiles,
    or PM health snapshots stored in the RAG knowledge base.

    The fix: fetch semantic context BEFORE choosing which path to use:
      const semanticContext = await getSemanticContext(text);
      // Then pass semanticContext to BOTH orchestrator and fallback paths.

    Currently the context is fetched AFTER the orchestrator call fails —
    by then the user has already waited for the orchestrator to respond,
    and the knowledge base context is too late to help.
    """
    content = read_file(page)
    if content is None:
        return []

    # Find the sendMessage function body
    send_m = re.search(r"async function sendMessage\s*\(", content)
    if not send_m:
        return []

    body = content[send_m.start():send_m.start() + 3000]

    # Find where getSemanticContext is called relative to the orchestrator call
    orch_m    = re.search(r"ai-orchestrator", body)
    semantic_m = re.search(r"getSemanticContext\s*\(", body)

    if not orch_m or not semantic_m:
        return []

    # If semantic context is fetched AFTER the orchestrator call, it's too late
    # to enrich the orchestrator path
    if semantic_m.start() > orch_m.start():
        return [{"check": "semantic_context_all_paths", "page": page, "skip": True,
                 "reason": (f"{page} getSemanticContext() is fetched AFTER the orchestrator call — "
                            f"team knowledge base context never reaches the orchestrator path; "
                            f"move semantic context fetch BEFORE the orchestrator call so both "
                            f"paths benefit from RAG enrichment")}]
    return []


# ── Layer 4: Data quality transparency ───────────────────────────────────────

def check_logbook_count_in_prompt(page):
    """
    assistant.html tracks logbookCount (via db.from('logbook').select count)
    and shows it in the sidebar UI. But this count is NEVER injected into the
    AI system prompt.

    The AI answers with the same confidence whether it has 2 logbook entries
    or 500 entries. Workers cannot distinguish between:
      - "I have only 3 entries to reason from" (low confidence)
      - "I have 200 entries across 6 years of operations" (high confidence)

    The fix: inject the entry count into the system prompt:
      TODAY'S DATE: ${todayReadable}
      YOUR KNOWLEDGE BASE: ${logbookCount} logbook entries available.
      I will only reference entries from the ${logbook.length} shown below.

    This makes the AI's data quality visible to the worker through its responses
    and helps calibrate when to trust AI insights vs when to check more data.
    """
    content = read_file(page)
    if content is None:
        return []

    # Check if logbookCount is referenced inside buildSystemPrompt
    build_m = re.search(r"async function buildSystemPrompt\s*\(", content)
    if not build_m:
        return []

    body = content[build_m.start():build_m.start() + 3000]
    if not re.search(r"logbookCount\b|logbook\.length\b|count.*entries|entries.*count", body):
        return [{"check": "logbook_count_in_prompt", "page": page, "skip": True,
                 "reason": (f"{page} logbookCount is tracked in the sidebar but never injected into "
                            f"the AI system prompt — the AI cannot calibrate confidence or tell the "
                            f"worker 'I am answering from 3 entries' vs 'from 500 entries'; "
                            f"add: 'YOUR KNOWLEDGE BASE: ${{logbookCount}} total logbook entries available.' "
                            f"to the system prompt header")}]
    return []


# ── Layer 5: Stale data signal ────────────────────────────────────────────────

def check_knowledge_freshness_indicator(page):
    """
    The AI system prompt has no indicator of when the knowledge base was last
    updated. A worker who hasn't logged anything in 3 months gets AI answers
    from 3-month-old operational context — with no indication the data is stale.

    For the floating AI widget, the system prompt explicitly states it has no
    access to work records (correct). For the full assistant, there is no
    similar transparency about data age.

    The fix: inject a freshness timestamp alongside the data:
      LOGBOOK: (${logbook.length} entries, most recent: ${logbook[0]?.date || 'none'})

    This single line tells the worker and the AI how current the context is,
    and lets the AI naturally say "your most recent entry is from 6 weeks ago
    — you may want to log today's work for more current insights."
    """
    content = read_file(page)
    if content is None:
        return []

    build_m = re.search(r"async function buildSystemPrompt\s*\(", content)
    if not build_m:
        return []

    body = content[build_m.start():build_m.start() + 3000]
    has_freshness = bool(re.search(
        r"most.*recent\b|last.*updated\b|freshness\b|as of\b.*date|date.*as of\b"
        r"|logbook\[0\].*date|\.date.*logbook|latest.*entry",
        body, re.IGNORECASE
    ))
    if not has_freshness:
        return [{"check": "knowledge_freshness_indicator", "page": page, "skip": True,
                 "reason": (f"{page} system prompt does not include a data freshness indicator — "
                            f"the AI answers with equal confidence from 3-year-old or yesterday's data; "
                            f"add most-recent entry date to the logbook context header: "
                            f"'LOGBOOK: (${{logbook.length}} entries, most recent: ${{logbook[0]?.date || \"none\"}})'")
                 }]
    return []


# ── Layer 6: Empty knowledge base handling ────────────────────────────────────

def check_empty_knowledge_handling(page):
    """
    getSemanticContext() returns an empty string silently when the knowledge
    base has no embeddings. The AI then answers from general industrial
    knowledge without informing the worker that it has no team history to
    draw from.

    The current system prompt handles empty LOGBOOK records correctly:
      "If records are empty, answer from general knowledge and mention
       no records exist yet. Do not invent any."

    But there is no equivalent handling for empty SEMANTIC CONTEXT. When
    the RAG search returns nothing (empty knowledge base), the AI silently
    falls back to general knowledge — the worker thinks they're getting
    team-specific insights but they're actually getting generic answers.

    The fix: when semanticContext is empty, inject a note:
      KNOWLEDGE BASE: No team fault history or skill records available yet.
      Answers below are from general industrial knowledge, not team-specific data.

    This gives workers accurate expectations and encourages them to log
    more to improve AI quality.
    """
    content = read_file(page)
    if content is None:
        return []

    # Find where semanticContext is used in sendMessage
    m = re.search(r"const enrichedPrompt\s*=\s*semanticContext", content)
    if not m:
        return []

    block = content[m.start():m.start() + 500]
    # Check if the empty semanticContext case adds an indicator to the prompt
    has_empty_handling = bool(re.search(
        r"no.*knowledge|knowledge.*empty|no.*team.*history|no.*semantic|empty.*context",
        block, re.IGNORECASE
    ))
    if not has_empty_handling:
        return [{"check": "empty_knowledge_handling", "page": page, "skip": True,
                 "reason": (f"{page} empty semanticContext silently falls back to general knowledge — "
                            f"workers think they're getting team-specific insights but get generic answers; "
                            f"when semanticContext is empty, add a note to the prompt: "
                            f"'KNOWLEDGE BASE: No team history available yet — answering from general knowledge'")}]
    return []


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "automation_log_monitored",
    "context_data_sources",
    "semantic_context_all_paths",
    "logbook_count_in_prompt",
    "knowledge_freshness_indicator",
    "empty_knowledge_handling",
]

CHECK_LABELS = {
    "automation_log_monitored":     "L1  automation_log monitored for pipeline failures",
    "context_data_sources":         "L2  buildSystemPrompt includes skill + inventory + PM context  [WARN]",
    "semantic_context_all_paths":   "L3  Semantic context fetched before orchestrator (not only fallback)  [WARN]",
    "logbook_count_in_prompt":      "L4  Logbook entry count injected into AI system prompt  [WARN]",
    "knowledge_freshness_indicator":"L5  System prompt includes data freshness indicator  [WARN]",
    "empty_knowledge_handling":     "L6  Empty knowledge base communicated to AI and worker  [WARN]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nAI Data Pipeline Validator (6-layer)"))
    print("=" * 55)
    print("  Addresses: stale data, data silos, data latency, broken")
    print("  pipelines, overloaded volume, lack of observability\n")

    all_issues = []
    all_issues += check_automation_log_monitored(SCHEDULED_AGENTS)
    all_issues += check_context_data_sources(ASSISTANT_PAGE)
    all_issues += check_semantic_context_on_all_paths(ASSISTANT_PAGE)
    all_issues += check_logbook_count_in_prompt(ASSISTANT_PAGE)
    all_issues += check_knowledge_freshness_indicator(ASSISTANT_PAGE)
    all_issues += check_empty_knowledge_handling(ASSISTANT_PAGE)

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "ai_data_pipeline",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("ai_data_pipeline_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
