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
import os
import json
import urllib.request
from pathlib import Path
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
    """Pull every model string from the PROVIDER_CHAIN array.

    ★THIS READ THE KEY AS QUOTED AND THE FILE WRITES IT BARE (found 2026-09-10). The pattern was
    `"model"\\s*:\\s*"..."`, but `_shared/ai-chain.ts` is TypeScript source, not JSON - it writes
    `model: "openai/gpt-oss-20b"` with an UNQUOTED key. So this returned an empty list, and
    `check_no_banned_models` iterated over nothing and reported clean, every run, for its whole
    life: 14 banned model IDs checked against 0 models. Measured at the moment of the fix - the
    gate could see 0 while the file held 19.

    That is not a cosmetic miss. Asked of the live provider the same day, FOUR of the six Groq
    entries were 404 - `meta-llama/llama-4-scout-17b-16e-instruct`, `llama-3.3-70b-versatile`,
    `qwen/qwen3-32b`, `llama-3.1-8b-instant` - so every AI call on the platform walked four
    guaranteed failures before reaching `openai/gpt-oss-20b`. The deny-list is also the wrong
    shape for the job (it only ever catches a name someone remembered to add); see
    check_models_are_live below, which asks the provider instead of a list.
    """
    chain_m = re.search(r"const PROVIDER_CHAIN[^=]*=\s*\[([\s\S]+?)\];", content)
    if not chain_m:
        return []
    return re.findall(r'\bmodel\s*:\s*"([^"]+)"', chain_m.group(1))


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


def _env_value(key):
    """Read a provider key from the function env files without importing anything."""
    for p in (Path("supabase/functions/.env"), Path(".env")):
        try:
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith(key + "="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            continue
    return os.environ.get(key)


# Providers that publish an OpenAI-compatible /models list. A provider absent from here is simply
# not liveness-checked - stated in the output rather than silently skipped.
#
# ★COVER EVERY PROVIDER, NOT THE TWO THAT PROMPTED THE FIX (2026-09-10). The first version asked only
# Groq and Cerebras, found 7 dead names, and looked finished. Asking the other three found FOUR MORE -
# `mistral-large-latest`, `openai/gpt-oss-120b:free`, `meta-llama/llama-3.3-70b-instruct:free` and
# `google/gemma-3-27b-it:free` - so 11 of the 18 entries were dead, not 7 of 9. A gate that watches
# part of the chain reports on part of the chain; the un-watched half is exactly where rot survives.
# `None` as the key means the list is public (OpenRouter), not that the check is skipped.
LIVE_LIST_ENDPOINTS = {
    "groq":       ("https://api.groq.com/openai/v1/models",                          "GROQ_API_KEY"),
    "cerebras":   ("https://api.cerebras.ai/v1/models",                              "CEREBRAS_API_KEY"),
    "google":     ("https://generativelanguage.googleapis.com/v1beta/openai/models", "GEMINI_API_KEY"),
    "mistral":    ("https://api.mistral.ai/v1/models",                               "MISTRAL_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1/models",                            None),
}


def check_models_are_live():
    """Ask each provider which models it actually serves, and fail on any that is gone.

    ★A DENY-LIST ONLY CATCHES WHAT SOMEONE REMEMBERED TO ADD (2026-09-10). `BANNED_MODELS` holds 14
    names retired at some past moment by a human who noticed. Nothing in this file could notice a
    model retiring TODAY - and four had. Asked of Groq's own /models endpoint with the platform's own
    working key, `meta-llama/llama-4-scout-17b-16e-instruct`, `llama-3.3-70b-versatile`,
    `qwen/qwen3-32b` and `llama-3.1-8b-instant` were all absent: the first FOUR entries of the Groq
    tier, so every AI call fell through four guaranteed 404s before reaching `openai/gpt-oss-20b`.
    `voice-model-call`, which carries its own chain, had NO live entry at all and answered every
    caller "All models failed (rate limited or down)" - a diagnosis it had no evidence for.

    Derive the truth from the provider instead of from a list, exactly as the SRI gate's page scope
    is derived from the deploy and the page roster from the git tree.

    NETWORK-OPTIONAL BY DESIGN: with no key or no reachable provider this SKIPS and says which
    provider it could not ask - it never invents a pass, and never fails the board for being offline.
    """
    issues = []
    content = read_shared_chain()
    if content is None:
        return issues

    chain_m = re.search(r"const PROVIDER_CHAIN[^=]*=\s*\[([\s\S]+?)\];", content)
    if not chain_m:
        return issues
    pairs = re.findall(r'provider:\s*"(\w+)"[^}]*?\bmodel:\s*"([^"]+)"', chain_m.group(1))

    checked = skipped = 0
    for provider, (url, env_key) in LIVE_LIST_ENDPOINTS.items():
        want = [m for p, m in pairs if p == provider]
        if not want:
            continue
        key = _env_value(env_key) if env_key else ""
        if env_key and not key:
            skipped += 1
            print(f"    (liveness: {provider} not asked - {env_key} is not set here)")
            continue
        try:
            # A default `Python-urllib/3.x` User-Agent is refused with 403 by the provider edge
            # (curl with the SAME key succeeds), which would have made this check skip forever while
            # reporting a tidy reason - a silent no-op wearing a good excuse.
            headers = {"User-Agent": "workhive-chain-validator/1.0", "Accept": "application/json"}
            if key:
                headers["Authorization"] = f"Bearer {key}"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=25) as r:
                # Google's OpenAI-compat list prefixes every id with "models/" - compare like with like
                live = {str(m.get("id", "")).replace("models/", "")
                        for m in json.loads(r.read().decode("utf-8")).get("data", [])}
        except Exception as e:
            skipped += 1
            print(f"    (liveness: {provider} not asked - {type(e).__name__}: {str(e)[:60]})")
            continue
        if not live:
            skipped += 1
            continue
        checked += 1
        for m in want:
            if m not in live:
                issues.append({"check": "models_are_live", "reason":
                               f"_shared/ai-chain.ts lists '{m}' for {provider}, but {provider} does "
                               f"not serve it - every call falls through this entry with a 404"})
    if checked:
        print(f"    (liveness: asked {checked} provider(s); {skipped} not asked)")
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
        # P1 roadmap 2026-05-27 turn 7: skip CODE blocks that USE entries
        # rather than DEFINE them. The provider-health autoswitch + cache
        # wiring introduced for-loop bodies that reference `entry.provider`
        # but aren't themselves chain entries. Heuristic: real chain entries
        # have `provider:` as a KEY (not `entry.provider` as a value).
        if "entry.provider" in block or "entry.envKey" in block or "entry.model" in block:
            continue
        # Real chain entries always have `provider:` (key form), not just `provider` substring.
        if not re.search(r"\bprovider\s*:", block):
            continue
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
    "models_are_live",
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
    "models_are_live":     "L1  Every configured model still EXISTS at its provider (asked, not assumed)",
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
    all_issues += check_models_are_live()
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
