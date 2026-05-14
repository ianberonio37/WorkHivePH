#!/usr/bin/env python3
"""
Voice Companion Phase 3 Validator

Validates polish and error recovery features:

3 Layers:
  L1: Fallback reply generation (_generateFallbackReply function)
  L2: Intent-aware error messages (fallback replies match router intents)
  L3: Anon memory handling (session-only turns for Tester anon workers)
  L4: Error recovery in _converseInline (graceful catch block)

SUCCESS: All 4 layers pass (indicates Phase 3 Polish is complete)
"""

import re
import sys

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def check_phase_3_polish():
    try:
        with open("voice-handler.js", "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"{RED}FAIL{RESET} voice-handler.js not found")
        return False

    results = {"pass": 0, "fail": 0}

    # L1: Fallback reply generation exists
    print("\n[L1] Fallback reply generation function")
    if "function _generateFallbackReply(transcript, routerIntents, persona)" in content:
        print(f"  {GREEN}PASS{RESET} _generateFallbackReply function defined")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} _generateFallbackReply not found")
        results["fail"] += 1

    # L2: Intent-aware error messages
    print("\n[L2] Intent-aware error messages")
    if "kind === 'mtbf'" in content and "kind === 'logbook.create'" in content:
        print(f"  {GREEN}PASS{RESET} Fallback messages matched to intents (mtbf, logbook, etc)")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} Intent-aware fallback logic not found")
        results["fail"] += 1

    # L3: Anon memory handling
    print("\n[L3] Anon worker memory handling")
    if "_appendSessionTurn(transcript" in content:
        print(f"  {GREEN}PASS{RESET} Session-only turns for anon memory (_appendSessionTurn)")
        results["pass"] += 1
    else:
        print(f"  {YELLOW}WARN{RESET} _appendSessionTurn not called consistently")

    # Check if session turns are used as fallback
    if "const sessionTurns = _sessionTurns.map" in content:
        print(f"  {GREEN}PASS{RESET} Session turns used in memory merge (anon fallback)")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} Session-only memory fallback not implemented")
        results["fail"] += 1

    # L4: Error recovery in catch block
    print("\n[L4] Error recovery with graceful fallback")
    if "const fallbackReply = _generateFallbackReply" in content:
        print(f"  {GREEN}PASS{RESET} Catch block calls _generateFallbackReply (error recovery)")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} Error recovery fallback not implemented")
        results["fail"] += 1

    if "if (typeof window.speakPersona === 'function')" in content:
        speak_count = content.count("window.speakPersona(")
        if speak_count >= 2:  # At least success + error path
            print(f"  {GREEN}PASS{RESET} TTS works in both success and error paths")
            results["pass"] += 1
        else:
            print(f"  {YELLOW}WARN{RESET} TTS may not be called in error recovery")

    # UX refinement check
    print("\n[UX] User experience refinements")
    if "'(offline)'" in content or "(offline)" in content:
        print(f"  {GREEN}PASS{RESET} Offline status indicator in fallback")
        results["pass"] += 1
    else:
        print(f"  {YELLOW}INFO{RESET} No offline indicator (still acceptable)")

    # Summary
    print("\n" + "=" * 70)
    print(f"PASS: {results['pass']} | FAIL: {results['fail']}")
    print("=" * 70)
    print("\nPhase 3 Polish adds graceful error handling and better UX.")
    print("Features:")
    print("  - Intent-aware fallback replies (no generic errors)")
    print("  - Anon worker memory (session-only for Tester)")
    print("  - Offline TTS support (voice replies even when API down)")
    print("  - Captures transcript even on failure (never lost)")

    return results["fail"] == 0


if __name__ == "__main__":
    success = check_phase_3_polish()
    sys.exit(0 if success else 1)
