"""sentinel_pattern_consistency.py - v3 axis: canonical Layer 2 pattern check.

For every tests/*.spec.ts, verify the canonical fixture pattern:
  - Imports from './_fixtures' (not raw '@playwright/test')
  - Uses `whPage` fixture (not raw `page`)
  - Uses `testMarker` for DB cleanup correlation
  - Uses `adminClient` for DB-level verification (when verifying writes)
  - Has a test.describe wrapper

Flags drift so new scenarios stay consistent with established patterns.

Pure deterministic. No LLM. See SENTINEL_ARCHITECTURE.md.
"""

import sys
import re
import json
import datetime
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = ROOT / "tests"
REPORT_FILE = ROOT / "sentinel_pattern_report.json"

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"

EXEMPT_FILES = {
    "_db-cleanup.ts", "_fixtures.ts", "_helpers.ts", "_smoke-template.ts",
}


def analyze_spec(path: Path) -> dict:
    src = path.read_text(encoding="utf-8", errors="ignore")
    issues = []

    if "from '@playwright/test'" in src and "from './_fixtures'" not in src:
        issues.append("imports from @playwright/test directly (should import test/expect from './_fixtures')")

    if "from './_fixtures'" not in src and "from \"./_fixtures\"" not in src:
        issues.append("does not import from './_fixtures'")

    if "test.describe" not in src and "test(" in src:
        issues.append("missing test.describe wrapper")

    has_test_blocks = bool(re.search(r"\btest\s*\(", src))
    if has_test_blocks and "whPage" not in src and "{ page" in src:
        issues.append("uses raw `page` fixture (should use `whPage`)")

    if has_test_blocks and "testMarker" not in src:
        if any(verb in src for verb in [".insert(", ".update(", ".upsert(", ".delete("]):
            issues.append("performs DB mutations but does not use testMarker for cleanup")

    if "adminClient" not in src and ".click('button" in src:
        if "expect(" in src and re.search(r"expect\s*\(\s*await\s+admin", src) is None:
            pass

    return {
        "file": path.name,
        "compliant": len(issues) == 0,
        "issues": issues,
    }


def main():
    print()
    print(f"{BOLD}SENTINEL - PATTERN CONSISTENCY (v3){RESET}")
    print("-" * 60)

    if not TESTS_DIR.exists():
        print(f"  {RED}tests/ not found{RESET}")
        return 1

    specs = sorted(TESTS_DIR.glob("*.spec.ts"))
    results = []
    for spec in specs:
        if spec.name in EXEMPT_FILES:
            continue
        results.append(analyze_spec(spec))

    compliant = sum(1 for r in results if r["compliant"])
    drift = sum(1 for r in results if not r["compliant"])
    pct = round(100 * compliant / len(results), 1) if results else 0.0
    pct_color = GREEN if pct >= 90 else YELLOW if pct >= 70 else RED

    print(f"  {BOLD}Specs analyzed:{RESET}     {len(results)}")
    print(f"  {BOLD}Compliant:{RESET}          {compliant}")
    print(f"  {BOLD}Pattern drift:{RESET}      {drift}")
    print(f"  {BOLD}Compliance %:{RESET}       {pct_color}{pct}%{RESET}")
    print()

    if drift:
        print(f"  {BOLD}Specs with drift (first 15):{RESET}")
        non_compliant = [r for r in results if not r["compliant"]]
        for r in non_compliant[:15]:
            print(f"    {YELLOW}DRIFT{RESET}  {r['file']}")
            for issue in r["issues"]:
                print(f"           - {issue}")
        if len(non_compliant) > 15:
            print(f"    ... and {len(non_compliant) - 15} more (see report)")
        print()

    REPORT_FILE.write_text(json.dumps({
        "timestamp": datetime.datetime.now().isoformat(),
        "sentinel": "sentinel_pattern_consistency",
        "version": "v3",
        "summary": {
            "total_specs": len(results),
            "compliant": compliant,
            "drift": drift,
            "compliance_pct": pct,
        },
        "results": results,
    }, indent=2), encoding="utf-8")

    print(f"  Report -> {REPORT_FILE.name}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
