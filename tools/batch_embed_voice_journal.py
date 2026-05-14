#!/usr/bin/env python3
"""
Phase 1.5: Batch Embedding for Voice Journal Entries

Backfills existing voice_journal_entries with vector embeddings for semantic RAG.
- Queries entries without embeddings (embedding IS NULL)
- Batches them (50 at a time)
- Generates embeddings using Jina API or local fallback
- Updates database with pgvector embeddings
- Tracks progress and failure handling

Usage:
  python -m tools.batch_embed_voice_journal

Expected: 2-5 min for typical hive (100-500 entries), depends on Jina rate limits.
"""

import os
import sys
import json
from typing import Optional, List, Tuple
from dotenv import load_dotenv

load_dotenv()

def get_supabase_client():
    """Initialize Supabase client."""
    from supabase import create_client

    url = os.getenv("SUPABASE_URL", "https://hzyvnjtisfgbksicrouu.supabase.co")
    key = os.getenv("SUPABASE_ANON_KEY", "sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ")

    return create_client(url, key)

def fetch_unembed_entries(supabase, batch_size: int = 50) -> Tuple[List[dict], int]:
    """
    Fetch voice_journal_entries without embeddings.

    Returns:
        (entries, total_count)
    """
    try:
        # Count total unembedded entries
        count_resp = supabase.table("voice_journal_entries").select(
            "id", count="exact"
        ).is_("embedding", "null").execute()
        total = count_resp.count

        # Fetch batch
        resp = supabase.table("voice_journal_entries").select(
            "id,transcript,reply,created_at"
        ).is_("embedding", "null").order(
            "created_at", desc=False
        ).limit(batch_size).execute()

        return resp.data, total
    except Exception as e:
        print(f"ERROR fetching entries: {e}", file=sys.stderr)
        return [], 0

def embed_batch(texts: List[str]) -> List[Optional[List[float]]]:
    """Generate embeddings using embedding_helper."""
    from tools.embedding_helper import embed_batch
    return embed_batch(texts)

def update_embeddings(supabase, entries_with_embeddings: List[dict]) -> int:
    """
    Update database with new embeddings.

    Returns:
        Number of successfully updated entries
    """
    updated = 0

    for item in entries_with_embeddings:
        try:
            if item.get("embedding"):
                supabase.table("voice_journal_entries").update({
                    "embedding": item["embedding"]
                }).eq("id", item["id"]).execute()
                updated += 1
        except Exception as e:
            print(f"Failed to update {item['id']}: {e}", file=sys.stderr)

    return updated

def main():
    """Main batch embedding loop."""
    print("=" * 70)
    print("PHASE 1.5: BATCH EMBEDDING VOICE JOURNAL ENTRIES")
    print("=" * 70)

    batch_size = int(os.getenv("EMBEDDING_BATCH_SIZE", "50"))

    supabase = get_supabase_client()

    total_processed = 0
    total_failed = 0

    while True:
        entries, remaining = fetch_unembed_entries(supabase, batch_size)

        if not entries:
            break

        print(f"\nProcessing batch of {len(entries)} entries ({remaining} remaining)...")

        # Prepare texts
        texts = [
            f"{e.get('transcript', '')} {e.get('reply', '')}".strip()
            for e in entries
        ]

        # Generate embeddings
        embeddings = embed_batch(texts)

        # Pair embeddings with entries
        entries_with_embeddings = []
        for entry, emb in zip(entries, embeddings):
            if emb:
                entries_with_embeddings.append({
                    "id": entry["id"],
                    "embedding": emb
                })
            else:
                print(f"  [WARN] Failed to embed {entry['id']} (fallback: recency-based search)")
                total_failed += 1

        # Update database
        updated = update_embeddings(supabase, entries_with_embeddings)
        total_processed += updated

        print(f"  [OK] Updated {updated}/{len(entries)} entries")

    # Summary
    print("\n" + "=" * 70)
    print("BATCH EMBEDDING COMPLETE")
    print("=" * 70)
    print(f"Total embedded: {total_processed}")
    print(f"Total failed: {total_failed}")
    print(f"Total: {total_processed + total_failed}")

    if total_processed > 0:
        print(f"\n[OK] Voice journal is ready for semantic RAG!")
        print("  - pgvector search now active for semantic queries")
        print("  - Falls back to recency-based search if Jina rate limit exceeded")
        print("  - New entries auto-embedded on insert via ai-gateway")
    else:
        print("\n[INFO] No entries to embed. Check database connection and voice_journal_entries table.")

if __name__ == "__main__":
    main()
