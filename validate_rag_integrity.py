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
    if "_fetchRAGContext(" in content and "semantic_search_kb" in content:
        print(f"  {GREEN}PASS{RESET} Semantic search RPC called")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} Semantic search not integrated")
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
