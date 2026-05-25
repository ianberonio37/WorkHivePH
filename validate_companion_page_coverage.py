#!/usr/bin/env python3
"""
validate_companion_page_coverage.py
Layer 0 — Forward-only ratchet.
Enforce: Every nav-hub page must also load companion-launcher.js.
Allowlist for intentional exclusions (assistant.html, index.html, dev/ops pages, test pages).
"""
import io
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent

# Pages that intentionally do NOT load companion (nav-hub but no companion)
ALLOWLIST = {
    "assistant.html",                  # dedicated AI interface, guard in launcher init()
    "index.html",                      # landing page, companion logic via wh-persona.js inline
    "agentic-rag-observability.html",  # dev/ops tool, not user-facing
    "platform-health.html",            # admin only, skips voice
}

def is_test_page(filename):
    """Check if page is a test page (not production user-facing)."""
    return "-test.html" in filename or filename.startswith("test-")

def check_companion_page_coverage():
    """Verify all user-facing pages with nav-hub.js also load companion-launcher.js."""
    root_html = list(ROOT.glob("*.html"))

    violations = []
    covered = []

    for html_file in sorted(root_html):
        if html_file.name in ALLOWLIST:
            covered.append(f"{html_file.name} (allowlisted)")
            continue

        if is_test_page(html_file.name):
            covered.append(f"{html_file.name} (test page)")
            continue

        content = html_file.read_text(encoding="utf-8", errors="replace")

        has_nav_hub = "nav-hub.js" in content
        has_companion = "companion-launcher.js" in content

        # If it has nav-hub, it must have companion-launcher (unless allowlisted)
        if has_nav_hub and not has_companion:
            violations.append({
                "file": html_file.name,
                "reason": "nav-hub present but companion-launcher missing",
            })
        elif has_nav_hub and has_companion:
            covered.append(html_file.name)
        elif not has_nav_hub:
            # Not a user-facing page (no nav-hub)
            pass

    return covered, violations

def main():
    covered, violations = check_companion_page_coverage()

    print("\n" + "=" * 80)
    print("  Companion Page Coverage Validator (Layer 0)")
    print("=" * 80 + "\n")

    print(f"Covered pages ({len(covered)}):")
    for page in sorted(covered):
        print(f"  OK  {page}")

    if violations:
        print(f"\n  VIOLATIONS ({len(violations)}):")
        for v in violations:
            print(f"  FAIL {v['file']} — {v['reason']}")

        print("\nACTION: Add <script src=\"companion-launcher.js\"></script> before </body>\n")
        return 1

    print(f"\nOK  All user-facing pages have companion-launcher.js\n")
    return 0

if __name__ == "__main__":
    sys.exit(main())
