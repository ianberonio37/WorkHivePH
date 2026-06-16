"""
Deploy-Safety Sentinel (Maturity Phase 3, 2026-06-16).
=======================================================
Closes the (H, GS) cell from COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §4 — proves
a deploy fails safe + has a rollback path.

  L1  rollback path documented      — ROLLBACK_RUNBOOK.md
  L2  pre-deploy gate present        — tools/pre_deploy_gate.py
  L3  every edge fn is in the deploy script (undeployed count frozen at 0 —
      a fn missing from deploy-functions.ps1 ships stale; devops standing rule)

Reads deploy_signals_report.json (auto-runs mine_deploy_signals.py).
Output:  deploy_safety_report.json
Baseline: deploy_safety_baseline.json   (undeployed count; only descends)
Exit code: 0 PASS / 1 FAIL (no rollback/pre-deploy, or a new undeployed fn)
"""
from __future__ import annotations
import io, json, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
SIGNALS = ROOT / "deploy_signals_report.json"
MINER   = ROOT / "tools" / "mine_deploy_signals.py"
REPORT   = ROOT / "deploy_safety_report.json"
BASELINE = ROOT / "deploy_safety_baseline.json"

CHECK_NAMES = ["deploy_safety"]
GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; BOLD = "\033[1m"; RESET = "\033[0m"


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
    undeployed = sorted(sig.get("undeployed_fns", []))
    cur = len(undeployed)

    base = _load(BASELINE)
    first_lock = base is None
    if first_lock:
        base = {"undeployed": cur, "fns": undeployed}
        BASELINE.write_text(json.dumps(base, indent=2), encoding="utf-8")
    baseline_n = int(base.get("undeployed", cur))
    new_undeployed = [f for f in undeployed if f not in set(base.get("fns", []))]

    fails: list[str] = []
    if not sig.get("rollback_runbook"):
        fails.append("ROLLBACK_RUNBOOK.md missing — no documented rollback path.")
    if not sig.get("pre_deploy_gate"):
        fails.append("tools/pre_deploy_gate.py missing — no pre-deploy gate.")
    if cur > baseline_n:
        fails.append(f"undeployed edge fns {cur} > baseline {baseline_n} — ships stale: {', '.join(new_undeployed)}")

    if cur < baseline_n and not fails:
        base["undeployed"] = cur; base["fns"] = undeployed
        BASELINE.write_text(json.dumps(base, indent=2), encoding="utf-8")

    REPORT.write_text(json.dumps({
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "undeployed": cur, "baseline": baseline_n, "new_undeployed": new_undeployed,
        "rollback_runbook": sig.get("rollback_runbook"), "pre_deploy_gate": sig.get("pre_deploy_gate"),
        "first_lock": first_lock, "fails": fails,
    }, indent=2), encoding="utf-8")

    print(f"{BOLD}Deploy-Safety Sentinel (H, GS){RESET}")
    print(f"  rollback runbook: {sig.get('rollback_runbook')} · pre-deploy gate: {sig.get('pre_deploy_gate')}")
    print(f"  undeployed edge fns: {cur}  (baseline {baseline_n})")
    if first_lock:
        print(f"{YEL}  baseline locked at {cur} (first run).{RESET}")
    if fails:
        print(f"{RED}FAIL: {len(fails)} deploy-safety issue(s):{RESET}")
        for f in fails:
            print(f"  - {f}")
        return 1
    print(f"{GREEN}PASS — rollback + pre-deploy present; no new undeployed fn.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
