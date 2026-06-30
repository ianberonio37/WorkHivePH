#!/usr/bin/env python3
"""
Validator: Project Manager ENGINE Value Accuracy (EVM math, not just the wire)

The Project Manager pages (project-manager.html, project-report.html) render
Earned Value Management tiles — SPI, CPI, EV, PV, schedule/cost variance — computed
by python-api/projects/*.py. As with the calc + analytics engines, a field-name
contract test and a DOM-parity check both pass even when the EVM FORMULA is wrong
(EV/PV/AC computed incorrectly renders faithfully and ships silently). This
validator value-verifies the EVM math against INDEPENDENTLY hand-computed PMBOK
oracles + a blind self-test for teeth. Hermetic (pure functions, no DB/edge).

Standard: PMI PMBOK 7th ed. (EVM) + AACE 80R-13.
  PV = BAC × planned%   ·   EV = BAC × pct_complete   ·   AC = hours × rate
  SPI = EV/PV   ·   CPI = EV/AC   ·   status by min(SPI,CPI) thresholds (AACE)

Run:        python tools/validate_projects_correctness.py
Self-test:  python tools/validate_projects_correctness.py --self-test
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


# A fully-elapsed (past) project so planned% saturates to 1.0 → PV = BAC, making
# the EVM oracle deterministic regardless of "now". One item 50% complete of 100h
# (EV = 50% × BAC) with 250 actual-h × ₱200/h (AC = 50000 = EV → CPI 1.0).
def _evm_inputs() -> dict:
    return {
        "project": {"budget_php": 100000, "start_date": "2020-01-01", "end_date": "2020-12-31"},
        "items": [{"estimated_hours": 100, "pct_complete": 50, "actual_hours": 250}],
        "logs": [],
    }


# CPM oracle (PMBOK 7th §6.5.2.2). Durations = ceil(estimated_hours / 8).
#   A:16h->2d []   B:24h->3d [A]   C:8h->1d [A]   D:16h->2d [B,C]
#   Forward EF: A=2,B=5,C=3,D=7 => finish 7. Backward LS: D=5,B=2,C=4,A=0.
#   Slack LS-ES: A=0,B=0,C=2,D=0 => critical [A,B,D]; C has 2d float (fast-trackable).
def _cpm_diamond() -> dict:
    def it(i, h, preds):
        return {"id": i, "title": i, "estimated_hours": h, "predecessors": preds, "status": "pending"}
    return {"items": [it("A", 16, []), it("B", 24, ["A"]), it("C", 8, ["A"]), it("D", 16, ["B", "C"])]}


# Linear chain A->B->C: every task critical, zero slack. Durations 2+1+3 = 6 days.
def _cpm_chain() -> dict:
    def it(i, h, preds):
        return {"id": i, "title": i, "estimated_hours": h, "predecessors": preds, "status": "pending"}
    return {"items": [it("A", 16, []), it("B", 8, ["A"]), it("C", 24, ["B"])]}


VECTORS = [
    {
        "module": "projects.diagnostic",
        "phase": "evm",
        "standard": "PMBOK 7th / AACE 80R-13 — Earned Value Management",
        "inputs": _evm_inputs(),
        "asserts": [
            {"path": "pv", "expected": 100000, "tol": 0,
             "note": "BAC × planned% (project fully elapsed → planned% = 1.0) = 100000"},
            {"path": "ev", "expected": 50000, "tol": 0,
             "note": "BAC × pct_complete(50%, hours-weighted) = 50000"},
            {"path": "ac", "expected": 50000, "tol": 0,
             "note": "250 actual-h × ₱200/h = 50000"},
            {"path": "spi", "expected": 0.5, "tol": 0.001,
             "note": "EV/PV = 50000/100000 = 0.50 (behind schedule)"},
            {"path": "cpi", "expected": 1.0, "tol": 0.001,
             "note": "EV/AC = 50000/50000 = 1.00 (on budget)"},
            {"path": "status", "expected": "red", "tol": 0,
             "note": "min(SPI 0.5, CPI 1.0) = 0.5 < 0.85 → red (AACE thresholds)"},
        ],
    },
    {
        "module": "projects.prescriptive",
        "phase": "cpm-diamond",
        "standard": "PMBOK 7th §6.5.2.2 — Critical Path Method (forward/backward pass)",
        "inputs": _cpm_diamond(),
        "asserts": [
            {"path": "critical_path.total_days", "expected": 7, "tol": 0,
             "note": "project finish = max EF = EF(D) = 7 working days"},
            {"path": "critical_path.item_ids", "expected": ["A", "B", "D"], "tol": 0,
             "note": "zero-slack chain A->B->D (C has float, off the path)"},
            {"path": "critical_path.slack_per_item.C", "expected": 2, "tol": 0,
             "note": "C slack = LS(4) - ES(2) = 2 days float"},
            {"path": "critical_path.slack_per_item.A", "expected": 0, "tol": 0,
             "note": "A is critical -> zero slack"},
            {"path": "fast_track_candidates.0.id", "expected": "C", "tol": 0,
             "note": "only C has positive slack -> the lone fast-track candidate"},
            {"path": "fast_track_candidates.0.slack_days", "expected": 2, "tol": 0,
             "note": "C fast-track slack = 2 days"},
        ],
    },
    {
        "module": "projects.prescriptive",
        "phase": "cpm-chain",
        "standard": "PMBOK 7th §6.5.2.2 — linear chain (every task critical)",
        "inputs": _cpm_chain(),
        "asserts": [
            {"path": "critical_path.total_days", "expected": 6, "tol": 0,
             "note": "A(2)+B(1)+C(3) = 6 days, all on the path"},
            {"path": "critical_path.item_ids", "expected": ["A", "B", "C"], "tol": 0,
             "note": "linear chain -> all three critical, in order"},
            {"path": "critical_path.slack_per_item.B", "expected": 0, "tol": 0,
             "note": "no parallel path -> every task zero-slack"},
        ],
    },
]


def _get(d, path):
    cur = d
    for part in path.split("."):
        if isinstance(cur, list):
            cur = cur[int(part)]
        elif isinstance(cur, dict):
            if part not in cur:
                raise KeyError(f"missing result field '{path}' (stopped at '{part}')")
            cur = cur[part]
        else:
            raise KeyError(f"cannot descend into '{part}' for '{path}'")
    return cur


def _close(a, e, tol):
    try:
        return abs(float(a) - float(e)) <= tol
    except (TypeError, ValueError):
        return a == e


def _run_vector(vec, blind=False):
    try:
        mod = importlib.import_module(vec["module"])
    except Exception as e:
        return "SKIP", [f"  [SKIP] {vec['phase']}: cannot import {vec['module']} ({e})"]
    results = []
    try:
        out = mod.calculate(vec["inputs"])
        for a in vec["asserts"]:
            actual = _get(out, a["path"])
            expected = a["expected"]
            if blind:
                expected = (expected + 1000) if isinstance(expected, (int, float)) else "__WRONG__"
            results.append((f"{a['path']} = {actual} (expect {expected} +/-{a['tol']})  [{a['note']}]",
                            _close(actual, expected, a["tol"])))
    except Exception as e:
        return "FAIL", [f"  [FAIL] {vec['phase']}: raised {type(e).__name__}: {e}"]
    all_ok = all(ok for _, ok in results)
    lines = [f"  [{'PASS' if all_ok else 'FAIL'}] {vec['phase']}  ({vec['standard']})"]
    lines += [f"        {'ok ' if ok else 'XX '}{lbl}" for lbl, ok in results]
    return ("PASS" if all_ok else "FAIL"), lines


def validate_projects_correctness(blind=False):
    print("\n[Projects Correctness] value-accuracy of the Project Manager EVM engine")
    print("  (complements DOM-parity: this proves the SPI/CPI/EV/PV NUMBERS are PMBOK-correct)")
    if blind:
        print("  *** SELF-TEST (blind): every oracle corrupted; a healthy validator FAILs all ***")
    n_pass = n_fail = n_skip = n_assert = 0
    for vec in VECTORS:
        status, lines = _run_vector(vec, blind=blind)
        for ln in lines:
            print(ln)
        n_pass += status == "PASS"
        n_fail += status == "FAIL"
        n_skip += status == "SKIP"
        n_assert += len(vec.get("asserts", []))
    print("\n  -- Summary --------------------------------------------")
    print(f"  Vectors: {n_pass} PASS / {n_fail} FAIL / {n_skip} SKIP   ·   {n_assert} PMBOK-anchored oracles")
    if blind:
        ok = (n_fail == (n_pass + n_fail) and n_fail > 0)
        print(f"  SELF-TEST {'PASS' if ok else 'FAIL'}: blind flipped {n_fail}/{n_pass + n_fail} ({'teeth' if ok else 'BROKEN'}).")
        return ok
    return n_fail == 0


if __name__ == "__main__":
    sys.exit(0 if validate_projects_correctness(blind="--self-test" in sys.argv) else 1)
