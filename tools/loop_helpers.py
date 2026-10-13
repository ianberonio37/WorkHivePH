#!/usr/bin/env python3
"""
Shared helpers for AI self-improvement loop layers.

Common utilities: free-tier AI calls through the platform chain (tools/ai_chain.py), logging, file operations.
Uses free tier providers ONLY — no paid APIs.
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

# Color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"

def call_claude_free(prompt: str, max_tokens: int = 2000) -> str:
    """
    Free-tier AI through the platform's chain: tools/ai_chain.call_ai_chain, the Python mirror of
    supabase/functions/_shared/ai-chain.ts (free models only, paced, falls through every provider).

    REROUTED 2026-10-08. This used to call providers itself and took only the FIRST one with a key, so a single
    429 ended the call - and every model it named was gone: Groq llama-3.3-70b-versatile (retired 2026-09-10),
    Cerebras (402 payment_required on every call; the provider is now off the platform), SambaNova (no key; credits
    expire, so never a candidate) and an OpenRouter llama-2 slug that no longer exists.
    Returns "" when nothing answered, as before.
    """
    root = str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    from tools.ai_chain import call_ai_chain
    out = call_ai_chain(prompt, max_tokens=max_tokens, json_mode=False)
    if out == "{}":
        print(f"{RED}ERROR: every free model in the chain was rate-limited, refused or unkeyed.{RESET}")
        return ""
    return out

def load_json_file(path: str) -> dict:
    """Load JSON file, return empty dict if not found or invalid."""
    p = Path(path)
    if not p.exists():
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}

def load_jsonl_file(path: str) -> list:
    """Load JSONL file (one JSON object per line)."""
    p = Path(path)
    if not p.exists():
        return []

    items = []
    try:
        with open(p) as f:
            for line in f:
                if line.strip():
                    try:
                        items.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    except Exception:
        pass

    return items

def save_jsonl_file(path: str, items: list, append: bool = False):
    """Save JSONL file (one JSON object per line)."""
    p = Path(path)
    mode = "a" if append else "w"

    try:
        with open(p, mode) as f:
            for item in items:
                f.write(json.dumps(item) + "\n")
    except Exception as e:
        print(f"{RED}Error writing {path}: {e}{RESET}")

def log_message(msg: str, level: str = "info"):
    """Log message with level indicator."""
    if level == "pass":
        prefix = f"{GREEN}[PASS]{RESET}"
    elif level == "fail":
        prefix = f"{RED}[FAIL]{RESET}"
    elif level == "warn":
        prefix = f"{YELLOW}[WARN]{RESET}"
    else:
        prefix = "[INFO]"

    print(f"  {prefix} {msg}")

def extract_json_from_text(text: str) -> Optional[dict]:
    """Extract JSON object from text (handles markdown code blocks)."""
    import re

    # Try to find JSON in code block
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if json_match:
        json_text = json_match.group(1)
    else:
        # Try to find JSON object directly
        json_match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', text)
        if json_match:
            json_text = json_match.group(1)
        else:
            return None

    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        return None

def ensure_test_images():
    """Create placeholder test images for visual defect scenarios."""
    test_images_dir = Path("test-images")
    test_images_dir.mkdir(exist_ok=True)

    # Create placeholder image (minimal valid PNG)
    placeholder_png = bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010802000000"
        "90773db3000000024944415408d76360000000020001e5276d50000000"
        "0049454e44ae426082"
    )

    test_file = test_images_dir / "defect-example.jpg"
    if not test_file.exists():
        try:
            test_file.write_bytes(placeholder_png)
            print(f"{GREEN}[PASS]{RESET} Created placeholder test image: {test_file}")
        except Exception as e:
            print(f"{YELLOW}[WARN]{RESET} Could not create test image: {e}")

def verify_environment() -> bool:
    """Check all required environment variables and services."""
    all_good = True

    # Check for at least one free AI provider
    # the keys the platform chain (tools/ai_chain.py) uses; it also reads .env and supabase/functions/.env itself
    providers = ["GROQ_API_KEY", "GEMINI_API_KEY", "MISTRAL_API_KEY", "OPENROUTER_API_KEY"]
    has_provider = any(os.getenv(p) for p in providers)

    if not has_provider:
        print(f"{YELLOW}[WARN]{RESET} No free AI provider configured")
        print("       Set ONE of: GROQ_API_KEY, GEMINI_API_KEY, MISTRAL_API_KEY, OPENROUTER_API_KEY")
        print("       Free tiers: https://console.groq.com, https://aistudio.google.com, https://console.mistral.ai, https://openrouter.ai")
        all_good = False
    else:
        for provider in providers:
            if os.getenv(provider):
                print(f"{GREEN}[PASS]{RESET} {provider} found")
                break

    return all_good

if __name__ == "__main__":
    ensure_test_images()
    verify_environment()
