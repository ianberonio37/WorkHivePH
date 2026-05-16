#!/usr/bin/env python3
"""
Layer 4: Meta-Validator — Loop Guardian

Validates the AI self-improvement loop itself:
- All findings have corresponding validators
- No validators deferred without reason
- Test data reproducible
- Loop metadata consistent

This prevents the loop from "gaming itself" or deferring work indefinitely.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def validate_loop_integrity() -> bool:
    """Run meta-validation checks on the improvement loop."""
    results = {"pass": 0, "fail": 0}

    print("\n" + "=" * 70)
    print("LAYER 4: META-VALIDATOR (LOOP GUARDIAN)")
    print("=" * 70)

    # ─────────────────────────────────────────────────────────────────────
    # CHECK 1: All findings have corresponding validators
    # ─────────────────────────────────────────────────────────────────────

    print("\n[Check 1] Finding -> Validator Coverage")

    findings_path = Path("SCENARIO_FINDINGS.jsonl")
    registry_path = Path("VALIDATOR_REGISTRY.json")

    if not findings_path.exists():
        print(f"  {YELLOW}SKIP{RESET} No findings file yet")
    elif not registry_path.exists():
        print(f"  {RED}FAIL{RESET} Findings exist but no validator registry")
        results["fail"] += 1
    else:
        try:
            # Load findings
            findings = []
            if findings_path.stat().st_size > 0:
                with open(findings_path) as f:
                    for line in f:
                        if line.strip():
                            findings.append(json.loads(line))

            # Load registry
            with open(registry_path) as f:
                registry = json.load(f)

            covered_count = registry.get("validators_registered", 0)
            total_count = len(findings)

            if covered_count >= total_count:
                print(f"  {GREEN}PASS{RESET} {covered_count}/{total_count} findings have validators")
                results["pass"] += 1
            else:
                print(f"  {RED}FAIL{RESET} Only {covered_count}/{total_count} findings covered")
                results["fail"] += 1

        except Exception as e:
            print(f"  {RED}FAIL{RESET} Error reading findings/registry: {e}")
            results["fail"] += 1

    # ─────────────────────────────────────────────────────────────────────
    # CHECK 2: No validators deferred without documented reason
    # ─────────────────────────────────────────────────────────────────────

    print("\n[Check 2] Validator Deferral Tracking")

    prod_fixes_path = Path("PRODUCTION_FIXES.md")

    if not prod_fixes_path.exists():
        print(f"  {YELLOW}SKIP{RESET} No PRODUCTION_FIXES.md yet")
    else:
        try:
            content = prod_fixes_path.read_text()

            # Look for deferred entries
            import re
            deferred_matches = re.findall(
                r'#(\d+).*?\(deferred\)(.*?)(?=#|\Z)',
                content,
                re.DOTALL
            )

            undocumented = []
            for entry_id, reason in deferred_matches:
                if not reason.strip() or len(reason.strip()) < 10:
                    undocumented.append(entry_id)

            if undocumented:
                print(f"  {RED}FAIL{RESET} {len(undocumented)} deferred entries without reason: {undocumented}")
                results["fail"] += 1
            else:
                documented = len(deferred_matches)
                if documented > 0:
                    print(f"  {GREEN}PASS{RESET} {documented} deferred entries all documented")
                else:
                    print(f"  {GREEN}PASS{RESET} No deferred entries")
                results["pass"] += 1

        except Exception as e:
            print(f"  {RED}FAIL{RESET} Error reading PRODUCTION_FIXES.md: {e}")
            results["fail"] += 1

    # ─────────────────────────────────────────────────────────────────────
    # CHECK 3: Test data reproducibility
    # ─────────────────────────────────────────────────────────────────────

    print("\n[Check 3] Test Data Reproducibility")

    try:
        # Check if seeder reset function is available
        test_seeder_path = Path("test-data-seeder") / "seeders" / "reset.py"

        if test_seeder_path.exists():
            content = test_seeder_path.read_text()

            if "def reset_all" in content or "def reset" in content:
                print(f"  {GREEN}PASS{RESET} Reset function available for reproducible seeding")
                results["pass"] += 1
            else:
                print(f"  {RED}FAIL{RESET} Reset function not found")
                results["fail"] += 1
        else:
            print(f"  {RED}FAIL{RESET} Seeder reset.py not found")
            results["fail"] += 1

    except Exception as e:
        print(f"  {RED}FAIL{RESET} Error checking seeder: {e}")
        results["fail"] += 1

    # ─────────────────────────────────────────────────────────────────────
    # CHECK 4: Loop run metadata consistency
    # ─────────────────────────────────────────────────────────────────────

    print("\n[Check 4] Loop Metadata Consistency")

    loop_metadata_path = Path("LOOP_METADATA.json")

    if not loop_metadata_path.exists():
        print(f"  {YELLOW}INFO{RESET} First loop run — metadata will be created")
    else:
        try:
            with open(loop_metadata_path) as f:
                metadata = json.load(f)

            checks = [
                ("loop_start" in metadata, "Start timestamp"),
                ("loop_end" in metadata, "End timestamp"),
                ("scenarios_run" in metadata, "Scenario count"),
                ("findings_extracted" in metadata, "Finding count"),
                ("validators_registered" in metadata, "Validator count"),
            ]

            passed_checks = sum(1 for check, _ in checks if check)

            if passed_checks >= 4:
                print(f"  {GREEN}PASS{RESET} Metadata complete ({passed_checks}/5 fields)")
                results["pass"] += 1
            else:
                print(f"  {RED}FAIL{RESET} Metadata incomplete ({passed_checks}/5 fields)")
                results["fail"] += 1

        except Exception as e:
            print(f"  {RED}FAIL{RESET} Error reading metadata: {e}")
            results["fail"] += 1

    # ─────────────────────────────────────────────────────────────────────
    # CHECK 5: Fast gate includes new validators
    # ─────────────────────────────────────────────────────────────────────

    print("\n[Check 5] Fast Gate Validator Registration")

    try:
        run_checks_path = Path("run_platform_checks.py")

        if not run_checks_path.exists():
            print(f"  {RED}FAIL{RESET} run_platform_checks.py not found")
            results["fail"] += 1
        else:
            content = run_checks_path.read_text()

            # Count AI validation entries
            ai_validators = content.count('"group":   "AI Validation"')

            if ai_validators > 0:
                print(f"  {GREEN}PASS{RESET} {ai_validators} AI validators registered in fast gate")
                results["pass"] += 1
            else:
                print(f"  {YELLOW}INFO{RESET} No AI validators yet (normal for first run)")
                results["pass"] += 1

    except Exception as e:
        print(f"  {RED}FAIL{RESET} Error checking fast gate: {e}")
        results["fail"] += 1

    # ─────────────────────────────────────────────────────────────────────
    # SUMMARY
    # ─────────────────────────────────────────────────────────────────────

    print("\n" + "=" * 70)
    print(f"META-VALIDATOR: {results['pass']} PASS | {results['fail']} FAIL")
    print("=" * 70)

    if results["fail"] == 0:
        print(f"\n{GREEN}Loop integrity OK. Safe to continue.{RESET}")
        return True
    else:
        print(f"\n{RED}Loop has integrity issues. Review before next run.{RESET}")
        return False


if __name__ == "__main__":
    success = validate_loop_integrity()
    sys.exit(0 if success else 1)
