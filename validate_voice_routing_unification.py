#!/usr/bin/env python3
"""
Voice Routing Unification Validator (Phase 0)

Checks that voice-handler.js uses router output as canonical intent source,
not duplicate _classifyDataIntent regex classifier.

3 Layers:
  L1: voice-action-router is invoked and result stored in routerData
  L2: routerData is passed to _converseInline (not just unhandledKind)
  L3: _classifyDataIntent is removed or no longer called in conversational path
"""

import re
import sys

# Colors
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def check_phase_0_unification():
    try:
        with open("voice-handler.js", "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"{RED}FAIL{RESET} voice-handler.js not found")
        return False

    results = {"pass": 0, "fail": 0}

    # ─────────────────────────────────────────────────────────────────────────────
    # L1: Router is invoked and output is stored
    # ─────────────────────────────────────────────────────────────────────────────
    print("\n[L1] Router invocation and storage")
    if "db.functions.invoke('voice-action-router'" in content:
        print(f"  {GREEN}PASS{RESET} voice-action-router is invoked")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} voice-action-router invocation not found")
        results["fail"] += 1

    if "const { data: routerData, error: routerErr }" in content:
        print(f"  {GREEN}PASS{RESET} Router result stored in routerData")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} Router result not stored in routerData")
        results["fail"] += 1

    # ─────────────────────────────────────────────────────────────────────────────
    # L2: Router output is passed to _converseInline (not just unhandledKind)
    # ─────────────────────────────────────────────────────────────────────────────
    print("\n[L2] Router context passed to _converseInline")

    # Find the _converseInline call in conversational path
    converse_call_match = re.search(
        r"await\s+_converseInline\s*\(\s*transcript\s*,\s*(\{[^}]+\})\s*\)",
        content,
        re.DOTALL
    )

    if converse_call_match:
        converse_args = converse_call_match.group(1)
        print(f"  Found _converseInline call with args: {converse_args[:80]}...")

        has_router_intents = "routerIntents" in converse_args
        has_router_narration = "routerNarration" in converse_args
        has_asset_resolution = "assetResolution" in converse_args

        if has_router_intents:
            print(f"    {GREEN}PASS{RESET} routerIntents passed")
            results["pass"] += 1
        else:
            print(f"    {RED}FAIL{RESET} routerIntents NOT passed")
            results["fail"] += 1

        if has_router_narration:
            print(f"    {GREEN}PASS{RESET} routerNarration passed")
            results["pass"] += 1
        else:
            print(f"    {YELLOW}INFO{RESET} routerNarration NOT passed (optional but recommended)")

        if has_asset_resolution:
            print(f"    {GREEN}PASS{RESET} assetResolution passed")
            results["pass"] += 1
        else:
            print(f"    {YELLOW}INFO{RESET} assetResolution NOT passed (optional)")
    else:
        print(f"  {RED}FAIL{RESET} Could not find _converseInline call pattern")
        results["fail"] += 1

    # ─────────────────────────────────────────────────────────────────────────────
    # L3: _classifyDataIntent is removed from conversational path
    # ─────────────────────────────────────────────────────────────────────────────
    print("\n[L3] Duplicate classifier removal")

    # Find _converseInline function definition
    converse_func_match = re.search(
        r"async\s+function\s+_converseInline\s*\([^)]*\)\s*\{(.*?)\n\s{2}\}(?:\s|$)",
        content,
        re.DOTALL
    )

    if converse_func_match:
        converse_body = converse_func_match.group(1)

        # Check if _classifyDataIntent is called in _converseInline
        if "const dataIntent = _classifyDataIntent(transcript)" in converse_body:
            print(f"  {RED}FAIL{RESET} Old _classifyDataIntent(transcript) call still present in _converseInline")
            results["fail"] += 1
        elif "_classifyDataIntent" in converse_body:
            print(f"  {YELLOW}INFO{RESET} _classifyDataIntent is still referenced in _converseInline (check if truly removed)")
        else:
            print(f"  {GREEN}PASS{RESET} _classifyDataIntent removed from _converseInline conversational path")
            results["pass"] += 1

        # Check if routerContext is extracted and used
        if "const routerContext = " in converse_body or "routerContext =" in converse_body:
            print(f"  {GREEN}PASS{RESET} routerContext is extracted from routerIntents")
            results["pass"] += 1
        else:
            print(f"  {RED}FAIL{RESET} routerContext extraction not found")
            results["fail"] += 1
    else:
        print(f"  {RED}FAIL{RESET} Could not find _converseInline function")
        results["fail"] += 1

    # ─────────────────────────────────────────────────────────────────────────────
    # Bonus: Check _buildVoiceSystemPrompt accepts routerContext
    # ─────────────────────────────────────────────────────────────────────────────
    print("\n[Bonus] System prompt builder wiring")

    # Check if _buildVoiceSystemPrompt signature includes routerContext
    if re.search(r"function _buildVoiceSystemPrompt\([^)]*routerContext[^)]*\)", content):
        print(f"  {GREEN}PASS{RESET} _buildVoiceSystemPrompt signature accepts routerContext")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} _buildVoiceSystemPrompt signature missing routerContext parameter")
        results["fail"] += 1

    # Check if routerContext is passed when calling _buildVoiceSystemPrompt
    if re.search(
        r"const\s+system\s+=\s+_buildVoiceSystemPrompt\([^)]*routerContext[^)]*\)",
        content,
        re.DOTALL
    ):
        print(f"  {GREEN}PASS{RESET} routerContext is passed to _buildVoiceSystemPrompt")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} routerContext not passed to _buildVoiceSystemPrompt")
        results["fail"] += 1

    # ─────────────────────────────────────────────────────────────────────────────
    # Summary
    # ─────────────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print(f"PASS: {results['pass']} | FAIL: {results['fail']}")
    print("=" * 70)

    return results["fail"] == 0


if __name__ == "__main__":
    success = check_phase_0_unification()
    sys.exit(0 if success else 1)
