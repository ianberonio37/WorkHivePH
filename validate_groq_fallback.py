"""
Groq Fallback Chain Validator — WorkHive Platform
==================================================
WorkHive's AI features depend entirely on Groq for LLM calls and
embeddings. Groq's free tier imposes TPM (tokens per minute) limits
per model — a single model call that hits a rate limit returns nothing.

The platform uses multi-model fallback chains to stay resilient:
  1. Try model 1 (highest TPM)
  2. On 429 (rate limit) or 413 (prompt too large): skip to model 2
  3. Continue until a model responds or all are exhausted

This validator ensures every LLM-calling edge function implements
this pattern correctly. A missing max_tokens or unhandled 413 is an
invisible failure — the caller gets no response and no error message
that points to the cause.

From the AI Engineer skill (Groq reliability rules).

Four things checked:

  1. Every LLM-calling function has a multi-model fallback chain
     — A GROQ_CHAIN / GROQ_FALLBACK_CHAIN / GROQ_NARRATIVE_CHAIN constant
       with at least 2 models must exist. A single-model function has zero
       resilience — one rate limit = zero AI response for that request.

  2. max_tokens set on every Groq chat completion call
     — Without max_tokens, the model generates until it hits its own
       context window limit, consuming all remaining tokens and leaving
       nothing for subsequent requests in the same minute. This is the
       primary cause of unexpected 429s at low traffic.

  3. Both 413 and 429 handled in the fallback loop
     — 429 = rate limit (too many requests per minute for this model)
     — 413 = payload too large (prompt exceeds this model's context window)
       Both must trigger a skip to the next model. Handling only 429 means
       a large prompt permanently fails instead of falling back to a model
       with a larger context window.

  4. GROQ_API_KEY validated before making any calls
     — If the key is missing (not set in Supabase Edge Function secrets),
       all Groq calls fail with an auth error. Functions must validate the
       key at the start of the callGroq helper and fail fast with a clear
       message — not deep in the retry loop with a cryptic 401.

Usage:  python validate_groq_fallback.py
Output: groq_fallback_report.json
"""
import re, json, sys, os

FUNCTIONS_DIR = os.path.join("supabase", "functions")

# Edge functions that make Groq LLM (chat completion) calls — need fallback chains
LLM_FUNCTIONS = [
    "ai-orchestrator",
    "engineering-calc-agent",
    "engineering-bom-sow",
    "scheduled-agents",
]

# Edge functions that call ANY Groq API (LLM + embeddings) — need key validation
ALL_GROQ_FUNCTIONS = LLM_FUNCTIONS + ["semantic-search", "embed-entry"]

# Minimum number of models in a fallback chain
MIN_CHAIN_MODELS = 2


def read_function(name):
    path = os.path.join(FUNCTIONS_DIR, name, "index.ts")
    try:
        with open(path, encoding="utf-8") as f:
            return f.read(), path
    except FileNotFoundError:
        return None, path


# ── Check 1: Every LLM function has a multi-model fallback chain ──────────────

def check_fallback_chains(func_names):
    """
    Every function that makes Groq chat completion calls must declare a
    fallback chain constant (any name containing GROQ and CHAIN or FALLBACK)
    with at least MIN_CHAIN_MODELS entries.

    A single-model function has no resilience: one rate limit hit means
    the entire feature fails for that request with no explanation to the user.
    """
    issues = []
    for name in func_names:
        content, path = read_function(name)
        if content is None:
            issues.append({
                "func":   name,
                "reason": f"{path} not found — cannot verify fallback chain",
            })
            continue

        # Find the chain constant declaration
        chain_m = re.search(
            r"(?:GROQ_CHAIN|GROQ_FALLBACK_CHAIN|GROQ_NARRATIVE_CHAIN)\s*=\s*\[([\s\S]+?)\]",
            content
        )
        if not chain_m:
            issues.append({
                "func":   name,
                "reason": (
                    f"{name}/index.ts has no Groq fallback chain constant "
                    f"(GROQ_CHAIN / GROQ_FALLBACK_CHAIN / GROQ_NARRATIVE_CHAIN) — "
                    f"a single rate limit hit will return no AI response"
                ),
            })
            continue

        # Count the number of model entries
        models = re.findall(r'["\']([^"\']+)["\']', chain_m.group(1))
        if len(models) < MIN_CHAIN_MODELS:
            issues.append({
                "func":   name,
                "models": models,
                "reason": (
                    f"{name}/index.ts fallback chain has only {len(models)} model(s) "
                    f"(minimum {MIN_CHAIN_MODELS}) — not enough redundancy for "
                    f"rate limit resilience"
                ),
            })
    return issues


# ── Check 2: max_tokens set on every Groq chat completion call ────────────────

def check_max_tokens(func_names):
    """
    max_tokens must be set on every Groq chat/completions API call body.
    Without it, the model generates up to its context limit, consuming
    the entire TPM budget in one call and causing 429s for subsequent requests.

    The AI Engineer skill specifies per-function limits:
    - Narratives (short): 512 tokens
    - Reports/analysis: 1024 tokens
    - BOM/SOW (long structured output): 8000 tokens
    """
    issues = []
    for name in func_names:
        content, path = read_function(name)
        if content is None:
            continue

        # Find all chat completion API calls
        # A Groq chat call contains the messages array + model + temperature
        has_chat_call = bool(re.search(
            r"openai/v1/chat/completions",
            content
        ))
        if not has_chat_call:
            continue

        # Every JSON body sent to the chat completions API should include max_tokens
        has_max_tokens = bool(re.search(r"\bmax_tokens\s*:", content))
        if not has_max_tokens:
            issues.append({
                "func":   name,
                "reason": (
                    f"{name}/index.ts makes Groq chat completion calls but "
                    f"does not set max_tokens — uncapped generation consumes "
                    f"the entire TPM budget, causing 429s for subsequent requests"
                ),
            })
    return issues


# ── Check 3: Both 413 and 429 handled in the fallback loop ───────────────────

def check_error_handling(func_names):
    """
    The fallback loop must handle both 429 AND 413:
    - 429 (Too Many Requests): rate limit hit — try next model
    - 413 (Request Entity Too Large): prompt too large for this model's context
      window — try next model with a larger window

    Handling only 429 is a common mistake. A large prompt (e.g., a complex
    BOM/SOW with 40+ items) that exceeds llama-3.1-8b's 8K context will get
    a 413 and permanently fail instead of falling back to llama-3.3-70b (32K).
    """
    issues = []
    for name in func_names:
        content, path = read_function(name)
        if content is None:
            continue

        has_chat_call = bool(re.search(r"openai/v1/chat/completions", content))
        if not has_chat_call:
            continue

        has_429 = bool(re.search(r"429", content))
        has_413 = bool(re.search(r"413", content))

        if not has_429:
            issues.append({
                "func":   name,
                "reason": (
                    f"{name}/index.ts does not handle HTTP 429 (rate limit) "
                    f"in the Groq fallback loop — rate limit hits will not "
                    f"trigger a fallback to the next model"
                ),
            })
        if not has_413:
            issues.append({
                "func":   name,
                "reason": (
                    f"{name}/index.ts does not handle HTTP 413 (payload too large) "
                    f"in the Groq fallback loop — large prompts will permanently "
                    f"fail instead of falling back to a model with a larger context window"
                ),
            })
    return issues


# ── Check 4: GROQ_API_KEY validated before making calls ──────────────────────

def check_api_key_validation(func_names):
    """
    Every function that calls the Groq API must validate GROQ_API_KEY
    at the start of the callGroq helper. If the key is missing (not set
    in Supabase Edge Function secrets), all calls fail with a cryptic 401.
    An explicit key check produces a clear error message immediately.

    Acceptable patterns:
    - if (!GROQ_KEY) throw new Error("GROQ_API_KEY not set")
    - if (!GROQ_API_KEY) { ... use fallback ... }
    Both throw and graceful-fallback are acceptable.
    """
    issues = []
    for name in func_names:
        content, path = read_function(name)
        if content is None:
            issues.append({
                "func":   name,
                "reason": f"{path} not found",
            })
            continue

        has_groq_call = bool(re.search(r"api\.groq\.com", content))
        if not has_groq_call:
            continue   # function doesn't call Groq, skip

        # Check for key validation pattern
        has_key_check = bool(re.search(
            r"if\s*\(\s*!GROQ(?:_API)?_KEY\s*\)",
            content
        ))
        if not has_key_check:
            issues.append({
                "func":   name,
                "reason": (
                    f"{name}/index.ts calls Groq but does not validate "
                    f"GROQ_API_KEY before making requests — a missing secret "
                    f"produces a cryptic 401 instead of a clear error message"
                ),
            })
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("\n" + "=" * 70)
print("Groq Fallback Chain Validator")
print("=" * 70)
print(f"\n  Checking {len(LLM_FUNCTIONS)} LLM-calling functions: "
      f"{', '.join(LLM_FUNCTIONS)}")
print(f"  API key validation includes {len(ALL_GROQ_FUNCTIONS)} Groq-calling functions\n")

fail_count = 0
warn_count = 0
report     = {}

checks = [
    (
        f"[1] Every LLM function has a multi-model fallback chain (>= {MIN_CHAIN_MODELS} models)",
        check_fallback_chains(LLM_FUNCTIONS),
        "FAIL",
    ),
    (
        "[2] max_tokens set on every Groq chat completion call",
        check_max_tokens(LLM_FUNCTIONS),
        "FAIL",
    ),
    (
        "[3] Both 413 and 429 handled in every fallback loop",
        check_error_handling(LLM_FUNCTIONS),
        "FAIL",
    ),
    (
        "[4] GROQ_API_KEY validated before use in all Groq-calling functions",
        check_api_key_validation(ALL_GROQ_FUNCTIONS),
        "FAIL",
    ),
]

for label, issues, severity in checks:
    print(f"\n{label}\n")
    if not issues:
        print("  PASS")
    else:
        for iss in issues:
            print(f"  {severity}  {iss.get('func', '?')}")
            print(f"        {iss['reason']}")
        if severity == "FAIL":
            fail_count += len(issues)
        else:
            warn_count += len(issues)
    report[label] = issues

print(f"\n{'=' * 70}")
print(f"Result: {fail_count} FAIL  {warn_count} WARN")

with open("groq_fallback_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved groq_fallback_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll Groq fallback checks PASS.")
