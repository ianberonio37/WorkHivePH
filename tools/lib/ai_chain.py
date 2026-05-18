"""Python replica of supabase/functions/_shared/ai-chain.ts.

Same 14-model fallback chain (Groq → Cerebras → OpenRouter) the edge
functions use. Missing API keys cause silent skip — script keeps working
with whatever's configured. 429 / 413 / 503 are recoverable; we move to
the next entry. Hard errors raise.

Why a local replica:
  - Edge functions can't be invoked from one-shot Python tools cleanly
  - Tools running against local Supabase (psycopg2) need direct LLM access
  - Keeps Python tools aligned with the platform's chain semantics
  - When the TS chain grows a new provider, mirror it here

Usage:
    from tools.lib.ai_chain import call_ai
    out = call_ai("Translate to Cebuano: oil leak", json_mode=False)
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Optional

import requests


@dataclass
class _Provider:
    provider:      str
    base_url:      str
    model:         str
    env_key:       str
    max_tokens_cap: Optional[int] = None
    extra_headers: Optional[dict[str, str]] = None


# Order mirrors _shared/ai-chain.ts exactly — change one, change both.
_CHAIN: list[_Provider] = [
    # Tier 1: Groq (LPU hardware, fastest)
    _Provider("groq", "https://api.groq.com/openai/v1", "meta-llama/llama-4-scout-17b-16e-instruct", "GROQ_API_KEY"),
    _Provider("groq", "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile",                    "GROQ_API_KEY"),
    _Provider("groq", "https://api.groq.com/openai/v1", "qwen/qwen3-32b",                             "GROQ_API_KEY"),
    _Provider("groq", "https://api.groq.com/openai/v1", "llama-3.1-8b-instant",                       "GROQ_API_KEY"),
    _Provider("groq", "https://api.groq.com/openai/v1", "openai/gpt-oss-20b",                         "GROQ_API_KEY"),
    _Provider("groq", "https://api.groq.com/openai/v1", "openai/gpt-oss-120b",                        "GROQ_API_KEY"),
    # Tier 2: Cerebras (1M tokens/day free)
    _Provider("cerebras", "https://api.cerebras.ai/v1", "llama-3.3-70b", "CEREBRAS_API_KEY", max_tokens_cap=4096),
    _Provider("cerebras", "https://api.cerebras.ai/v1", "qwen-3-32b",    "CEREBRAS_API_KEY", max_tokens_cap=4096),
    # Tier 3: OpenRouter (200 req/day on :free models)
    _Provider("openrouter", "https://openrouter.ai/api/v1", "nvidia/nemotron-3-super-120b-a12b:free",
              "OPENROUTER_API_KEY", extra_headers={"HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive"}),
    _Provider("openrouter", "https://openrouter.ai/api/v1", "google/gemma-4-31b-it:free",
              "OPENROUTER_API_KEY", extra_headers={"HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive"}),
    _Provider("openrouter", "https://openrouter.ai/api/v1", "openai/gpt-oss-120b:free",
              "OPENROUTER_API_KEY", extra_headers={"HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive"}),
    _Provider("openrouter", "https://openrouter.ai/api/v1", "google/gemma-4-26b-a4b-it:free",
              "OPENROUTER_API_KEY", extra_headers={"HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive"}),
    _Provider("openrouter", "https://openrouter.ai/api/v1", "meta-llama/llama-3.3-70b-instruct:free",
              "OPENROUTER_API_KEY", extra_headers={"HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive"}),
    _Provider("openrouter", "https://openrouter.ai/api/v1", "google/gemma-3-27b-it:free",
              "OPENROUTER_API_KEY", extra_headers={"HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive"}),
]


class AIChainError(RuntimeError):
    pass


def call_ai(
    prompt:         str,
    *,
    system_prompt:  Optional[str] = None,
    temperature:    float = 0.2,
    max_tokens:     int   = 1024,
    json_mode:      bool  = True,
    timeout_s:      int   = 60,
    verbose:        bool  = False,
) -> tuple[str, str]:
    """Run prompt through the fallback chain. Returns (content, provider_label).

    Skips providers without a configured key. On 429/413/503 — try next.
    On other 4xx/5xx with a body — log a snippet and try next.
    Returns the first successful response. Raises AIChainError if every
    configured provider fails.
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    errors: list[str] = []
    for entry in _CHAIN:
        api_key = os.environ.get(entry.env_key)
        if not api_key or api_key.startswith("PASTE_"):
            continue

        effective_max = (
            min(max_tokens, entry.max_tokens_cap) if entry.max_tokens_cap else max_tokens
        )
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
        if entry.extra_headers:
            headers.update(entry.extra_headers)

        body = {
            "model":       entry.model,
            "messages":    messages,
            "temperature": temperature,
            "max_tokens":  effective_max,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        label = f"{entry.provider}/{entry.model.split('/')[-1]}"
        try:
            res = requests.post(
                f"{entry.base_url}/chat/completions",
                headers=headers, json=body, timeout=timeout_s,
            )
        except requests.RequestException as e:
            errors.append(f"{label}: network {e.__class__.__name__}")
            if verbose:
                print(f"  [ai-chain] {label} network err — next")
            continue

        if res.status_code in (429, 413, 503):
            errors.append(f"{label}: HTTP {res.status_code}")
            if verbose:
                print(f"  [ai-chain] {label} skipped (HTTP {res.status_code})")
            # Tiny pause helps if the throttle is provider-wide rather than model-wide
            time.sleep(0.3)
            continue

        if not res.ok:
            snippet = res.text[:120].replace("\n", " ")
            errors.append(f"{label}: HTTP {res.status_code}: {snippet}")
            if verbose:
                print(f"  [ai-chain] {label} HTTP {res.status_code}: {snippet} — next")
            continue

        try:
            data = res.json()
            content = data["choices"][0]["message"]["content"]
        except (KeyError, ValueError, IndexError) as e:
            errors.append(f"{label}: bad payload {e}")
            continue

        if not content:
            errors.append(f"{label}: empty content")
            continue

        if verbose:
            print(f"  [ai-chain] {label} OK ({len(content)} chars)")
        return content, label

    raise AIChainError(
        "All providers failed or unconfigured. Tried:\n  " + "\n  ".join(errors)
    )
