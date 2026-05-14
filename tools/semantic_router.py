#!/usr/bin/env python3
"""
Semantic Router for Voice Companion

Lightweight intent classifier (20 tokens, ~50ms Groq call) that decides:
1. Does the question need PLATFORM DATA (equipment status, risk scores, PM status)?
   Examples: "How many PMs are overdue?", "What's our risk?", "Which assets are down?"
   → Route to Platform Scraper Agent

2. Does the question need SEMANTIC DEPTH (failure patterns, historical trends)?
   Examples: "Why does the pump keep failing?", "What changed with downtime?", "Is this normal?"
   → Route to RAG Agent + existing specialist agents

3. Is this a SIMPLE QUERY (current state, quick fact, no agents needed)?
   Examples: "What time is it?", "How am I doing today?", "Thanks"
   → Use memory context only

Classifier runs via callAI (Groq Scout free tier), outputs a route decision.
"""

import json
import sys
from typing import Optional, Dict

ROUTER_SYSTEM = """You are a lightweight intent router for a voice assistant in an industrial maintenance platform.

Given a worker's question, output ONLY a JSON object with these fields:
{
  "route": "platform" | "semantic" | "simple",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}

Route selection rules:
- "platform": Question asks for real-time KPI status (equipment running/down, PM counts, inventory, risk scores, adoption metrics)
  Examples: "How many assets are down?", "What's overdue?", "Is the pump still running?"

- "semantic": Question asks for patterns, analysis, or historical context (WHY something fails, WHAT changed, IS this normal)
  Examples: "Why does this pump fail?", "What's trending?", "Is downtime increasing?", "How can I prevent this?"

- "simple": Question is a greeting, thank you, or doesn't need real-time data
  Examples: "Thanks", "Hi", "What time is it?", "What's new?"

Confidence: How certain you are (0.5-1.0 range). If unsure between routes, pick the most likely and note it.

BE CONCISE. JSON only, no explanation outside the JSON block.
"""

def classify_intent(
    transcript: str,
    router_intents: Optional[list] = None,
    model: str = "meta-llama/llama-4-scout-17b-16e-instruct",
) -> Dict:
    """
    Classify whether the question needs platform data, semantic depth, or simple reply.

    Args:
        transcript: Worker's spoken question
        router_intents: Output from voice-action-router (used as pre-classifier hint)
        model: LLM model to use (default: Groq Scout free tier)

    Returns:
        Dict with keys: route, confidence, reasoning
    """
    import os
    from dotenv import load_dotenv

    load_dotenv()

    # If router already classified as a structured intent (pm.complete, inventory.use, etc.),
    # we might skip this step and go straight to platform route. But for now,
    # let the semantic router decide.

    messages = [
        {"role": "system", "content": ROUTER_SYSTEM},
        {"role": "user", "content": transcript},
    ]

    try:
        # Use Groq (Scout) free tier
        import requests

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            # Fallback: use a heuristic classifier if no API key
            return _heuristic_classify(transcript)

        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "max_tokens": 100,
                "temperature": 0,
            },
            timeout=5,
        )

        if resp.status_code != 200:
            print(f"Router error: {resp.status_code}", file=sys.stderr)
            return _heuristic_classify(transcript)

        data = resp.json()
        answer = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )

        # Parse JSON from response
        try:
            result = json.loads(answer)
            # Validate required fields
            if "route" in result and "confidence" in result:
                return result
        except json.JSONDecodeError:
            pass

        # Fallback if parsing fails
        return _heuristic_classify(transcript)

    except Exception as e:
        print(f"Semantic router error: {e}", file=sys.stderr)
        return _heuristic_classify(transcript)


def _heuristic_classify(transcript: str) -> Dict:
    """
    Fallback heuristic classifier (no API call needed).

    Keyword-based routing for robustness.
    """
    transcript_lower = transcript.lower()

    # Platform route keywords
    platform_keywords = [
        "how many", "count", "how much", "overdue", "due", "down", "running",
        "risk", "high risk", "alert", "alert", "low stock", "out of stock",
        "active workers", "adoption", "status", "inventory", "equipment",
    ]

    # Semantic route keywords
    semantic_keywords = [
        "why", "how can", "prevent", "improve", "trend", "pattern", "changing",
        "different", "normal", "unusual", "problem", "issue", "advice", "analysis",
        "historical", "forecast", "predict", "cause", "root cause", "what changed",
    ]

    # Simple route keywords (low priority)
    simple_keywords = ["thanks", "thank you", "hi", "hello", "bye", "goodbye"]

    platform_score = sum(1 for kw in platform_keywords if kw in transcript_lower)
    semantic_score = sum(1 for kw in semantic_keywords if kw in transcript_lower)
    simple_score = sum(1 for kw in simple_keywords if kw in transcript_lower)

    if platform_score > semantic_score and platform_score > 0:
        return {
            "route": "platform",
            "confidence": min(0.9, 0.5 + 0.1 * platform_score),
            "reasoning": "Keywords suggest real-time status query",
        }
    elif semantic_score > 0:
        return {
            "route": "semantic",
            "confidence": min(0.9, 0.5 + 0.1 * semantic_score),
            "reasoning": "Keywords suggest analysis/pattern question",
        }
    elif simple_score > 0:
        return {
            "route": "simple",
            "confidence": 0.9,
            "reasoning": "Greeting or closing",
        }
    else:
        # Default to semantic for ambiguous questions (safer to fetch more context)
        return {
            "route": "semantic",
            "confidence": 0.5,
            "reasoning": "Ambiguous; defaulting to semantic depth",
        }


if __name__ == "__main__":
    test_queries = [
        "How many PMs are overdue?",
        "Why does the pump keep failing?",
        "Thanks for the help",
        "What's our MTBF trending?",
        "Is the compressor still running?",
    ]

    for query in test_queries:
        result = classify_intent(query)
        print(f"Query: {query}")
        print(f"Route: {result['route']} ({result['confidence']:.2f})")
        print(f"Reason: {result['reasoning']}\n")
