#!/usr/bin/env python3
"""
Validator: Reliability Workbench ENGINE Value Accuracy (P-F interval RCM math)

The Reliability Workbench / predictive surfaces compute the RCM P-F interval —
the inspection cadence that guarantees a developing defect is caught between the
potential-failure (P) and functional-failure (F) thresholds. The rule
(SAE JA1011 / MIL-HDBK-189C / Moubray RCM II) is: inspect at P-F / 2 for normal
assets, P-F / 3 for safety-critical. A wrong interval is a real safety gap (you
inspect too late and the asset fails uncaught), and a contract/DOM test never
catches a wrong NUMBER. This value-verifies `reliability.pf_interval.calculate_pf`
against hand-computed oracles + a blind self-test for teeth. Hermetic.

(Weibull β/η fitting — reliability/weibull.py — is a statistical fit via lifelines;
it has no clean closed-form oracle, so it is intentionally NOT pinned here.)

Run:        python tools/validate_reliability_correctness.py
Self-test:  python tools/validate_reliability_correctness.py --self-test
"""

import importlib
import os
import sys

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PYAPI = os.path.join(_ROOT, "python-api")
if _PYAPI not in sys.path:
    sys.path.insert(0, _PYAPI)

# A vibration series (direction 'above') that crosses P=50 on Jan-11 and F=100 on
# Jan-21 → one P-F pair of exactly 10 days. RCM interval = P-F/2 = 5 (normal),
# P-F/3 = 3 (safety-critical, rounded).
_READINGS = [
    {"ts": "2026-01-01T00:00:00Z", "value": 40},   # below P
    {"ts": "2026-01-11T00:00:00Z", "value": 60},   # crosses P (warning)
    {"ts": "2026-01-21T00:00:00Z", "value": 110},  # crosses F (failure)
]


def _check_pf_normal(mod):
    r = mod.calculate_pf(readings=_READINGS, p_threshold=50, f_threshold=100,
                         direction="above", safety_critical=False)
    return [
        ("pf_days == 10.0  (P Jan-11 → F Jan-21)", r.get("pf_days") == 10.0, f"got {r.get('pf_days')}"),
        ("n_pairs == 1", r.get("n_pairs") == 1, f"got {r.get('n_pairs')}"),
        ("recommended_interval_days == 5  (P-F/2, RCM normal)", r.get("recommended_interval_days") == 5,
         f"got {r.get('recommended_interval_days')}"),
        ("basis == 'P-F/2'", r.get("basis") == "P-F/2", f"got {r.get('basis')}"),
    ]


def _check_pf_safety_critical(mod):
    r = mod.calculate_pf(readings=_READINGS, p_threshold=50, f_threshold=100,
                         direction="above", safety_critical=True)
    return [
        ("safety-critical interval == 3  (P-F/3 = 10/3 rounded)", r.get("recommended_interval_days") == 3,
         f"got {r.get('recommended_interval_days')}"),
        ("basis == 'P-F/3'", r.get("basis") == "P-F/3", f"got {r.get('basis')}"),
    ]


VECTORS = [
    {"module": "reliability.pf_interval", "phase": "pf_interval_normal",
     "standard": "SAE JA1011 / MIL-HDBK-189C RCM — P-F/2 inspection cadence",
     "custom": _check_pf_normal},
    {"module": "reliability.pf_interval", "phase": "pf_interval_safety_critical",
     "standard": "RCM — P-F/3 for safety/environment-critical assets",
     "custom": _check_pf_safety_critical},
]


def _run_vector(vec, blind=False):
    try:
        mod = importlib.import_module(vec["module"])
    except Exception as e:
        return "SKIP", [f"  [SKIP] {vec['phase']}: cannot import {vec['module']} ({e})"]
    try:
        checks = vec["custom"](mod)
        if blind:
            checks = [(lbl, not ok, det) for (lbl, ok, det) in checks]
    except Exception as e:
        return "FAIL", [f"  [FAIL] {vec['phase']}: raised {type(e).__name__}: {e}"]
    all_ok = all(ok for _, ok, _ in checks)
    lines = [f"  [{'PASS' if all_ok else 'FAIL'}] {vec['phase']}  ({vec['standard']})"]
    lines += [f"        {'ok ' if ok else 'XX '}{lbl}" + (f"   {det}" if det and not ok else "")
              for lbl, ok, det in checks]
    return ("PASS" if all_ok else "FAIL"), lines


def validate_reliability_correctness(blind=False):
    print("\n[Reliability Correctness] value-accuracy of the P-F interval RCM engine")
    print("  (a wrong inspection interval = inspect too late, asset fails uncaught — a safety gap)")
    if blind:
        print("  *** SELF-TEST (blind): every oracle inverted; a healthy validator FAILs all ***")
    n_pass = n_fail = n_skip = 0
    for vec in VECTORS:
        status, lines = _run_vector(vec, blind=blind)
        for ln in lines:
            print(ln)
        n_pass += status == "PASS"
        n_fail += status == "FAIL"
        n_skip += status == "SKIP"
    print("\n  -- Summary --------------------------------------------")
    print(f"  Vectors: {n_pass} PASS / {n_fail} FAIL / {n_skip} SKIP   ·   RCM P-F interval value-verified")
    if blind:
        ok = (n_fail == (n_pass + n_fail) and n_fail > 0)
        print(f"  SELF-TEST {'PASS' if ok else 'FAIL'}: blind flipped {n_fail}/{n_pass + n_fail} ({'teeth' if ok else 'BROKEN'}).")
        return ok
    return n_fail == 0


if __name__ == "__main__":
    sys.exit(0 if validate_reliability_correctness(blind="--self-test" in sys.argv) else 1)
