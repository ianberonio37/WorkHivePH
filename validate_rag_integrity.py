#!/usr/bin/env python3
"""Phase 3 Validator: RAG Integrity (Semantic Search + Citations)"""
import sys

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

RED, GREEN, YELLOW, RESET = "\033[91m", "\033[92m", "\033[93m", "\033[0m"

def check():
    try:
        with open("voice-handler.js", "r", encoding="utf-8") as f:
            content = f.read()
    except:
        print(f"{RED}FAIL{RESET} voice-handler.js not found")
        return False

    results = {"pass": 0, "fail": 0}
    print("\n[L1] RAG Schema")
    
    try:
        with open("supabase/migrations/20260516000004_kb_rag_phase3.sql") as f:
            mig = f.read()
        if "kb_documents" in mig and "kb_chunks" in mig:
            print(f"  {GREEN}PASS{RESET} kb_documents + kb_chunks tables defined")
            results["pass"] += 1
        else:
            print(f"  {RED}FAIL{RESET} KB tables missing")
            results["fail"] += 1
    except:
        print(f"  {RED}FAIL{RESET} Migration not found")
        results["fail"] += 1

    print("\n[L2] Semantic Search")
    # ★THE SEARCH MOVED TO THE SERVER (BRH-AO, 2026-10-27). voice-handler.js ran semantic_search_kb in the browser and put
    # the result in a platform_prompt no server read; the gateway now retrieves it (_shared/hive-knowledge.ts, called
    # from ai-gateway for a signed-in person). The search must be wired THERE - and the browser must not rebuild it.
    try:
        with open("supabase/functions/_shared/hive-knowledge.ts", encoding="utf-8") as f:
            hk = f.read()
        with open("supabase/functions/ai-gateway/index.ts", encoding="utf-8") as f:
            gw = f.read()
    except OSError:
        hk = gw = ""
    if "semantic_search_kb" in hk and "loadHiveKnowledge(" in gw and "_fetchRAGContext(" not in content:
        print(f"  {GREEN}PASS{RESET} Semantic search runs server-side (hive-knowledge.ts, called by ai-gateway)")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} Semantic search not integrated server-side (or the browser builds it again)")
        results["fail"] += 1

    print("\n[L3] Citation Format")
    if "[" in content and "]" in content and "doc_title" in content:
        print(f"  {GREEN}PASS{RESET} Citation format [source] text")
        results["pass"] += 1
    else:
        print(f"  {YELLOW}WARN{RESET} Citation format unclear")

    print("\n" + "="*70)
    print(f"PASS: {results['pass']} | FAIL: {results['fail']}")
    return results["fail"] == 0

if __name__ == "__main__":
    sys.exit(0 if check() else 1)
