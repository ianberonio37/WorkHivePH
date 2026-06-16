"""
Connection-Pool / Saturation Ratchet (Maturity Phase 1, 2026-06-16).
=====================================================================
Closes the (LB, GH) cell from COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §4 —
the "connection-pool saturation alarm" (study §7 #20).

The Load-Balancing layer saturates on realtime channel exhaustion (ceiling
1000 / comfortable 500 per CAPACITY_PLAN.md §1). This gate is the alarm:

  L1  leak-risk surfaces (subscribe > teardown) frozen at baseline (Rule B).
      A growing leak count is a connection LEAK → guaranteed eventual exhaustion.
  L2  realtime-surface count frozen at baseline — new connection surfaces are
      allowed only by consciously re-baselining AND confirming the peak-channel
      projection stays under the CAPACITY_PLAN comfortable ceiling.
  L3  CAPACITY_PLAN.md declares a machine-checkable saturation alarm threshold.

Reads capacity_signals_report.json (auto-runs mine_capacity_signals.py if absent).

Output:  connection_pool_saturation_report.json
Baseline: connection_pool_saturation_baseline.json   (only descends)

Exit code:
  0  PASS (no regression vs baseline + alarm threshold declared)
  1  FAIL (leak count up, surface count up un-baselined, or threshold undeclared)
"""
from __future__ import annotations
import io, json, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
SIGNALS = ROOT / "capacity_signals_report.json"
MINER   = ROOT / "tools" / "mine_capacity_signals.py"
CAPPLAN = ROOT / "CAPACITY_PLAN.md"
REPORT   = ROOT / "connection_pool_saturation_report.json"
BASELINE = ROOT / "connection_pool_saturation_baseline.json"

CHECK_NAMES = ["connection_pool_saturation"]
# the machine marker validate_load_resilience + this gate both look for
ALARM_MARKER = "SATURATION-ALARM:"

GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; BOLD = "\033[1m"; RESET = "\033[0m"


def _load(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _signals() -> dict:
    if not SIGNALS.exists() and MINER.exists():
        subprocess.run([sys.executable, str(MINER)], cwd=str(ROOT),
                       capture_output=True, text=True, timeout=60)
    return _load(SIGNALS) or {}


def main() -> int:
    sig = _signals()
    tot = sig.get("totals", {})
    cur = {
        "leak_risk_surfaces": int(tot.get("leak_risk_surfaces", 0)),
        "realtime_surfaces":  int(tot.get("realtime_surfaces", 0)),
    }

    base = _load(BASELINE)
    first_lock = base is None
    if first_lock:
        base = dict(cur)
        BASELINE.write_text(json.dumps(base, indent=2), encoding="utf-8")

    fails: list[str] = []
    # L1 — leaks may never grow
    if cur["leak_risk_surfaces"] > base.get("leak_risk_surfaces", 0):
        fails.append(f"L1 leak-risk surfaces {cur['leak_risk_surfaces']} > baseline {base['leak_risk_surfaces']} — a subscribe() lost its teardown (connection leak).")
    # L2 — surface count may not grow without a conscious re-baseline
    if cur["realtime_surfaces"] > base.get("realtime_surfaces", 0):
        fails.append(f"L2 realtime surfaces {cur['realtime_surfaces']} > baseline {base['realtime_surfaces']} — new connection surface. Confirm peak channels < CAPACITY_PLAN comfortable ceiling, then re-baseline.")
    # L3 — alarm threshold must be declared
    cap_text = CAPPLAN.read_text(encoding="utf-8", errors="replace") if CAPPLAN.exists() else ""
    if ALARM_MARKER not in cap_text:
        fails.append(f"L3 CAPACITY_PLAN.md has no '{ALARM_MARKER}' declaration — the saturation alarm threshold is undeclared.")

    # lock improvements downward (Rule B)
    improved = {}
    for k in cur:
        if cur[k] < base.get(k, 0):
            improved[k] = (base[k], cur[k]); base[k] = cur[k]
    if improved and not fails:
        BASELINE.write_text(json.dumps(base, indent=2), encoding="utf-8")

    REPORT.write_text(json.dumps({
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "current": cur, "baseline": base, "alarm_declared": ALARM_MARKER in cap_text,
        "first_lock": first_lock, "improved": improved, "fails": fails,
    }, indent=2), encoding="utf-8")

    print(f"{BOLD}Connection-Pool / Saturation Ratchet (LB, GH){RESET}")
    print(f"  realtime surfaces : {cur['realtime_surfaces']}  (baseline {base['realtime_surfaces']})")
    print(f"  leak-risk surfaces: {cur['leak_risk_surfaces']}  (baseline {base['leak_risk_surfaces']})")
    print(f"  saturation alarm declared in CAPACITY_PLAN: {'yes' if ALARM_MARKER in cap_text else 'NO'}")
    if first_lock:
        print(f"{YEL}  baseline locked at current (first run).{RESET}")
    if improved:
        print(f"{GREEN}  improved (baseline lowered): {improved}{RESET}")
    if fails:
        print(f"{RED}FAIL: {len(fails)} saturation regression(s):{RESET}")
        for f in fails:
            print(f"  - {f}")
        return 1
    print(f"{GREEN}PASS — no connection-saturation regression; alarm threshold declared.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
