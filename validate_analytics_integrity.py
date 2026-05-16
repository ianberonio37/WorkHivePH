#!/usr/bin/env python3
"""Phase 8 Validator: Conversation Analytics & Learning Loop"""
import sys

RED, GREEN, YELLOW, RESET = "\033[91m", "\033[92m", "\033[93m", "\033[0m"

def check():
    try:
        with open("supabase/migrations/20260516000007_voice_analytics_phase8.sql") as f:
            mig = f.read()
    except:
        print(f"{RED}FAIL{RESET} Migration not found")
        return False

    results = {"pass": 0, "fail": 0}
    print("\n[L1] Analytics Table")
    
    if "conversation_analytics" in mig:
        print(f"  {GREEN}PASS{RESET} conversation_analytics table defined")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} Table missing")
        results["fail"] += 1

    print("\n[L2] Quality Metrics")
    if "answer_quality_rating" in mig and "avg_quality" in mig:
        print(f"  {GREEN}PASS{RESET} Quality rating + aggregation view")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} Quality metrics not tracked")
        results["fail"] += 1

    print("\n[L3] Learning Signals")
    if "v_conversation_health" in mig:
        print(f"  {GREEN}PASS{RESET} Health view for quality tracking")
        results["pass"] += 1
    else:
        print(f"  {YELLOW}WARN{RESET} Learning signals view missing")

    print("\n" + "="*70)
    print(f"PASS: {results['pass']} | FAIL: {results['fail']}")
    return results["fail"] == 0

if __name__ == "__main__":
    sys.exit(0 if check() else 1)
