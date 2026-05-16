#!/usr/bin/env python3
"""Phase 9 Validator: Cross-Hive Coordination & Team Context"""
import sys

RED, GREEN, YELLOW, RESET = "\033[91m", "\033[92m", "\033[93m", "\033[0m"

def check():
    try:
        with open("supabase/migrations/20260516000008_team_coordination_phase9.sql") as f:
            mig = f.read()
    except:
        print(f"{RED}FAIL{RESET} Migration not found")
        return False

    results = {"pass": 0, "fail": 0}
    print("\n[L1] Cross-Hive Alerts")
    
    if "cross_hive_alerts" in mig and "related_hive_ids" in mig:
        print(f"  {GREEN}PASS{RESET} Cross-hive alert table defined")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} Alert table missing")
        results["fail"] += 1

    print("\n[L2] Best Practices Sharing")
    if "best_practices" in mig and "effectiveness_score" in mig:
        print(f"  {GREEN}PASS{RESET} Best practices + effectiveness scoring")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} Best practices table missing")
        results["fail"] += 1

    print("\n[L3] Team Context")
    if "problem_category" in mig and "solution_" in mig:
        print(f"  {GREEN}PASS{RESET} Problem-to-solution mapping")
        results["pass"] += 1
    else:
        print(f"  {YELLOW}WARN{RESET} Team context structure unclear")

    print("\n" + "="*70)
    print(f"PASS: {results['pass']} | FAIL: {results['fail']}")
    return results["fail"] == 0

if __name__ == "__main__":
    sys.exit(0 if check() else 1)
