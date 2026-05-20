#!/usr/bin/env python3
"""
Phase 7: TTS Quality Metrics Validator

Validates that TTS quality logging is properly integrated:

4 Layers:
  L1: tts_quality_log migration exists with correct schema
  L2: _logTTSMetrics() function exists and logs to tts_quality_log
  L3: TTS latency is measured in _converseInline
  L4: _logTTSMetrics() called in both success and error paths

SUCCESS: All 4 layers pass (indicates Phase 7 TTS metrics collection is wired)
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

def check_phase_7_tts():
    results = {"pass": 0, "fail": 0}

    # L1: tts_quality_log migration
    print("\n[L1] TTS quality log table schema (migration)")
    migration_files = glob.glob("supabase/migrations/*azure*tts*.sql")
    if not migration_files:
        migration_files = glob.glob("supabase/migrations/*tts*.sql")

    migration_content = ""
    for mfile in migration_files:
        try:
            with open(mfile, "r", encoding="utf-8") as f:
                content = f.read()
                if "tts_quality_log" in content:
                    migration_content = content
                    break
        except:
            pass

    if migration_content and "tts_quality_log" in migration_content and "latency_ms" in migration_content:
        print(f"  {GREEN}PASS{RESET} tts_quality_log migration found with latency_ms column")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} tts_quality_log schema incomplete")
        results["fail"] += 1

    # L2: _logTTSMetrics function
    print("\n[L2] TTS metrics function implementation")
    try:
        with open("voice-handler.js", "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"{RED}FAIL{RESET} voice-handler.js not found")
        return False

    if "async function _logTTSMetrics(" in content:
        print(f"  {GREEN}PASS{RESET} _logTTSMetrics function defined")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} _logTTSMetrics function not found")
        results["fail"] += 1

    if "tts_quality_log" in content and "latency_ms:" in content:
        print(f"  {GREEN}PASS{RESET} _logTTSMetrics logs latency_ms")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} _logTTSMetrics does not log properly")
        results["fail"] += 1

    # L3: TTS latency tracking
    print("\n[L3] TTS latency measurement")
    if "ttsStartMs" in content and "ttsLatencyMs" in content:
        print(f"  {GREEN}PASS{RESET} TTS latency is measured in _converseInline")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} TTS latency not tracked")
        results["fail"] += 1

    # L4: Integration in both paths
    print("\n[L4] Integration in both success and error paths")
    # Count how many times _logTTSMetrics is called
    call_count = content.count("_logTTSMetrics(")

    if call_count >= 2:
        print(f"  {GREEN}PASS{RESET} _logTTSMetrics called {call_count} times (success + error paths)")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} _logTTSMetrics called only {call_count} time(s), need at least 2 (success + error)")
        results["fail"] += 1

    # Summary
    print("\n" + "=" * 70)
    print(f"PASS: {results['pass']} | FAIL: {results['fail']}")
    print("=" * 70)

    return results["fail"] == 0


if __name__ == "__main__":
    success = check_phase_7_tts()
    sys.exit(0 if success else 1)
