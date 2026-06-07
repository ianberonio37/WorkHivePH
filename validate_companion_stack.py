"""
Companion Stack Validator (G0) — Step 7 capstone self-coverage.
================================================================
Keeps the Companion Stack Battery (the agentic E2E critic) wired and green, the
same way validate_grounded_sweep.py keeps the UFAI sweep's locks intact. The
battery (companion_battery.js / window.__CSB) drives the unified Companion via
the Playwright MCP + the durable journey-companion-comprehensive.spec.ts and
grades the trajectory against the 3 reference stacks (Agent/Memory/RAG) + the
frozen Step-0 Safety baseline, asserting OBSERVABLES (gateway envelope
model_chain, agent_memory rows for the session_key, asset-brain cited[],
leak-regex) per Agent-as-a-Judge (arXiv 2508.02994).

This validator (static, paid-call-free — it does NOT drive the browser):
  1. Asserts the capstone ARTIFACTS exist (battery + durable spec + rubric).
  2. Forward-only ratchet on the rubric's baseline.max_major_defects: the
     capstone's invariant is that every HARD grounded proof passes (Major == 0).
     A run that surfaces a Major defect updates the rubric to >0 -> this FAILs,
     forcing a fix (or a conscious re-baseline). Minor defects (model-dependent
     recall, taste) ride in sweep_critiques.json -> promotion_dispositions.json.
  3. Asserts the rubric still grades all 4 pillars (structural integrity).

Degrade-to-SKIP (exit 0) when the rubric is absent (fresh checkout / capstone
not yet run) so it never false-FAILs. Re-baseline after a conscious change:
edit companion_stack_rubric.json baseline.max_major_defects.

Exit codes:
  0  artifacts present + max_major_defects <= 0 + 4 pillars graded (or rubric absent -> SKIP).
  1  a capstone artifact is missing, OR max_major_defects > 0, OR a pillar dropped.
"""
from __future__ import annotations
import io, json, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
RUBRIC = ROOT / "companion_stack_rubric.json"
BATTERY = ROOT / "companion_battery.js"
SPEC = ROOT / "tests" / "journey-companion-comprehensive.spec.ts"
REPORT = ROOT / "companion_stack_report.json"
PILLARS = ("Agent", "Memory", "RAG", "Safety")

GREEN, RED, CYAN, BOLD, RESET = "\033[92m", "\033[91m", "\033[96m", "\033[1m", "\033[0m"


def _skip(reason: str) -> int:
    print(f"{CYAN}SKIP{RESET}  Companion Stack: {reason}")
    print("  (run the Companion Stack Battery to establish companion_stack_rubric.json)")
    return 0


def main() -> int:
    print(f"{BOLD}\nCompanion Stack Validator (Step 7 capstone self-coverage){RESET}")
    print("=" * 60)

    if not RUBRIC.exists():
        return _skip("companion_stack_rubric.json not found")

    issues: list[str] = []

    # 1. Artifacts must exist (the capstone can't erode silently).
    if not BATTERY.exists():
        issues.append("companion_battery.js (the injectable battery) is missing")
    if not SPEC.exists():
        issues.append("tests/journey-companion-comprehensive.spec.ts (the durable driver) is missing")

    # 2. + 3. Rubric integrity + forward-only Major ratchet.
    try:
        rubric = json.loads(RUBRIC.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"{RED}FAIL{RESET}  companion_stack_rubric.json is not valid JSON: {e}")
        _write_report(0, 1, ["rubric not valid JSON"])
        return 1

    baseline = rubric.get("baseline", {})
    max_major = baseline.get("max_major_defects")
    if max_major is None:
        issues.append("baseline.max_major_defects missing from the rubric")
    elif int(max_major) > 0:
        issues.append(
            f"baseline.max_major_defects = {max_major} (> 0): the capstone surfaced an "
            f"unresolved MAJOR grounded defect. Fix the product, then re-run the battery; "
            f"or consciously re-baseline if it's accepted."
        )

    pillars = (baseline.get("pillars") or {})
    for p in PILLARS:
        if p not in pillars:
            issues.append(f"pillar '{p}' is not graded in the rubric")

    n_pass = 4 - len([1 for i in issues])  # informational
    if issues:
        for i in issues:
            print(f"{RED}FAIL{RESET}  {i}")
        _write_report(0, len(issues), issues)
        return 1

    print(f"{GREEN}PASS{RESET}  artifacts present (battery + spec + rubric)")
    print(f"{GREEN}PASS{RESET}  max_major_defects = {max_major} (all hard grounded proofs green)")
    print(f"{GREEN}PASS{RESET}  all 4 pillars graded: {', '.join(PILLARS)}")
    print(f"{GREEN}\n  Companion Stack capstone intact.{RESET}")
    _write_report(3, 0, [])
    return 0


def _write_report(passed: int, failed: int, issues: list[str]) -> None:
    REPORT.write_text(json.dumps({
        "validator": "companion_stack",
        "passed": passed, "failed": failed, "issues": issues,
    }, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
