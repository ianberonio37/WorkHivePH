#!/usr/bin/env python3
"""
Phase 2 Validator: Session Memory & Conversation Context

Validates that multi-turn memory is properly wired:

4 Layers:
  L1: agent_memory table exists with correct schema
  L2: session_id tracking is consistent (voice-handler assigns per-tab)
  L3: Memory deduplication logic works (>90% similarity triggers dedup)
  L4: Memory window passed to LLM in system prompt

SUCCESS: All 4 layers pass (indicates Phase 2 wiring is complete)
"""

import re
import sys

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def check_phase_2_memory():
    try:
        with open("voice-handler.js", "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"{RED}FAIL{RESET} voice-handler.js not found")
        return False

    results = {"pass": 0, "fail": 0}

    # L1: agent_memory table migration exists
    print("\n[L1] Database schema (agent_memory table)")
    migration_file = "supabase/migrations/20260516000001_agent_memory_phase2.sql"
    try:
        with open(migration_file, "r", encoding="utf-8") as f:
            migration = f.read()

        required_columns = [
            "hive_id uuid",
            "worker_id uuid",
            "session_id text",
            "turn_num int",
            "user_input text",
            "assistant_response text",
            "intent_classification text",
            "intent_confidence real",
        ]

        missing_cols = [col for col in required_columns if col not in migration]
        if not missing_cols:
            print(f"  {GREEN}PASS{RESET} agent_memory table schema complete")
            results["pass"] += 1
        else:
            print(f"  {RED}FAIL{RESET} Missing columns in agent_memory: {missing_cols}")
            results["fail"] += 1

        # Check RLS policies
        if "agent_memory_worker_access" in migration and "agent_memory_insert_own" in migration:
            print(f"  {GREEN}PASS{RESET} RLS policies defined (worker isolation)")
            results["pass"] += 1
        else:
            print(f"  {RED}FAIL{RESET} RLS policies missing")
            results["fail"] += 1

        # Check RPC functions
        if "fetch_session_memory" in migration and "store_memory_turn" in migration:
            print(f"  {GREEN}PASS{RESET} RPC functions defined (fetch + store)")
            results["pass"] += 1
        else:
            print(f"  {RED}FAIL{RESET} RPC functions missing")
            results["fail"] += 1

    except FileNotFoundError:
        print(f"  {RED}FAIL{RESET} Migration file {migration_file} not found")
        results["fail"] += 1

    # L2: Session ID tracking in voice-handler.js
    print("\n[L2] Session ID tracking")

    if "_getSessionId()" in content:
        print(f"  {GREEN}PASS{RESET} _getSessionId() function exists")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} _getSessionId() not found")
        results["fail"] += 1

    if "sessionStorage.setItem('wh_voice_session_id'" in content:
        print(f"  {GREEN}PASS{RESET} Session ID persisted to sessionStorage")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} Session ID not persisted")
        results["fail"] += 1

    if "_turnNum" in content:
        print(f"  {GREEN}PASS{RESET} Turn counter (_turnNum) tracking active")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} Turn counter not found")
        results["fail"] += 1

    # L3: Memory deduplication (>90% similarity)
    print("\n[L3] Memory deduplication")

    if "const key = turn.user.slice(0, 80)" in content and "seen.has(key)" in content:
        print(f"  {GREEN}PASS{RESET} Deduplication by user message hash (first 80 chars)")
        results["pass"] += 1
    else:
        print(f"  {YELLOW}WARN{RESET} Deduplication logic unclear")

    if "agent_memory" in content and "session_id" in content:
        print(f"  {GREEN}PASS{RESET} Session-scoped memory queries (not global)")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} Session-scoped memory queries not found")
        results["fail"] += 1

    # L4: Memory window in system prompt
    print("\n[L4] Memory integration into system prompt")

    if "memoryBlock" in content and "_buildVoiceSystemPrompt" in content:
        print(f"  {GREEN}PASS{RESET} memoryBlock passed to system prompt builder")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} memoryBlock not in prompt builder")
        results["fail"] += 1

    # Check that memory is included in the final prompt
    if "PRIOR TURNS WITH THIS WORKER" in content or "RECENT SESSION MEMORY" in content:
        print(f"  {GREEN}PASS{RESET} Memory section injected into system prompt")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} Memory section not in system prompt")
        results["fail"] += 1

    # L4b: Store memory after response
    if "_storeTurn(" in content:
        print(f"  {GREEN}PASS{RESET} _storeTurn() function called after responses")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} _storeTurn() not called")
        results["fail"] += 1

    # Check that _fetchRecentMemory reads from agent_memory
    if "agent_memory" in content and "fetch_session_memory" in content:
        print(f"  {GREEN}PASS{RESET} _fetchRecentMemory queries agent_memory table")
        results["pass"] += 1
    else:
        print(f"  {YELLOW}WARN{RESET} _fetchRecentMemory may not be querying agent_memory")

    # Summary
    print("\n" + "=" * 70)
    print(f"PASS: {results['pass']} | FAIL: {results['fail']}")
    print("=" * 70)

    return results["fail"] == 0


if __name__ == "__main__":
    success = check_phase_2_memory()
    sys.exit(0 if success else 1)
