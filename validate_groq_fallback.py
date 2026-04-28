"""
Groq Fallback Chain Validator — WorkHive Platform
==================================================
WorkHive's AI features depend entirely on Groq for LLM calls and
embeddings. Groq's free tier imposes TPM (tokens per minute) limits
per model — a single model call that hits a rate limit returns nothing.

  Layer 1 — Chain resilience
    1.  Multi-model fallback chain     — every LLM function needs >= 2 models

  Layer 2 — Token budget safety
    2.  max_tokens on every call       — uncapped calls exhaust TPM, causing 429s

  Layer 3 — Error handling completeness
    3.  413 and 429 both handled       — large prompts fall back, not permanently fail
    4.  GROQ_API_KEY validated upfront — missing key gives cryptic 401 deep in retry loop

  Layer 4 — Call hygiene
    5.  No deprecated model IDs        — stale model names return 404 silently
    6.  AbortSignal timeout on calls   — hanging Groq fetch blocks the edge function forever

Usage:  python validate_groq_fallback.py
Output: groq_fallback_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

FUNCTIONS_DIR = os.path.join("supabase", "functions")

LLM_FUNCTIONS = [
    "ai-orchestrator",
    "engineering-calc-agent",
    "engineering-bom-sow",
    "scheduled-agents",
]

ALL_GROQ_FUNCTIONS = LLM_FUNCTIONS + ["semantic-search", "embed-entry"]

MIN_CHAIN_MODELS = 2

# Model IDs confirmed deprecated by Groq — using these returns 404
DEPRECATED_MODELS = {
    "llama2-70b-4096",
    "llama3-70b-8192",
    "llama3-8b-8192",
    "llama3-groq-70b-8192-tool-use-preview",
    "llama3-groq-8b-8192-tool-use-preview",
    "mixtral-8x7b-32768",
    "gemma-7b-it",
    "llama-3.1-70b-versatile",   # superseded by llama-3.3-70b-versatile
}


def read_function(name):
    path = os.path.join(FUNCTIONS_DIR, name, "index.ts")
    try:
        with open(path, encoding="utf-8") as f:
            return f.read(), path
    except FileNotFoundError:
        return None, path


# ── Layer 1: Chain resilience ─────────────────────────────────────────────────

def check_fallback_chains(func_names):
    """Every LLM-calling function must declare a fallback chain constant with
    >= 2 models. A single model has zero rate-limit resilience."""
    issues = []
    for name in func_names:
        content, path = read_function(name)
        if content is None:
            issues.append({"check": "fallback_chains", "func": name,
                           "reason": f"{path} not found — cannot verify fallback chain"})
            continue
        chain_m = re.search(
            r"(?:GROQ_CHAIN|GROQ_FALLBACK_CHAIN|GROQ_NARRATIVE_CHAIN)\s*=\s*\[([\s\S]+?)\]",
            content
        )
        if not chain_m:
            issues.append({"check": "fallback_chains", "func": name,
                           "reason": (f"{name}/index.ts has no Groq fallback chain constant — "
                                      f"a single rate limit hit will return no AI response")})
            continue
        models = re.findall(r'["\']([^"\']+)["\']', chain_m.group(1))
        if len(models) < MIN_CHAIN_MODELS:
            issues.append({"check": "fallback_chains", "func": name,
                           "reason": (f"{name}/index.ts chain has only {len(models)} model(s) "
                                      f"(minimum {MIN_CHAIN_MODELS}) — insufficient rate limit resilience")})
    return issues


# ── Layer 2: Token budget safety ──────────────────────────────────────────────

def check_max_tokens(func_names):
    """max_tokens must be set on every Groq chat completion call body — uncapped
    generation consumes the entire TPM budget, causing 429s for subsequent requests."""
    issues = []
    for name in func_names:
        content, path = read_function(name)
        if content is None:
            continue
        if not re.search(r"openai/v1/chat/completions", content):
            continue
        if not re.search(r"\bmax_tokens\s*:", content):
            issues.append({"check": "max_tokens", "func": name,
                           "reason": (f"{name}/index.ts makes Groq chat calls but does not set "
                                      f"max_tokens — uncapped generation exhausts the TPM budget")})
    return issues


# ── Layer 3: Error handling completeness ─────────────────────────────────────

def check_error_handling(func_names):
    """Both 429 (rate limit) and 413 (payload too large) must trigger fallback.
    Handling only 429 means large prompts permanently fail instead of falling back."""
    issues = []
    for name in func_names:
        content, path = read_function(name)
        if content is None:
            continue
        if not re.search(r"openai/v1/chat/completions", content):
            continue
        if not re.search(r"429", content):
            issues.append({"check": "error_handling", "func": name,
                           "reason": (f"{name}/index.ts does not handle HTTP 429 — "
                                      f"rate limit hits will not trigger model fallback")})
        if not re.search(r"413", content):
            issues.append({"check": "error_handling", "func": name,
                           "reason": (f"{name}/index.ts does not handle HTTP 413 — "
                                      f"large prompts permanently fail instead of falling back")})
    return issues


def check_api_key_validation(func_names):
    """GROQ_API_KEY must be validated before making any calls — a missing secret
    produces a cryptic 401 deep in the retry loop."""
    issues = []
    for name in func_names:
        content, path = read_function(name)
        if content is None:
            issues.append({"check": "api_key_validation", "func": name,
                           "reason": f"{path} not found"})
            continue
        if not re.search(r"api\.groq\.com", content):
            continue
        if not re.search(r"if\s*\(\s*!GROQ(?:_API)?_KEY\s*\)", content):
            issues.append({"check": "api_key_validation", "func": name,
                           "reason": (f"{name}/index.ts calls Groq but does not validate "
                                      f"GROQ_API_KEY upfront — missing secret gives cryptic 401")})
    return issues


# ── Layer 4: Call hygiene ─────────────────────────────────────────────────────

def check_deprecated_models(func_names):
    """
    Chain arrays must not contain model IDs deprecated by Groq. Deprecated models
    return a 404 or specific error — the fallback loop catches it and moves on,
    but a deprecated primary model wastes the first attempt on every call and
    causes visible latency. As Groq retires older models, stale IDs become
    silent performance drains.
    """
    issues = []
    for name in func_names:
        content, path = read_function(name)
        if content is None:
            continue
        chain_m = re.search(
            r"(?:GROQ_CHAIN|GROQ_FALLBACK_CHAIN|GROQ_NARRATIVE_CHAIN)\s*=\s*\[([\s\S]+?)\]",
            content
        )
        if not chain_m:
            continue
        models = re.findall(r'["\']([^"\']+)["\']', chain_m.group(1))
        for model in models:
            if model in DEPRECATED_MODELS:
                issues.append({"check": "deprecated_models", "func": name,
                               "reason": (f"{name}/index.ts chain contains deprecated model "
                                          f"'{model}' — Groq has retired this ID; "
                                          f"replace with a current model (e.g. llama-3.3-70b-versatile)")})
    return issues


def check_groq_timeout(func_names):
    """
    Every fetch() to the Groq API must include an AbortSignal timeout.
    Without it, a slow or unresponsive Groq endpoint hangs the edge function
    until Supabase's 150-second wall clock limit, blocking the worker's entire
    request. engineering-calc-agent already uses AbortSignal.timeout(60000) —
    the other LLM functions are missing this guard.

    Correct pattern: signal: AbortSignal.timeout(60000)
    """
    issues = []
    for name in func_names:
        content, path = read_function(name)
        if content is None:
            continue
        if not re.search(r"api\.groq\.com|openai/v1/chat/completions|openai/v1/embeddings", content):
            continue
        has_timeout = bool(re.search(r"AbortSignal\.timeout|AbortController", content))
        if not has_timeout:
            issues.append({"check": "groq_timeout", "func": name,
                           "reason": (f"{name}/index.ts makes Groq API calls but has no "
                                      f"AbortSignal.timeout() — a slow Groq response hangs "
                                      f"the edge function until Supabase's 150s wall clock limit; "
                                      f"add signal: AbortSignal.timeout(60000) to every Groq fetch()")})
    return issues


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "fallback_chains",
    "max_tokens",
    "error_handling",
    "api_key_validation",
    "deprecated_models",
    "groq_timeout",
]

CHECK_LABELS = {
    "fallback_chains":    "L1  Every LLM function has a multi-model fallback chain",
    "max_tokens":         "L2  max_tokens set on every Groq chat completion call",
    "error_handling":     "L3  Both 413 and 429 handled in every fallback loop",
    "api_key_validation": "L3  GROQ_API_KEY validated before use in all Groq functions",
    "deprecated_models":  "L4  No deprecated Groq model IDs in chain constants",
    "groq_timeout":       "L4  AbortSignal.timeout() on all Groq fetch() calls",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nGroq Fallback Chain Validator (4-layer)"))
    print("=" * 55)
    print(f"  {len(LLM_FUNCTIONS)} LLM functions: {', '.join(LLM_FUNCTIONS)}\n")

    all_issues = []
    all_issues += check_fallback_chains(LLM_FUNCTIONS)
    all_issues += check_max_tokens(LLM_FUNCTIONS)
    all_issues += check_error_handling(LLM_FUNCTIONS)
    all_issues += check_api_key_validation(ALL_GROQ_FUNCTIONS)
    all_issues += check_deprecated_models(LLM_FUNCTIONS)
    all_issues += check_groq_timeout(ALL_GROQ_FUNCTIONS)

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "groq_fallback",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("groq_fallback_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
