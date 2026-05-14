#!/usr/bin/env python3
"""
Phase 2: Free-Tier Model Orchestrator

A/B tests and switches between multiple free-tier LLM models:
- Groq Scout (meta-llama/llama-4-scout-17b-16e-instruct) — PRIMARY / baseline
- Cerebras Qwen (qwen2.5-7b-instruct) — Fast, 2.5 family fine-tuning
- Voyage AI (mistral-large-2411) — Strong reasoning, creative tasks

All three offer free tier with generous limits:
  - Groq Scout: Fastest, lowest latency, proven baseline in voice
  - Cerebras Qwen: Excellent for structured output, good for intent routing
  - Voyage AI: Best reasoning, good for semantic depth questions

Configuration:
  MODEL_STRATEGY: "scout" (default) | "qwen" | "voyage" | "round-robin" | "quality-based"
  AI_EVAL_ENABLED: 1 (track quality metrics) | 0 (production default)

Returns:
  (model_name, api_url, headers, parsed_response)
"""

import os
import sys
import json
from typing import Optional, Tuple, Dict, Any

def get_model_config(strategy: str = "scout") -> Tuple[str, str, Dict]:
    """
    Get model, API endpoint, and headers for the specified strategy.

    Args:
        strategy: Model selection strategy (scout/qwen/voyage/jina/round-robin)

    Returns:
        (model_name, api_url, headers)
    """
    strategy = strategy.lower()

    if strategy == "qwen":
        return (
            "qwen2.5-7b-instruct",
            "https://api.cerebras.ai/v1/chat/completions",
            {
                "Authorization": f"Bearer {os.getenv('CEREBRAS_API_KEY', '')}",
                "Content-Type": "application/json",
            },
        )
    elif strategy == "voyage":
        return (
            "mistral-large-2411",
            "https://api.voyage.ai/v1/chat/completions",
            {
                "Authorization": f"Bearer {os.getenv('VOYAGE_API_KEY', '')}",
                "Content-Type": "application/json",
            },
        )
    elif strategy == "jina":
        return (
            "jina-ai/reader",  # or other Jina LLM if available
            "https://api.jina.ai/v1/chat/completions",
            {
                "Authorization": f"Bearer {os.getenv('JINA_API_KEY', '')}",
                "Content-Type": "application/json",
            },
        )
    else:  # Default to Scout
        return (
            "meta-llama/llama-4-scout-17b-16e-instruct",
            "https://api.groq.com/openai/v1/chat/completions",
            {
                "Authorization": f"Bearer {os.getenv('GROQ_API_KEY', '')}",
                "Content-Type": "application/json",
            },
        )


def call_model(
    messages: list,
    model_strategy: str = "scout",
    max_tokens: int = 280,
    temperature: float = 0.7,
) -> Optional[str]:
    """
    Call the specified free-tier model and return the response text.

    Args:
        messages: OpenAI-format messages list
        model_strategy: Which model to use (scout/qwen/sambanova)
        max_tokens: Max tokens in response
        temperature: Sampling temperature

    Returns:
        Response text, or None if call fails
    """
    import requests

    model_name, api_url, headers = get_model_config(model_strategy)

    # Check that API key is configured
    if not headers.get("Authorization") or "Bearer" not in headers.get("Authorization", ""):
        print(
            f"Warning: {model_strategy} API key not configured, skipping",
            file=sys.stderr,
        )
        return None

    try:
        resp = requests.post(
            api_url,
            headers=headers,
            json={
                "model": model_name,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=10,
        )

        if resp.status_code != 200:
            print(
                f"Model call failed ({model_strategy}): {resp.status_code}",
                file=sys.stderr,
            )
            return None

        data = resp.json()
        answer = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )

        return answer if answer else None
    except Exception as e:
        print(f"Model call error ({model_strategy}): {e}", file=sys.stderr)
        return None


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
