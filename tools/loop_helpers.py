#!/usr/bin/env python3
"""
Shared helpers for AI self-improvement loop layers.

Common utilities: Free AI calls (Groq/Cerebras/SambaNova), logging, file operations.
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
    Call free-tier AI via Groq (primary) or fallback providers.

    Priority order:
    1. Groq (GROQ_API_KEY) — free tier, fast
    2. Cerebras (CEREBRAS_API_KEY) — free tier
    3. SambaNova (SAMBANOVA_API_KEY) — free tier
    4. OpenRouter (OPENROUTER_API_KEY) — has free tier options

    Uses environment variables only — no hardcoded keys.
    """

    # Try Groq first (recommended free tier)
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        return _call_groq(prompt, groq_key, max_tokens)

    # Try Cerebras
    cerebras_key = os.getenv("CEREBRAS_API_KEY")
    if cerebras_key:
        return _call_cerebras(prompt, cerebras_key, max_tokens)

    # Try SambaNova
    sambanova_key = os.getenv("SAMBANOVA_API_KEY")
    if sambanova_key:
        return _call_sambanova(prompt, sambanova_key, max_tokens)

    # Try OpenRouter
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_key:
        return _call_openrouter(prompt, openrouter_key, max_tokens)

    print(f"{RED}ERROR: No free AI provider configured.{RESET}")
    print("Set one of: GROQ_API_KEY, CEREBRAS_API_KEY, SAMBANOVA_API_KEY, OPENROUTER_API_KEY")
    return ""

def _call_groq(prompt: str, api_key: str, max_tokens: int) -> str:
    """Call Groq API (free tier)."""
    try:
        from groq import Groq
    except ImportError:
        print(f"{YELLOW}Groq not installed. Run: pip install groq{RESET}")
        return ""

    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # Free tier, current model (May 2026)
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"{RED}Groq error: {e}{RESET}")
        return ""

def _call_cerebras(prompt: str, api_key: str, max_tokens: int) -> str:
    """Call Cerebras API (free tier)."""
    try:
        from openai import OpenAI
    except ImportError:
        print(f"{YELLOW}OpenAI SDK not installed. Run: pip install openai{RESET}")
        return ""

    try:
        client = OpenAI(api_key=api_key, base_url="https://api.cerebras.ai/v1")
        response = client.chat.completions.create(
            model="cerebras/llama-2-70b-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"{RED}Cerebras error: {e}{RESET}")
        return ""

def _call_sambanova(prompt: str, api_key: str, max_tokens: int) -> str:
    """Call SambaNova API (free tier)."""
    try:
        from openai import OpenAI
    except ImportError:
        print(f"{YELLOW}OpenAI SDK not installed. Run: pip install openai{RESET}")
        return ""

    try:
        client = OpenAI(api_key=api_key, base_url="https://api.sambanova.ai/v1")
        response = client.chat.completions.create(
            model="Meta-Llama-3.1-70B-Instruct",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"{RED}SambaNova error: {e}{RESET}")
        return ""

def _call_openrouter(prompt: str, api_key: str, max_tokens: int) -> str:
    """Call OpenRouter API (has free tier models)."""
    try:
        from openai import OpenAI
    except ImportError:
        print(f"{YELLOW}OpenAI SDK not installed. Run: pip install openai{RESET}")
        return ""

    try:
        client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
        response = client.chat.completions.create(
            model="meta-llama/llama-2-70b-chat",  # Free tier option
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"{RED}OpenRouter error: {e}{RESET}")
        return ""

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
    providers = ["GROQ_API_KEY", "CEREBRAS_API_KEY", "SAMBANOVA_API_KEY", "OPENROUTER_API_KEY"]
    has_provider = any(os.getenv(p) for p in providers)

    if not has_provider:
        print(f"{YELLOW}[WARN]{RESET} No free AI provider configured")
        print("       Set ONE of: GROQ_API_KEY, CEREBRAS_API_KEY, SAMBANOVA_API_KEY, OPENROUTER_API_KEY")
        print("       Free tiers: https://groq.com, https://cerebras.ai, https://sambanova.ai, https://openrouter.ai")
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
