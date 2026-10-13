#!/usr/bin/env python3
"""
Phase 2: Free-Tier Model Orchestrator

A/B tests and switches between free-tier LLM models. Every call goes through the platform chain
(tools/ai_chain.call_ai_chain, the Python mirror of supabase/functions/_shared/ai-chain.ts): a strategy only
says which chain model to try FIRST, and the rest of the chain is the fallback.

REROUTED 2026-10-08. Each strategy used to call a provider directly, and none of them could answer: Groq Scout
(meta-llama/llama-4-scout-17b-16e-instruct) was retired from Groq on 2026-09-10, "qwen" was Cerebras
qwen2.5-7b-instruct (a name Cerebras never served, and Cerebras now answers 402 payment_required - it is off the
platform), and "voyage"/"jina" pointed at embeddings companies with no chat endpoint at all. The strategy NAMES are
kept for callers and map to the same chain models voice-model-call uses:

  scout  -> qwen/qwen3.8-27b       (Groq; the chain's head)
  qwen   -> mistral-small-latest   (Mistral)
  voyage -> openai/gpt-oss-20b     (Groq)
  jina   -> openai/gpt-oss-120b    (Groq)

Configuration:
  MODEL_STRATEGY: "scout" (default) | "qwen" | "voyage" | "jina"
  AI_EVAL_ENABLED: 1 (track quality metrics) | 0 (production default)
"""

import os
import sys
from pathlib import Path
from typing import Optional, Tuple, Dict

_ROOT = str(Path(__file__).resolve().parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

STRATEGY_MODEL = {
    "scout":  "qwen/qwen3.8-27b",
    "qwen":   "mistral-small-latest",
    "voyage": "openai/gpt-oss-20b",
    "jina":   "openai/gpt-oss-120b",
}


def _entry_for(strategy: str) -> dict:
    from tools.ai_chain import PROVIDER_CHAIN
    model = STRATEGY_MODEL.get((strategy or "scout").lower(), STRATEGY_MODEL["scout"])
    for e in PROVIDER_CHAIN:
        if e["model"] == model:
            return e
    raise KeyError(f"{model} is not in tools/ai_chain.py PROVIDER_CHAIN - update STRATEGY_MODEL")


def get_model_config(strategy: str = "scout") -> Tuple[str, str, Dict]:
    """
    (model_name, chat_completions_url, headers) for a strategy - READ from the platform chain, never typed here.
    """
    e = _entry_for(strategy)
    headers = {
        "Authorization": f"Bearer {os.getenv(e['env_key'], '')}",
        "Content-Type": "application/json",
        **e.get("extra_headers", {}),
    }
    return e["model"], f"{e['base_url']}/chat/completions", headers


def call_model(
    messages: list,
    model_strategy: str = "scout",
    max_tokens: int = 280,
    temperature: float = 0.7,
) -> Optional[str]:
    """
    Call the platform chain with this strategy's model tried first. Returns the answer text, or None when every
    free model in the chain was rate-limited, refused or unkeyed. Which model actually answered:
    tools.ai_chain.last_outcome()["served_by"].
    """
    from tools.ai_chain import call_ai_chain
    model = _entry_for(model_strategy)["model"]
    out = call_ai_chain("", messages=messages, max_tokens=max_tokens, temperature=temperature,
                        json_mode=False, prefer_model=model, timeout=30)
    return None if out == "{}" else (out.strip() or None)


def call_with_fallback(
    messages: list,
    primary_strategy: str = "scout",
    fallback_strategies: list = None,
    max_tokens: int = 280,
) -> Tuple[Optional[str], str]:
    """
    Call primary model with automatic fallback to alternates.

    Args:
        messages: OpenAI-format messages
        primary_strategy: First model to try
        fallback_strategies: List of strategies to try if primary fails
        max_tokens: Max tokens

    Returns:
        (response_text, model_used)
    """
    if fallback_strategies is None:
        # call_model already falls through the whole platform chain; these re-ask with a different model FIRST
        fallback_strategies = ["qwen", "voyage", "jina"]

    # Try primary
    result = call_model(messages, primary_strategy, max_tokens)
    if result:
        return (result, primary_strategy)

    # Try fallbacks
    for strategy in fallback_strategies:
        result = call_model(messages, strategy, max_tokens)
        if result:
            return (result, strategy)

    # All failed
    return (None, "none")


if __name__ == "__main__":
    # Test: call each model with a simple message
    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant. Reply with exactly 1 sentence.",
        },
        {"role": "user", "content": "What is the capital of France?"},
    ]

    for strategy in ["scout", "qwen", "voyage", "jina"]:
        print(f"\n=== {strategy.upper()} ===")
        result, model_used = call_with_fallback(
            messages, primary_strategy=strategy, fallback_strategies=[]
        )
        if result:
            print(f"Model: {model_used}")
            print(f"Response: {result[:100]}")
        else:
            print(f"No response (API key not configured or rate limited)")

    print(f"\n=== FALLBACK CHAIN (Scout → Qwen → Voyage → Jina) ===")
    result, model_used = call_with_fallback(messages)
    if result:
        print(f"Primary attempt failed, fell back to: {model_used}")
        print(f"Response: {result[:100]}")
