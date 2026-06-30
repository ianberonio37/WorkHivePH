"""
Companion gate-teeth self-test — Phase 8 §8.3 / C1.1 acceptance proof.
=====================================================================
Proves DETERMINISTICALLY (no live LLM, no clobbering the committed baselines) that the
per-dimension companion gate (`ai_eval_gate.companion_gate`) actually BLOCKS (exit 1) when the
MEMORY dimension regresses on the locked-test split, and PASSES (exit 0) when it does not.

Why this exists: the LIVE gate's verdict on a real capture depends on free-tier-LLM phrasing
(inherently a little flaky), so "run the capture twice" is not a stable CI proof. This test pins
the gate's DECISION LOGIC against synthetic clean/degraded fixtures laid over the REAL locked-test
membership (read from gate_eval_splits.json). It is the durable "the gate has teeth" guard the
C1.1 acceptance bar demands — *a deliberately-degraded result FAILs; a clean result passes* — and
it runs in every `run_platform_checks` pass with zero model calls.

It drives the SAME `companion_gate()` code production uses, via its injectable fixture paths
(baseline_path/scorecard_path) so no committed baseline is touched.

Exit:
  0 = teeth proven (gate PASSES clean AND BLOCKS degraded), OR degrade-to-SKIP when the locked-test
      memory set is too small (n<2) to construct an honest blocking scenario (never a false FAIL);
  1 = the gate did NOT discriminate (it blocked a clean run, or let a degraded run pass) = a defect.
"""
from __future__ import annotations
import io
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = Path(__file__).resolve().parent
TEETH_DIR = ROOT / ".tmp" / "teeth"

sys.path.insert(0, str(TOOLS_DIR))

GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; CYAN = "\033[96m"; BOLD = "\033[1m"; RESET = "\033[0m"

DIM = "memory"


def _locked_test_memory_ids() -> list[str]:
    """The REAL locked-test membership for the memory golden set, from gate_eval_splits.json."""
    try:
        from gate_eval_splits import members_for_split
    except Exception:
        return []
    return sorted(members_for_split("test", "memory_golden"))


def _write(path: Path, obj: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    return path


def _results(ids: list[str], n_fail: int) -> dict:
    """A results artifact over the locked-test ids; the first `n_fail` are marked failed."""
    rows = []
    for i, uid in enumerate(ids):
        passed = i >= n_fail
        rows.append({"id": uid, "passed": passed, "score": 100 if passed else 0,
                     "verdict": "PASS" if passed else "FAIL"})
    return {"generated_ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": "companion_gate_teeth", "dimension": DIM, "results": rows}


def _baseline(n: int, tol: float) -> dict:
    return {"_meta": {"ai_asset_version": 1},
            "dimensions": {DIM: {"frozen_ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                 "source": "companion_gate_teeth", "tolerance_pp": tol,
                                 "locked_test": {"pass_rate": 100.0, "n": n},
                                 "val": {"pass_rate": 100.0, "n": n}, "train": {"pass_rate": 100.0, "n": n}}}}


def _scorecard(results_ref: str) -> dict:
    return {"dimensions": {DIM: {"status": "active", "blocking": True, "results_ref": results_ref}}}


def main() -> int:
    from ai_eval_gate import companion_gate

    ids = _locked_test_memory_ids()
    n = len(ids)

    # Use the REAL production tolerance + blocking intent for the memory dim, so this proves the
    # ACTUAL configured gate has teeth — NOT a synthetic-permissive tolerance that could green-light
    # a config too lax to ever block (the false-sense trap). Read it from the live registry.
    reg = json.loads((ROOT / "companion_eval_scorecard.json").read_text(encoding="utf-8"))
    mem_reg = (reg.get("dimensions") or {}).get(DIM) or {}
    blocking = bool(mem_reg.get("blocking"))
    tol = float((mem_reg.get("tolerance") or {}).get("pass_rate_pp", 5.0))
    n_needed = math.ceil(100.0 / tol) if tol > 0 else 10 ** 9

    print(f"\n{BOLD}Companion gate-teeth self-test{RESET}  ·  memory locked-test n={n}  ·  "
          f"registry tolerance -{tol}pp (blocking={blocking})")
    print("=" * 70)

    if not blocking:
        print(f"{CYAN}SKIP{RESET} — memory dim registry blocking=false (intent not yet declared); the gate "
              f"is not meant to FAIL CI for this dim. Not a failure.")
        return 0

    if n < 2:
        print(f"{CYAN}SKIP{RESET} — locked-test memory set has n={n} (<2): no honest blocking scenario "
              f"can be constructed (a single unit = a 100pp swing). Expand companion_memory_golden.json "
              f"and re-run gate_eval_splits.py build. Not a failure.")
        return 0

    if n < n_needed:
        # memory is active+blocking, but the configured tolerance is too tight for this locked-test n,
        # so companion_gate self-throttles to WARN and a degraded run can NEVER FAIL CI — a toothless
        # gate masquerading as blocking. That is exactly the C1.1 defect; FAIL with the fix.
        print(f"{RED}FAIL{RESET} — memory is blocking=true but the registry tolerance -{tol}pp needs "
              f"locked-test n>={n_needed} to ever block (n_needed=ceil(100/tol)); current n={n}. The gate "
              f"is TOOTHLESS. Fix: raise dimensions.memory.tolerance.pass_rate_pp to >= {math.ceil(100.0 / n)} "
              f"(so n_needed<=n) OR grow the golden so memory locked-test n>={n_needed}.")
        print("=" * 70)
        return 1

    # The configured tolerance CAN block at this n. Fail enough units to clear it unambiguously.
    n_fail = min(n, max(2, math.floor(tol * n / 100.0) + 2))
    degraded_rate = round(100.0 * (n - n_fail) / n, 1)

    baseline_path = _write(TEETH_DIR / "baseline.json", _baseline(n, tol))
    clean_res_ref = ".tmp/teeth/clean_results.json"
    degr_res_ref = ".tmp/teeth/degraded_results.json"
    _write(ROOT / clean_res_ref, _results(ids, 0))
    _write(ROOT / degr_res_ref, _results(ids, n_fail))
    sc_clean = _write(TEETH_DIR / "scorecard_clean.json", _scorecard(clean_res_ref))
    sc_degr = _write(TEETH_DIR / "scorecard_degraded.json", _scorecard(degr_res_ref))

    print(f"  fixture: floor 100% (n={n}), tolerance -{tol}pp (n_needed={n_needed}<=n), "
          f"degraded run = {n_fail}/{n} units fail -> {degraded_rate}% (Δ{degraded_rate - 100:+.1f}pp).")
    print(f"  locked-test ids: {ids}\n")

    print(f"{CYAN}-- scenario 1: CLEAN run (should PASS, exit 0) --{RESET}")
    clean_rc = companion_gate(baseline_path=baseline_path, scorecard_path=sc_clean)
    print(f"\n{CYAN}-- scenario 2: DEGRADED run (should BLOCK, exit 1) --{RESET}")
    degr_rc = companion_gate(baseline_path=baseline_path, scorecard_path=sc_degr)

    print("\n" + "=" * 70)
    ok_clean = clean_rc == 0
    ok_degr = degr_rc == 1
    print(f"  clean run  -> exit {clean_rc}  ({'OK, passed as expected' if ok_clean else 'WRONG, should be 0'})")
    print(f"  degraded   -> exit {degr_rc}  ({'OK, blocked as expected' if ok_degr else 'WRONG, should be 1'})")
    if ok_clean and ok_degr:
        print(f"\n{GREEN}OK{RESET}  the memory gate HAS TEETH: it passes a clean locked-test run and "
              f"BLOCKS a degraded one. (C1.1 acceptance bar.)")
        print("=" * 70)
        return 0
    print(f"\n{RED}FAIL{RESET}  the memory gate did NOT discriminate clean from degraded — the gate is "
          f"toothless or mis-wired. Investigate ai_eval_gate.companion_gate / the registry tolerance/n.")
    print("=" * 70)
    return 1


if __name__ == "__main__":
    sys.exit(main())
