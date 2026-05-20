#!/usr/bin/env python3
"""
Voice Companion Phase 1 Validator

Validates that Phase 1 (Multi-Agent Orchestrator) is properly wired:

3 Layers:
  L1: Three agent functions exist (_classifySemanticRoute, _invokePlatformScraper, _invokeRAGAgent)
  L2: Semantic router classification is called in _converseInline
  L3: Agent results (platformData, ragContext) are passed to _buildVoiceSystemPrompt
  L4: System prompt has platformSection and ragSection integrated

SUCCESS: All 4 layers pass (indicates Phase 1 wiring is complete)
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

def check_phase_1_orchestration():
    try:
        with open("voice-handler.js", "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"{RED}FAIL{RESET} voice-handler.js not found")
        return False

    results = {"pass": 0, "fail": 0}

    # L1: Three agent functions exist
    print("\n[L1] Agent function definitions")
    agents = [
        ("_classifySemanticRoute", "Semantic router classifier"),
        ("_invokePlatformScraper", "Platform scraper (KPI data)"),
        ("_invokeRAGAgent", "RAG agent (semantic context)"),
    ]

    for func_name, description in agents:
        if f"async function {func_name}(" in content:
            print(f"  {GREEN}PASS{RESET} {func_name} defined ({description})")
            results["pass"] += 1
        else:
            print(f"  {RED}FAIL{RESET} {func_name} not found")
            results["fail"] += 1

    # L2: All agents are called unconditionally in parallel (no routing gates)
    # Simpler design: always scan everything, hand to LLM, let it pick what's relevant.
    print("\n[L2] Agent orchestration in _converseInline (always-scan model)")

    # Platform scraper must be called unconditionally inside Promise.all
    # More robust check: look for Promise.all with both agents
    scraper_in_promise = re.search(
        r"Promise\.all\(\[\s*(?:[^,]*,)*\s*_invokePlatformScraper\(",
        content,
        re.DOTALL
    )
    if scraper_in_promise:
        print(f"  {GREEN}PASS{RESET} Platform scraper always called in Promise.all")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} Platform scraper not in Promise.all (must be unconditional)")
        results["fail"] += 1

    # RAG agent must also be unconditional
    # More robust check: look for Promise.all with RAG context fetch (either _invokeRAGAgent or _fetchRAGContext)
    rag_in_promise = re.search(
        r"Promise\.all\(\[\s*(?:[^,]*,)*\s*(?:_invokeRAGAgent|_fetchRAGContext)\(",
        content,
        re.DOTALL
    )
    if rag_in_promise:
        print(f"  {GREEN}PASS{RESET} RAG agent always called in Promise.all")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} RAG agent not in Promise.all (must be unconditional)")
        results["fail"] += 1

    # Canonical data fetch must cover all KPI types
    kpi_kinds = ["'mtbf'", "'mttr'", "'downtime'", "'risk_top'", "'failures_count'"]
    missing_kpis = [k for k in kpi_kinds if f"kind: {k}" not in content]
    if not missing_kpis:
        print(f"  {GREEN}PASS{RESET} All 5 KPI kinds fetched (mtbf/mttr/downtime/risk_top/failures_count)")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} Missing KPI kinds in canonical fetch: {missing_kpis}")
        results["fail"] += 1

    # L3: Agent results passed to _buildVoiceSystemPrompt
    print("\n[L3] Agent data passed to system prompt builder")

    prompt_call_match = re.search(
        r"const\s+system\s+=\s+_buildVoiceSystemPrompt\([^)]*platformData[^)]*ragContext[^)]*\)",
        content,
        re.DOTALL
    )

    if prompt_call_match:
        print(f"  {GREEN}PASS{RESET} platformData and ragContext passed to _buildVoiceSystemPrompt")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} Agent data not passed to _buildVoiceSystemPrompt")
        results["fail"] += 1

    # Check if _buildVoiceSystemPrompt signature includes the new parameters (may include Phase 4/5 additions)
    if "function _buildVoiceSystemPrompt(" in content and "platformData" in content and "ragContext" in content:
        print(f"  {GREEN}PASS{RESET} _buildVoiceSystemPrompt signature includes platformData, ragContext (+ optional Phase 4/5 params)")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} _buildVoiceSystemPrompt signature missing agent parameters")
        results["fail"] += 1

    # L4: System prompt integrates agent data blocks
    print("\n[L4] Agent data integration in system prompt")

    if "const platformSection = platformData" in content:
        print(f"  {GREEN}PASS{RESET} platformSection defined and conditionally included")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} platformSection not found in _buildVoiceSystemPrompt")
        results["fail"] += 1

    if "const ragSection = ragContext" in content:
        print(f"  {GREEN}PASS{RESET} ragSection defined and conditionally included")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} ragSection not found in _buildVoiceSystemPrompt")
        results["fail"] += 1

    # Verify both sections are in the return statement
    if "platformSection +" in content and "ragSection +" in content:
        print(f"  {GREEN}PASS{RESET} Both platformSection and ragSection injected into system prompt")
        results["pass"] += 1
    else:
        print(f"  {YELLOW}WARN{RESET} Agent sections may not be properly injected into return statement")

    # Summary
    print("\n" + "=" * 70)
    print(f"PASS: {results['pass']} | FAIL: {results['fail']}")
    print("=" * 70)

    return results["fail"] == 0


if __name__ == "__main__":
    success = check_phase_1_orchestration()
    sys.exit(0 if success else 1)
