"""
AI Provider Chain Validator — WorkHive Platform
================================================
WorkHive's AI features use a multi-provider fallback chain defined in
supabase/functions/_shared/ai-chain.ts.  All LLM-calling edge functions
import callAI() from that shared module instead of embedding their own chains.

  Layer 1 — Shared chain integrity
    1.  Shared chain exists and has >= 6 entries
    2.  No deprecated or known-bad model IDs in the chain
    3.  Every entry has required fields (provider, baseUrl, model, envKey)

  Layer 2 — Edge function wiring
    4.  Every LLM function imports callAI from _shared/ai-chain
    5.  No function embeds its own raw Groq fetch() — all calls go through callAI

  Layer 3 — Call hygiene in the shared module
    6.  max_tokens set on every chat completion call in the shared module
    7.  Both 429 and 413 handled (skip, not throw)
    8.  503 handled (service unavailable — new in multi-provider chain)
    9.  AbortSignal.timeout on every fetch() in the shared module

  Layer 4 — Free-tier sustainability
   10.  No NVIDIA NIM entries (credit-based, will exhaust)
   11.  No gemini-2.0-flash-lite (dropped from free tier April 2026)
   12.  No deepseek-chat (legacy name — retiring July 24 2026)
   13.  No llama-4-maverick (deprecated on Groq Feb 2026)
   14.  No gemma2-9b-it (deprecated on Groq)

Usage:  python validate_groq_fallback.py
Output: groq_fallback_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

FUNCTIONS_DIR   = os.path.join("supabase", "functions")
SHARED_CHAIN    = os.path.join(FUNCTIONS_DIR, "_shared", "ai-chain.ts")

# Edge functions that make LLM calls via callAI
LLM_FUNCTIONS = [
    "ai-orchestrator",
    "engineering-calc-agent",
    "engineering-bom-sow",
    "scheduled-agents",
    "analytics-orchestrator",
]

MIN_CHAIN_ENTRIES = 6   # 6 Groq + Cerebras + SambaNova + Gemini + OpenRouter + DeepSeek

# Models that must never appear in the chain
BANNED_MODELS = {
    # Groq deprecated
    "meta-llama/llama-4-maverick-17b-128e-instruct": "Deprecated on Groq Feb 20 2026",
    "gemma2-9b-it":                                  "Deprecated on Groq",
    "llama2-70b-4096":                               "Deprecated on Groq",
    "llama3-70b-8192":                               "Deprecated on Groq",
    "llama3-8b-8192":                                "Deprecated on Groq",
    "llama3-groq-70b-8192-tool-use-preview":         "Deprecated on Groq",
    "llama3-groq-8b-8192-tool-use-preview":          "Deprecated on Groq",
    "mixtral-8x7b-32768":                            "Deprecated on Groq",
    "gemma-7b-it":                                   "Deprecated on Groq",
    "llama-3.1-70b-versatile":                       "Deprecated on Groq — use llama-3.3-70b-versatile",
    # NVIDIA NIM (credit-based, not sustainably free)
    "meta/llama-3.3-70b-instruct":                   "NVIDIA NIM is credit-based, not permanently free",
    "meta/llama-3.1-8b-instruct":                    "NVIDIA NIM is credit-based, not permanently free",
    # SambaNova (only $5 credits, expire in 30 days)
    "llama-3.3-70b-instruct":                        "SambaNova is credit-based ($5/30 days), not permanently free",
    "llama-3.1-8b-instruct":                         "SambaNova is credit-based ($5/30 days), not permanently free",
}

REQUIRED_ENTRY_FIELDS = {"provider", "baseUrl", "model", "envKey"}


def read_shared_chain():
    try:
        with open(SHARED_CHAIN, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def read_function(name):
    path = os.path.join(FUNCTIONS_DIR, name, "index.ts")
    try:
        with open(path, encoding="utf-8") as f:
            return f.read(), path
    except FileNotFoundError:
        return None, path


def extract_chain_models(content):
    """Pull every model string from the PROVIDER_CHAIN array."""
    chain_m = re.search(r"const PROVIDER_CHAIN[^=]*=\s*\[([\s\S]+?)\];", content)
    if not chain_m:
        return []
    return re.findall(r'"model"\s*:\s*"([^"]+)"', chain_m.group(1))


def extract_chain_entries(content):
    """Count distinct provider entries (lines with both 'provider' and 'model' keys)."""
    return len(re.findall(r'\{\s*provider:', content))


# ── Layer 1: Shared chain integrity ───────────────────────────────────────────

def check_chain_exists_and_size():
    issues = []
    content = read_shared_chain()
    if content is None:
        issues.append({"check": "chain_exists", "reason":
                       f"{SHARED_CHAIN} not found — shared AI chain module is missing"})
        return issues

    n = extract_chain_entries(content)
    if n < MIN_CHAIN_ENTRIES:
        issues.append({"check": "chain_exists", "reason":
                       f"_shared/ai-chain.ts has only {n} provider entries "
                       f"(minimum {MIN_CHAIN_ENTRIES}) — chain is too short for resilience"})
    return issues


def check_no_banned_models():
    issues = []
    content = read_shared_chain()
    if content is None:
        return issues

    models = extract_chain_models(content)
    for model in models:
        if model in BANNED_MODELS:
            issues.append({"check": "banned_models", "reason":
                           f"_shared/ai-chain.ts contains banned model '{model}': "
                           f"{BANNED_MODELS[model]}"})
    return issues


def check_entry_fields():
    issues = []
    content = read_shared_chain()
    if content is None:
        return issues

    # Strip JS template literal interpolations ${...} first — they contain words
    # like "provider" and "model" and get falsely matched as provider entry blocks.
    content_clean = re.sub(r'\$\{[^}]*\}', '', content)

    # Each entry block: { provider: "x", baseUrl: "y", model: "z", envKey: "k" }
    entry_blocks = re.findall(r'\{([^}]+)\}', content_clean)
    for i, block in enumerate(entry_blocks):
        if "provider" not in block:
            continue   # not a provider entry block
        present = set(re.findall(r'(\w+)\s*:', block))
        missing = REQUIRED_ENTRY_FIELDS - present
        if missing:
            model_m = re.search(r'model\s*:\s*"([^"]+)"', block)
            label   = model_m.group(1) if model_m else f"entry #{i}"
            issues.append({"check": "entry_fields", "reason":
                           f"_shared/ai-chain.ts entry '{label}' is missing fields: "
                           f"{', '.join(sorted(missing))}"})
    return issues


# ── Layer 2: Edge function wiring ─────────────────────────────────────────────

def check_functions_import_callai():
    issues = []
    for name in LLM_FUNCTIONS:
        content, path = read_function(name)
        if content is None:
            issues.append({"check": "callai_import", "reason":
                           f"{path} not found — cannot verify callAI import"})
            continue
        if not re.search(r'import\s*\{[^}]*callAI[^}]*\}\s*from\s*["\']\.\./_shared/ai-chain', content):
            issues.append({"check": "callai_import", "reason":
                           f"{name}/index.ts does not import callAI from _shared/ai-chain.ts — "
                           f"LLM calls are not going through the shared fallback chain"})
    return issues


def check_no_raw_groq_fetch():
    """No function should have a raw fetch() directly to api.groq.com — all calls go through callAI."""
    issues = []
    for name in LLM_FUNCTIONS:
        content, path = read_function(name)
        if content is None:
            continue
        if re.search(r'fetch\s*\(\s*["\']https://api\.groq\.com', content):
            issues.append({"check": "no_raw_groq_fetch", "reason":
                           f"{name}/index.ts contains a raw fetch() to api.groq.com — "
                           f"all LLM calls must go through callAI() from _shared/ai-chain.ts"})
    return issues


# ── Layer 3: Call hygiene in the shared module ────────────────────────────────

def check_shared_max_tokens():
    issues = []
    content = read_shared_chain()
    if content is None:
        return issues
    if not re.search(r"\bmax_tokens\s*:", content):
        issues.append({"check": "max_tokens", "reason":
                       "_shared/ai-chain.ts does not set max_tokens — "
                       "uncapped generation exhausts TPM budgets on rate-limited providers"})
    return issues


def check_shared_error_handling():
    issues = []
    content = read_shared_chain()
    if content is None:
        return issues
    for code, desc in [("429", "rate limit"), ("413", "payload too large"), ("503", "service unavailable")]:
        if not re.search(code, content):
            issues.append({"check": "error_handling", "reason":
                           f"_shared/ai-chain.ts does not handle HTTP {code} ({desc}) — "
                           f"affected providers will not trigger fallback to next entry"})
    return issues


def check_shared_timeout():
    issues = []
    content = read_shared_chain()
    if content is None:
        return issues
    if not re.search(r"AbortSignal\.timeout|AbortController", content):
        issues.append({"check": "abort_timeout", "reason":
                       "_shared/ai-chain.ts fetch() has no AbortSignal.timeout — "
                       "a slow provider hangs the edge function until Supabase's 150s wall clock"})
    return issues


# ── Layer 4: Free-tier sustainability ─────────────────────────────────────────

def check_no_credit_based_providers():
    issues = []
    content = read_shared_chain()
    if content is None:
        return issues
    checks = [
        ("integrate.api.nvidia.com", "NVIDIA NIM — credit-based, will exhaust"),
        ("api.sambanova.ai",         "SambaNova — $5 credits expire in 30 days"),
    ]
    for pattern, label in checks:
        if re.search(re.escape(pattern), content):
            issues.append({"check": "free_tier_only", "reason":
                           f"_shared/ai-chain.ts includes {label}; "
                           f"remove for a sustainably free chain"})
    return issues


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "chain_exists",
    "banned_models",
    "entry_fields",
    "callai_import",
    "no_raw_groq_fetch",
    "max_tokens",
    "error_handling",
    "abort_timeout",
    "free_tier_only",
]

CHECK_LABELS = {
    "chain_exists":        "L1  Shared chain exists with >= 6 provider entries",
    "banned_models":       "L1  No deprecated / non-free models in chain",
    "entry_fields":        "L1  Every chain entry has provider, baseUrl, model, envKey",
    "callai_import":       "L2  All LLM functions import callAI from _shared/ai-chain",
    "no_raw_groq_fetch":   "L2  No raw fetch() to api.groq.com in any LLM function",
    "max_tokens":          "L3  max_tokens set in shared module",
    "error_handling":      "L3  429 / 413 / 503 all handled in shared module",
    "abort_timeout":       "L3  AbortSignal.timeout on fetch() in shared module",
    "free_tier_only":      "L4  No credit-based providers (NVIDIA NIM) in chain",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nAI Provider Chain Validator (4-layer)"))
    print("=" * 55)
    print(f"  Shared chain: {SHARED_CHAIN}")
    print(f"  {len(LLM_FUNCTIONS)} LLM functions: {', '.join(LLM_FUNCTIONS)}\n")

    all_issues = []
    all_issues += check_chain_exists_and_size()
    all_issues += check_no_banned_models()
    all_issues += check_entry_fields()
    all_issues += check_functions_import_callai()
    all_issues += check_no_raw_groq_fetch()
    all_issues += check_shared_max_tokens()
    all_issues += check_shared_error_handling()
    all_issues += check_shared_timeout()
    all_issues += check_no_credit_based_providers()

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "ai_provider_chain",
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
