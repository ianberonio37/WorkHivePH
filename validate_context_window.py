"""
Context Window Management Validator — WorkHive Platform
========================================================
The MEMENTO paper achieves 2.5x KV cache reduction by compressing
reasoning context into dense summaries. WorkHive's approach is simpler
but follows the same principle: send LESS context per request, not MORE.

Two AI surfaces manage conversation history:
  1. floating-ai.js  — the floating widget (correct: maxHistory=20, slice(-10))
  2. assistant.html  — the full assistant page (unbounded sessionMessages)

Unbounded context causes:
  - Token cost explosion: 50 exchange session = 10,000+ tokens per request
  - Context window overflow: very long sessions hit model limits and fail
  - Response quality degradation: most models lose attention on early messages
  - Supabase Edge Function timeouts: large payloads take longer to process

The AI Engineer skill says: 'maxHistory: 20, half (10) are sent to model
per request' — this applies to all AI surfaces.

Four things checked:

  1. floating-ai.js maxHistory is declared and bounded
     — The config.maxHistory value keeps the in-memory history array from
       growing indefinitely across a browser session. If missing or too
       high (> 30), every message is retained and the context grows
       without bound.

  2. floating-ai.js sends a bounded history slice per request
     — Even with maxHistory set, what matters is how many messages are
       sent per API call. The correct pattern is history.slice(-N) where
       N is half of maxHistory. Sending the full history array means
       later messages in a session use twice the tokens of early messages.

  3. assistant.html sessionMessages is bounded before sending
     — The full assistant page uses sessionMessages to track the
       conversation. If sent in full with no .slice(), the entire session
       history goes with every request. At 40 exchanges: 80 messages +
       a 3,000-token system prompt can exceed 15,000 tokens per request.
       Reported as WARN — works for normal sessions, fails long ones.

  4. Semantic search context injection has a match_count limit
     — getSemanticContext() calls the semantic-search edge function with
       a match_count parameter. Without a cap, the function returns the
       default (3 per source = 9 total). This should always be explicitly
       bounded to prevent a future change to the edge function default
       from suddenly injecting 50 results into every prompt.

Usage:  python validate_context_window.py
Output: context_window_report.json
"""
import re, json, sys

FLOATING_AI    = "floating-ai.js"
ASSISTANT_PAGE = "assistant.html"

# Maximum allowed maxHistory (AI Engineer skill says 20 — flag if > this)
MAX_HISTORY_LIMIT = 30

# Maximum allowed match_count for semantic search injection
MAX_MATCH_COUNT = 10


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


# ── Check 1: floating-ai.js maxHistory declared and <= MAX_HISTORY_LIMIT ──────

def check_max_history(page):
    """
    config.maxHistory keeps the in-memory history array bounded. Without it,
    every message sent in a browser session accumulates in memory and gets
    included in subsequent API calls, growing the context window without limit.

    The AI Engineer skill specifies: maxHistory: 20 (max messages kept).
    Values above MAX_HISTORY_LIMIT are flagged — they indicate the bound
    was loosened without considering the token cost implications.
    """
    issues = []
    content = read_file(page)
    if content is None:
        return [{"page": page, "reason": f"{page} not found"}]

    m = re.search(r"maxHistory\s*:\s*(\d+)", content)
    if not m:
        issues.append({
            "page": page,
            "reason": (
                f"{page} has no maxHistory setting — conversation history "
                f"grows without limit, causing unbounded token usage as sessions "
                f"grow longer"
            ),
        })
        return issues

    val = int(m.group(1))
    if val > MAX_HISTORY_LIMIT:
        issues.append({
            "page":  page,
            "value": val,
            "limit": MAX_HISTORY_LIMIT,
            "reason": (
                f"{page} maxHistory = {val} (maximum recommended: {MAX_HISTORY_LIMIT}) — "
                f"keeping {val} messages in memory means long sessions accumulate "
                f"a large context before any slicing"
            ),
        })
    return issues


# ── Check 2: floating-ai.js sends bounded history slice per request ───────────

def check_history_slice(page):
    """
    Even with maxHistory set, what matters is how many messages are sent
    per API call. The correct pattern is history.slice(-N) where N is
    roughly half of maxHistory.

    Sending the full history array without slicing means:
    - Message 1: 1 entry in messages array
    - Message 20: 20 entries in messages array
    - Message 20 costs 20× the tokens of message 1

    The correct pattern sends a fixed window (e.g., slice(-10)) so every
    request costs approximately the same tokens.
    """
    issues = []
    content = read_file(page)
    if content is None:
        return []

    # Check for history.slice(-N) or similar bounded send pattern
    has_slice = bool(re.search(
        r"history\.slice\s*\(\s*-\d+\s*\)",
        content
    ))
    if not has_slice:
        issues.append({
            "page": page,
            "reason": (
                f"{page} does not slice history before sending — the full "
                f"history array is sent per request, meaning token usage grows "
                f"linearly with session length instead of staying constant"
            ),
        })
    return issues


# ── Check 3: assistant.html sessionMessages is bounded before sending ─────────

def check_session_messages_bound(page):
    """
    assistant.html uses sessionMessages to track the conversation.
    If sent in full (no .slice()), every request includes the entire
    session history, not just the recent exchanges.

    At 40 message exchanges:
    - 80 messages × ~100 tokens avg = 8,000 tokens for history alone
    - Plus 3,000-token system prompt + logbook context = 11,000+ tokens
    - This approaches llama-4-scout's 16K context window

    The pattern should be:  ...sessionMessages.slice(-20)
    Not:                    ...sessionMessages  (sends everything)

    Reported as WARN because:
    - Normal work sessions (< 20 exchanges) work fine
    - The orchestrator path doesn't include sessionMessages
    - The Cloudflare Worker accepts large payloads
    """
    issues = []
    content = read_file(page)
    if content is None:
        return [{"page": page, "reason": f"{page} not found"}]

    # Find the pattern where sessionMessages is spread into messages array
    spread_m = re.search(
        r"\.\.\.(sessionMessages)(\s*)(?!\.slice)",
        content
    )
    if spread_m:
        # Confirm it's inside a messages array (not some other spread)
        context_around = content[max(0, spread_m.start()-200):spread_m.end()+200]
        if "messages" in context_around and "role" in context_around:
            issues.append({
                "page": page,
                "reason": (
                    f"{page} sends full sessionMessages without slicing "
                    f"(...sessionMessages instead of ...sessionMessages.slice(-N)) — "
                    f"long work sessions accumulate context that may exceed model "
                    f"limits or cause slow responses due to large payloads"
                ),
            })
    return issues


# ── Check 4: Semantic search injection has explicit match_count limit ─────────

def check_semantic_match_count(page):
    """
    getSemanticContext() calls the semantic-search edge function. The
    match_count parameter controls how many knowledge base matches are
    returned and injected into the system prompt as RAG context.

    Without an explicit match_count, the edge function uses its default
    (3 per source = up to 9 total results). If the default ever changes,
    every prompt would suddenly include far more context.

    An explicit match_count = N (≤ MAX_MATCH_COUNT) makes the token
    budget for semantic context predictable and bounded.
    """
    issues = []
    content = read_file(page)
    if content is None:
        return [{"page": page, "reason": f"{page} not found"}]

    # Find the semantic-search call
    sem_m = re.search(r"semantic-search[\s\S]{0,500}?match_count", content)
    if not sem_m:
        issues.append({
            "page": page,
            "reason": (
                f"{page} calls semantic-search without an explicit match_count "
                f"— the number of RAG results injected per prompt depends on the "
                f"edge function default, which could change and expand context silently"
            ),
        })
        return issues

    # Check the actual value
    block = content[sem_m.start():sem_m.start() + 300]
    count_m = re.search(r"match_count\s*:\s*(\d+)", block)
    if count_m:
        val = int(count_m.group(1))
        if val > MAX_MATCH_COUNT:
            issues.append({
                "page":  page,
                "value": val,
                "limit": MAX_MATCH_COUNT,
                "reason": (
                    f"{page} semantic search match_count = {val} "
                    f"(maximum recommended: {MAX_MATCH_COUNT}) — "
                    f"injecting {val * 3} knowledge results per prompt "
                    f"may significantly increase token usage"
                ),
            })
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("\n" + "=" * 70)
print("Context Window Management Validator")
print("=" * 70)

fail_count = 0
warn_count = 0
report     = {}

checks = [
    (
        f"[1] floating-ai.js maxHistory declared and <= {MAX_HISTORY_LIMIT}",
        check_max_history(FLOATING_AI),
        "FAIL",
    ),
    (
        "[2] floating-ai.js sends bounded history.slice(-N) per request",
        check_history_slice(FLOATING_AI),
        "FAIL",
    ),
    (
        "[3] assistant.html sessionMessages bounded before sending",
        check_session_messages_bound(ASSISTANT_PAGE),
        "WARN",
    ),
    (
        f"[4] Semantic search injection has explicit match_count <= {MAX_MATCH_COUNT}",
        check_semantic_match_count(ASSISTANT_PAGE),
        "FAIL",
    ),
]

for label, issues, severity in checks:
    print(f"\n{label}\n")
    if not issues:
        print("  PASS")
    else:
        for iss in issues:
            print(f"  {severity}  {iss.get('page', '?')}")
            print(f"        {iss['reason']}")
        if severity == "FAIL":
            fail_count += len(issues)
        else:
            warn_count += len(issues)
    report[label] = issues

print(f"\n{'=' * 70}")
print(f"Result: {fail_count} FAIL  {warn_count} WARN")

with open("context_window_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved context_window_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll context window checks PASS.")
