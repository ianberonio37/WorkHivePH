"""sentinel_depth.py - v3 axis: test depth analysis.

For each tests/*.spec.ts, score each test() block on assertion depth:
  0 = no assertions (just goto/wait)
  1 = visibility-only (toBeVisible) - shallow
  2 = behavioral assertion (toHaveText, toContain, toEqual, toBe...)
  3 = behavioral + DB-level verification (uses adminClient.from(...))

Tests scoring 0 or 1 are flagged as "shallow" - they pass but don't prove
much. The platform is more confident with tests at depth >= 2.

Pure deterministic. See SENTINEL_ARCHITECTURE.md.
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
REPORT_FILE = ROOT / "sentinel_depth_report.json"

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"

EXEMPT_FILES = {
    "_db-cleanup.ts", "_fixtures.ts", "_helpers.ts", "_smoke-template.ts",
}

BEHAVIORAL_MATCHERS = (
    "toHaveText", "toContainText", "toHaveValue", "toHaveURL", "toHaveTitle",
    "toEqual", "toBe(", "toBeTruthy", "toBeFalsy", "toMatch", "toContain(",
    "toHaveCount", "toHaveClass", "toHaveAttribute", "toHaveCSS", "toBeChecked",
    "toBeEnabled", "toBeDisabled", "toBeFocused", "toBeEmpty",
)
SHALLOW_MATCHERS = ("toBeVisible", "toBeHidden", "toBeAttached")


def split_into_tests(src: str) -> list:
    """Crude split of source into test() blocks by tracking brace depth."""
    blocks = []
    pat = re.compile(r"""test\s*\(\s*['"`]([^'"`]+)['"`]""")
    matches = list(pat.finditer(src))
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(src)
        blocks.append({
            "name": m.group(1),
            "body": src[start:end],
        })
    return blocks


def score_test(body: str) -> int:
    expect_count = body.count("expect(")
    has_behavioral = any(matcher in body for matcher in BEHAVIORAL_MATCHERS)
    has_shallow = any(matcher in body for matcher in SHALLOW_MATCHERS)
    has_db_check = bool(re.search(r"\badmin(?:Client)?\.\s*from\s*\(", body)) \
                   or "adminClient.rpc" in body
    if expect_count == 0:
        return 0
    if has_db_check and has_behavioral:
        return 3
    if has_behavioral:
        return 2
    if has_shallow:
        return 1
    return 1


def analyze_spec(path: Path) -> dict:
    src = path.read_text(encoding="utf-8", errors="ignore")
    tests = split_into_tests(src)
    scored = [{"name": t["name"], "depth": score_test(t["body"])} for t in tests]
    total = sum(s["depth"] for s in scored)
    avg = round(total / len(scored), 2) if scored else 0.0
    shallow = [s for s in scored if s["depth"] <= 1]
    return {
        "file": path.name,
        "test_count": len(scored),
        "avg_depth": avg,
        "shallow_count": len(shallow),
        "shallow_tests": [s["name"][:80] for s in shallow],
    }


def main():
    print()
    print(f"{BOLD}SENTINEL - TEST DEPTH (v3){RESET}")
    print("-" * 60)

    if not TESTS_DIR.exists():
        print(f"  {RED}tests/ not found{RESET}")
        return 1

    specs = sorted(TESTS_DIR.glob("*.spec.ts"))
    results = []
    total_tests = 0
    total_shallow = 0
    depth_sum = 0.0

    for spec in specs:
        if spec.name in EXEMPT_FILES:
            continue
        r = analyze_spec(spec)
        results.append(r)
        total_tests += r["test_count"]
        total_shallow += r["shallow_count"]
        depth_sum += r["avg_depth"] * r["test_count"]

    overall_avg = round(depth_sum / total_tests, 2) if total_tests else 0.0
    shallow_pct = round(100 * total_shallow / total_tests, 1) if total_tests else 0.0
    avg_color = GREEN if overall_avg >= 2.0 else YELLOW if overall_avg >= 1.5 else RED

    print(f"  {BOLD}Specs analyzed:{RESET}     {len(results)}")
    print(f"  {BOLD}Total tests:{RESET}        {total_tests}")
    print(f"  {BOLD}Avg depth (0-3):{RESET}    {avg_color}{overall_avg}{RESET}")
    print(f"  {BOLD}Shallow tests:{RESET}      {total_shallow} ({shallow_pct}%)")
    print()

    deepest = sorted(results, key=lambda r: -r["avg_depth"])[:3]
    shallowest = sorted([r for r in results if r["test_count"] > 0],
                        key=lambda r: r["avg_depth"])[:5]

    print(f"  {BOLD}Shallowest specs:{RESET}")
    for r in shallowest:
        print(f"    avg={r['avg_depth']:.2f}  {r['file']}  ({r['shallow_count']}/{r['test_count']} shallow)")
    print()

    REPORT_FILE.write_text(json.dumps({
        "timestamp": datetime.datetime.now().isoformat(),
        "sentinel": "sentinel_depth",
        "version": "v3",
        "summary": {
            "total_specs": len(results),
            "total_tests": total_tests,
            "overall_avg_depth": overall_avg,
            "shallow_tests": total_shallow,
            "shallow_pct": shallow_pct,
        },
        "results": results,
    }, indent=2), encoding="utf-8")

    print(f"  Report -> {REPORT_FILE.name}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
