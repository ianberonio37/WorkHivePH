#!/usr/bin/env python3
"""Arc V (EFFORTLESS) - interaction-cost ratchet gate (fast, static).

The Effortless sweep (`tools/effortless_sweep.mjs`) re-drives every registered JTBD with
COUNTED helpers and writes two artifacts:
  - arc_v_results.json   (journeys[] + summary: total_click_hops / total_debt / measured)
  - arc_v_baseline.json  (the forward-only ratchet: total click-hops is a CEILING, debt<=N)

This validator is the CHEAP CI guard: it does NOT re-drive the browser (that's the multi-min
`node tools/effortless_sweep.mjs --accept` run, done locally/full-CI). It just asserts the
LAST recorded results still meet the locked ceiling - total interaction cost (clicks+hops)
never RISES (any new friction = more clicks fails here), and excess-click debt never grows.
Same read-the-harness-json pattern as validate_live_page_journeys.py (Arc K).

Exit 0 = ratchet held; exit 1 = regression (a flow got costlier, or debt grew) or a
missing/garbled artifact. The exit code is enforced via sys.exit(main()) - NOT the
flywheel "reporting-only, exit 0 always" path (run_platform_checks.py:998).
"""
import json
import os
import sys
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

RESULTS = "arc_v_results.json"
BASELINE = "arc_v_baseline.json"
REPORT = "arc_v_effort_check_report.json"


def _load(path):
    if not os.path.exists(path):
        return None, f"missing {path}"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f), None
    except Exception as ex:  # noqa: BLE001
        return None, f"unreadable {path}: {ex}"


def _write_report(obj):
    try:
        with open(REPORT, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2)
    except Exception:  # noqa: BLE001
        pass


def main():
    res, e1 = _load(RESULTS)
    base, e2 = _load(BASELINE)
    if e1 or e2:
        msg = e1 or e2
        print(f"[Arc V effortless] ERROR - {msg}")
        print("  run: node tools/effortless_sweep.mjs --accept --update-baseline")
        _write_report({"status": "ERROR", "reason": msg})
        return 1

    summary = res.get("summary", {})
    cost = int(summary.get("total_click_hops", 0))
    debt = int(summary.get("total_debt", 0))
    measured = int(summary.get("measured", 0))

    base_cost = int(base.get("total_click_hops", 0))
    base_debt = base.get("total_debt", None)
    base_measured = int(base.get("measured", 0))
    tol = int(base.get("tol", 2))  # a few drives branch on seeded state -> total can jitter +/-2
    # L-lens (cognitive Load) floor: discriminating signals only (Miller >7-choice + >40 walls +
    # competing primaries; raw density is informational). Ratchets once the baseline carries it.
    load_floor = int((res.get("load") or {}).get("total_load_floor", 0))
    base_load = base.get("total_load_floor", None)
    # F-lens (Flow / Doherty) floor: DEAD-ENDS - an interactive click/fill that didn't land (the
    # user is stuck). DETERMINISTIC (same elements present/absent vs seeded state each run), so it
    # ratchets cleanly -> 0. The Doherty slow-AND-silent signal (>400ms, no busy affordance) is
    # TIMING-NOISY (jitters +/-3 run-to-run) so it is tracked INFORMATIONALLY in results (ranks
    # fix targets) but NOT gated - same calibration discipline as the L-lens raw `density`.
    flow_floor = int((res.get("flow") or {}).get("total_flow_floor", 0))
    base_flow = base.get("total_flow_floor", None)

    # Partial/subset run guard: a dev `--page`/`--phase` run leaves a results.json with fewer
    # journeys than the full-suite baseline. The ceiling only compares like-for-like full runs,
    # so a partial result is NOT a regression - pass with a note.
    if base_measured and measured < base_measured:
        print("=" * 64)
        print("Arc V - EFFORTLESS interaction-cost ratchet gate")
        print("=" * 64)
        print(f"  PARTIAL results ({measured} < baseline {base_measured} journeys) - "
              "subset run, full-suite ceiling not evaluated.")
        print("  refresh: node tools/effortless_sweep.mjs --accept --update-baseline")
        _write_report({"status": "PASS", "partial": True,
                       "measured": measured, "baseline_measured": base_measured})
        print("  [OK] pass (partial run not gated)")
        return 0

    failures = []
    if cost > base_cost + tol:
        failures.append(f"interaction cost ROSE: {cost} > baseline {base_cost} (+{tol} tol)")
    if base_debt is not None and debt > int(base_debt):
        failures.append(f"excess-click debt GREW: {debt} > baseline {base_debt}")
    if base_load is not None and load_floor > base_load:
        failures.append(f"cognitive-load floor GREW: {load_floor} > baseline {base_load} "
                        "(denser UI: a new Miller >7-choice set, >40 above-fold wall, or competing primary CTA)")
    if base_flow is not None and flow_floor > int(base_flow) + tol:
        failures.append(f"flow floor GREW: {flow_floor} > baseline {base_flow} (+{tol} tol) "
                        "(slower UI: a new >400ms action with NO busy affordance, or a dead-end click/fill)")

    print("=" * 64)
    print("Arc V - EFFORTLESS interaction-cost ratchet gate")
    print("=" * 64)
    print(f"  measured : {measured} journeys  total click-hops {cost}  excess-click debt {debt}  load-floor {load_floor}  flow-floor {flow_floor}")
    print(f"  baseline : click-hops <= {base_cost} (+{tol} tol)  debt <= {base_debt}  load-floor <= {base_load}  flow-floor <= {base_flow} (+{tol})")

    report = {
        "status": "FAIL" if failures else "PASS",
        "total_click_hops": cost, "total_debt": debt, "load_floor": load_floor, "flow_floor": flow_floor, "measured": measured,
        "baseline_click_hops": base_cost, "baseline_debt": base_debt, "baseline_load_floor": base_load, "baseline_flow_floor": base_flow, "tol": tol,
        "failures": failures,
    }
    _write_report(report)

    if failures:
        for f in failures:
            print(f"  [X] {f}")
        print("  -> a flow got costlier (more clicks/hops) or excess-click debt grew.")
        return 1

    print(f"  [OK] ratchet held: cost {cost} <= {base_cost}(+{tol}), debt {debt} <= {base_debt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
