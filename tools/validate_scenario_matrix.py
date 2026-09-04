#!/usr/bin/env python3
"""validate_scenario_matrix.py — T1.2: the diversity guarantee has to guarantee something.

The scenario matrix (substrate/reference/scenario_matrix.json) is the trajectory program's
claim that user diversity is COVERED, not sampled. This gate makes four assertions:

  1. STRUCTURE — the cell set is exactly the cartesian product of the declared axes
     (no silently dropped combination, no phantom cell, no duplicate).
  2. NO SILENT AXIS — every axis VALUE appears in >=1 cell that is NOT declared_na.
     An axis value covered only by NA rows is a persona the program quietly stopped
     serving (a skipped partition reads as a covered one).
  3. NA IS REASONED — every declared_na carries a na_reason naming WHY no user story
     exists. Unreasoned NA is a stop-in-disguise.
  4. COVERED IS EVIDENCED — every covered cell names its evidence artifact and >=1
     trajectory. Coverage without a receipt is vibes.

Exit 1 on any violation. Registered in run_platform_checks (Platform group).
"""
from __future__ import annotations

import io
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MATRIX = ROOT / "substrate" / "reference" / "scenario_matrix.json"
MATRIX_V2 = ROOT / "substrate" / "reference" / "scenario_matrix_v2.json"

CHECK_NAMES = ["scenario_matrix"]

VALID_STATUS = {"covered", "planned", "declared_na"}


def check_doc(doc: dict, label: str) -> tuple[list[str], str]:
    """The four rules, applied to ONE matrix doc (v1 human-acquisition OR v2 expansion). The rules
    are axis-name-agnostic — they read whatever axes _meta declares — so the same gate holds both."""
    axes = doc["_meta"]["axes"]
    cells = doc["cells"]
    problems: list[str] = []

    # 1. STRUCTURE — the cell set is exactly the cartesian product of the declared axes
    expected = {"|".join(k) for k in itertools.product(*axes.values())}
    actual = [c["id"] for c in cells]
    if len(actual) != len(set(actual)):
        problems.append(f"[{label}] duplicate cell ids")
    missing = expected - set(actual)
    phantom = set(actual) - expected
    if missing:
        problems.append(f"[{label}] {len(missing)} product combination(s) absent: {sorted(missing)[:3]}…")
    if phantom:
        problems.append(f"[{label}] {len(phantom)} cell(s) outside the axes: {sorted(phantom)[:3]}…")
    if doc["_meta"].get("cell_count") != len(cells):
        problems.append(f"[{label}] _meta.cell_count {doc['_meta'].get('cell_count')} != {len(cells)}")

    # 2. NO SILENT AXIS — every axis value appears in >=1 non-NA cell
    for axis, values in axes.items():
        for v in values:
            live = [c for c in cells if c.get(axis) == v and c.get("status") != "declared_na"]
            if not live:
                problems.append(f"[{label}] axis {axis}={v} exists ONLY as declared_na — a silently dropped persona")

    # 3 + 4. per-cell discipline
    for c in cells:
        st = c.get("status")
        if st not in VALID_STATUS:
            problems.append(f"[{label}] {c['id']}: invalid status {st!r}")
        if st == "declared_na" and not (c.get("na_reason") or "").strip():
            problems.append(f"[{label}] {c['id']}: declared_na without a reason")
        if st == "covered":
            if not c.get("trajectories"):
                problems.append(f"[{label}] {c['id']}: covered but names no trajectory")
            if not (c.get("evidence") or "").strip():
                problems.append(f"[{label}] {c['id']}: covered but names no evidence artifact")

    from collections import Counter
    counts = Counter(c["status"] for c in cells)
    summary = f"{label}: {len(cells)} cells · " + " · ".join(f"{k} {v}" for k, v in sorted(counts.items()))
    return problems, summary


def main() -> int:
    problems: list[str] = []
    for path, label in [(MATRIX, "scenario-matrix"), (MATRIX_V2, "scenario-matrix-v2")]:
        if not path.exists():
            problems.append(f"[{label}] matrix file missing: {path.name}")
            continue
        p, summary = check_doc(json.loads(path.read_text(encoding="utf-8")), label)
        print(summary)
        problems += p
    # v2 is GENERATED — hold it to a fresh build so a hand-edit (which the 4 rules can miss, e.g.
    # emptying a planned cell's trajectory) cannot survive, exactly as the header scoreboard is held.
    import subprocess
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "build_scenario_matrix_v2.py"), "--check"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        problems.append("[scenario-matrix-v2] drifted from tools/build_scenario_matrix_v2.py "
                        "(run it to regenerate)")
    if problems:
        for p in problems:
            print(f"  FAIL {p}")
        return 1
    print("PASS scenario-matrix (v1+v2) — structure complete, no silent axis, NA reasoned, coverage evidenced.")
    return 0


def self_test() -> int:
    """The gate must be able to FAIL: feed it mutated worlds and demand reds."""
    import copy
    doc = json.loads(MATRIX.read_text(encoding="utf-8"))

    def run(mutated) -> list[str]:
        # inline reimplementation would re-derive the gate; instead monkeypatch read
        global MATRIX
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(mutated, f)
            tmp = Path(f.name)
        old = MATRIX
        try:
            MATRIX = tmp
            import contextlib
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = main()
            return rc, buf.getvalue()
        finally:
            MATRIX = old
            tmp.unlink(missing_ok=True)

    fails = []
    m1 = copy.deepcopy(doc); m1["cells"] = m1["cells"][1:]                      # dropped combo
    if run(m1)[0] == 0: fails.append("dropped combination should FAIL")
    m2 = copy.deepcopy(doc)
    for c in m2["cells"]:
        if c["device"] == "pc-1280":
            c["status"] = "declared_na"; c["na_reason"] = "x"                    # silent axis
    if run(m2)[0] == 0: fails.append("axis value living only as NA should FAIL")
    m3 = copy.deepcopy(doc)
    na = next(c for c in m3["cells"] if c["status"] == "declared_na"); na.pop("na_reason", None)
    if run(m3)[0] == 0: fails.append("unreasoned NA should FAIL")
    m4 = copy.deepcopy(doc)
    cov = next(c for c in m4["cells"] if c["status"] == "covered"); cov.pop("evidence", None)
    if run(m4)[0] == 0: fails.append("unevidenced coverage should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_scenario_matrix self-test (4 mutations all redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
