"""
CI-Gate Sentinel (Maturity Phase 3, 2026-06-16).
==================================================
Closes the (CI, GS) cell from COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §4 — proves
a gate fires on every change (gate-on-commit discipline).

GitHub Actions may be written-not-enabled, so the honest local-substitute (D3)
is: the LOCAL ci_gate is runnable AND a workflow is wired to run the gate, so
the moment Actions is enabled it gates. The discipline is provable now.

  L1  local CI gate present + runnable   — tools/ci_gate.py
  L2  >= 1 workflow runs the gate         — references run_platform_checks/ci_gate/fullstack_dev
  L3  reproducible-build pin present      — .tool-versions
  L4  >= 1 workflow is wired (has on:)    — fires on push/PR

Reads ci_signals_report.json (auto-runs mine_ci_signals.py).
Output:  ci_gate_sentinel_report.json
Exit code: 0 PASS / 1 FAIL (no local gate, or no workflow runs it, or no pin)
"""
from __future__ import annotations
import io, json, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
SIGNALS = ROOT / "ci_signals_report.json"
MINER   = ROOT / "tools" / "mine_ci_signals.py"
REPORT  = ROOT / "ci_gate_sentinel_report.json"

CHECK_NAMES = ["ci_gate_sentinel"]
GREEN = "\033[92m"; RED = "\033[91m"; BOLD = "\033[1m"; RESET = "\033[0m"


def _load(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _signals() -> dict:
    if not SIGNALS.exists() and MINER.exists():
        subprocess.run([sys.executable, str(MINER)], cwd=str(ROOT), capture_output=True, text=True, timeout=60)
    return _load(SIGNALS) or {}


def main() -> int:
    sig = _signals()
    checks = [
        ("L1 local CI gate present (tools/ci_gate.py)", bool(sig.get("local_ci_gate"))),
        ("L2 a workflow runs the gate (run_platform_checks/ci_gate/fullstack_dev)", int(sig.get("gate_running_workflows", 0)) >= 1),
        ("L3 reproducible-build pin (.tool-versions)", bool(sig.get("tool_versions_pin"))),
        ("L4 a workflow is wired (has on: trigger)", int(sig.get("wired_workflows", 0)) >= 1),
    ]
    fails = [name for name, ok in checks if not ok]

    REPORT.write_text(json.dumps({
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "checks": {n: ok for n, ok in checks},
        "workflow_count": sig.get("workflow_count"), "fails": fails,
    }, indent=2), encoding="utf-8")

    print(f"{BOLD}CI-Gate Sentinel (CI, GS){RESET}")
    for name, ok in checks:
        print(f"  {GREEN+'PASS'+RESET if ok else RED+'FAIL'+RESET}  {name}")
    if fails:
        print(f"{RED}FAIL: {len(fails)} CI-gate invariant(s) unproven.{RESET}")
        return 1
    print(f"{GREEN}PASS — gate-on-commit discipline provable (local gate + wired workflow + pin).{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
