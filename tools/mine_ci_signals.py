"""
CI-Config Substrate Miner (Maturity Phase 3, 2026-06-16).
==========================================================
Closes the (CI, G-1.5) cell from COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §4.

The CI/CD layer's drift is "a workflow exists but isn't wired to fire", or the
reproducible-build pins drift. This miner surfaces the CI SHAPE: which GitHub
Actions workflows exist, whether they have triggers (on:), and whether the
local gate + reproducible pins are present.

Inputs:  .github/workflows/*.yml, .tool-versions, tools/ci_gate.py
Output:  ci_signals_report.json
Exit code: 0 (informational miner)
"""
from __future__ import annotations
import io, json, sys
from pathlib import Path
from datetime import datetime, timezone

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
WF_DIR = ROOT / ".github" / "workflows"
TOOLVERS = ROOT / ".tool-versions"
CI_GATE = ROOT / "tools" / "ci_gate.py"
REPORT = ROOT / "ci_signals_report.json"

CHECK_NAMES = ["ci_signals"]


def main() -> int:
    workflows = []
    if WF_DIR.exists():
        for wf in sorted(WF_DIR.glob("*.yml")) + sorted(WF_DIR.glob("*.yaml")):
            t = wf.read_text(encoding="utf-8", errors="replace")
            # a workflow is "wired" if it declares a trigger
            wired = bool(__import__("re").search(r"^on:|^\s*on:", t, __import__("re").M)) or "on:" in t
            workflows.append({"file": wf.name, "wired": wired,
                              "runs_gate": ("run_platform_checks" in t or "ci_gate" in t or "fullstack_dev" in t)})

    out = {
        "scanned_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "workflow_count": len(workflows),
        "wired_workflows": sum(1 for w in workflows if w["wired"]),
        "gate_running_workflows": sum(1 for w in workflows if w["runs_gate"]),
        "tool_versions_pin": TOOLVERS.exists(),
        "local_ci_gate": CI_GATE.exists(),
        "workflows": workflows,
    }
    REPORT.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(f"CI-signals miner: {len(workflows)} workflow(s).")
    for w in workflows:
        print(f"    - {w['file']}: wired={w['wired']} runs_gate={w['runs_gate']}")
    print(f"  .tool-versions pin: {out['tool_versions_pin']} · local ci_gate.py: {out['local_ci_gate']}")
    print(f"  See: {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
