#!/usr/bin/env python3
"""
Embedding Helper for Voice Companion Semantic RAG (Phase 1.5)

Generates vector embeddings for voice transcripts using free APIs:
- Jina AI (free tier: 8,000 requests/month, 384-dim)
- Or local embedding fallback (using sentence-transformers if available)

Used by:
1. ai-gateway to embed new voice transcripts before search
2. RAG agent to find semantically similar past entries via pgvector search

When embeddings fail, falls back to time-based + keyword matching.
"""

import os
import json
import sys
from typing import Optional, List

def embed_text(text: str, model: str = "jina-embeddings-v2-base-en") -> Optional[List[float]]:
    """
    Generate embedding for a single text string.

    Uses Jina AI free tier (384-dim) by default. Falls back to local
    sentence-transformers if API is unavailable.

    Args:
        text: Text to embed (transcript, reply, or query)
        model: Embedding model (default: Jina's free 384-dim)

    Returns:
        List of floats (embedding vector), or None if both methods fail
    """
    if not text or not isinstance(text, str):
        return None

    # Try Jina API first (free tier: 8k requests/month)
    jina_key = os.getenv("JINA_API_KEY")
    if jina_key:
        try:
            import requests

            resp = requests.post(
                "https://api.jina.ai/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {jina_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "input": [text],
                },
                timeout=10,
            )

            if resp.status_code == 200:
                data = resp.json()
                embeddings = data.get("data", [])
                if embeddings and len(embeddings) > 0:
                    return embeddings[0].get("embedding", None)
        except Exception as e:
            print(f"Jina API failed (non-fatal): {e}", file=sys.stderr)

    # Fallback: local embedding using sentence-transformers (requires pip install)
    try:
        from sentence_transformers import SentenceTransformer

        model_obj = SentenceTransformer("all-MiniLM-L6-v2")  # 384-dim, lightweight
        embedding = model_obj.encode(text).tolist()
        return embedding if embedding else None
    except ImportError:
        pass  # Library not installed
    except Exception as e:
        print(f"Local embedding failed (non-fatal): {e}", file=sys.stderr)

    # Both methods failed — return None (caller will use fallback recency-based search)
    return None


def embed_batch(texts: List[str]) -> List[Optional[List[float]]]:
    """
    Generate embeddings for a batch of texts (more efficient than per-text calls).

    Args:
        texts: List of texts to embed

    Returns:
        List of embeddings (None for failed entries)
    """
    if not texts:
        return []

    # Try Jina batch API
    jina_key = os.getenv("JINA_API_KEY")
    if jina_key:
        try:
            import requests

            resp = requests.post(
                "https://api.jina.ai/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {jina_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "jina-embeddings-v2-base-en",
                    "input": texts,
                },
                timeout=30,
            )

            if resp.status_code == 200:
                data = resp.json()
                embeddings_data = data.get("data", [])
                # Sort by index to maintain order
                embeddings_data.sort(key=lambda x: x.get("index", 0))
                return [
                    e.get("embedding", None) for e in embeddings_data
                ]
        except Exception as e:
            print(f"Jina batch API failed (non-fatal): {e}", file=sys.stderr)

    # Fallback: local batch embedding
    try:
        from sentence_transformers import SentenceTransformer

        model_obj = SentenceTransformer("all-MiniLM-L6-v2")
        embeddings = model_obj.encode(texts).tolist()
        return embeddings if embeddings else [None] * len(texts)
    except Exception as e:
        print(f"Local batch embedding failed (non-fatal): {e}", file=sys.stderr)

    # Both failed — return None for all
    return [None] * len(texts)


if __name__ == "__main__":
    # Test: embed a single text
    from dotenv import load_dotenv

    load_dotenv()

    test_texts = [
        "Why does the pump keep failing?",
        "What's our MTBF this month?",
        "Thanks for the help",
    ]

    print("=== Single Embedding Test ===")
    for text in test_texts[:1]:
        emb = embed_text(text)
        if emb:
            print(f"Text: {text}")
            print(f"Embedding (first 5 dims): {emb[:5]}")
            print(f"Dimension: {len(emb)}")
        else:
            print(f"Text: {text} -> NO EMBEDDING (fallback to recency search)")

    print("\n=== Batch Embedding Test ===")
    embeddings = embed_batch(test_texts)
    print(f"Embedded {sum(1 for e in embeddings if e is not None)} of {len(test_texts)} texts")
