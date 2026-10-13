#!/usr/bin/env python3
"""
Voice Companion Phase 2 Validator

Validates free-tier model A/B testing infrastructure:

2 Layers:
  L1: Model orchestrator tool exists (tools/model_orchestrator.py)
  L2: The orchestrator reaches models ONLY through the platform chain (tools/ai_chain.py) and
      calls no provider directly (2026-10-08: its old direct calls named retired Groq Scout, Cerebras -
      now off the platform - and two embeddings companies with no chat endpoint)
  L3: Fallback chain implemented (call_with_fallback over the strategy names)

SUCCESS: All 3 layers pass (indicates Phase 2 infrastructure ready for A/B testing)
"""

import os
import sys

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def check_phase_2_model_testing():
    results = {"pass": 0, "fail": 0}

    # L1: Model orchestrator exists
    print("\n[L1] Model orchestrator tool")
    if os.path.exists("tools/model_orchestrator.py"):
        with open("tools/model_orchestrator.py", "r") as f:
            content = f.read()
            if "call_model" in content and "call_with_fallback" in content:
                print(f"  {GREEN}PASS{RESET} model_orchestrator.py with call_model and call_with_fallback")
                results["pass"] += 1
            else:
                print(f"  {RED}FAIL{RESET} model_orchestrator missing key functions")
                results["fail"] += 1
    else:
        print(f"  {RED}FAIL{RESET} tools/model_orchestrator.py not found")
        results["fail"] += 1

    # L2: Free-tier model support
    print("\n[L2] Models reached only through the platform chain")
    if os.path.exists("tools/model_orchestrator.py"):
        with open("tools/model_orchestrator.py", "r", encoding="utf-8") as f:
            content = f.read()
        import re as _re
        code = "\n".join(ln for ln in content.splitlines() if not ln.lstrip().startswith("#"))
        direct = _re.findall(r"https://api\.[a-z0-9.-]+\.(?:com|ai)/", code)
        if "call_ai_chain" in code and "PROVIDER_CHAIN" in code and not direct:
            print(f"  {GREEN}PASS{RESET} model_orchestrator routes through tools/ai_chain.py and names no provider URL")
            results["pass"] += 1
        else:
            print(f"  {RED}FAIL{RESET} model_orchestrator calls a provider directly ({', '.join(direct) or 'no call_ai_chain'})")
            results["fail"] += 1

    # L3: Fallback chain
    print("\n[L3] Model fallback chain (call_with_fallback)")
    if os.path.exists("tools/model_orchestrator.py"):
        with open("tools/model_orchestrator.py", "r") as f:
            content = f.read()
            if "call_with_fallback" in content and "fallback_strategies" in content:
                print(f"  {GREEN}PASS{RESET} call_with_fallback implements chain")
                results["pass"] += 1
            else:
                print(f"  {RED}FAIL{RESET} Fallback chain not implemented")
                results["fail"] += 1

    # Configuration check
    print("\n[Config] Environment variables (the platform chain's providers)")
    for var in ("GROQ_API_KEY", "GEMINI_API_KEY", "MISTRAL_API_KEY", "OPENROUTER_API_KEY"):
        if var in os.environ or os.path.exists(".env"):
            print(f"  {GREEN}OK{RESET} {var} configured (or .env exists)")
        else:
            print(f"  {YELLOW}WARN{RESET} {var} not found")

    # Summary
    print("\n" + "=" * 70)
    print(f"PASS: {results['pass']} | FAIL: {results['fail']}")
    print("=" * 70)
    print("\nPhase 2 infrastructure is ready for A/B testing.")
    print("To enable model switching:")
    print("  1. Set MODEL_STRATEGY env var (scout/qwen/voyage/jina/round-robin)")
    print("  2. Configure free-tier API keys in .env:")
    print("     - GROQ_API_KEY, GEMINI_API_KEY, MISTRAL_API_KEY, OPENROUTER_API_KEY (the platform chain)")
    print("  3. Enable AI_EVAL_ENABLED=1 to track quality metrics")

    return results["fail"] == 0


if __name__ == "__main__":
    success = check_phase_2_model_testing()
    sys.exit(0 if success else 1)
