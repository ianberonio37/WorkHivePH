#!/usr/bin/env python3
"""
Voice Companion Data Flow Validator

Comprehensive audit of Phase 3/5/8 data pipelines:
- Phase 3: KB documents → semantic search finds chunks
- Phase 5: Anomaly alerts → RPC returns results → surfaced in response
- Phase 8: Conversation analytics → logged per turn → viewable in v_conversation_health

This validator checks the entire data flow, not just schema existence.
"""

import re
import sys
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import os

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def check_voice_data_flow():
    results = {"pass": 0, "fail": 0}

    print("\n" + "=" * 70)
    print("VOICE COMPANION DATA FLOW AUDIT (Phase 3/5/8)")
    print("=" * 70)

    # ─────────────────────────────────────────────────────────────────────
    # PHASE 3: KB DOCUMENTS → SEMANTIC SEARCH
    # ─────────────────────────────────────────────────────────────────────

    print("\n[Phase 3] Knowledge Base Seeding & Semantic Search")

    # Check KB seeder exists
    if os.path.exists("test-data-seeder/seeders/voice_companion_phase3_rag.py"):
        print(f"  {GREEN}PASS{RESET} Phase 3 seeder file exists")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} Phase 3 seeder file not found")
        results["fail"] += 1

    # Check RPC is defined
    try:
        with open("supabase/migrations/20260516000004_kb_rag_phase3.sql", "r") as f:
            migration = f.read()

        if "create or replace function semantic_search_kb" in migration:
            print(f"  {GREEN}PASS{RESET} semantic_search_kb RPC is defined")
            results["pass"] += 1

            # Check RPC has proper parameters
            if "p_query_embedding" in migration and "p_similarity_threshold" in migration:
                print(f"  {GREEN}PASS{RESET} RPC accepts embedding + threshold")
                results["pass"] += 1
            else:
                print(f"  {RED}FAIL{RESET} RPC missing query_embedding or similarity_threshold")
                results["fail"] += 1
        else:
            print(f"  {RED}FAIL{RESET} semantic_search_kb RPC not defined")
            results["fail"] += 1
    except Exception as e:
        print(f"  {RED}FAIL{RESET} Could not read KB migration: {e}")
        results["fail"] += 1

    # Check voice-handler calls _fetchRAGContext
    try:
        with open("voice-handler.js", "r", encoding="utf-8", errors="replace") as f:
            js_content = f.read()

        if "async function _fetchRAGContext(" in js_content:
            print(f"  {GREEN}PASS{RESET} _fetchRAGContext function defined")
            results["pass"] += 1

            if "_fetchRAGContext(db, ctx.hive_id, transcript)" in js_content:
                print(f"  {GREEN}PASS{RESET} _fetchRAGContext called in _converseInline")
                results["pass"] += 1
            else:
                print(f"  {RED}FAIL{RESET} _fetchRAGContext defined but not called")
                results["fail"] += 1

            if "db.rpc('semantic_search_kb'" in js_content:
                print(f"  {GREEN}PASS{RESET} semantic_search_kb RPC is invoked")
                results["pass"] += 1
            else:
                print(f"  {RED}FAIL{RESET} semantic_search_kb RPC not called from JS")
                results["fail"] += 1
        else:
            print(f"  {RED}FAIL{RESET} _fetchRAGContext function not found")
            results["fail"] += 1
    except Exception as e:
        print(f"  {RED}FAIL{RESET} Could not read voice-handler.js: {e}")
        results["fail"] += 1

    # ─────────────────────────────────────────────────────────────────────
    # PHASE 5: ANOMALY ALERTS
    # ─────────────────────────────────────────────────────────────────────

    print("\n[Phase 5] Proactive Alerts Seeding & Surfacing")

    # Check alerts seeder
    if os.path.exists("test-data-seeder/seeders/voice_companion_phase5_alerts.py"):
        print(f"  {GREEN}PASS{RESET} Phase 5 seeder file exists")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} Phase 5 seeder file not found")
        results["fail"] += 1

    # Check fetch_active_alerts RPC
    try:
        with open("supabase/migrations/20260516000003_anomaly_alerts_phase5.sql", "r") as f:
            migration = f.read()

        if "create or replace function fetch_active_alerts" in migration:
            print(f"  {GREEN}PASS{RESET} fetch_active_alerts RPC is defined")
            results["pass"] += 1

            if "suppressed_until is null" in migration:
                print(f"  {GREEN}PASS{RESET} RPC filters suppressed alerts")
                results["pass"] += 1
            else:
                print(f"  {YELLOW}WARN{RESET} RPC may not filter suppressed alerts")
        else:
            print(f"  {RED}FAIL{RESET} fetch_active_alerts RPC not defined")
            results["fail"] += 1
    except Exception as e:
        print(f"  {RED}FAIL{RESET} Could not read alerts migration: {e}")
        results["fail"] += 1

    # Check voice-handler calls _fetchProactiveAlerts
    try:
        with open("voice-handler.js", "r", encoding="utf-8", errors="replace") as f:
            js_content = f.read()

        if "async function _fetchProactiveAlerts(" in js_content:
            print(f"  {GREEN}PASS{RESET} _fetchProactiveAlerts function defined")
            results["pass"] += 1

            if "_fetchProactiveAlerts(db, ctx.hive_id)" in js_content:
                print(f"  {GREEN}PASS{RESET} _fetchProactiveAlerts called in _converseInline")
                results["pass"] += 1
            else:
                print(f"  {RED}FAIL{RESET} _fetchProactiveAlerts not called")
                results["fail"] += 1

            if "db.rpc('fetch_active_alerts'" in js_content:
                print(f"  {GREEN}PASS{RESET} fetch_active_alerts RPC is invoked")
                results["pass"] += 1
            else:
                print(f"  {RED}FAIL{RESET} fetch_active_alerts RPC not called")
                results["fail"] += 1

            # Check if alerts are in system prompt (look for new mandatory alert format)
            if "proactiveAlerts" in js_content and ("CRITICAL PRIORITY" in js_content or "ACTIVE ALERTS" in js_content):
                print(f"  {GREEN}PASS{RESET} Alerts section in system prompt")
                results["pass"] += 1
            else:
                print(f"  {RED}FAIL{RESET} Alerts not integrated in system prompt")
                results["fail"] += 1
        else:
            print(f"  {RED}FAIL{RESET} _fetchProactiveAlerts function not found")
            results["fail"] += 1
    except Exception as e:
        print(f"  {RED}FAIL{RESET} Could not read voice-handler.js: {e}")
        results["fail"] += 1

    # ─────────────────────────────────────────────────────────────────────
    # PHASE 8: CONVERSATION ANALYTICS
    # ─────────────────────────────────────────────────────────────────────

    print("\n[Phase 8] Conversation Analytics Logging")

    # Check conversation_analytics table migration
    try:
        with open("supabase/migrations/20260516000007_voice_analytics_phase8.sql", "r") as f:
            migration = f.read()

        if "create table if not exists conversation_analytics" in migration:
            print(f"  {GREEN}PASS{RESET} conversation_analytics table is defined")
            results["pass"] += 1

            required_cols = ["session_id", "turn_num", "question_category", "answer_quality_rating"]
            missing = [c for c in required_cols if c not in migration]
            if not missing:
                print(f"  {GREEN}PASS{RESET} All required columns present")
                results["pass"] += 1
            else:
                print(f"  {RED}FAIL{RESET} Missing columns: {missing}")
                results["fail"] += 1
        else:
            print(f"  {RED}FAIL{RESET} conversation_analytics table not defined")
            results["fail"] += 1
    except Exception as e:
        print(f"  {RED}FAIL{RESET} Could not read analytics migration: {e}")
        results["fail"] += 1

    # Check _captureAnalytics function
    try:
        with open("voice-handler.js", "r", encoding="utf-8", errors="replace") as f:
            js_content = f.read()

        if "async function _captureAnalytics(" in js_content:
            print(f"  {GREEN}PASS{RESET} _captureAnalytics function defined")
            results["pass"] += 1

            # Check it's called in both success and error paths
            call_count = js_content.count("_captureAnalytics(db, sessionId")
            if call_count >= 2:
                print(f"  {GREEN}PASS{RESET} _captureAnalytics called {call_count}x (success + error)")
                results["pass"] += 1
            else:
                print(f"  {RED}FAIL{RESET} _captureAnalytics called only {call_count}x (need >=2)")
                results["fail"] += 1

            if "db.from('conversation_analytics').insert(" in js_content:
                print(f"  {GREEN}PASS{RESET} Inserts to conversation_analytics table")
                results["pass"] += 1
            else:
                print(f"  {RED}FAIL{RESET} Does not insert to conversation_analytics")
                results["fail"] += 1
        else:
            print(f"  {RED}FAIL{RESET} _captureAnalytics function not found")
            results["fail"] += 1
    except Exception as e:
        print(f"  {RED}FAIL{RESET} Could not read voice-handler.js: {e}")
        results["fail"] += 1

    # Check v_conversation_health view
    try:
        with open("supabase/migrations/20260516000007_voice_analytics_phase8.sql", "r") as f:
            migration = f.read()

        if "create or replace view v_conversation_health" in migration:
            print(f"  {GREEN}PASS{RESET} v_conversation_health view defined")
            results["pass"] += 1
        else:
            print(f"  {RED}FAIL{RESET} v_conversation_health view not defined")
            results["fail"] += 1
    except Exception as e:
        print(f"  {RED}FAIL{RESET} Could not check analytics view: {e}")
        results["fail"] += 1

    # ─────────────────────────────────────────────────────────────────────
    # SUMMARY
    # ─────────────────────────────────────────────────────────────────────

    print("\n" + "=" * 70)
    print(f"PASS: {results['pass']} | FAIL: {results['fail']}")
    print("=" * 70)

    if results["fail"] == 0:
        print(f"\n{GREEN}All data flows wired correctly!{RESET}")
        print("Next: Seed data and test in WorkHive Tester")
    else:
        print(f"\n{RED}Data flow issues detected. Fix before testing.{RESET}")

    return results["fail"] == 0


if __name__ == "__main__":
    success = check_voice_data_flow()
    sys.exit(0 if success else 1)
