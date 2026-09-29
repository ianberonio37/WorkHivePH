#!/usr/bin/env python3
"""validate_trajectory_registry.py — the 500-trajectory program cannot overstate itself.

Checks (each one an anti-drift rule Ian asked for or a lesson already paid for):
  1. COMPLETE — ids are exactly T1..T500 + every declared named wave (VD/VM/VP, and the
     2026-09-05 second program P1..P500 whose wave sizes are IMPORTED from its seeder, never
     re-typed), in program order; waves match the declared ranges.
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

import glob
import io
import json
import os
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

# ★SECOND PROGRAM P1-P500 (2026-09-05) — the P-A..P-L waves. The ★×16 rule again: the wave
# sizes are NOT re-typed here (a second copy is a second thing to drift). They are IMPORTED from
# the one place that declares them, tools/seed_p_program_catalog.py, so the seeder and the gate
# cannot disagree about how big a wave is — the seeder's WAVES list is the single source of truth
# for the id ranges, and this file derives its expected ids from it.
_P_IMPORT_ERROR = None
try:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from seed_p_program_catalog import WAVES as _P_WAVES        # [(wave, name, size), ...]
    _n = 0
    for _w, _nm, _sz in _P_WAVES:
        NAMED_WAVES[_w] = [f"P{i}" for i in range(_n + 1, _n + _sz + 1)]
        _n += _sz
    P_PROGRAM_TOTAL = _n
except Exception as _e:                                          # seeder missing -> fail loudly
    P_PROGRAM_TOTAL = 0
    _P_IMPORT_ERROR = _e

# ★LAYER-UX WAVE LX1.. (2026-09-06) — the expansion that brings every thin full-stack layer to the
# 90-row target, asking what a PERSON FEELS when that layer misbehaves. The ★×16 rule for the third
# time: the size is not re-typed here either. tools/seed_layer_ux_wave.py's plan() is the one place
# that decides how many rows the wave has (lenses x the surfaces each lens applies to), so the gate
# derives its expected ids from that function and the two can never disagree about the wave's size.
_LX_IMPORT_ERROR = None
try:
    from seed_layer_ux_wave import plan as _lx_plan
    _lx_rows = _lx_plan()
    LX_PROGRAM_TOTAL = len(_lx_rows)
    # The wave code carries the LAYER (LX-CI, LX-L, ...) so a row says which layer it serves without
    # a lookup. plan() emits them layer-major, so each sub-wave owns a contiguous id range; deriving
    # the ranges from the same function keeps the gate exact per sub-wave rather than per prefix.
    for _i, _r in enumerate(_lx_rows, start=1):
        NAMED_WAVES.setdefault(_r["wave"], []).append(f"LX{_i}")
except Exception as _e:                                          # seeder missing -> fail loudly
    LX_PROGRAM_TOTAL = 0
    _LX_IMPORT_ERROR = _e

# ★LX-FN (2026-09-07): the 18 edge functions and 1 learn article the program had never named at all -
# the last of what "uncharted" meant at the surface level. Its own wave rather than folded into the
# layer lenses, because these are not a lens applied across surfaces, they ARE the surfaces. The ★×16
# rule a fourth time: tools/seed_layer_fn_wave.py declares the list, and the ids are derived from it.
try:
    from seed_layer_fn_wave import plan as _lxfn_plan, WAVE as _LXFN_WAVE
    _lxfn_rows = _lxfn_plan()
    _base = LX_PROGRAM_TOTAL
    NAMED_WAVES[_LXFN_WAVE] = [f"LX{_base + _i}" for _i in range(1, len(_lxfn_rows) + 1)]
    LX_PROGRAM_TOTAL = _base + len(_lxfn_rows)
except Exception as _e:
    _LX_IMPORT_ERROR = _LX_IMPORT_ERROR or _e

# ★EXPANSION WAVE 2, EX1.. (2026-09-07) — eight waves seeded as one change (persona x device x entry
# cells, Tagalog-first, the per-page floor, hostile personas, AI trust, recovery, shift boundaries,
# accessibility personas), every row declaring the UFAI dimension it improves. The ★×16 rule a fifth
# time: tools/seed_expansion_wave.py's plan() is the one place that decides the wave's size - its
# rosters are MEASURED at plan time (every page without a _t() call, every rostered destructive
# control, every page under the floor) - and this gate derives its expected ids from that function.
# plan() emits wave-major, so each EX-* sub-wave owns a contiguous id range.
_EX_IMPORT_ERROR = None
try:
    from seed_expansion_wave import plan as _ex_plan
    _ex_rows = _ex_plan()
    EX_PROGRAM_TOTAL = len(_ex_rows)
    for _i, _r in enumerate(_ex_rows, start=1):
        NAMED_WAVES.setdefault(_r["wave"], []).append(f"EX{_i}")
except Exception as _e:                                          # seeder missing -> fail loudly
    EX_PROGRAM_TOTAL = 0
    _EX_IMPORT_ERROR = _e

# The registry's named-wave block is in PROGRAM order (the order the waves landed), not
# alphabetical — plain sorted() would file the 2026-09-05 P waves ahead of the 2026-09-02 vehicle
# waves and redden a correct registry.
NAMED_WAVE_ORDER = (["VD", "VM", "VP"] + [w for w, _, _ in _P_WAVES]) if P_PROGRAM_TOTAL else ["VD", "VM", "VP"]
# ...and the LAYER-UX wave landed after the P program, so its sub-waves come last, in the order
# seed_layer_ux_wave.py emits them (thinnest layer first). Same derivation, no second list to drift.
if LX_PROGRAM_TOTAL:
    _seen_lx = []
    for _r in _lx_rows:
        if _r["wave"] not in _seen_lx:
            _seen_lx.append(_r["wave"])
    NAMED_WAVE_ORDER = NAMED_WAVE_ORDER + _seen_lx + [_LXFN_WAVE]
# ...and the expansion waves landed after the layer-UX wave, in the order plan() emits them.
if EX_PROGRAM_TOTAL:
    _seen_ex = []
    for _r in _ex_rows:
        if _r["wave"] not in _seen_ex:
            _seen_ex.append(_r["wave"])
    NAMED_WAVE_ORDER = NAMED_WAVE_ORDER + _seen_ex

# ★EXPANSION WAVE 3, W31.. (2026-09-07) — nine directions, the largest of them W3-JN: 32 journey
# ARCHETYPES cast in the platform's own six hives, in four tiers, every row a whole story across >=4
# pages (tier D: >=8 pages, >=5 layers, >=3 moments). The ★×16 rule a sixth time: the wave's size is
# decided in exactly one place - tools/seed_expansion_wave3.py's plan() - and this gate derives its
# expected ids from that function. plan() REPLAYS the seeded rows once any W3 row exists, because every
# deficit it measures (a learn article's missing dimensions, a page's unwalked persona cell, an empty
# page x layer cell) is closed by the rows it writes; a plan that re-measured after the write would
# hand the gate a shorter list than the registry holds.
_W3_IMPORT_ERROR = None
try:
    from seed_expansion_wave3 import plan as _w3_plan
    _w3_rows = _w3_plan()
    W3_PROGRAM_TOTAL = len(_w3_rows)
    for _i, _r in enumerate(_w3_rows, start=1):
        NAMED_WAVES.setdefault(_r["wave"], []).append(f"W3{_i}")
except Exception as _e:                                          # seeder missing -> fail loudly
    W3_PROGRAM_TOTAL = 0
    _W3_IMPORT_ERROR = _e
if W3_PROGRAM_TOTAL:
    _seen_w3 = []
    for _r in _w3_rows:
        if _r["wave"] not in _seen_w3:
            _seen_w3.append(_r["wave"])
    NAMED_WAVE_ORDER = NAMED_WAVE_ORDER + _seen_w3

# ★EXPANSION WAVE 4, W41.. (2026-09-14) — every served page x every action x every layer, lived start to
# end, x 3 axes (phone-390 en · narrow-320 en · phone-390 fil). The ★×16 rule a seventh time: the wave's
# size is decided in exactly one place - tools/seed_expansion_wave4.py's plan(), which MEASURES it (the
# substrate-verified actions per page, the pages that load nav-hub.js, the (page, layer) cells no gated
# journey has lived) - and this gate derives its expected ids from that function. plan() REPLAYS the
# seeded rows once any W4 row exists, for the same reason wave 3's does. One wave code, W4.
_W4_IMPORT_ERROR = None
try:
    from seed_expansion_wave4 import plan as _w4_plan, WAVE as _W4_WAVE
    _w4_rows = _w4_plan()
    W4_PROGRAM_TOTAL = len(_w4_rows)
    NAMED_WAVES[_W4_WAVE] = [f"W4{_i}" for _i in range(1, W4_PROGRAM_TOTAL + 1)]
except Exception as _e:                                          # seeder missing -> fail loudly
    W4_PROGRAM_TOTAL = 0
    _W4_IMPORT_ERROR = _e
if W4_PROGRAM_TOTAL:
    NAMED_WAVE_ORDER = NAMED_WAVE_ORDER + [_W4_WAVE]


def wave_of(n: int) -> str:
    for w, a, b in WAVES:
        if a <= n <= b:
            return w
    return "?"


def _load_journey_receipts() -> dict:
    """id -> (result, mtime, path) from every journey receipt, NEWEST walk winning.

    An id is often walked more than once - W349 carries a red receipt from the pre-fix walk and a
    green one from the re-walk twelve hours later. Taking the newest is what makes "fix it and
    re-walk" the way to clear a contradiction; taking any other would make a stale red permanent
    and a stale green a licence.
    """
    receipts: dict = {}
    for path in sorted(glob.glob(".tmp/full_journeys_*.json")):
        try:
            with open(path, encoding="utf-8") as fh:
                doc = json.load(fh)
            mtime = os.path.getmtime(path)
        except Exception:
            continue                      # an unreadable receipt is not evidence either way
        for r in (doc.get("results") or []):
            rid = r.get("id")
            if not rid:
                continue
            prev = receipts.get(rid)
            if prev is None or mtime >= prev[1]:
                receipts[rid] = (r, mtime, path)
    return receipts


def _receipt_reach(reg: dict) -> tuple[int, int]:
    """(locked rows a receipt can judge, locked rows in total)."""
    receipts = _load_journey_receipts()
    locked = [t for t in (reg.get("trajectories") or reg.get("rows") or [])
              if t.get("status") == "locked"]
    return sum(1 for t in locked if t.get("id") in receipts), len(locked)


def check_locked_rows_agree_with_their_receipts(reg: dict, receipts: dict | None = None) -> list[str]:
    """A row locked on a journey gate must not be contradicted by that journey's own receipt.

    ★FOUR ROWS SAT GREEN WHILE THE PROVER ON DISK CALLED THEM BAD (2026-09-10). W349, W3275, W3276
    and W3277 were `locked` at pct 100 while `.tmp/full_journeys_J26.json` recorded ok:false for each
    - all four failing the same hop, hive -> alert-hub, with no way onward at all. The registry and
    the evidence disagreed for as long as nobody put them side by side, and the headline counted all
    four as closed the entire time.

    THE HOLE IS A SECOND DOOR, not a missing rule. tools/bank_journey_walk.py is disciplined - it
    partitions the receipt into `ok` and `held` and banks only the former ("none is banked green") -
    but advance_trajectory.py --ids takes whatever ids it is handed and never opens a receipt. So the
    careful path was careful and the direct path walked straight past it. A rule enforced on one of
    two doors is a rule on neither.

    WHY THIS IS AGREEMENT AND NOT PROOF, which is the whole design of the check: .tmp/ is disposable
    by project rule, so requiring a receipt would make the check fail on a clean tree and teach people
    to delete evidence to get green - the exact inversion. It therefore judges only rows it can SEE a
    receipt for, and reports that count so the number is never mistaken for coverage. A row with no
    receipt on disk is unjudged, not innocent.
    """
    problems = []
    # receipts is injectable so the self-test can hand it a known-red one without writing to .tmp/
    receipts = _load_journey_receipts() if receipts is None else receipts
    rows = reg.get("trajectories") or reg.get("rows") or []
    for t in rows:
        if t.get("status") != "locked":
            continue
        # ★THE REACH IS PART OF THE RULE (2026-09-10, the same lesson twice in one session). The first
        # cut of this check judged only rows whose gate list literally named 'full-journeys' - EIGHT
        # rows, the ones fixed minutes earlier - while the receipts on disk carry 679 ids. It would
        # have reported clean forever and looked like a working lock. What makes a row judgeable is
        # that a prover WROTE A RECEIPT ABOUT IT, not the label its banker happened to type, so the
        # gate name is not consulted at all.
        seen = receipts.get(t.get("id"))
        if not seen:
            continue                      # unjudged: no receipt on disk to agree or disagree with
        rec, _mtime, path = seen
        # ★A GREEN RECEIPT THE BASIS NEVER MENTIONS IS A ROW THAT COUNTS AS PROSE (2026-09-10). Ten
        # rows walked by a browser sat OPEN today because live_walk_manifest classifies a row by
        # reading its BASIS for the instrument that produced it, and an append-only basis whose latest
        # entry is a CORRECTION note describes the fix without ever saying what ran. The row was right
        # and its account of itself was not - the same shape as a label that under-claims its check.
        # This fires only where a receipt actually exists, so it can never ask anyone to invent
        # evidence: it says "you have the proof, go name it".
        if rec.get("ok") and not rec.get("unbuilt"):
            _b = " ".join((t.get("basis") or "").split())
            if not re.search(r"(tools/(prove|probe)_[\w.]+|WALKED LIVE|walked live|measured live)", _b, re.I):
                problems.append(
                    f"{t['id']}: has a GREEN receipt ({path}) but its basis never names the instrument "
                    f"that produced it, so the evidence ledger reads it as 'prose' and counts it OPEN. "
                    f"Append a line naming the prover and the run - the evidence exists, the account "
                    f"of it does not")
        if rec.get("unbuilt"):
            problems.append(
                f"{t['id']}: locked on full-journeys, but {path} records the journey as UNBUILT - "
                f"a story that could not be constructed cannot have held together")
        elif not rec.get("ok"):
            why = "; ".join(rec.get("problems") or []) or "no reason recorded"
            problems.append(
                f"{t['id']}: locked on full-journeys, but its own receipt {path} says ok:false ({why}). "
                f"Fix the journey and RE-WALK, or drop the row back to walking - do not bank a red "
                f"receipt green. tools/bank_journey_walk.py holds these back; advance_trajectory.py "
                f"--ids does not, which is how this gets in")
    return problems


def check(reg: dict, header_ok: bool, matrix: dict, gate_ids: set[str]) -> list[str]:
    problems: list[str] = []
    ts = reg["trajectories"]
    ids = [t["id"] for t in ts]
    if not P_PROGRAM_TOTAL:
        problems.append("the P-program wave sizes could not be imported from "
                        f"tools/seed_p_program_catalog.py ({_P_IMPORT_ERROR!r}) — the gate cannot "
                        "validate ids it has no declaration for")
    expected = [f"T{n}" for n in range(1, 501)] + [i for w in NAMED_WAVE_ORDER for i in NAMED_WAVES[w]]
    if ids != expected:
        problems.append(f"ids are not exactly T1..T500 + named waves ({'+'.join(NAMED_WAVE_ORDER)}) "
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
    # ★THE PATH IS STORED TWICE AND ONLY ONE COPY IS READ (2026-09-10). A journey row carries its route
    # at BOTH `pages` and `journey.pages`; the seeder assigns the same list to both, so they agree the
    # day they are written and nothing keeps them agreeing afterwards. Fixing three Tier D paths by
    # hand, I patched `journey.pages`, re-walked, and got the identical failure back - because
    # prove_full_journeys.mjs reads the TOP-LEVEL `t.pages` (line ~1347). The rows then sat at 16 and 17
    # pages in the same object. Two copies of one fact is one fact and one liability.
    for t in reg.get("trajectories", []):
        j = t.get("journey") or {}
        if "pages" in j and "pages" in t and list(j["pages"]) != list(t["pages"]):
            problems.append(
                f"{t['id']}: journey.pages ({len(j['pages'])}) and pages ({len(t['pages'])}) disagree - "
                f"the prover reads the top-level one, so editing only journey.pages changes nothing")
    problems += check_locked_rows_agree_with_their_receipts(reg)
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
    # ★SAY HOW FAR THE RECEIPT CHECK CAN SEE, so a clean line is never read as full coverage. It can
    # only judge a locked row a prover actually wrote a receipt about; the rest are unjudged, not
    # innocent. The number climbs on its own as the journey wave closes.
    _judged, _locked_n = _receipt_reach(reg)
    # ★AND SAY WHAT THE REMAINDER IS, BECAUSE THE FIRST VERSION OF THIS LINE READ AS A HOLE
    # (2026-09-10). It said "16 of 1467 locked rows ... (1451 unjudged - no receipt on disk, not a
    # pass)", which sounds like 99% of the locks rest on nothing. Measured, the truth is the opposite:
    # only 16 locked rows are JOURNEY rows at all, all 16 carry a receipt, and the other 1,451 are
    # rows from waves whose provers do not write journey receipts - out of scope, not unexamined.
    # Both halves of the fraction have to be visible, or an honest scope statement is read as a
    # failure. Kin of [[feedback_metric_label_is_a_claim_add_the_missing_half]].
    _jn_locked = sum(1 for t in (reg.get("trajectories") or reg.get("rows") or [])
                     if t.get("status") == "locked" and (t.get("wave") == "W3-JN" or t.get("journey")))
    _out_of_scope = _locked_n - _jn_locked
    print(f"  receipt agreement: {_judged} of {_jn_locked} LOCKED JOURNEY rows carry a receipt to be "
          f"judged against ({_jn_locked - _judged} unjudged - no receipt on disk, not a pass); the "
          f"other {_out_of_scope} locked rows belong to waves whose provers write no journey receipt, "
          f"so this check does not reach them")
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
    # ★a locked row may not contradict its own walk receipt, and the NEWEST receipt is what counts.
    # Both directions are asserted: a red receipt must redden, and a green one must NOT - without the
    # second leg the check could simply reject everything and still look like it worked.
    m8 = copy.deepcopy(reg)
    m8["trajectories"][8].update({"status": "locked", "pct": 100,
                                  "artifacts": {"gates": ["cv-funnel"]}})
    _rid = m8["trajectories"][8]["id"]
    _red = {_rid: ({"id": _rid, "ok": False, "problems": ["self-test: hop with no way onward"]},
                   9e9, ".tmp/self-test.json")}
    if not any("ok:false" in p for p in
               check_locked_rows_agree_with_their_receipts(m8, _red)):
        fails.append("locked row with a red receipt should FAIL")
    _green = {_rid: ({"id": _rid, "ok": True, "problems": []}, 9e9, ".tmp/self-test.json")}
    # the control is about CONTRADICTION only: a green receipt must never be called a disagreement.
    # (An instrument-less basis on the same row is a different, real finding - asserted just below -
    # so this control checks the claim it is actually making rather than "no output at all".)
    if any(("ok:false" in p or "UNBUILT" in p)
           for p in check_locked_rows_agree_with_their_receipts(m8, _green)):
        fails.append("locked row with a GREEN receipt must not read as contradicted (control)")
    _unbuilt = {_rid: ({"id": _rid, "ok": False, "unbuilt": True}, 9e9, ".tmp/self-test.json")}
    if not any("UNBUILT" in p for p in
               check_locked_rows_agree_with_their_receipts(m8, _unbuilt)):
        fails.append("locked row whose journey was UNBUILT should FAIL")
    # ★a green receipt the basis never names reads as prose and counts OPEN - the row is right and its
    # account of itself is not. Both directions again: silent when the instrument IS named.
    m9 = copy.deepcopy(m8)
    m9["trajectories"][8]["basis"] = "the story held together and the effect landed. pct -> 100"
    if not any("never names the instrument" in p for p in
               check_locked_rows_agree_with_their_receipts(m9, _green)):
        fails.append("green receipt with an instrument-less basis should FAIL")
    m9["trajectories"][8]["basis"] = ("WALKED LIVE 2026-09-10 via tools/prove_full_journeys.mjs - "
                                      "the story held together. pct -> 100")
    if any("never names the instrument" in p for p in
           check_locked_rows_agree_with_their_receipts(m9, _green)):
        fails.append("a basis that DOES name its prover must not fail (control)")

    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_trajectory_registry self-test (fake-pct / missing-id / header-drift / ghost-gate / "
          "ungated-locking / bad-matrix-ref / red-receipt / unbuilt-receipt / unnamed-instrument all redden; a green receipt and a basis that names its prover both stay quiet)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
