"""
Context Window Management Validator — WorkHive Platform
========================================================
The MEMENTO paper achieves 2.5x KV cache reduction by compressing
reasoning context into dense summaries. WorkHive's approach is simpler
but follows the same principle: send LESS context per request, not MORE.

  Layer 1 — History bounds
    1.  floating-ai.js maxHistory declared   — history array must be bounded
    2.  floating-ai.js history.slice(-N)     — only a window of messages sent per request

  Layer 2 — Session bounds
    3.  assistant sessionMessages bounded    — no full-session spread into messages  [WARN]
    4.  Semantic search match_count explicit — RAG injection bounded explicitly

  Layer 3 — Prompt size
    5.  System prompt size reasonable        — static prompt > 5000 chars leaves
                                              little room in small fallback models  [WARN]
    6.  All context sources have .limit()    — schedule_items and similar queries
                                              must cap injected records

Usage:  python validate_context_window.py
Output: context_window_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

FLOATING_AI    = "floating-ai.js"
ASSISTANT_PAGE = "assistant.html"

MAX_HISTORY_LIMIT   = 30
MAX_MATCH_COUNT     = 10
MAX_PROMPT_CHARS    = 5000   # ~1250 tokens — keeps headroom on llama-3.1-8b (8192 tok)


def _extract_template_literal(content, search_pattern):
    """Find a template literal starting at search_pattern and return its text."""
    m = re.search(search_pattern, content)
    if not m:
        return None
    tick = content.find("`", m.start())
    if tick == -1:
        return None
    i, depth = tick + 1, 0
    while i < len(content):
        c = content[i]
        if c == "$" and i + 1 < len(content) and content[i + 1] == "{":
            depth += 1
        elif c == "}" and depth > 0:
            depth -= 1
        elif c == "`" and depth == 0:
            return content[tick + 1:i]
        i += 1
    return None


# ── Layer 1: History bounds ───────────────────────────────────────────────────

def check_max_history(page):
    """config.maxHistory keeps the in-memory history array bounded. Without it,
    every message in a browser session gets sent with subsequent API calls."""
    content = read_file(page)
    if content is None:
        return [{"check": "max_history", "page": page, "reason": f"{page} not found"}]
    m = re.search(r"maxHistory\s*:\s*(\d+)", content)
    if not m:
        return [{"check": "max_history", "page": page,
                 "reason": (f"{page} has no maxHistory setting — conversation history "
                            f"grows without limit, causing unbounded token usage")}]
    val = int(m.group(1))
    if val > MAX_HISTORY_LIMIT:
        return [{"check": "max_history", "page": page,
                 "reason": (f"{page} maxHistory = {val} (max recommended: {MAX_HISTORY_LIMIT}) — "
                            f"keeping {val} messages means long sessions accumulate large context")}]
    return []


def check_history_slice(page):
    """history.slice(-N) must be used per request — sending the full history array
    makes later messages cost N× more tokens than early ones."""
    content = read_file(page)
    if content is None:
        return []
    if not re.search(r"history\.slice\s*\(\s*-\d+\s*\)", content):
        return [{"check": "history_slice", "page": page,
                 "reason": (f"{page} does not slice history before sending — full history "
                            f"array sent per request; token usage grows with session length")}]
    return []


# ── Layer 2: Session bounds ───────────────────────────────────────────────────

def check_session_messages_bound(page):
    """assistant.html must bound sessionMessages with .slice(-N) before spreading
    into the messages array — at 40 exchanges, unsent full history is 8000+ tokens."""
    content = read_file(page)
    if content is None:
        return [{"check": "session_messages_bound", "page": page,
                 "reason": f"{page} not found"}]
    spread_m = re.search(r"\.\.\.(sessionMessages)(\s*)(?!\.slice)", content)
    if spread_m:
        ctx = content[max(0, spread_m.start() - 200):spread_m.end() + 200]
        if "messages" in ctx and "role" in ctx:
            return [{"check": "session_messages_bound", "page": page, "skip": True,
                     "reason": (f"{page} sends full sessionMessages without slicing — "
                                f"long sessions may exceed small fallback model context windows")}]
    return []


def check_semantic_match_count(page):
    """Semantic search match_count must be explicit and bounded to prevent a future
    edge function default change from silently expanding every prompt."""
    content = read_file(page)
    if content is None:
        return [{"check": "semantic_match_count", "page": page, "reason": f"{page} not found"}]
    sem_m = re.search(r"semantic-search[\s\S]{0,500}?match_count", content)
    if not sem_m:
        return [{"check": "semantic_match_count", "page": page,
                 "reason": (f"{page} calls semantic-search without explicit match_count — "
                            f"RAG result count depends on edge function default")}]
    block = content[sem_m.start():sem_m.start() + 300]
    count_m = re.search(r"match_count\s*:\s*(\d+)", block)
    if count_m and int(count_m.group(1)) > MAX_MATCH_COUNT:
        return [{"check": "semantic_match_count", "page": page,
                 "reason": (f"{page} match_count = {count_m.group(1)} "
                            f"(max recommended: {MAX_MATCH_COUNT}) — "
                            f"injects {int(count_m.group(1)) * 3} RAG results per prompt")}]
    return []


# ── Layer 3: Prompt size ──────────────────────────────────────────────────────

def check_system_prompt_size(pages):
    """
    The static portion of each AI surface's system prompt must not exceed
    MAX_PROMPT_CHARS characters (~1250 tokens). Large static prompts consume
    the token budget before any conversation history or RAG context is added.

    When the primary models are rate-limited and the chain falls back to
    llama-3.1-8b-instant (8192 token limit), a 2000+ token static system
    prompt leaves only 6192 tokens for history + RAG + response. A long
    assistant.html session can hit this limit silently — the model receives
    truncated context and returns lower-quality answers with no error.

    The assistant.html platform description alone is ~9000 chars (~2250 tokens),
    which is 27% of the 8192-token fallback model limit before any dynamic
    context is injected.
    """
    issues = []
    prompt_patterns = {
        "floating-ai.js":  r"const system\s*=\s*`",
        "assistant.html":  r"return\s*`You are",
    }
    for page in pages:
        if page not in prompt_patterns:
            continue
        content = read_file(page)
        if content is None:
            continue
        prompt = _extract_template_literal(content, prompt_patterns[page])
        if prompt is None:
            continue
        if len(prompt) > MAX_PROMPT_CHARS:
            issues.append({"check": "system_prompt_size", "page": page, "skip": True,
                           "reason": (f"{page} static system prompt is {len(prompt)} chars "
                                      f"(~{len(prompt)//4} tokens, limit ~{MAX_PROMPT_CHARS//4} tokens) — "
                                      f"on llama-3.1-8b-instant (8192 tok fallback), this consumes "
                                      f"{len(prompt)//4 * 100 // 2048}% of the token budget before "
                                      f"any history or RAG context is added; consider splitting the "
                                      f"platform description into a shorter 'relevant tools only' summary")})
    return issues


def check_context_sources_bounded(pages):
    """
    Every data source injected into the system prompt must have an explicit
    .limit() call. The assistant.html schedule_items query uses a 17-day date
    range but NO .limit() — a worker with 30+ scheduled items in that window
    gets all of them injected, potentially adding 3000+ chars of schedule data
    to an already large system prompt.

    Logbook correctly uses .limit(10). Schedule items should use .limit(20)
    or similar to prevent injection bloat on busy planning windows.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        # Find queries to schedule_items or similar context tables without .limit()
        for table in ("schedule_items", "pm_completions"):
            for m in re.finditer(rf"from\(['\"]({re.escape(table)})['\"]", content):
                # Get the query chain (up to 300 chars)
                chain = content[m.start():m.start() + 300]
                if ".limit(" not in chain and ".select(" in chain:
                    # Only flag if this query is inside the system prompt builder
                    surrounding = content[max(0, m.start() - 500):m.start()]
                    if "buildSystemPrompt" in surrounding or "systemPrompt" in surrounding or "return `" in surrounding:
                        issues.append({"check": "context_sources_bounded", "page": page,
                                       "reason": (f"{page} query on '{table}' inside system prompt "
                                                  f"builder has no .limit() — all matching rows are "
                                                  f"injected into the prompt; add .limit(20) to cap "
                                                  f"the injected record count")})
                        break
    return issues


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "max_history",
    "history_slice",
    "session_messages_bound",
    "semantic_match_count",
    "system_prompt_size",
    "context_sources_bounded",
]

CHECK_LABELS = {
    "max_history":              "L1  floating-ai.js maxHistory declared and bounded",
    "history_slice":            "L1  floating-ai.js sends bounded history.slice(-N) per request",
    "session_messages_bound":   "L2  assistant.html sessionMessages bounded before sending  [WARN]",
    "semantic_match_count":     "L2  Semantic search match_count explicit and bounded",
    "system_prompt_size":       "L3  Static system prompts <= 5000 chars (1250 tokens)  [WARN]",
    "context_sources_bounded":  "L3  All context data sources have explicit .limit() calls",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nContext Window Management Validator (3-layer)"))
    print("=" * 55)

    all_issues = []
    all_issues += check_max_history(FLOATING_AI)
    all_issues += check_history_slice(FLOATING_AI)
    all_issues += check_session_messages_bound(ASSISTANT_PAGE)
    all_issues += check_semantic_match_count(ASSISTANT_PAGE)
    all_issues += check_system_prompt_size([FLOATING_AI, ASSISTANT_PAGE])
    all_issues += check_context_sources_bounded([ASSISTANT_PAGE])

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "context_window",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("context_window_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
