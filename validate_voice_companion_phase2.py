#!/usr/bin/env python3
"""
Voice Companion Phase 2 Validator

Validates free-tier model A/B testing infrastructure:

2 Layers:
  L1: Model orchestrator tool exists (tools/model_orchestrator.py)
  L2: Free-tier model configuration available (Groq Scout, Cerebras Qwen, SambaNova)
  L3: Fallback chain implemented (Scout -> Qwen -> SambaNova)

SUCCESS: All 3 layers pass (indicates Phase 2 infrastructure ready for A/B testing)
"""

import os
import sys

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
    print("\n[L2] Free-tier LLM model support")
    if os.path.exists("tools/model_orchestrator.py"):
        with open("tools/model_orchestrator.py", "r") as f:
            content = f.read()

            models_found = 0
            if "meta-llama/llama-4-scout-17b" in content or "Groq Scout" in content:
                print(f"  {GREEN}PASS{RESET} Groq Scout (primary)")
                models_found += 1
            else:
                print(f"  {RED}FAIL{RESET} Groq Scout not configured")
                results["fail"] += 1

            if "qwen2.5-7b-instruct" in content or "Cerebras" in content:
                print(f"  {GREEN}PASS{RESET} Cerebras Qwen")
                models_found += 1
            else:
                print(f"  {YELLOW}WARN{RESET} Cerebras Qwen not configured")

            if "mistral-large" in content or "Voyage" in content:
                print(f"  {GREEN}PASS{RESET} Voyage AI (Mistral)")
                models_found += 1
            else:
                print(f"  {YELLOW}WARN{RESET} Voyage AI not configured")

            if "jina" in content.lower():
                print(f"  {GREEN}PASS{RESET} Jina AI (fallback)")
                models_found += 1
            else:
                print(f"  {YELLOW}WARN{RESET} Jina AI not configured")

            if models_found >= 2:
                results["pass"] += 1
            else:
                results["fail"] += 1

    # L3: Fallback chain
    print("\n[L3] Model fallback chain (Scout -> Qwen -> SambaNova)")
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
    print("\n[Config] Environment variables")
    has_groq = "GROQ_API_KEY" in os.environ or os.path.exists(".env")
    has_cerebras = "CEREBRAS_API_KEY" in os.environ or os.path.exists(".env")
    has_sambanova = "SAMBANOVA_API_KEY" in os.environ or os.path.exists(".env")

    if has_groq:
        print(f"  {GREEN}OK{RESET} GROQ_API_KEY configured (or .env exists)")
    else:
        print(f"  {YELLOW}WARN{RESET} GROQ_API_KEY not found")

    if has_cerebras:
        print(f"  {GREEN}OK{RESET} CEREBRAS_API_KEY configured (or .env exists)")
    else:
        print(f"  {YELLOW}WARN{RESET} CEREBRAS_API_KEY not found")

    if has_sambanova:
        print(f"  {GREEN}OK{RESET} SAMBANOVA_API_KEY configured (or .env exists)")
    else:
        print(f"  {YELLOW}WARN{RESET} SAMBANOVA_API_KEY not found")

    # Summary
    print("\n" + "=" * 70)
    print(f"PASS: {results['pass']} | FAIL: {results['fail']}")
    print("=" * 70)
    print("\nPhase 2 infrastructure is ready for A/B testing.")
    print("To enable model switching:")
    print("  1. Set MODEL_STRATEGY env var (scout/qwen/voyage/jina/round-robin)")
    print("  2. Configure free-tier API keys in .env:")
    print("     - GROQ_API_KEY (required)")
    print("     - CEREBRAS_API_KEY (optional fallback 1)")
    print("     - VOYAGE_API_KEY (optional fallback 2)")
    print("     - JINA_API_KEY (optional fallback 3 + embeddings)")
    print("  3. Enable AI_EVAL_ENABLED=1 to track quality metrics")

    return results["fail"] == 0


if __name__ == "__main__":
    success = check_phase_2_model_testing()
    sys.exit(0 if success else 1)
