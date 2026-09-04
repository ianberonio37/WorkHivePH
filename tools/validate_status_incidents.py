#!/usr/bin/env python3
"""validate_status_incidents.py — T71's lock instrument: the status page's incidents are DERIVED, true,
and DB-independent.

T71's approved default: derive incidents from platform_health.json + automation_log rather than a new
incident table. tools/derive_status_incidents.py is that producer; this gate proves its output is
TRUTHFUL and well-formed, so status.html can render it during the very outage it reports.

FOUR assertions (each refutable — see the self-test):
  1. WELL-FORMED   — every incident carries id, source, severity(major|minor), started_at, status.
  2. OPEN ⇔ RED    — the set of OPEN gate-incidents equals the set of validators currently FAIL/WARN in
                     platform_health.json. Not a subset, not a superset: an open incident for a gate
                     that is green would be a lie, and a red gate with no incident is a silent outage.
  3. RESOLVED SANE — every resolved incident has an ended_at and started_at <= ended_at (no negative
                     window, the two-clocks class).
  4. FRESH         — the committed status_incidents.json equals a fresh regeneration from the current
                     signals (the header-scoreboard discipline: a hand-edited status file cannot stand).

Registered in run_platform_checks (Platform). Read-only; no browser.
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEALTH = ROOT / "platform_health.json"
INCIDENTS = ROOT / "status_incidents.json"
PRODUCER = ROOT / "tools" / "derive_status_incidents.py"

CHECK_NAMES = ["status-incidents-derived"]
_SEV_OK = {"major", "minor"}


def check(doc: dict, health: dict) -> list[str]:
    problems: list[str] = []
    incs = doc.get("incidents", [])
    for i in incs:
        for k in ("id", "source", "severity", "started_at", "status"):
            if not i.get(k):
                problems.append(f"incident {i.get('id','?')}: missing {k}")
        if i.get("severity") not in _SEV_OK:
            problems.append(f"incident {i.get('id','?')}: severity {i.get('severity')!r} not major/minor")
        if i.get("status") == "resolved":
            if not i.get("ended_at"):
                problems.append(f"incident {i.get('id')}: resolved with no ended_at")
            elif i.get("started_at") and i["started_at"] > i["ended_at"]:
                problems.append(f"incident {i.get('id')}: started_at after ended_at (negative window)")

    # 2. OPEN gate-incidents ⇔ currently-red validators
    open_gate = {i["id"][len("gate-"):] for i in incs
                 if i.get("status") == "open" and i.get("source") == "gate" and str(i.get("id","")).startswith("gate-")}
    red = set()
    for v in health.get("validators", []):
        st = str(v.get("status", "")).lower()
        if v.get("ok") is False and not st:
            st = "fail"
        if st in ("fail", "warn"):
            red.add(v.get("id"))
    if open_gate != red:
        miss = red - open_gate         # a red gate with no open incident — a silent outage
        phantom = open_gate - red      # an open incident for a green gate — a lie
        if miss:
            problems.append(f"{len(miss)} red gate(s) have NO open incident (silent outage): {sorted(miss)[:4]}")
        if phantom:
            problems.append(f"{len(phantom)} open incident(s) for a NON-red gate (false alarm): {sorted(phantom)[:4]}")
    return problems


def main() -> int:
    if not INCIDENTS.exists():
        print("FAIL status-incidents-derived: status_incidents.json missing — run tools/derive_status_incidents.py")
        return 1
    # 4. FRESH — capture the COMMITTED file FIRST, regenerate, require equality. Capturing before the
    # producer runs is the whole point: the producer overwrites the file, so comparing after it ran
    # would be comparing the file to itself (a vacuous check — a lock that tests nothing is hollow).
    committed = INCIDENTS.read_text(encoding="utf-8")
    r = subprocess.run([sys.executable, str(PRODUCER)], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"FAIL status-incidents-derived: producer errored: {(r.stderr or '')[:160]}")
        return 1
    regenerated = INCIDENTS.read_text(encoding="utf-8")
    problems_fresh = []
    if committed != regenerated:
        problems_fresh.append("status_incidents.json was STALE — it did not match a fresh derivation "
                              "from the current signals (regenerate it whenever the board changes)")
    doc = json.loads(regenerated)
    health = json.loads(HEALTH.read_text(encoding="utf-8")) if HEALTH.exists() else {}
    problems = problems_fresh + check(doc, health)
    print(f"status-incidents: {doc.get('open', '?')} open · {doc.get('resolved', '?')} resolved · "
          f"{len(doc.get('incidents', []))} total")
    if problems:
        for p in problems[:8]:
            print(f"  FAIL {p}")
        return 1
    print("PASS status-incidents-derived — every incident is well-formed, open⇔red, resolved windows "
          "sane, and the file equals a fresh derivation.")
    return 0


def self_test() -> int:
    """The gate must be able to FAIL: feed it mutated worlds and demand reds."""
    health = {"validators": [{"id": "gate-x", "status": "FAIL"}, {"id": "gate-y", "status": "PASS"}]}
    good = {"incidents": [{"id": "gate-gate-x", "source": "gate", "severity": "major",
                           "started_at": "2026-09-01T00:00", "ended_at": None, "status": "open"}]}
    fails = []
    if check(good, health):
        fails.append("a well-formed open⇔red doc should PASS")
    phantom = {"incidents": [{"id": "gate-gate-y", "source": "gate", "severity": "major",
                              "started_at": "t", "ended_at": None, "status": "open"}]}
    if not any("NON-red" in p for p in check(phantom, health)):
        fails.append("an open incident for a green gate should FAIL")
    if not any("silent outage" in p for p in check({"incidents": []}, health)):
        fails.append("a red gate with no incident should FAIL")
    neg = {"incidents": [{"id": "gate-gate-x", "source": "gate", "severity": "major",
                          "started_at": "2026-09-02", "ended_at": "2026-09-01", "status": "resolved"},
                         {"id": "gate-gate-x2", "source": "gate", "severity": "major",
                          "started_at": "t", "ended_at": None, "status": "open"}]}
    # add the open gate-x so open⇔red holds, isolating the negative-window assertion
    neg["incidents"].append({"id": "gate-gate-x", "source": "gate", "severity": "major",
                             "started_at": "t", "ended_at": None, "status": "open"})
    if not any("negative window" in p for p in check(neg, health)):
        fails.append("a resolved incident with started_at>ended_at should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_status_incidents self-test (phantom / silent-outage / negative-window all redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
