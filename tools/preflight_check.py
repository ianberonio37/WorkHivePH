#!/usr/bin/env python3
"""
Pre-flight check for AI self-improvement loop.

Verifies:
- All layer files exist and are executable
- Required Python packages installed
- Environment variables set
- Services reachable
- Test data/images ready
"""

import os
import socket
import sys
from pathlib import Path

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def check(name: str, passed: bool, error: str = "") -> bool:
    """Print check result."""
    if passed:
        print(f"  {GREEN}[PASS]{RESET} {name}")
    else:
        print(f"  {RED}[FAIL]{RESET} {name}")
        if error:
            print(f"        {error}")
    return passed

def main():
    print("\n" + "=" * 70)
    print("PRE-FLIGHT CHECK: AI Self-Improvement Loop")
    print("=" * 70)

    all_pass = True
    root = Path(__file__).parent.parent

    # ─────────────────────────────────────────────────────────────────────
    # 1. Layer files
    # ─────────────────────────────────────────────────────────────────────

    print("\n[Files]")

    layer_files = [
        "tools/playwright_scenario_executor.py",
        "tools/analyze_scenario_findings.py",
        "tools/auto_fix_findings.py",
        "tools/generate_and_register_validator.py",
        "tools/validate_improvement_loop_integrity.py",
        "tools/ai_self_improvement_loop.py",
        "tools/loop_helpers.py",
    ]

    for file in layer_files:
        path = root / file
        exists = path.exists()
        all_pass &= check(f"{file}", exists, f"Not found" if not exists else "")

    # ─────────────────────────────────────────────────────────────────────
    # 2. Python packages
    # ─────────────────────────────────────────────────────────────────────

    print("\n[Python Packages]")

    packages = [
        ("playwright", "pip install playwright && playwright install chromium"),
        ("supabase", "pip install supabase"),
    ]

    # Check for at least one free AI SDK
    ai_packages = [("groq", "pip install groq"), ("openai", "pip install openai")]
    has_ai_sdk = False

    for pkg, install_cmd in ai_packages:
        try:
            __import__(pkg)
            if pkg == "groq":
                check(f"{pkg} (for free AI)", True)
            else:
                check(f"{pkg} (for cerebras/sambanova/openrouter)", True)
            has_ai_sdk = True
            break
        except ImportError:
            pass

    if not has_ai_sdk:
        check("Free AI SDK (groq or openai)", False, "Run: pip install groq (or pip install openai)")
        all_pass = False

    for pkg, install_cmd in packages:
        try:
            __import__(pkg)
            check(f"{pkg}", True)
        except ImportError:
            check(f"{pkg}", False, f"Run: {install_cmd}")
            all_pass = False

    # ─────────────────────────────────────────────────────────────────────
    # 3. Environment variables
    # ─────────────────────────────────────────────────────────────────────

    print("\n[Environment]")

    free_providers = [
        ("GROQ_API_KEY", "https://console.groq.com"),
        ("CEREBRAS_API_KEY", "https://cerebras.ai"),
        ("SAMBANOVA_API_KEY", "https://sambanova.ai"),
        ("OPENROUTER_API_KEY", "https://openrouter.ai"),
    ]

    has_ai_provider = False
    for env_var, url in free_providers:
        exists = env_var in os.environ
        if exists:
            has_ai_provider = True
            check(f"{env_var} (free tier)", True)
        else:
            check(f"{env_var} (free tier)", False, f"Optional: Get free key at {url}")

    if not has_ai_provider:
        print(f"      [REQUIRED] Set at least ONE free AI provider key above")
        all_pass = False

    # ─────────────────────────────────────────────────────────────────────
    # 4. Services
    # ─────────────────────────────────────────────────────────────────────

    print("\n[Services]")

    services = [
        ("Flask Tester", "127.0.0.1", 5000),
        ("Local Supabase", "127.0.0.1", 54321),
    ]

    for name, host, port in services:
        try:
            with socket.create_connection((host, port), timeout=2):
                check(f"{name} ({host}:{port})", True)
        except OSError:
            check(f"{name} ({host}:{port})", False, f"Start with: python test-data-seeder/app.py or supabase start")
            all_pass = False

    # ─────────────────────────────────────────────────────────────────────
    # 5. Test data
    # ─────────────────────────────────────────────────────────────────────

    print("\n[Test Data]")

    test_images_dir = root / "test-images"
    test_images_dir.mkdir(exist_ok=True)

    # Create placeholder image if needed
    test_image = test_images_dir / "defect-example.jpg"
    if not test_image.exists():
        try:
            # Minimal valid PNG (1x1 transparent)
            placeholder_png = bytes.fromhex(
                "89504e470d0a1a0a0000000d4948445200000001000000010802000000"
                "90773db3000000024944415408d76360000000020001e5276d50000000"
                "0049454e44ae426082"
            )
            test_image.write_bytes(placeholder_png)
            check("Test image (defect-example.jpg)", True)
        except Exception as e:
            check("Test image (defect-example.jpg)", False, str(e))
            all_pass = False
    else:
        check("Test image (defect-example.jpg)", True)

    # ─────────────────────────────────────────────────────────────────────
    # 6. Git setup
    # ─────────────────────────────────────────────────────────────────────

    print("\n[Git]")

    is_git_repo = (root / ".git").exists()
    all_pass &= check("Git repository", is_git_repo, "Run: git init" if not is_git_repo else "")

    # ─────────────────────────────────────────────────────────────────────
    # Summary
    # ─────────────────────────────────────────────────────────────────────

    print("\n" + "=" * 70)

    if all_pass:
        print(f"{GREEN}[PASS] All checks passed! Ready to run the loop.{RESET}")
        print("\nQuick start:")
        print("  python tools/ai_self_improvement_loop.py --fast --surface=VOICE")
        return 0
    else:
        print(f"{RED}[FAIL] Some checks failed. Fix the issues above, then retry.{RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
