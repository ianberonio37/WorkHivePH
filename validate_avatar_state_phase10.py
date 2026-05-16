#!/usr/bin/env python3
"""
Phase 10: Avatar State Validator

Validates that avatar state tracking is properly integrated:

4 Layers:
  L1: avatar_state migration exists with correct schema
  L2: _updateAvatarState() function exists and upserts to avatar_state
  L3: avatar_animations migration exists (optional)
  L4: _updateAvatarState() called after response generation

SUCCESS: All 4 layers pass (indicates Phase 10 avatar state management is wired)
"""

import re
import sys
import glob

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def check_phase_10_avatar():
    results = {"pass": 0, "fail": 0}

    # L1: avatar_state migration
    print("\n[L1] Avatar state table schema (migration)")
    migration_files = glob.glob("supabase/migrations/*avatar*.sql")
    if migration_files:
        try:
            with open(migration_files[0], "r", encoding="utf-8") as f:
                migration_content = f.read()
            if "avatar_state" in migration_content and "emotion" in migration_content:
                print(f"  {GREEN}PASS{RESET} avatar_state migration found")
                results["pass"] += 1
            else:
                print(f"  {RED}FAIL{RESET} avatar_state schema incomplete")
                results["fail"] += 1
        except:
            print(f"  {RED}FAIL{RESET} Could not read migration file")
            results["fail"] += 1
    else:
        print(f"  {RED}FAIL{RESET} avatar_state migration not found")
        results["fail"] += 1

    # L3: avatar_animations migration (optional)
    print("\n[L3] Avatar animations table schema (migration)")
    if migration_files:
        with open(migration_files[0], "r", encoding="utf-8") as f:
            migration_content = f.read()
        if "avatar_animations" in migration_content:
            print(f"  {GREEN}PASS{RESET} avatar_animations migration found")
            results["pass"] += 1
        else:
            print(f"  {YELLOW}WARN{RESET} avatar_animations not found (optional)")

    # L2: _updateAvatarState function
    print("\n[L2] Avatar state function implementation")
    try:
        with open("voice-handler.js", "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"{RED}FAIL{RESET} voice-handler.js not found")
        return False

    if "async function _updateAvatarState(" in content:
        print(f"  {GREEN}PASS{RESET} _updateAvatarState function defined")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} _updateAvatarState function not found")
        results["fail"] += 1

    if "avatar_state" in content and ".upsert({" in content:
        print(f"  {GREEN}PASS{RESET} _updateAvatarState uses upsert")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} _updateAvatarState does not use upsert properly")
        results["fail"] += 1

    # L4: Integration in _converseInline
    print("\n[L4] Integration in _converseInline")
    avatar_call_count = content.count("_updateAvatarState(db, sessionId")
    if avatar_call_count >= 1:
        print(f"  {GREEN}PASS{RESET} _updateAvatarState called {avatar_call_count} time(s)")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} _updateAvatarState not integrated")
        results["fail"] += 1

    # Summary
    print("\n" + "=" * 70)
    print(f"PASS: {results['pass']} | FAIL: {results['fail']}")
    print("=" * 70)

    return results["fail"] == 0


if __name__ == "__main__":
    success = check_phase_10_avatar()
    sys.exit(0 if success else 1)
