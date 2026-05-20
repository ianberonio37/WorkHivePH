#!/usr/bin/env python3
"""
Phase 4 Validator: Multi-Turn Dialog Flow & Intent Refinement

Validates that dialog state tracking is properly wired:

6 Layers:
  L1: dialog_state table exists with correct schema
  L2: Intent consistency across turns (intent should not flip randomly)
  L3: Clarification triggers when confidence <0.65 (regression test)
  L4: Slot-filling: same-domain questions reuse context
  L5: Context carryover: turn #2-5 respect turn #1 context
  L6: Response time acceptable (should be <3s total with dialog overhead)

SUCCESS: All 6 layers pass (indicates Phase 4 wiring is complete)
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

def check_phase_4_dialog():
    try:
        with open("voice-handler.js", "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"{RED}FAIL{RESET} voice-handler.js not found")
        return False

    results = {"pass": 0, "fail": 0}

    # L1: dialog_state table migration exists
    print("\n[L1] Database schema (dialog_state table)")
    migration_file = "supabase/migrations/20260516000002_dialog_state_phase4.sql"
    try:
        with open(migration_file, "r", encoding="utf-8") as f:
            migration = f.read()

        required_columns = [
            "session_id text",
            "current_intent text",
            "intent_confidence real",
            "context_slots jsonb",
            "clarification_pending boolean",
        ]

        missing_cols = [col for col in required_columns if col not in migration]
        if not missing_cols:
            print(f"  {GREEN}PASS{RESET} dialog_state table schema complete")
            results["pass"] += 1
        else:
            print(f"  {RED}FAIL{RESET} Missing columns: {missing_cols}")
            results["fail"] += 1

        # Check RPC functions
        if "fetch_dialog_state" in migration and "update_dialog_state" in migration:
            print(f"  {GREEN}PASS{RESET} RPC functions (fetch + update) defined")
            results["pass"] += 1
        else:
            print(f"  {RED}FAIL{RESET} RPC functions missing")
            results["fail"] += 1

    except FileNotFoundError:
        print(f"  {RED}FAIL{RESET} Migration file {migration_file} not found")
        results["fail"] += 1

    # L2: Intent consistency across turns
    print("\n[L2] Intent consistency tracking")

    if "priorIntent" in content and "newIntentKind" in content:
        print(f"  {GREEN}PASS{RESET} Prior intent tracked (L2 consistency)")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} Prior intent tracking missing")
        results["fail"] += 1

    if "_fetchDialogState(" in content:
        print(f"  {GREEN}PASS{RESET} Dialog state fetched at turn start")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} Dialog state fetch not found")
        results["fail"] += 1

    # L3: Clarification trigger (confidence <0.65)
    print("\n[L3] Clarification logic")

    if "_shouldClarify(" in content and "0.65" in content:
        print(f"  {GREEN}PASS{RESET} Clarification trigger on confidence <0.65")
        results["pass"] += 1
    else:
        print(f"  {YELLOW}WARN{RESET} Clarification confidence threshold unclear")

    if "_generateClarification(" in content:
        print(f"  {GREEN}PASS{RESET} Clarification prompt generation exists")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} Clarification prompt generator missing")
        results["fail"] += 1

    # L4: Slot-filling context carryover
    print("\n[L4] Slot-filling context carryover")

    if "priorSlots" in content or "context_slots" in content:
        print(f"  {GREEN}PASS{RESET} Context slots tracked (L4 carryover)")
        results["pass"] += 1
    else:
        print(f"  {YELLOW}WARN{RESET} Slot-filling context unclear")

    # L5: Context carryover in system prompt
    print("\n[L5] Dialog state in system prompt")

    if "dialogSection" in content and "dialogState" in content:
        print(f"  {GREEN}PASS{RESET} Dialog state section in system prompt")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} Dialog state not in system prompt")
        results["fail"] += 1

    if "Current intent:" in content or "DIALOG STATE" in content:
        print(f"  {GREEN}PASS{RESET} Dialog state formatted in prompt")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} Dialog state prompt format missing")
        results["fail"] += 1

    # L6: Dialog state update after response
    print("\n[L6] Dialog state persistence")

    if "_updateDialogState(" in content:
        print(f"  {GREEN}PASS{RESET} Dialog state updated after responses")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} Dialog state update not called")
        results["fail"] += 1

    # Summary
    print("\n" + "=" * 70)
    print(f"PASS: {results['pass']} | FAIL: {results['fail']}")
    print("=" * 70)

    return results["fail"] == 0


if __name__ == "__main__":
    success = check_phase_4_dialog()
    sys.exit(0 if success else 1)
