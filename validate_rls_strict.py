"""
RLS Strict Baseline Validator (L0, P1 roadmap 2026-05-27 turn 7).
==================================================================
Promotes the substrate findings from `tools/mine_rls_policies.py` into a
forward-only ratchet. Two counts are baselined:

  - permissive_using_true     (currently 15; locked at 15, FAIL on >15)
  - permissive_check_true     (currently 5;  locked at 5,  FAIL on >5)

The missing-TO count (currently 123) is too large to ratchet today — too
many legacy policies. It surfaces in the substrate manifest but doesn't
gate the build. Future work: pick a top-20 list, fix them, baseline at
the remainder.

Exit codes:
  0  counts ≤ baseline (improvement is auto-tightened)
  1  any count > baseline (a new permissive policy slipped in)
  2  miner output missing — run tools/mine_rls_policies.py first
"""
from __future__ import annotations
import io, json, subprocess, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
MINER = ROOT / "tools" / "mine_rls_policies.py"
REPORT = ROOT / "rls_policy_mining_report.json"
BASELINE = ROOT / "rls_strict_baseline.json"

CHECK_NAMES = ["rls_strict"]


def main() -> int:
    # Re-run the miner first so the baseline check sees fresh data.
    if MINER.exists():
        subprocess.run([sys.executable, str(MINER)], check=False, capture_output=True)
    if not REPORT.exists():
        print("\033[91mFAIL: rls_policy_mining_report.json missing — run tools/mine_rls_policies.py first\033[0m")
        return 2

    data = json.loads(REPORT.read_text(encoding="utf-8", errors="replace"))
    n_using = len(data.get("permissive_using_true", []))
    n_check = len(data.get("permissive_check_true", []))

    baseline = {"using_true": n_using, "check_true": n_check}
    if BASELINE.exists():
        try:
            baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        except Exception:
            BASELINE.write_text(json.dumps(baseline), encoding="utf-8")
    else:
        BASELINE.write_text(json.dumps(baseline), encoding="utf-8")

    print(f"RLS strict baseline:")
    print(f"  USING(true)        : {n_using} (baseline {baseline.get('using_true', n_using)})")
    print(f"  WITH CHECK(true)   : {n_check} (baseline {baseline.get('check_true', n_check)})")

    bumped = False
    if n_using > baseline.get("using_true", n_using):
        print(f"\033[91mFAIL: USING(true) regressed +{n_using - baseline['using_true']}\033[0m")
        bumped = True
    if n_check > baseline.get("check_true", n_check):
        print(f"\033[91mFAIL: WITH CHECK(true) regressed +{n_check - baseline['check_true']}\033[0m")
        bumped = True
    if bumped:
        return 1

    # Auto-tighten when counts drop.
    if n_using < baseline.get("using_true", n_using) or n_check < baseline.get("check_true", n_check):
        BASELINE.write_text(json.dumps({"using_true": n_using, "check_true": n_check}), encoding="utf-8")
        print(f"\033[92mPASS: baseline tightened\033[0m")
        return 0

    print("\033[92mPASS\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
