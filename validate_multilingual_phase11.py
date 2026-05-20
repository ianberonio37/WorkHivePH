#!/usr/bin/env python3
"""
Phase 11: Multilingual Support Validator

Validates that multilingual term lookup is properly integrated:

4 Layers:
  L1: multilingual_terms migration exists with correct schema
  L2: language_preferences migration exists (optional)
  L3: _lookupMultilingualTerm() function implemented
  L4: System prompt acknowledges multilingual input handling

SUCCESS: All 4 layers pass (indicates Phase 11 multilingual support is wired)
"""

import re
import sys
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import glob

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def check_phase_11_multilingual():
    results = {"pass": 0, "fail": 0}

    # L1: multilingual_terms migration
    print("\n[L1] Multilingual terms table schema (migration)")
    migration_files = glob.glob("supabase/migrations/*multilingual*.sql")
    if migration_files:
        try:
            with open(migration_files[0], "r", encoding="utf-8") as f:
                migration_content = f.read()
            if "multilingual_terms" in migration_content and "tagalog_term" in migration_content:
                print(f"  {GREEN}PASS{RESET} multilingual_terms migration found")
                results["pass"] += 1
            else:
                print(f"  {RED}FAIL{RESET} multilingual_terms schema incomplete")
                results["fail"] += 1
        except:
            print(f"  {RED}FAIL{RESET} Could not read migration file")
            results["fail"] += 1
    else:
        print(f"  {RED}FAIL{RESET} multilingual_terms migration not found")
        results["fail"] += 1

    # L2: language_preferences migration
    print("\n[L2] Language preferences table schema (migration)")
    if migration_files:
        with open(migration_files[0], "r", encoding="utf-8") as f:
            migration_content = f.read()
        if "language_preferences" in migration_content:
            print(f"  {GREEN}PASS{RESET} language_preferences migration found")
            results["pass"] += 1
        else:
            print(f"  {YELLOW}WARN{RESET} language_preferences not found (optional)")
    else:
        print(f"  {YELLOW}WARN{RESET} language_preferences migration not found (optional)")

    # L3: _lookupMultilingualTerm function
    print("\n[L3] Multilingual lookup function implementation")
    try:
        with open("voice-handler.js", "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"{RED}FAIL{RESET} voice-handler.js not found")
        return False

    if "async function _lookupMultilingualTerm(" in content:
        print(f"  {GREEN}PASS{RESET} _lookupMultilingualTerm function defined")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} _lookupMultilingualTerm function not found")
        results["fail"] += 1

    if "multilingual_terms" in content and ("tagalog_term" in content or "visayan_term" in content):
        print(f"  {GREEN}PASS{RESET} _lookupMultilingualTerm queries multilingual_terms")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} _lookupMultilingualTerm does not query multilingual_terms properly")
        results["fail"] += 1

    # L4: System prompt language awareness
    print("\n[L4] System prompt language awareness")
    if "Filipino / Cebuano / Tagalog" in content or "Tagalog / Cebuano" in content:
        print(f"  {GREEN}PASS{RESET} System prompt acknowledges multilingual input")
        results["pass"] += 1
    else:
        print(f"  {YELLOW}WARN{RESET} System prompt language instructions not explicit (optional)")

    # Summary
    print("\n" + "=" * 70)
    print(f"PASS: {results['pass']} | FAIL: {results['fail']}")
    print("=" * 70)

    return results["fail"] == 0


if __name__ == "__main__":
    success = check_phase_11_multilingual()
    sys.exit(0 if success else 1)
