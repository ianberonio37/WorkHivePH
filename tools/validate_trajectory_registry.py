#!/usr/bin/env python3
"""validate_trajectory_registry.py — the 500-trajectory program cannot overstate itself.

Checks (each one an anti-drift rule Ian asked for or a lesson already paid for):
  1. COMPLETE — ids are exactly T1..T500, waves match the declared ranges.
  2. HONEST pct — statuses map to fixed pct (specced 5 · walked 25 · fixed 60 · locked 100);
     any other pct requires an in-flight status ('locking'/'walking'/'fixing') AND a written
     basis. A percentage without a basis is a vibe.
  3. HEADER PARITY — the roadmap's scoreboard block equals a fresh regeneration from this
     registry (update_trajectory_scoreboard.py --check). The header IS the anti-drift surface;
     a stale or hand-edited header fails the board.
  4. MATRIX REFS — every trajectory id the scenario matrix names exists here.
  5. LOCKING/LOCKED = GATED — 'locking' must name a gate (that status MEANS the lock exists),
     and a 'locked' trajectory must name >=1 gate whose id must
     be registered in run_platform_checks.py (the registry cannot claim a lock nobody runs).
"""
from __future__ import annotations

import io
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "trajectory_registry.json"
MATRIX = ROOT / "substrate" / "reference" / "scenario_matrix.json"
CHECKS_FILE = ROOT / "run_platform_checks.py"

CHECK_NAMES = ["trajectory_registry"]

WAVES = [("A", 1, 8), ("B", 9, 18), ("C", 19, 28), ("D", 29, 36), ("E", 37, 44), ("F", 45, 50),
         ("G", 51, 62), ("H", 63, 78), ("I", 79, 92), ("J", 93, 104), ("K", 105, 112),
         ("L", 113, 126), ("M", 127, 140), ("N", 141, 150), ("O", 151, 162), ("P", 163, 172),
         ("Q", 173, 184), ("R", 185, 196), ("S", 197, 200),
         # T201-T500 expansion (Ian, 2026-08-31, exhaustive option): framework extended BEFORE
         # any new row exists, so no T201+ row can ever be written un-validated.
         ("T", 201, 253), ("U", 254, 313), ("V", 314, 360), ("W", 361, 384), ("X", 385, 402),
         ("Y", 403, 420), ("Z", 421, 438), ("AA", 439, 454), ("AB", 455, 470), ("AC", 471, 484),
         ("AD", 485, 492), ("AE", 493, 500)]
STATUS_PCT = {"specced": 5, "walked": 25, "fixed": 60, "locked": 100}
IN_FLIGHT = {"walking", "fixing", "locking"}

# VEHICLE SEED wave (2026-09-02): ids are VM1..VM10 (not T-numbered) — the vehicle-lane
# trajectories (solo owner + fleet). The ★×16 rule: this list grows in the SAME change
# as the registry rows, so no VM row can ever be written un-validated.
NAMED_WAVES = {"VM": [f"VM{n}" for n in range(1, 11)], "VD": [f"VD{n}" for n in range(1, 16)], "VP": [f"VP{n}" for n in range(1, 201)]}


def wave_of(n: int) -> str:
    for w, a, b in WAVES:
        if a <= n <= b:
            return w
    return "?"


def check(reg: dict, header_ok: bool, matrix: dict, gate_ids: set[str]) -> list[str]:
    problems: list[str] = []
    ts = reg["trajectories"]
    ids = [t["id"] for t in ts]
    expected = [f"T{n}" for n in range(1, 501)] + [i for w in sorted(NAMED_WAVES) for i in NAMED_WAVES[w]]
    if ids != expected:
        problems.append(f"ids are not exactly T1..T500 + named waves ({'+'.join(sorted(NAMED_WAVES))}) "
                        f"in order ({len(ids)} entries)")
    for t in ts:
        m = re.match(r"^T(\d+)$", t["id"])
        if m:
            n = int(m.group(1))
            if t.get("wave") != wave_of(n):
                problems.append(f"{t['id']}: wave {t.get('wave')} != declared range {wave_of(n)}")
        else:
            _w = next((w for w, idlist in NAMED_WAVES.items() if t["id"] in idlist), None)
            if _w is None:
                problems.append(f"{t['id']}: id belongs to no declared wave (extend NAMED_WAVES in the "
                                "same change as the registry — the ★×16 rule)")
            elif t.get("wave") != _w:
                problems.append(f"{t['id']}: wave {t.get('wave')} != declared named wave {_w}")
        st, pct = t.get("status"), t.get("pct")
        if st in STATUS_PCT:
            if pct != STATUS_PCT[st]:
                problems.append(f"{t['id']}: status {st} must carry pct {STATUS_PCT[st]}, has {pct}")
        elif st in IN_FLIGHT:
            if not (t.get("basis") or "").strip() or not isinstance(pct, int) or not (0 <= pct <= 100):
                problems.append(f"{t['id']}: in-flight status {st} needs a written basis and a 0-100 pct")
        elif st == "descoped":
            # ★DESCOPED = a deliberate, transparent scope decision (2026-09-01). A trajectory that
            # describes a product WorkHive is NOT (the T455-T470 org-federation tier: parent-org
            # rollups, SSO, data residency, merge-hives, cross-org billing) is out of scope for the
            # current hive-scoped product's path to 100%. It is neither done nor failing - it is not
            # part of the program. It carries pct 0 (no progress is claimed) and is EXCLUDED from the
            # overall denominator (see main / scoreboard), so "100%" means 100% of what WorkHive IS,
            # with the deferred count reported alongside - honest, not %-gaming.
            if not (t.get("basis") or "").strip():
                problems.append(f"{t['id']}: descoped needs a written basis (why it is out of scope)")
            if pct != 0:
                problems.append(f"{t['id']}: descoped must carry pct 0 (no progress is claimed on out-of-scope work)")
        else:
            problems.append(f"{t['id']}: unknown status {st!r}")

        # ★6. THE PCT MUST MATCH WHAT THE BASIS ITSELF LAST SAID (2026-08-31). A basis is append-only:
        # a later pass often revises the number in prose ("pct -> 72") and only the PROSE gets updated,
        # leaving the field holding an older, higher value. Audited today, SIX rows had drifted and every
        # one was INFLATED - T121 field 99 vs basis 78, T147 95 vs 72, T47 95 vs 88, T78 90 vs 84,
        # T169 86 vs 80, T129 99 vs 98. Never once deflated, because nothing was checking: the number a
        # reader trusts drifts up while the narrative underneath it says otherwise. Rules 2 and 5 could
        # not see it - they check status->pct and gates, not whether a row agrees with its own account.
        _basis = " ".join((t.get("basis") or "").split())
        _said = re.findall(r"pct\s*(?:\d+\s*)?->\s*(\d+)", _basis, re.I)
        if _said and int(_said[-1]) != pct:
            problems.append(f"{t['id']}: pct field {pct} disagrees with its own basis, which last says "
                            f"pct -> {_said[-1]} (update the field, or the number flatters)")
        # ★LOCKING MEANS THE GATE IS BUILT, so it must name one (2026-08-26). The check below has
        # always held 'locked' to naming a registered gate, and said nothing about 'locking' - the
        # status whose entire definition IS "the lock exists". An audit found THREE sitting at 80-85%
        # claiming a lock that was never registered (T40, T173, T193), plus T6 at 90% and T7 at 85%
        # in the same shape - the invite-code round trip, the most load-bearing flow on the platform,
        # protected by nobody. A status that asserts protection has to be checkable, or it is just a
        # number that drifts upward.
        if st == "locking":
            if not ((t.get("artifacts") or {}).get("gates") or []):
                problems.append(f"{t['id']}: status 'locking' but names no gate - locking MEANS the "
                                f"gate is built, so either register it or drop back to 'fixing'")

        if st == "locked":
            gates = (t.get("artifacts") or {}).get("gates") or []
            if not gates:
                problems.append(f"{t['id']}: locked but names no gates")
            for g in gates:
                base = g.split("(")[0]
                if base not in gate_ids:
                    problems.append(f"{t['id']}: locked gate '{base}' is not registered in run_platform_checks")
    if not header_ok:
        problems.append("roadmap header scoreboard drifted from the registry "
                        "(run tools/update_trajectory_scoreboard.py)")
    reg_ids = set(ids)
    for c in matrix["cells"]:
        for tid in c.get("trajectories", []):
            if tid not in reg_ids:
                problems.append(f"scenario-matrix cell {c['id']} names unknown trajectory {tid}")
    return problems


def main() -> int:
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "update_trajectory_scoreboard.py"),
                        "--check"], capture_output=True, text=True)
    gate_ids = set(re.findall(r'"id":\s*"([a-z0-9\-_]+)"', CHECKS_FILE.read_text(encoding="utf-8")))
    problems = check(reg, r.returncode == 0, matrix, gate_ids)
    # the T201-T500 catalog block in the roadmap is ALSO generated from this registry — hold it to a
    # fresh regeneration too, so neither generated surface (header scoreboard, expansion catalog) can
    # be hand-edited or left stale after a registry change.
    rc = subprocess.run([sys.executable, str(ROOT / "tools" / "emit_expansion_catalog_md.py"),
                         "--check"], capture_output=True, text=True)
    if rc.returncode != 0:
        problems.append("expansion catalog block drifted from the registry "
                        "(run tools/emit_expansion_catalog_md.py)")
    from collections import Counter
    st = Counter(t["status"] for t in reg["trajectories"])
    scoped = [t for t in reg["trajectories"] if t["status"] != "descoped"]
    descoped_n = len(reg["trajectories"]) - len(scoped)
    overall = sum(t["pct"] for t in scoped) / len(scoped)
    print(f"trajectory-registry: {len(reg['trajectories'])} entries "
          + (f"({len(scoped)} in-scope + {descoped_n} descoped) " if descoped_n else "")
          + f"· overall {overall:.1f}% of in-scope · "
          + " · ".join(f"{k} {v}" for k, v in st.most_common()) + " · header "
          + ("current" if r.returncode == 0 else "DRIFTED"))
    if problems:
        for p in problems[:10]:
            print(f"  FAIL {p}")
        return 1
    print("PASS trajectory-registry — complete, pct honest, header scoreboard current, "
          "matrix refs resolve, locks gated.")
    return 0


def self_test() -> int:
    import copy
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    gate_ids = {"cv-funnel"}
    fails = []
    m1 = copy.deepcopy(reg); m1["trajectories"][5]["pct"] = 40          # specced with fake pct
    if not check(m1, True, matrix, gate_ids):
        fails.append("specced pct=40 should FAIL")
    m2 = copy.deepcopy(reg); m2["trajectories"].pop(10)                 # missing id
    if not check(m2, True, matrix, gate_ids):
        fails.append("missing trajectory should FAIL")
    if not check(reg, False, matrix, gate_ids):                          # header drift
        fails.append("header drift should FAIL")
    m3 = copy.deepcopy(reg)
    m3["trajectories"][2].update({"status": "locked", "pct": 100, "artifacts": {"gates": ["ghost-gate"]}})
    if not any("ghost-gate" in p for p in check(m3, True, matrix, gate_ids)):
        fails.append("unregistered locked gate should FAIL")
    # a status that ASSERTS a lock must be refutable, or it is just a number that drifts upward -
    # three trajectories sat at 80-85% claiming one, and nothing could say otherwise until this rule
    m5 = copy.deepcopy(reg)
    m5["trajectories"][3].update({"status": "locking", "pct": 80, "artifacts": {"gates": []}})
    if not any("names no gate" in p for p in check(m5, True, matrix, gate_ids)):
        fails.append("locking with no gate should FAIL")

    m4 = copy.deepcopy(matrix); m4["cells"][0]["trajectories"] = ["T999"]
    if not any("T999" in p for p in check(reg, True, m4, gate_ids)):
        fails.append("unknown matrix ref should FAIL")
    # ★descoped teeth: pct!=0 and empty-basis must both redden (a descoped row cannot smuggle progress)
    m6 = copy.deepcopy(reg); m6["trajectories"][6].update({"status": "descoped", "pct": 50, "basis": "x"})
    if not any("descoped must carry pct 0" in p for p in check(m6, True, matrix, gate_ids)):
        fails.append("descoped with pct!=0 should FAIL")
    m7 = copy.deepcopy(reg); m7["trajectories"][7].update({"status": "descoped", "pct": 0, "basis": ""})
    if not any("descoped needs a written basis" in p for p in check(m7, True, matrix, gate_ids)):
        fails.append("descoped with no basis should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_trajectory_registry self-test (fake-pct / missing-id / header-drift / ghost-gate / ungated-locking / bad-matrix-ref all redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
