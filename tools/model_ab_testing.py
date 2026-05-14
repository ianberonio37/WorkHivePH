#!/usr/bin/env python3
"""
Phase 2: Model A/B Testing Framework

Compares free-tier LLM models for voice companion responses:
- Groq Scout (primary, fastest)
- Cerebras Qwen (structured output)
- Voyage AI (reasoning depth)
- Jina AI (fallback)

Tracks quality metrics:
- Latency (response time)
- Token efficiency (tokens per answer)
- Quality score (user rating, answer relevance)
- Cost (free tier limits)

Run tests against the same prompts across all models and compare results.

Usage:
  python -m tools.model_ab_testing --prompt "Why does pump fail?" --all
  python -m tools.model_ab_testing --test-set maintenance_questions.jsonl
"""

import os
import sys
import json
import time
import argparse
from typing import Optional, Tuple, Dict, Any
from dotenv import load_dotenv

load_dotenv()

def call_model(
    messages: list,
    model_strategy: str = "scout",
    max_tokens: int = 280,
    temperature: float = 0.7,
) -> Tuple[Optional[str], float, Dict[str, Any]]:
    """
    Call a specific model and track latency + metadata.

    Returns:
        (response_text, latency_ms, metadata)
    """
    from tools.model_orchestrator import get_model_config

    model_name, api_url, headers = get_model_config(model_strategy)

    # Check API key
    if not headers.get("Authorization") or "Bearer" not in headers.get("Authorization", ""):
        return (
            None,
            0,
            {"error": f"{model_strategy}: API key not configured", "model": model_name},
        )

    try:
        import requests

        start = time.time()

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

        latency_ms = (time.time() - start) * 1000

        if resp.status_code != 200:
            return (
                None,
                latency_ms,
                {"error": f"HTTP {resp.status_code}", "model": model_name},
            )

        data = resp.json()
        answer = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )

        usage = data.get("usage", {})
        metadata = {
            "model": model_name,
            "strategy": model_strategy,
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }

        return (answer if answer else None, latency_ms, metadata)
    except Exception as e:
        return (None, 0, {"error": str(e), "model": model_name})


def test_prompt(prompt: str, models: list = None) -> Dict[str, Any]:
    """
    Test a single prompt against all models.

    Args:
        prompt: User question
        models: List of model strategies (default: all)

    Returns:
        Comparison results with latency, quality, cost
    """
    if models is None:
        models = ["scout", "qwen", "voyage", "jina"]

    messages = [
        {"role": "system", "content": "You are a helpful maintenance assistant. Reply with exactly 1 sentence."},
        {"role": "user", "content": prompt},
    ]

    results = {}

    for strategy in models:
        print(f"  Testing {strategy}...", end=" ", flush=True)
        response, latency_ms, metadata = call_model(messages, strategy)

        if response:
            results[strategy] = {
                "response": response[:100] + "..." if len(response) > 100 else response,
                "latency_ms": round(latency_ms, 2),
                "tokens": metadata.get("total_tokens", 0),
                "status": "OK",
            }
            print(f"OK ({latency_ms:.0f}ms)")
        else:
            results[strategy] = {
                "error": metadata.get("error"),
                "status": "FAIL",
            }
            print(f"FAIL ({metadata.get('error')})")

    return results


def compare_models(test_set: list) -> Dict[str, Any]:
    """
    Run A/B test against multiple prompts and aggregate results.

    Returns:
        Aggregated comparison: latency, success rate, cost per model
    """
    models = ["scout", "qwen", "voyage", "jina"]
    results = {}

    for strategy in models:
        results[strategy] = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "latency_ms": [],
            "tokens": [],
        }

    for test_prompt in test_set:
        prompt = test_prompt if isinstance(test_prompt, str) else test_prompt.get("prompt", "")

        messages = [
            {"role": "system", "content": "You are a helpful maintenance assistant. Reply with exactly 1 sentence."},
            {"role": "user", "content": prompt},
        ]

        for strategy in models:
            response, latency_ms, metadata = call_model(messages, strategy)

            results[strategy]["total"] += 1

            if response:
                results[strategy]["success"] += 1
                results[strategy]["latency_ms"].append(latency_ms)
                results[strategy]["tokens"].append(metadata.get("total_tokens", 0))
            else:
                results[strategy]["failed"] += 1

    # Aggregate statistics
    aggregated = {}
    for strategy, data in results.items():
        if data["success"] > 0:
            avg_latency = sum(data["latency_ms"]) / len(data["latency_ms"])
            avg_tokens = sum(data["tokens"]) / len(data["tokens"])
            success_rate = (data["success"] / data["total"]) * 100
        else:
            avg_latency = 0
            avg_tokens = 0
            success_rate = 0

        aggregated[strategy] = {
            "success_rate": f"{success_rate:.1f}%",
            "avg_latency_ms": f"{avg_latency:.0f}",
            "avg_tokens": f"{avg_tokens:.0f}",
            "successful": data["success"],
            "total": data["total"],
        }

    return aggregated


def main():
    parser = argparse.ArgumentParser(description="Model A/B testing framework")
    parser.add_argument(
        "--prompt",
        type=str,
        help="Single prompt to test against all models",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Test all models (default: scout only)",
    )
    parser.add_argument(
        "--test-set",
        type=str,
        help="JSONL file with test prompts",
    )

    args = parser.parse_args()

    print("=" * 70)
    print("PHASE 2: MODEL A/B TESTING FRAMEWORK")
    print("=" * 70)

    if args.prompt:
        print(f"\nTesting prompt: '{args.prompt}'")
        print("-" * 70)

        models = ["scout", "qwen", "voyage", "jina"] if args.all else ["scout"]
        results = test_prompt(args.prompt, models)

        print("\nResults:")
        for strategy, result in results.items():
            if result.get("status") == "OK":
                print(f"  [{strategy}] {result['latency_ms']}ms, {result['tokens']} tokens")
                print(f"           {result['response']}")
            else:
                print(f"  [{strategy}] ERROR: {result.get('error')}")

    elif args.test_set:
        print(f"\nLoading test set from {args.test_set}...")
        test_prompts = []
        with open(args.test_set) as f:
            for line in f:
                test_prompts.append(json.loads(line))

        print(f"Testing {len(test_prompts)} prompts against 4 models...")
        print("-" * 70)

        aggregated = compare_models(test_prompts)

        print("\nAggregated Results:")
        print(f"{'Model':<12} {'Success Rate':<15} {'Avg Latency':<15} {'Avg Tokens':<12}")
        print("-" * 70)
        for strategy, stats in aggregated.items():
            print(
                f"{strategy:<12} {stats['success_rate']:<15} "
                f"{stats['avg_latency_ms']}ms{' ' * 8} {stats['avg_tokens']:<12}"
            )

    else:
        print("\nQuick Test: Comparing all models on a sample prompt...")
        print("-" * 70)

        sample_prompt = "What's our MTBF this month?"
        results = test_prompt(sample_prompt, ["scout", "qwen", "voyage", "jina"])

        print("\nResults:")
        for strategy, result in results.items():
            if result.get("status") == "OK":
                print(f"  [OK] {strategy}: {result['latency_ms']}ms")
            else:
                print(f"  [FAIL] {strategy}: {result.get('error')}")

    print("\n" + "=" * 70)
    print("RECOMMENDATIONS")
    print("=" * 70)
    print("Set MODEL_STRATEGY in .env:")
    print("  - scout       = Fastest, proven baseline (use for most calls)")
    print("  - qwen        = Structured output, good intent routing")
    print("  - voyage      = Best reasoning, semantic depth")
    print("  - jina        = Fallback when others rate-limited")
    print("  - round-robin = Rotate all, test quality differences")


if __name__ == "__main__":
    main()
