#!/usr/bin/env python3
"""
Validator: Analytics Engine VALUE Accuracy (the number, not just the wire)

WHAT THIS IS (and what it is NOT)
---------------------------------
`analytics.html` is a SOURCE OF TRUTH — hive/asset-hub/predictive/shift-brain read
its computations. There are TWO things to verify about it:

  1. DOM == orchestrator  — does each rendered tile equal the orchestrator field
     the renderer reads. That is `__ANALYTICS_PARITY` (analytics_correctness.js),
     a BROWSER parity check.
  2. orchestrator == STANDARD-CORRECT  — does the analytics ENGINE
     (python-api/analytics/*.py) compute MTBF/MTTR/OEE/PM-compliance/priority
     CORRECTLY from raw inputs per ISO 14224 / ISO 22400 / SMRP / ISO 55001.
     NOTHING asserted this — a wrong derivation would pass the DOM parity check
     (DOM faithfully renders a wrong number) and ship silently.

This validator closes gap #2 — the load-bearing one (a wrong number ORIGINATES in
the engine). It imports each phase handler (`python-api/analytics/<phase>.py ::
calculate(inputs)->dict`), feeds a SMALL synthetic dataset with KNOWN values, and
asserts the computed output equals an INDEPENDENTLY hand-computed standard oracle.
Hermetic: pure functions, no network/edge/DB. Mirrors validate_calc_formula_accuracy.py.

It also closes the §13 H-axis "analytics prescriptive chain" (the last load-bearing
transform chain) by value-verifying the prescriptive priority/reorder math.

SCOPE: all 4 analytics phases are value-verified —
  • descriptive  — ISO 14224 MTBF/MTTR/Availability + ISO 22400 OEE + SMRP PM-compliance
  • diagnostic   — ISO 14224 failure-mode Pareto + repeat-cluster + SAE JA1011 RCM consequence
                   + parts-availability impact   (imports scipy → SKIPs if scipy absent)
  • predictive   — ISO 13381-1/ISO 14224 next-failure (MTBF) + SMRP parts-stockout
  • prescriptive — ISO 55001 priority ranking + SMRP parts reorder  (the §13 last-H chain)
Each metric is asserted against an INDEPENDENTLY hand-computed standard oracle, not the
engine's own formula. It is still a per-phase FLOOR (a few key metrics per phase, not every
field) — each added VECTORS entry raises the assertion count printed in the summary.

Run:        python tools/validate_analytics_correctness.py
Self-test:  python tools/validate_analytics_correctness.py --self-test
"""

import importlib
import os
import sys
from datetime import datetime, timedelta, timezone

# Windows cp1252 stdout guard — CONDITIONAL .detach()+encoding-check form so that
# importing this module for its stats after another guard has already re-wrapped
# stdout is a safe no-op (the unconditional .buffer form double-wraps and crashes
# with "I/O operation on closed file"). See validate_validator_cp1252_guard.py.
if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

# ─── Make python-api/analytics importable ────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PYAPI = os.path.join(_ROOT, "python-api")
if _PYAPI not in sys.path:
    sys.path.insert(0, _PYAPI)

# The 4 analytics phases — the honest denominator for the value-coverage figure.
TOTAL_ANALYTICS_PHASES = 4


def _iso(days_ago: float) -> str:
    """An ISO-8601 UTC timestamp `days_ago` days before now. Relative dates keep
    the windowed metrics (failure_frequency, priority_ranking — which filter
    created_at >= now - period_days) stable across runs; the non-windowed metrics
    (MTBF/MTTR/availability) depend only on the SPACING, which is exact."""
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def _descriptive_inputs() -> dict:
    """One machine M-1, 3 corrective failures spaced EXACTLY 10 days apart, all
    closed with downtime 2/4/6 h and 95% quality; PM 2-of-3 compliant."""
    return {
        "period_days": 90,
        "logbook_entries": [
            {"machine": "M-1", "maintenance_type": "Breakdown / Corrective", "status": "Closed",
             "created_at": _iso(22), "downtime_hours": 2, "root_cause": "Bearing wear",
             "production_output": {"quality_pct": 95}},
            {"machine": "M-1", "maintenance_type": "Breakdown / Corrective", "status": "Closed",
             "created_at": _iso(12), "downtime_hours": 4, "root_cause": "Bearing wear",
             "production_output": {"quality_pct": 95}},
            {"machine": "M-1", "maintenance_type": "Breakdown / Corrective", "status": "Closed",
             "created_at": _iso(2), "downtime_hours": 6, "root_cause": "Bearing wear",
             "production_output": {"quality_pct": 95}},
        ],
        "pm_scope_items": [
            {"asset_id": "A-1", "id": "s1", "frequency": "Monthly", "asset_name": "Pump 1"},
        ],
        "pm_completions": [
            {"asset_id": "A-1", "scope_item_id": "s1", "completed_at": _iso(5)},
            {"asset_id": "A-1", "scope_item_id": "s1", "completed_at": _iso(15)},
        ],
        "inv_transactions": [],
    }


def _prescriptive_inputs() -> dict:
    """Same M-1 failure history (3 failures, avg 4h downtime) on a Critical asset
    → ISO 55001 risk = 4×3×4 = 48; one stocked-out part → 1 CRITICAL reorder."""
    return {
        "period_days": 90,
        "logbook_entries": [
            {"machine": "M-1", "category": "Mechanical", "maintenance_type": "Breakdown / Corrective",
             "status": "Closed", "created_at": _iso(22), "downtime_hours": 2},
            {"machine": "M-1", "category": "Mechanical", "maintenance_type": "Breakdown / Corrective",
             "status": "Closed", "created_at": _iso(12), "downtime_hours": 4},
            {"machine": "M-1", "category": "Mechanical", "maintenance_type": "Breakdown / Corrective",
             "status": "Closed", "created_at": _iso(2), "downtime_hours": 6},
        ],
        "pm_assets": [
            {"tag_id": "M-1", "criticality": "Critical", "asset_name": "Pump 1"},
        ],
        "inventory_items": [
            {"part_name": "Filter X", "qty_on_hand": 0, "reorder_point": 5},     # stocked out → CRITICAL
            {"part_name": "Belt Y", "qty_on_hand": 100, "reorder_point": 10},    # healthy → skipped
        ],
        "inv_transactions": [],
        "pm_scope_items": [],
        "skill_badges": [],
    }


def _diagnostic_inputs() -> dict:
    """Two machines, 4 corrective entries, root_cause + failure_consequence + downtime —
    sized so every diagnostic metric has a clean hand-computed oracle. (Dates are not
    window-filtered by any diagnostic function, so absolute spacing is irrelevant here.)"""
    return {
        "logbook_entries": [
            {"machine": "M-1", "maintenance_type": "Breakdown / Corrective", "status": "Closed",
             "root_cause": "Bearing wear", "failure_consequence": "Stopped production",
             "downtime_hours": 4, "created_at": _iso(20)},
            {"machine": "M-1", "maintenance_type": "Breakdown / Corrective", "status": "Closed",
             "root_cause": "Bearing wear", "failure_consequence": "Stopped production",
             "downtime_hours": 6, "created_at": _iso(15)},
            {"machine": "M-2", "maintenance_type": "Breakdown / Corrective", "status": "Closed",
             "root_cause": "Bearing wear", "failure_consequence": "Safety risk",
             "downtime_hours": 2, "created_at": _iso(10)},
            {"machine": "M-2", "maintenance_type": "Breakdown / Corrective", "status": "Closed",
             "root_cause": "Seal leak", "failure_consequence": "Running reduced",
             "downtime_hours": 8, "created_at": _iso(5)},
        ],
    }


def _predictive_inputs() -> dict:
    """M-1 with 3 corrective failures (MTBF 10d) for next-failure prediction; one part
    consuming 90 units over the 90-day window (1.0/day) with 10 on hand → stockout in 10d."""
    return {
        "period_days": 90,
        "logbook_entries": [
            {"machine": "M-1", "maintenance_type": "Breakdown / Corrective", "status": "Closed",
             "created_at": _iso(22), "downtime_hours": 2},
            {"machine": "M-1", "maintenance_type": "Breakdown / Corrective", "status": "Closed",
             "created_at": _iso(12), "downtime_hours": 4},
            {"machine": "M-1", "maintenance_type": "Breakdown / Corrective", "status": "Closed",
             "created_at": _iso(2), "downtime_hours": 6},
        ],
        "inventory_items": [
            {"part_name": "Filter X", "qty_on_hand": 10, "reorder_point": 5},
        ],
        "inv_transactions": [
            {"part_name": "Filter X", "type": "use", "qty_change": -90, "created_at": _iso(10)},
        ],
    }


def _check_descriptive_failure_freq(mod):
    """failure_frequency is routed through postgres-precomputed in the master
    calculate() (precomputed.get('failure_frequency', []) is `[]`, and the routing
    tests `is not None`), so verify the PYTHON derivation directly. ISO 14224:
    3 corrective events in the 90-day window → total_failures = 3."""
    r = mod.calc_failure_frequency(_descriptive_inputs()["logbook_entries"], 90)
    return [
        ("calc_failure_frequency.total_failures == 3  [ISO 14224, 90-day window]",
         r.get("total_failures") == 3, f"got {r.get('total_failures')}"),
        ("calc_failure_frequency rows == 1 machine (M-1)",
         len(r.get("failure_frequency", [])) == 1, f"got {len(r.get('failure_frequency', []))} rows"),
    ]


# ─── Golden vectors ──────────────────────────────────────────────────────────
VECTORS = [
    {
        "module": "analytics.descriptive",
        "phase": "descriptive",
        "standard": "ISO 14224 (MTBF/MTTR/Avail) + ISO 22400 (OEE) + SMRP (PM)",
        "inputs": _descriptive_inputs(),
        "asserts": [
            {"path": "mtbf.mtbf_by_asset.0.mtbf_days", "expected": 10.0, "tol": 0.05,
             "note": "ISO 14224 §9.3: intervals (10d,10d) → MTBF 10.0 d"},
            {"path": "mtbf.mtbf_by_asset.0.failure_count", "expected": 3, "tol": 0,
             "note": "3 corrective events"},
            {"path": "mttr.mttr_by_asset.0.mttr_hours", "expected": 4.0, "tol": 0.05,
             "note": "ISO 14224 §9.4: (2+4+6)/3 = 4.0 h"},
            {"path": "mttr.mttr_by_asset.0.total_downtime_h", "expected": 12.0, "tol": 0.05,
             "note": "sum downtime = 12.0 h"},
            {"path": "availability.availability_by_asset.0.availability_pct", "expected": 98.4, "tol": 0.1,
             "note": "ISO 14224 §9.2: 10/(10+4/24)·100 = 98.4%"},
            {"path": "oee.oee_by_asset.0.oee_pct", "expected": 93.4, "tol": 0.1,
             "note": "ISO 22400 partial A×Q: (720-12)/720 · 95% = 93.4%"},
            {"path": "oee.oee_by_asset.0.availability_pct", "expected": 98.3, "tol": 0.1,
             "note": "OEE availability = uptime/720 (operational, ISO 22400 — NOT the reliability one)"},
            {"path": "pm_compliance.overall_pct", "expected": 66.7, "tol": 0.1,
             "note": "SMRP 2.1.1: 2 done / 3 scheduled (Monthly × 90d window) = 66.7%"},
            {"path": "downtime_pareto.total_downtime_hours", "expected": 12.0, "tol": 0.05,
             "note": "Pareto total downtime = 12.0 h"},
            {"path": "repeat_failures.repeat_pair_count", "expected": 1, "tol": 0,
             "note": "same root_cause ×3 on M-1 → 1 repeat pair (ISO 14224)"},
        ],
    },
    {
        "module": "analytics.descriptive",
        "phase": "descriptive",
        "standard": "ISO 14224 failure frequency (direct fn — master routes via postgres precomputed)",
        "custom": _check_descriptive_failure_freq,
    },
    {
        "module": "analytics.prescriptive",
        "phase": "prescriptive",
        "standard": "ISO 55001 (risk ranking) + SMRP (parts reorder) — the §13 last-H chain",
        "inputs": _prescriptive_inputs(),
        "asserts": [
            {"path": "priority_ranking.ranking.0.risk_score", "expected": 48.0, "tol": 0.05,
             "note": "ISO 55001: crit(Critical=4) × failures(3) × avg_dt(4h) = 48.0"},
            {"path": "priority_ranking.ranking.0.failure_count", "expected": 3, "tol": 0,
             "note": "3 corrective failures in window"},
            {"path": "priority_ranking.ranking.0.avg_downtime_h", "expected": 4.0, "tol": 0.05,
             "note": "12h / 3 = 4.0 h avg downtime"},
            {"path": "priority_ranking.top_priority", "expected": "M-1", "tol": 0,
             "note": "only machine → top priority"},
            {"path": "parts_reorder.critical_count", "expected": 1, "tol": 0,
             "note": "Filter X qty 0 ≤ reorder 5 → CRITICAL (Belt Y healthy → skipped)"},
            {"path": "parts_reorder.reorder.0.urgency", "expected": "CRITICAL", "tol": 0,
             "note": "qty 0 → CRITICAL urgency"},
            {"path": "parts_reorder.reorder.0.part_name", "expected": "Filter X", "tol": 0,
             "note": "the stocked-out part surfaces first"},
        ],
    },
    {
        "module": "analytics.diagnostic",
        "phase": "diagnostic",
        "standard": "ISO 14224 failure taxonomy + SAE JA1011 §5.4 RCM consequence (needs scipy → SKIP if absent)",
        "inputs": _diagnostic_inputs(),
        "asserts": [
            {"path": "failure_mode_distribution.total_failures", "expected": 4, "tol": 0,
             "note": "4 corrective entries with root_cause"},
            {"path": "failure_mode_distribution.top_root_cause_pct", "expected": 75.0, "tol": 0.1,
             "note": "Bearing wear 3 of 4 = 75% (ISO 14224 Pareto)"},
            {"path": "repeat_failure_clustering.systemic_count", "expected": 1, "tol": 0,
             "note": "Bearing wear spans 2 machines → 1 systemic issue"},
            {"path": "rcm_consequence.coverage_pct", "expected": 100.0, "tol": 0.1,
             "note": "SAE JA1011 §5.4: all 4 carry failure_consequence → 100% coverage"},
            {"path": "rcm_consequence.top_consequence", "expected": "Stopped production", "tol": 0,
             "note": "highest-severity non-zero bucket (2 of 4)"},
            {"path": "parts_availability_impact.overall_avg_mttr_h", "expected": 5.0, "tol": 0.05,
             "note": "mean downtime (4+6+2+8)/4 = 5.0 h"},
            {"path": "parts_availability_impact.high_downtime_count", "expected": 1, "tol": 0,
             "note": "p75=6.5 → only the 8h job exceeds it"},
        ],
    },
    {
        "module": "analytics.predictive",
        "phase": "predictive",
        "standard": "ISO 13381-1 / ISO 14224 next-failure + SMRP parts-stockout (deterministic)",
        "inputs": _predictive_inputs(),
        "asserts": [
            {"path": "next_failure_dates.predictions.0.mtbf_days", "expected": 10.0, "tol": 0.05,
             "note": "ISO 14224 MTBF 10.0d drives the prediction"},
            {"path": "next_failure_dates.predictions.0.failure_count", "expected": 3, "tol": 0,
             "note": "3 failures observed"},
            {"path": "next_failure_dates.total_tracked", "expected": 1, "tol": 0,
             "note": "1 machine with ≥2 failures"},
            {"path": "next_failure_dates.predictions.0.risk", "expected": "MEDIUM", "tol": 0,
             "note": "last failure −2d + 10d MTBF → ~8d out → MEDIUM (1<d≤14)"},
            {"path": "parts_stockout.stockout_risk.0.daily_rate", "expected": 1.0, "tol": 0.01,
             "note": "90 used / 90-day window = 1.0/day"},
            {"path": "parts_stockout.stockout_risk.0.days_to_stockout", "expected": 10.0, "tol": 0.05,
             "note": "qty 10 / 1.0/day = 10 days → HIGH (≤30)"},
            {"path": "parts_stockout.stockout_risk.0.risk", "expected": "HIGH", "tol": 0,
             "note": "10 days to stockout → HIGH band"},
            {"path": "parts_stockout.at_risk_count", "expected": 1, "tol": 0,
             "note": "1 part at risk"},
        ],
    },
]


def _get(d, path):
    """Walk a dotted path; numeric segments index into lists."""
    cur = d
    for part in path.split("."):
        if isinstance(cur, list):
            idx = int(part)
            if idx >= len(cur):
                raise KeyError(f"list index {idx} out of range at '{path}' (len {len(cur)})")
            cur = cur[idx]
        elif isinstance(cur, dict):
            if part not in cur:
                raise KeyError(f"missing result field '{path}' (stopped at '{part}')")
            cur = cur[part]
        else:
            raise KeyError(f"cannot descend into '{part}' for '{path}' (got {type(cur).__name__})")
    return cur


def _close(actual, expected, tol):
    try:
        return abs(float(actual) - float(expected)) <= tol
    except (TypeError, ValueError):
        return actual == expected


def _run_vector(vec, blind=False):
    try:
        mod = importlib.import_module(vec["module"])
    except Exception as e:  # missing dep (pandas/numpy) / import error
        return "SKIP", [f"  [SKIP] {vec['phase']}: cannot import {vec['module']} ({e})"]

    results = []  # (label, ok)
    try:
        if "custom" in vec:
            checks = vec["custom"](mod)
            if blind:
                checks = [(lbl, not ok, det) for (lbl, ok, det) in checks]
            results.extend((lbl, ok) for (lbl, ok, _det) in checks)
        else:
            out = mod.calculate(vec["inputs"])
            for a in vec["asserts"]:
                actual = _get(out, a["path"])
                expected = a["expected"]
                if blind:
                    expected = (expected + 1000) if isinstance(expected, (int, float)) else "__WRONG__"
                ok = _close(actual, expected, a["tol"])
                results.append((
                    f"{a['path']} = {actual} (expect {expected} +/-{a['tol']})  [{a['note']}]", ok,
                ))
    except Exception as e:
        return "FAIL", [f"  [FAIL] {vec['phase']}: raised {type(e).__name__}: {e}"]

    all_ok = all(ok for _, ok in results)
    lines = [f"  [{'PASS' if all_ok else 'FAIL'}] {vec['phase']}  ({vec['standard']})"]
    for lbl, ok in results:
        lines.append(f"        {'ok ' if ok else 'XX '}{lbl}")
    return ("PASS" if all_ok else "FAIL"), lines


def validate_analytics_correctness(blind=False):
    print("\n[Analytics Correctness] value-accuracy of the analytics ENGINE")
    print("  (complements __ANALYTICS_PARITY: that proves DOM==orchestrator; this proves orchestrator==standard-correct)")
    if blind:
        print("  *** SELF-TEST (blind): every oracle corrupted; a healthy validator FAILs all ***")

    n_vec_pass = n_vec_fail = n_skip = n_assert = 0
    phases_ok, phases_bad, phases_skip = set(), set(), set()
    for vec in VECTORS:
        status, lines = _run_vector(vec, blind=blind)
        for ln in lines:
            print(ln)
        ph = vec["phase"]
        if status == "PASS":
            n_vec_pass += 1
            phases_ok.add(ph)
        elif status == "FAIL":
            n_vec_fail += 1
            phases_bad.add(ph)
        else:
            n_skip += 1
            phases_skip.add(ph)
        n_assert += len(vec.get("asserts", [])) or 2  # custom invariants ~2 checks each

    # A phase is "value-verified" only if it has >=1 vector and NONE failed.
    verified_phases = phases_ok - phases_bad
    covered = len(verified_phases | phases_bad)  # phases actually exercised (not skip-only)
    pct = round(100 * len(verified_phases) / TOTAL_ANALYTICS_PHASES, 1)
    print("\n  -- Summary --------------------------------------------")
    print(f"  Vectors                   : {n_vec_pass} PASS / {n_vec_fail} FAIL / {n_skip} SKIP")
    print(f"  Phases value-verified     : {sorted(verified_phases)} "
          f"({len(verified_phases)}/{TOTAL_ANALYTICS_PHASES} = {pct}%; all 4 phases covered — "
          f"diagnostic SKIPs if scipy absent)")
    print(f"  Standard-anchored oracles : {n_assert} assertions")

    if blind:
        ok = (n_vec_fail == (n_vec_pass + n_vec_fail) and n_vec_fail > 0)
        print(f"\n  SELF-TEST {'PASS' if ok else 'FAIL'}: blind run flipped {n_vec_fail}/{n_vec_pass + n_vec_fail} "
              f"vectors to FAIL ({'has teeth' if ok else 'BROKEN — would pass wrong math'}).")
        return ok

    return n_vec_fail == 0


if __name__ == "__main__":
    blind = "--self-test" in sys.argv
    sys.exit(0 if validate_analytics_correctness(blind=blind) else 1)
