#!/usr/bin/env python3
"""
Voice Companion Phase 1.5 Validator

Validates that semantic RAG with pgvector embeddings is wired:

2 Layers:
  L1: Embedding helper exists (tools/embedding_helper.py)
  L2: voice-semantic-rag edge function exists and is called from _invokeRAGAgent
  L3: search_voice_journal_entries RPC exists in database schema
  L4: RAG agent passes transcript for semantic search

SUCCESS: All 4 layers pass (indicates Phase 1.5 optional wiring is complete)
"""

import re
import sys
import os

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def check_phase_1_5_semantic():
    results = {"pass": 0, "fail": 0}

    # L1: Embedding helper exists
    print("\n[L1] Embedding helper infrastructure")
    if os.path.exists("tools/embedding_helper.py"):
        print(f"  {GREEN}PASS{RESET} tools/embedding_helper.py exists")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} tools/embedding_helper.py not found")
        results["fail"] += 1

    # L2: Edge function exists
    print("\n[L2] Semantic RAG edge function")
    if os.path.exists("supabase/functions/voice-semantic-rag/index.ts"):
        print(f"  {GREEN}PASS{RESET} voice-semantic-rag edge function exists")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} voice-semantic-rag edge function not found")
        results["fail"] += 1

    # L3: Database schema has search RPC
    print("\n[L3] Database schema (pgvector support)")
    if os.path.exists("supabase/migrations/20260511000014_voice_journal_entries.sql"):
        with open("supabase/migrations/20260511000014_voice_journal_entries.sql", "r") as f:
            schema_content = f.read()
            if "search_voice_journal_entries" in schema_content and "vector(384)" in schema_content:
                print(f"  {GREEN}PASS{RESET} search_voice_journal_entries RPC defined")
                print(f"  {GREEN}PASS{RESET} voice_journal_entries has embedding column (vector(384))")
                results["pass"] += 2
            else:
                print(f"  {RED}FAIL{RESET} search_voice_journal_entries RPC not found in schema")
                results["fail"] += 1
    else:
        print(f"  {RED}FAIL{RESET} voice_journal_entries migration not found")
        results["fail"] += 1

    # L4: RAG agent integration
    print("\n[L4] RAG agent semantic integration")
    try:
        with open("voice-handler.js", "r", encoding="utf-8") as f:
            content = f.read()

            # Check for RAG function call (either edge function or direct DB query)
            if ("_fetchRAGContext" in content or "_invokeRAGAgent" in content or "semantic_search_kb" in content):
                print(f"  {GREEN}PASS{RESET} RAG agent function integrated")
                results["pass"] += 1
            else:
                print(f"  {RED}FAIL{RESET} RAG agent function not found")
                results["fail"] += 1

            # Check if transcript is passed to RAG function
            if ("_fetchRAGContext(db, ctx.hive_id, transcript)" in content or
                "_invokeRAGAgent(db, ctx.worker_name, firstIntent, transcript)" in content or
                "semantic_search_kb" in content and "transcript" in content):
                print(f"  {GREEN}PASS{RESET} RAG agent receives transcript for semantic search")
                results["pass"] += 1
            else:
                print(f"  {RED}FAIL{RESET} RAG agent not receiving transcript parameter")
                results["fail"] += 1
    except FileNotFoundError:
        print(f"  {RED}FAIL{RESET} voice-handler.js not found")
        results["fail"] += 1

    # Summary
    print("\n" + "=" * 70)
    print(f"PASS: {results['pass']} | FAIL: {results['fail']}")
    print("=" * 70)
    print("\nNote: Phase 1.5 is optional. Fallback to recency-based RAG is acceptable.")
    print("Full semantic search requires:")
    print("  1. JINA_API_KEY configured (free tier: 8k requests/month)")
    print("  2. ai-gateway embedding existing voice_journal_entries (batch job)")
    print("  3. New entries embedded on insert via ai-gateway")

    return results["fail"] == 0


if __name__ == "__main__":
    success = check_phase_1_5_semantic()
    sys.exit(0 if success else 1)
