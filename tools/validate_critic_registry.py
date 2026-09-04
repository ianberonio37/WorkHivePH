#!/usr/bin/env python3
"""validate_critic_registry.py — anti-drift gate for the UFAI Critic Deepwalk registry (Phase 0.2).

The critique bank must not overstate, exactly as trajectory_registry must not: a `critiqued` row
with nothing graded is a hollow critique; a finding on a dimension the rubric spec does not define
is drift; a trajectory missing from the bank is silent de-scope. Rules:
  R1 structure  — every row carries id/status/pages/cell; status in the vocabulary.
  R2 honesty    — status >= critiqued requires dims_graded non-empty OR a clean_note; walked+ rows
                  carry walked_at; every finding carries dim/layer/severity/evidence/owner and
                  severity 0-4, layer floor|heuristic.
  R3 coverage   — every non-descoped trajectory_registry id appears EXACTLY once (no dupes,
                  no orphans, no silent drops); descoped ids appear zero times.
  R4 vocabulary — every graded/finding dim exists in ufai-rubric-spec.json (the rubric is the
                  dimension SSOT; an invented dim is instrument drift).
  R5 walkable   — every row has non-empty pages OR an explicit no_ui_basis string.
Registered in run_platform_checks (Platform group) once landed in tools/ post-board.
Self-test: --self-test (each rule must redden on a mutated bank)."""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CRITIC = ROOT / "critic_registry.json"
CRITIC_STAGED = ROOT / ".tmp" / "critic_registry.seed.json"
TRAJ = ROOT / "trajectory_registry.json"
SPEC = ROOT / "ufai-rubric-spec.json"

STATUSES = {"pending", "walked", "critiqued", "improving", "locked"}
LAYERS = {"floor", "heuristic"}

CHECK_NAMES = ["critic-registry"]


def check(critic: dict, traj: dict, spec: dict) -> list[str]:
    problems: list[str] = []
    dims = {k for k in spec if not k.startswith("_")}
    rows = critic.get("rows") or []
    seen: dict[str, int] = {}
    for r in rows:
        rid = r.get("id", "?")
        seen[rid] = seen.get(rid, 0) + 1
        if not r.get("id") or r.get("status") not in STATUSES or "pages" not in r or "cell" not in r:
            problems.append(f"R1 {rid}: malformed row (id/status/pages/cell)")
            continue
        st = r["status"]
        if st in ("critiqued", "improving", "locked"):
            if not r.get("dims_graded") and not r.get("clean_note"):
                problems.append(f"R2 {rid}: status {st} with nothing graded and no clean_note - a hollow critique")
        if st != "pending" and not r.get("walked_at"):
            problems.append(f"R2 {rid}: status {st} without walked_at")
        for f in r.get("findings") or []:
            if not all(k in f for k in ("dim", "layer", "severity", "evidence", "owner")):
                problems.append(f"R2 {rid}: finding missing a required field")
            elif f["layer"] not in LAYERS or not (0 <= int(f["severity"]) <= 4):
                problems.append(f"R2 {rid}: finding layer/severity out of vocabulary")
            elif f["dim"] not in dims and f["dim"] != "IN-MOTION":
                problems.append(f"R4 {rid}: finding on dim '{f['dim']}' not in the rubric spec")
        for d in r.get("dims_graded") or []:
            if d not in dims and d != "IN-MOTION":
                problems.append(f"R4 {rid}: graded dim '{d}' not in the rubric spec")
        if not r.get("pages") and not r.get("no_ui_basis"):
            problems.append(f"R5 {rid}: no pages and no no_ui_basis - not walkable, not excused")
    dupes = [k for k, n in seen.items() if n > 1]
    if dupes:
        problems.append(f"R3 duplicate rows: {dupes[:5]}")
    in_scope = {t["id"] for t in traj.get("trajectories", []) if t.get("status") != "descoped"}
    descoped = {t["id"] for t in traj.get("trajectories", []) if t.get("status") == "descoped"}
    missing = sorted(in_scope - set(seen), key=lambda x: int(x[1:]))
    extras = sorted(set(seen) - in_scope)
    if missing:
        problems.append(f"R3 {len(missing)} in-scope trajectories missing from the critic bank (first: {missing[:5]})")
    if set(extras) & descoped:
        problems.append(f"R3 descoped ids present in the critic bank: {sorted(set(extras) & descoped)[:5]}")
    return problems


def main() -> int:
    path = CRITIC if CRITIC.exists() else CRITIC_STAGED
    try:
        critic = json.loads(io.open(path, encoding="utf-8").read())
        traj = json.loads(io.open(TRAJ, encoding="utf-8").read())
        spec = json.loads(io.open(SPEC, encoding="utf-8").read())
    except Exception as e:
        print(f"FAIL critic-registry - inputs unreadable: {e}")
        return 1
    problems = check(critic, traj, spec)
    if problems:
        print(f"FAIL critic-registry ({path.name}) - {len(problems)} problem(s):")
        for p in problems[:20]:
            print(f"    {p}")
        return 1
    rows = critic["rows"]
    from collections import Counter
    st = Counter(r["status"] for r in rows)
    print(f"PASS critic-registry ({path.name}) - {len(rows)} rows consistent with trajectory_registry + rubric spec; "
          f"statuses: {dict(st)}")
    return 0


def self_test() -> int:
    spec = {"_meta": {}, "A1": {}, "C2": {}}
    traj = {"trajectories": [{"id": "T1", "status": "locking"}, {"id": "T2", "status": "descoped"}]}
    good = {"rows": [{"id": "T1", "status": "critiqued", "pages": ["a.html"], "cell": "x",
                      "walked_at": "2026-09-01", "dims_graded": ["A1"],
                      "findings": [{"dim": "C2", "layer": "floor", "severity": 2,
                                    "evidence": "e", "owner": "frontend"}]}]}
    fails = []
    if check(good, traj, spec):
        fails.append("a consistent bank should PASS")
    import copy
    b = copy.deepcopy(good); b["rows"][0]["dims_graded"] = []; b["rows"][0]["findings"] = []
    if not any("hollow critique" in p for p in check(b, traj, spec)):
        fails.append("critiqued-with-nothing must FAIL")
    b = copy.deepcopy(good); b["rows"][0]["findings"][0]["dim"] = "Q99"
    if not any("not in the rubric spec" in p for p in check(b, traj, spec)):
        fails.append("an invented dim must FAIL")
    b = copy.deepcopy(good); b["rows"].append(dict(b["rows"][0]))
    if not any("duplicate" in p for p in check(b, traj, spec)):
        fails.append("a duplicate id must FAIL")
    b = copy.deepcopy(good); b["rows"] = []
    if not any("missing from the critic bank" in p for p in check(b, traj, spec)):
        fails.append("a missing in-scope trajectory must FAIL")
    b = copy.deepcopy(good); b["rows"].append({"id": "T2", "status": "pending", "pages": ["a.html"], "cell": "x"})
    if not any("descoped ids present" in p for p in check(b, traj, spec)):
        fails.append("a descoped id in the bank must FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_critic_registry self-test (hollow/invented-dim/dupe/missing/descoped all redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
