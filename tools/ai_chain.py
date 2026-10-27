"""
Python mirror of supabase/functions/_shared/ai-chain.ts

WHY THIS EXISTS:
The platform's TypeScript edge functions route every AI call through a
free-tier fallback chain (Groq -> Gemini -> Mistral -> OpenRouter :free, code
models last). The Python side previously had a 3-model shortcut that would blow
through Groq's 30-req/min limit, exhaust its second provider, and then dead-end
because OpenRouter wasn't always keyed.

PACED (2026-10-08): these calls spend the SAME provider keys as the live platform. Every call goes
through tools/lib/chain_pacer.process_pacer(): at least WH_AI_MIN_GAP_S (3 s) between calls in one
process, at most WH_AI_MAX_CALLS (90) per process, and once every provider has answered 429 on two
calls in a row the next calls return "{}" without sending anything ("QUOTA EXHAUSTED").

This module is the SINGLE source of truth for Python AI calls. All Python
tools (video_idea_generator, platform_pack, future agents) should import
call_ai_chain() from here. NEVER call provider SDKs directly. NEVER hardcode
a model anywhere else.

Order: fastest / most generous limits first, deeper fallbacks last.
Only permanently free tiers — no credits that expire.

API mirrors callAI() in ai-chain.ts:
  call_ai_chain(prompt, system_prompt=None, temperature=0.2,
                max_tokens=1024, json_mode=True) -> str

On total failure (no key set, every provider 429s, all timeouts), returns
the literal string "{}" to mirror TS behaviour — callers parse it as empty
JSON and handle gracefully rather than crashing.
"""

import os
import json
import time
import requests
from pathlib import Path

# Single-source the reasoning-strip (mirror TS stripReasoningBlocks) from lib.ai_chain
# so the <think>/untagged-persona-scaffold regexes never drift between the two Python mirrors.
try:
    from lib.ai_chain import _strip_reasoning_blocks
except ImportError:  # invoked as `python -m tools.ai_chain` or from repo root
    try:
        from tools.lib.ai_chain import _strip_reasoning_blocks
    except ImportError:
        def _strip_reasoning_blocks(t):  # last-resort no-op (keeps tools working)
            return (t or "").strip()


def _load_env():
    """Mirror the loader pattern used by video_idea_generator.py +
    platform_intel.py so standalone CLI calls (e.g.,
    `python tools/scaffold_article.py`) pick up API keys from .env without
    needing the Flask app to be running. Idempotent: never overrides
    already-set env vars (setdefault). Safe to call at module import time."""
    root = Path(__file__).parent.parent
    for p in [root / ".env", root / "supabase/functions/.env",
              root / "test-data-seeder/.env"]:
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())


_load_env()


# ── Provider chain (mirror of PROVIDER_CHAIN in ai-chain.ts) ─────────────────

PROVIDER_CHAIN = [
    # ── Tier 1: Groq — custom LPU hardware, fastest inference ────────────────
    # ★MIRRORED 2026-09-10: seven of the first nine entries named models that no longer exist,
    # measured against each provider's own /models endpoint with this platform's own keys. The dead
    # Groq names were meta-llama/llama-4-scout-17b-16e-instruct, llama-3.3-70b-versatile,
    # qwen/qwen3-32b and llama-3.1-8b-instant; all three Cerebras names were dead too. So every AI
    # call collected four 404s before openai/gpt-oss-20b answered, and the Cerebras tier was inert.
    # `validate_groq_fallback.check_models_are_live` now ASKS each provider rather than consulting a
    # deny-list, so this can be caught the day it happens instead of months later.
    # Qwen3.8 27B: 131K context, text AND image (the provider reports input_modalities), tools+json.
    {"provider": "groq",     "base_url": "https://api.groq.com/openai/v1",  "model": "qwen/qwen3.8-27b",                          "env_key": "GROQ_API_KEY"},
    # 2026-09-28 (v6): `qwen/qwen3.6-27b` removed — Groq no longer serves it, and of the eleven ids
    # Groq returns today only qwen3.8-27b (above) accepts images, so there is no second Groq vision
    # model to fall back to. Mirrors _shared/ai-chain.ts.
    # GPT-OSS 20B: strict JSON-schema adherence (structured_outputs), cheapest per token.
    # v9 (2026-10-08): reasoning_effort "low" on both gpt-oss entries - at the default effort the reasoning spent the
    # whole max_tokens and Groq answered 400 json_validate_failed (failed_generation ""). Mirrors the TS chain.
    {"provider": "groq",     "base_url": "https://api.groq.com/openai/v1",  "model": "openai/gpt-oss-20b",                        "env_key": "GROQ_API_KEY", "extra_body": {"reasoning_effort": "low"}},
    # GPT-OSS 120B: largest model on Groq free tier — last quality resort.
    {"provider": "groq",     "base_url": "https://api.groq.com/openai/v1",  "model": "openai/gpt-oss-120b",                       "env_key": "GROQ_API_KEY", "extra_body": {"reasoning_effort": "low"}},
    # 2026-09-28 (v6): `groq/compound-mini` removed — Groq no longer serves it, and its only other
    # live general chat models are the two gpt-oss entries already above. Mirrors _shared/ai-chain.ts.

    # (Tier 2 was Cerebras: REMOVED from the platform 2026-10-08 - 402 payment_required on every call since
    # 2026-09-10. Its slots went to gemini-3.1-flash-lite and mistral-small-latest. Mirrors the TS chain.)

    # NOTE: SambaNova was evaluated (FreeLLMAPI lists it) but REJECTED — its
    # free tier is $5 of credits that expire in 30 days, not permanently free.

    # ── Tier 3: Google Gemini — OpenAI-compat endpoint, 250K TPM, vision ──────
    # Use an AI Studio key (aistudio.google.com), NOT a GCP Console key (limit:0).
    {"provider": "google",   "base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "model": "gemini-2.5-flash",      "env_key": "GEMINI_API_KEY", "extra_body": {"reasoning_effort": "none"}},
    # v10 (2026-10-08): a separate per-model free quota; "low" thinking kept a 320-token JSON answer whole.
    {"provider": "google",   "base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "model": "gemini-3.1-flash-lite", "env_key": "GEMINI_API_KEY", "extra_body": {"reasoning_effort": "low"}},
    {"provider": "google",   "base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "model": "gemini-2.5-flash-lite", "env_key": "GEMINI_API_KEY"},

    # ── Tier 4: Mistral — 500K TPM but only 2 RPM, OpenAI-compatible ──────────
    {"provider": "mistral",  "base_url": "https://api.mistral.ai/v1",        "model": "mistral-medium-latest",                      "env_key": "MISTRAL_API_KEY"},
    # v9 (2026-10-08): fills a slot Cerebras held. Mirrors the TS chain.
    {"provider": "mistral",  "base_url": "https://api.mistral.ai/v1",        "model": "mistral-small-latest",                       "env_key": "MISTRAL_API_KEY"},

    # ── Tier 5: OpenRouter — :free models, $0/token, 200 req/day ─────────────
    {"provider": "openrouter", "base_url": "https://openrouter.ai/api/v1",  "model": "google/gemma-4-31b-it:free",                "env_key": "OPENROUTER_API_KEY", "extra_headers": {"HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive"}},
    {"provider": "openrouter", "base_url": "https://openrouter.ai/api/v1",  "model": "google/gemma-4-26b-a4b-it:free",            "env_key": "OPENROUTER_API_KEY", "extra_headers": {"HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive"}},
    {"provider": "openrouter", "base_url": "https://openrouter.ai/api/v1",  "model": "nvidia/nemotron-3-ultra-550b-a55b:free",    "env_key": "OPENROUTER_API_KEY", "extra_headers": {"HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive"}},
    # 2026-09-28 (v6): was `nex-agi/nex-n2.5-mini:free`, which OpenRouter no longer serves; replaced
    # from its live :free list by reported input_modalities (text,image,video). Mirrors the TS chain.
    # 2026-10-07 (v7): qwen3.8-27b:free is gone too (404); dots-3-note-preview:free answered (text,image). Mirrors the TS chain.
    {"provider": "openrouter", "base_url": "https://openrouter.ai/api/v1",  "model": "dots-studio/dots-3-note-preview:free",                    "env_key": "OPENROUTER_API_KEY", "extra_headers": {"HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive"}},
    # v8 (2026-10-07): code-specialist models are last resorts for general calls (mirrors the TS chain).
    {"provider": "mistral",  "base_url": "https://api.mistral.ai/v1",        "model": "codestral-latest",                          "env_key": "MISTRAL_API_KEY"},
    {"provider": "openrouter", "base_url": "https://openrouter.ai/api/v1",  "model": "poolside/laguna-s-2.1:free",                  "env_key": "OPENROUTER_API_KEY", "extra_headers": {"HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive"}},
]


def call_ai_chain(
    prompt: str,
    system_prompt: str | None = None,
    temperature: float        = 0.6,
    max_tokens:  int          = 4096,
    json_mode:   bool         = False,
    timeout:     int          = 90,
    prefer_model: str | None  = None,
    messages:    list | None  = None,
) -> str:
    """
    Walk the fallback chain top-to-bottom. Return the first non-empty content.
    Return "{}" if every provider is unkeyed, rate-limited, or errors.

    Args:
        prompt: user message text.
        system_prompt: optional system instruction.
        temperature: 0.0-1.0. Lower = deterministic, higher = creative.
        max_tokens: response length cap.
        json_mode: if True, request JSON object response (OpenAI-compatible).
        timeout: per-provider HTTP timeout in seconds.
        prefer_model: optional substring match against entry['model']; entries
            matching this substring are tried FIRST, before the standard chain
            order. Useful when a task needs a specific model trait (e.g.,
            'gpt-oss-20b' for strict JSON-schema adherence). The rest of the
            chain still serves as fallback.
        messages: an OpenAI-format messages list to send instead of prompt/system_prompt (multi-turn callers).
    """
    if messages is None:
        messages = (
            [{"role": "system", "content": system_prompt},
             {"role": "user",   "content": prompt}]
            if system_prompt else
            [{"role": "user",   "content": prompt}]
        )
    pm = _pacer()
    pacer = pm.process_pacer()
    _LAST.clear()
    _LAST.update({"statuses": [], "served_by": None})
    if not pacer.wait():
        print(f"  [ai-chain] {pacer.stop_reason} - nothing sent, returning empty JSON")
        return "{}"

    # Re-order chain to put preferred model entries first, preserving the
    # rest as fallbacks. Substring-match is intentional (so "gpt-oss-20b"
    # matches "openai/gpt-oss-20b" without exact-string fragility).
    chain = list(PROVIDER_CHAIN)
    if prefer_model:
        preferred = [e for e in chain if prefer_model in e["model"]]
        rest      = [e for e in chain if prefer_model not in e["model"]]
        chain = preferred + rest

    for entry in chain:
        api_key = os.environ.get(entry["env_key"], "").strip()
        if not api_key:
            continue

        effective_max_tokens = min(max_tokens, entry["max_tokens_cap"]) \
            if entry.get("max_tokens_cap") else max_tokens

        headers = {
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {api_key}",
            **entry.get("extra_headers", {}),
        }
        body = {
            "model":       entry["model"],
            "messages":    messages,
            "temperature": temperature,
            "max_tokens":  effective_max_tokens,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        body.update(entry.get("extra_body") or {})   # provider-specific fields, as ai-chain.ts extraBody

        try:
            res = requests.post(
                f"{entry['base_url']}/chat/completions",
                headers=headers,
                json=body,
                timeout=timeout,
            )
        except Exception as exc:
            print(f"  [ai-chain] {entry['provider']}/{entry['model']} threw: "
                  f"{str(exc)[:80]} — trying next")
            _LAST["statuses"].append(0)
            continue
        _LAST["statuses"].append(res.status_code)

        # 429 (rate-limited), 413 (payload too large), 503 (unavailable) -> next
        if res.status_code in (429, 413, 503):
            print(f"  [ai-chain] {entry['provider']}/{entry['model']} "
                  f"skipped (HTTP {res.status_code})")
            continue

        if not res.ok:
            err = res.text[:120].replace("\n", " ")
            print(f"  [ai-chain] {entry['provider']}/{entry['model']} "
                  f"error {res.status_code}: {err} — trying next")
            continue

        try:
            data = res.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content")
        except Exception as exc:
            print(f"  [ai-chain] {entry['provider']}/{entry['model']} "
                  f"parse fail: {exc} — trying next")
            continue

        content = _strip_reasoning_blocks(content or "")
        if content:
            print(f"  [ai-chain] served by {entry['provider']} / {entry['model']}")
            _LAST["served_by"] = f"{entry['provider']}/{entry['model']}"
            pacer.record("served")
            return content

        print(f"  [ai-chain] {entry['provider']}/{entry['model']} "
              f"returned empty/reasoning-only content — trying next")

    print("  [ai-chain] ALL providers exhausted. Returning empty JSON.")
    pacer.record(pm.outcome_from_statuses(_LAST["statuses"], served=False))
    return "{}"


_LAST: dict = {}


def last_outcome() -> dict:
    """What the most recent call_ai_chain() did: {"statuses": [HTTP status per entry asked], "served_by": "p/model"|None}."""
    return dict(_LAST)


def _pacer():
    """The process-wide pacer from tools/lib/chain_pacer.py, loaded by file path so it is ONE object whichever mirror
    (and whichever sys.path layout) the caller came through."""
    import importlib.util
    import sys as _sys
    mod = _sys.modules.get("wh_chain_pacer")
    if mod is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib", "chain_pacer.py")
        spec = importlib.util.spec_from_file_location("wh_chain_pacer", path)
        mod = importlib.util.module_from_spec(spec)
        _sys.modules["wh_chain_pacer"] = mod
        spec.loader.exec_module(mod)
    return mod

