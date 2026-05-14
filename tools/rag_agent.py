#!/usr/bin/env python3
"""
RAG Agent for Voice Companion

Queries voice_journal_entries table for semantic context:
- Recent turns (last 5-10 turns for continuity)
- Semantically related turns (pgvector search when embeddings available)
- Topic-scoped history (when worker mentions asset/discipline, fetch related entries)

Phase 1: Time-based recency (next 5-10 turns sorted by created_at DESC)
Phase 1.5: Add pgvector embeddings for semantic search (no context inflation)
"""

import json
import sys
from datetime import datetime, timedelta
from typing import Optional, List, Dict

def fetch_recent_memory(
    supabase_url: str,
    supabase_key: str,
    worker_name: str,
    limit: int = 10,
    days_back: int = 30,
) -> List[Dict]:
    """
    Fetch most recent voice journal turns for continuity context.

    Args:
        supabase_url: Supabase project URL
        supabase_key: Supabase public key
        worker_name: Worker name
        limit: Number of recent turns to fetch (default 10)
        days_back: Only fetch turns from last N days (default 30)

    Returns:
        List of dicts with keys: timestamp, transcript, response, intent_kind
    """
    from supabase import create_client

    client = create_client(supabase_url, supabase_key)

    result = []
    cutoff_date = (datetime.utcnow() - timedelta(days=days_back)).isoformat()

    try:
        resp = client.from_("voice_journal_entries").select(
            "created_at, transcript, response, router_intent_kind"
        ).eq(
            "worker_name", worker_name
        ).gt(
            "created_at", cutoff_date
        ).order(
            "created_at", desc=True
        ).limit(limit).execute()

        if resp.data:
            for row in resp.data:
                result.append({
                    "timestamp": row["created_at"],
                    "transcript": row.get("transcript", ""),
                    "response": row.get("response", ""),
                    "intent": row.get("router_intent_kind", "query.ask")
                })
    except Exception as e:
        print(f"Error fetching recent memory: {e}", file=sys.stderr)

    return result


def fetch_topic_scoped_memory(
    supabase_url: str,
    supabase_key: str,
    worker_name: str,
    topic: str,  # e.g., "asset:pump-12", "discipline:hydraulics", "pm:scheduled"
    limit: int = 5,
    days_back: int = 90,
) -> List[Dict]:
    """
    Fetch voice journal entries related to a specific topic (asset, discipline, etc.).

    Args:
        topic: Topic identifier (asset:NAME, discipline:NAME, action:KIND, etc.)
        limit: Number of turns to fetch
        days_back: Search window in days

    Returns:
        List of dicts matching the topic
    """
    from supabase import create_client

    client = create_client(supabase_url, supabase_key)

    result = []
    cutoff_date = (datetime.utcnow() - timedelta(days=days_back)).isoformat()

    try:
        # For now, use a simple text search on transcript field.
        # Phase 1.5 will add pgvector semantic search.
        search_term = topic.split(":")[-1] if ":" in topic else topic

        resp = client.from_("voice_journal_entries").select(
            "created_at, transcript, response, router_intent_kind"
        ).eq(
            "worker_name", worker_name
        ).gt(
            "created_at", cutoff_date
        ).ilike(
            "transcript", f"%{search_term}%"
        ).order(
            "created_at", desc=True
        ).limit(limit).execute()

        if resp.data:
            for row in resp.data:
                result.append({
                    "timestamp": row["created_at"],
                    "transcript": row.get("transcript", ""),
                    "response": row.get("response", ""),
                    "intent": row.get("router_intent_kind", "query.ask"),
                    "relevance": "text_match"
                })
    except Exception as e:
        print(f"Error fetching topic memory: {e}", file=sys.stderr)

    return result


def format_memory_block(turns: List[Dict]) -> str:
    """
    Convert raw journal entries into a system-prompt-friendly memory block.

    Returns a plain text summary of recent turns, oldest first.
    Format: "Worker: <transcript>\nAssistant: <response>"
    """
    if not turns:
        return ""

    lines = []
    for turn in reversed(turns):  # Reverse so oldest is first
        lines.append(f"Worker: {turn['transcript']}")
        lines.append(f"Assistant: {turn['response']}")

    return "\n".join(lines)


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    worker = sys.argv[1] if len(sys.argv) > 1 else "test-worker"

    # Fetch recent memory
    recent = fetch_recent_memory(url, key, worker, limit=5)
    print("=== Recent Memory (last 5 turns) ===")
    print(json.dumps(recent, indent=2))

    # Optionally fetch topic-scoped
    if len(sys.argv) > 2:
        topic = sys.argv[2]
        scoped = fetch_topic_scoped_memory(url, key, worker, topic, limit=3)
        print(f"\n=== Topic-Scoped Memory ({topic}) ===")
        print(json.dumps(scoped, indent=2))

    # Format for system prompt
    print("\n=== Memory Block (for system prompt) ===")
    block = format_memory_block(recent[:3])
    print(block if block else "(no recent history)")
