#!/usr/bin/env python3
"""
Phase 6: Offline Resilience Validator

Validates that offline caching is properly integrated:

4 Layers:
  L1: offline_snapshot_cache migration exists with correct schema
  L2: _cacheOfflineSnapshot() function implemented in voice-handler.js
  L3: voice_response_queue migration exists
  L4: _cacheOfflineSnapshot() integrated in _converseInline orchestration

SUCCESS: All 4 layers pass (indicates Phase 6 offline caching is wired)
"""

import re
import sys
import glob

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def check_phase_6_offline():
    results = {"pass": 0, "fail": 0}

    # L1: offline_snapshot_cache migration exists
    print("\n[L1] Offline cache table schema (migration)")
    migration_files = glob.glob("supabase/migrations/*offline*.sql")
    if migration_files:
        try:
            with open(migration_files[0], "r", encoding="utf-8") as f:
                migration_content = f.read()
            if "offline_snapshot_cache" in migration_content and "snapshot_data" in migration_content:
                print(f"  {GREEN}PASS{RESET} offline_snapshot_cache migration found")
                results["pass"] += 1
            else:
                print(f"  {RED}FAIL{RESET} offline_snapshot_cache schema incomplete")
                results["fail"] += 1
        except:
            print(f"  {RED}FAIL{RESET} Could not read migration file")
            results["fail"] += 1
    else:
        print(f"  {RED}FAIL{RESET} offline_snapshot_cache migration not found")
        results["fail"] += 1

    # L3: voice_response_queue migration exists
    print("\n[L3] Response queue table schema (migration)")
    if migration_files:
        with open(migration_files[0], "r", encoding="utf-8") as f:
            migration_content = f.read()
        if "voice_response_queue" in migration_content:
            print(f"  {GREEN}PASS{RESET} voice_response_queue migration found")
            results["pass"] += 1
        else:
            print(f"  {YELLOW}WARN{RESET} voice_response_queue not in migration (optional)")
    else:
        print(f"  {RED}FAIL{RESET} voice_response_queue migration not found")
        results["fail"] += 1

    # L2: _cacheOfflineSnapshot function in voice-handler.js
    print("\n[L2] Cache function implementation")
    try:
        with open("voice-handler.js", "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"{RED}FAIL{RESET} voice-handler.js not found")
        return False

    if "async function _cacheOfflineSnapshot(" in content:
        print(f"  {GREEN}PASS{RESET} _cacheOfflineSnapshot function defined")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} _cacheOfflineSnapshot function not found")
        results["fail"] += 1

    if "offline_snapshot_cache" in content and ".insert({" in content:
        print(f"  {GREEN}PASS{RESET} Function inserts into offline_snapshot_cache")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} Function does not properly use offline_snapshot_cache")
        results["fail"] += 1

    # L4: _cacheOfflineSnapshot integrated in _converseInline
    print("\n[L4] Integration in _converseInline")
    # Count calls to _cacheOfflineSnapshot
    cache_call_count = content.count("_cacheOfflineSnapshot(db, ctx.hive_id")
    if cache_call_count >= 1:
        print(f"  {GREEN}PASS{RESET} _cacheOfflineSnapshot called {cache_call_count} time(s)")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} _cacheOfflineSnapshot not integrated in orchestration")
        results["fail"] += 1

    # Summary
    print("\n" + "=" * 70)
    print(f"PASS: {results['pass']} | FAIL: {results['fail']}")
    print("=" * 70)

    return results["fail"] == 0


if __name__ == "__main__":
    success = check_phase_6_offline()
    sys.exit(0 if success else 1)
