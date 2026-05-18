"""
Python mirror of supabase/functions/_shared/ai-chain.ts

WHY THIS EXISTS:
The platform's TypeScript edge functions route every AI call through a
14-model fallback chain (6 Groq models -> 2 Cerebras -> 6 OpenRouter :free
models). The Python side previously had a 3-model shortcut that would blow
through Groq's 30-req/min limit, exhaust 1 Cerebras model, and then dead-end
because OpenRouter wasn't always keyed.

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
    # Llama 4 Scout: 30K TPM, 500K TPD (highest on Groq free tier), multimodal
    {"provider": "groq",     "base_url": "https://api.groq.com/openai/v1",  "model": "meta-llama/llama-4-scout-17b-16e-instruct", "env_key": "GROQ_API_KEY"},
    # Llama 3.3 70B: proven quality, 6K TPM
    {"provider": "groq",     "base_url": "https://api.groq.com/openai/v1",  "model": "llama-3.3-70b-versatile",                   "env_key": "GROQ_API_KEY"},
    # Qwen3 32B: 60 RPM, 500K TPD
    {"provider": "groq",     "base_url": "https://api.groq.com/openai/v1",  "model": "qwen/qwen3-32b",                            "env_key": "GROQ_API_KEY"},
    # Llama 3.1 8B: fastest, 500K TPD, high TPM
    {"provider": "groq",     "base_url": "https://api.groq.com/openai/v1",  "model": "llama-3.1-8b-instant",                      "env_key": "GROQ_API_KEY"},
    # GPT-OSS 20B: strict JSON-schema adherence, 8K TPM
    {"provider": "groq",     "base_url": "https://api.groq.com/openai/v1",  "model": "openai/gpt-oss-20b",                        "env_key": "GROQ_API_KEY"},
    # GPT-OSS 120B: largest model on Groq free tier, 8K TPM — last Groq resort
    {"provider": "groq",     "base_url": "https://api.groq.com/openai/v1",  "model": "openai/gpt-oss-120b",                       "env_key": "GROQ_API_KEY"},

    # ── Tier 2: Cerebras — 1M tokens/day free, 8K total context cap ──────────
    {"provider": "cerebras", "base_url": "https://api.cerebras.ai/v1",       "model": "llama-3.3-70b",                             "env_key": "CEREBRAS_API_KEY", "max_tokens_cap": 4096},
    {"provider": "cerebras", "base_url": "https://api.cerebras.ai/v1",       "model": "qwen-3-32b",                                "env_key": "CEREBRAS_API_KEY", "max_tokens_cap": 4096},

    # ── Tier 3: OpenRouter — :free models, $0/token, 200 req/day ─────────────
    {"provider": "openrouter", "base_url": "https://openrouter.ai/api/v1",  "model": "nvidia/nemotron-3-super-120b-a12b:free",    "env_key": "OPENROUTER_API_KEY", "extra_headers": {"HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive"}},
    {"provider": "openrouter", "base_url": "https://openrouter.ai/api/v1",  "model": "google/gemma-4-31b-it:free",                "env_key": "OPENROUTER_API_KEY", "extra_headers": {"HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive"}},
    {"provider": "openrouter", "base_url": "https://openrouter.ai/api/v1",  "model": "openai/gpt-oss-120b:free",                  "env_key": "OPENROUTER_API_KEY", "extra_headers": {"HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive"}},
    {"provider": "openrouter", "base_url": "https://openrouter.ai/api/v1",  "model": "google/gemma-4-26b-a4b-it:free",            "env_key": "OPENROUTER_API_KEY", "extra_headers": {"HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive"}},
    {"provider": "openrouter", "base_url": "https://openrouter.ai/api/v1",  "model": "meta-llama/llama-3.3-70b-instruct:free",    "env_key": "OPENROUTER_API_KEY", "extra_headers": {"HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive"}},
    {"provider": "openrouter", "base_url": "https://openrouter.ai/api/v1",  "model": "google/gemma-3-27b-it:free",                "env_key": "OPENROUTER_API_KEY", "extra_headers": {"HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive"}},
]


def call_ai_chain(
    prompt: str,
    system_prompt: str | None = None,
    temperature: float        = 0.6,
    max_tokens:  int          = 4096,
    json_mode:   bool         = False,
    timeout:     int          = 90,
) -> str:
    """
    Walk the fallback chain top-to-bottom. Return the first non-empty content.
    Return "{}" if every provider is unkeyed, rate-limited, or errors.

    Args:
        prompt: user message text.
        system_prompt: optional system instruction.
        temperature: 0.0-1.0. Lower = deterministic, higher = creative.
        max_tokens: response length cap. Cerebras hard-caps at 4096.
        json_mode: if True, request JSON object response (OpenAI-compatible).
        timeout: per-provider HTTP timeout in seconds.
    """
    messages = (
        [{"role": "system", "content": system_prompt},
         {"role": "user",   "content": prompt}]
        if system_prompt else
        [{"role": "user",   "content": prompt}]
    )

    for entry in PROVIDER_CHAIN:
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
            continue

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

        if content:
            print(f"  [ai-chain] served by {entry['provider']} / {entry['model']}")
            return content

        print(f"  [ai-chain] {entry['provider']}/{entry['model']} "
              f"returned empty content — trying next")

    print("  [ai-chain] ALL providers exhausted. Returning empty JSON.")
    return "{}"
