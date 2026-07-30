#!/usr/bin/env python3
"""
marketplace_deepwalk_scoreboard.py — the ANTI-DRIFT COMPASS for the Marketplace Deepwalk
Expansion arc (MARKETPLACE_DEEPWALK_EXPANSION_ROADMAP.md).

WHY THIS EXISTS (framework, not a one-off doc): a roadmap whose % is *vibed* drifts. This reads
`marketplace_deepwalk_state.json` and emits a MEASURED %-board over BOTH expansion denominators:

  BOARD 1 · JOURNEYS  — 20 journeys x 5 phases (G/W/O/H/R). done=1.0, partial=0.5, todo=0.
  BOARD 2 · CLASSES   — 10 MK dimension classes x 6 stages (harvest/define/detect/sweep/fix/gate).

"Done" is defined by BOTH boards (feedback_seed_resolved_is_not_roadmap_done) — a green headline on
one board never ends the arc.

FORWARD-ONLY RATCHET (the teeth): `--check` FAILS if either board's % falls below the accepted
baseline in `marketplace_deepwalk_baseline.json`. Progress may only rise; a regression (someone
downgrades a phase without doing the work, or a journey is dropped) breaks the build.
`--accept` ratchets the baseline UP to the current measurement (never down).

USAGE
  python tools/marketplace_deepwalk_scoreboard.py            # print the board + write the .md
  python tools/marketplace_deepwalk_scoreboard.py --check    # gate mode (forward-only ratchet)
  python tools/marketplace_deepwalk_scoreboard.py --accept   # ratchet the baseline up
  python tools/marketplace_deepwalk_scoreboard.py --selftest # verify the maths
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path

ROOT     = Path(__file__).resolve().parent.parent
STATE    = ROOT / "marketplace_deepwalk_state.json"
BASELINE = ROOT / "marketplace_deepwalk_baseline.json"
OUT_MD   = ROOT / "MARKETPLACE_DEEPWALK_SCOREBOARD.md"

PHASES = ["G", "W", "O", "H", "R"]
STAGES = ["harvest", "define", "detect", "sweep", "fix", "gate"]
VALUE  = {"done": 1.0, "partial": 0.5, "todo": 0.0}

GREEN, YELLOW, RED, BOLD, RESET = "\033[92m", "\033[93m", "\033[91m", "\033[1m", "\033[0m"
DIM = "\033[2m"


def _pct(earned: float, total: float) -> float:
    return round(100.0 * earned / total, 1) if total else 0.0


def _derive_w(j: dict) -> str:
    """The walk phase, computed from the evidence — plus the ROLE-PAIR rule.

    `>=2 personas AND >=2 states` was the whole rule, and Ian found what it lets through
    (2026-07-29): `J29-live-map-tracking` was walked as P-client-supervisor and P-client-worker —
    two WATCHERS, zero publishers — and read `done`. The count was satisfied while the axis that
    carries the entire feature (a provider's watchPosition publishing a position) was never once
    exercised.

    So a journey whose value IS a handoff declares its sides as `role_pair: ["publisher:P-provider",
    "watcher:P-client"]`, and every named persona must appear in `walked.personas`. Missing a side
    caps the journey at `partial` no matter how many personas were walked
    ([[feedback_two_sided_journeys_need_a_role_pair]]).
    """
    w = j.get("walked", {}) or {}
    personas = set(w.get("personas", []) or [])
    states = w.get("states", []) or []
    base = ("done" if (len(personas) >= 2 and len(states) >= 2)
            else ("partial" if (personas or states) else "todo"))
    if base != "done":
        return base
    pair = j.get("role_pair") or []
    needed = {p.split(":", 1)[1] for p in pair if ":" in p}
    if needed and not needed.issubset(personas):
        return "partial"          # both sides, or it is not a walk of this journey
    return "done"


def measure(state: dict) -> dict:
    """Compute both boards. Pure function of the state -> unit-testable."""
    journeys = state.get("journeys", {})
    classes  = state.get("dim_classes", {})

    # BOARD 1 — journeys, rolled up per TYPE and per PHASE
    per_type: dict[str, list[float]] = {}
    per_phase: dict[str, list[float]] = {p: [] for p in PHASES}
    j_earned = j_total = 0.0
    j_rows = []
    for jid, j in sorted(journeys.items()):
        ph = dict(j.get("phases", {}))
        # W IS DERIVED, NEVER TRUSTED. The service-hailing board already computes it from
        # walked.personas/states — this board read whatever was typed in, so a hand-set "W: done"
        # could outrank the evidence. Deriving it here makes the two boards score the same way, which
        # is what lets the 33 SJ journeys be absorbed without inventing or losing a phase.
        ph["W"] = _derive_w(j)
        vals = [VALUE.get(ph.get(p, "todo"), 0.0) for p in PHASES]
        earned, total = sum(vals), float(len(PHASES))
        j_earned += earned
        j_total  += total
        per_type.setdefault(j.get("type", "?"), []).append(_pct(earned, total))
        for p, v in zip(PHASES, vals):
            per_phase[p].append(v)
        # W is derived above, so "shallow" now means the STATE FILE still claims a walk the evidence
        # does not support — a disagreement worth printing rather than silently overriding.
        w = j.get("walked", {}) or {}
        shallow = (j.get("phases", {}).get("W") == "done" and ph["W"] != "done")
        pair = j.get("role_pair") or []
        missing_side = [p for p in pair
                        if ":" in p and p.split(":", 1)[1] not in set(w.get("personas", []) or [])]
        j_rows.append({"id": jid, "type": j.get("type", "?"), "pct": _pct(earned, total),
                       "phases": {p: ph.get(p, "todo") for p in PHASES},
                       "personas": len(w.get("personas", [])), "states": len(w.get("states", [])),
                       "shallow_W": shallow, "missing_side": missing_side})

    # BOARD 2 — MK classes
    c_earned = c_total = 0.0
    c_rows = []
    for cid, c in sorted(classes.items()):
        st = c.get("stages", {})
        vals = [VALUE.get(st.get(s, "todo"), 0.0) for s in STAGES]
        earned, total = sum(vals), float(len(STAGES))
        c_earned += earned
        c_total  += total
        c_rows.append({"id": cid, "pct": _pct(earned, total),
                       "stages": {s: st.get(s, "todo") for s in STAGES}})

    return {
        "journey_pct": _pct(j_earned, j_total),
        "class_pct":   _pct(c_earned, c_total),
        "overall_pct": _pct(j_earned + c_earned, j_total + c_total),
        "per_type":    {t: round(sum(v) / len(v), 1) for t, v in sorted(per_type.items())},
        "per_phase":   {p: _pct(sum(v), float(len(v))) for p, v in per_phase.items()},
        "journeys":    j_rows,
        "classes":     c_rows,
        "counts":      {"journeys": len(journeys), "classes": len(classes)},
        "shallow_W":   [r["id"] for r in j_rows if r["shallow_W"]],
        # A journey that names its sides and walked only one of them. Printed, never folded into a %:
        # it is the exact hole Ian found, and a number would hide which side is missing.
        "missing_side": {r["id"]: r["missing_side"] for r in j_rows if r["missing_side"]},
        # Banked so a later journey-board DROP can PROVE it was scope growth (33 SJ journeys arriving)
        # rather than a walk that stopped holding.
        "journey_earned": round(j_earned, 2),
    }


def _mark(v: str) -> str:
    return {"done": "✅", "partial": "🟡", "todo": "⬜"}.get(v, "⬜")


def write_md(m: dict) -> None:
    L = ["# Marketplace Deepwalk — MEASURED Scoreboard",
         "",
         "> Auto-generated by `tools/marketplace_deepwalk_scoreboard.py` from",
         "> `marketplace_deepwalk_state.json`. Do not hand-edit — edit the STATE, re-run the tool.",
         "> Companion roadmap: `MARKETPLACE_DEEPWALK_EXPANSION_ROADMAP.md`.",
         "",
         f"**OVERALL {m['overall_pct']}%** · journeys **{m['journey_pct']}%** "
         f"({m['counts']['journeys']}) · MK classes **{m['class_pct']}%** ({m['counts']['classes']})",
         "",
         "## Board 1 — Journeys (G/W/O/H/R)", "",
         "| Journey | Type | G | W | O | H | R | personas×states | % |",
         "|---|---|:-:|:-:|:-:|:-:|:-:|:-:|--:|"]
    for r in m["journeys"]:
        ph = " | ".join(_mark(r["phases"][p]) for p in PHASES)
        flag = " ⚠shallow" if r["shallow_W"] else ""
        L.append(f"| {r['id']} | {r['type']} | {ph} | {r['personas']}×{r['states']}{flag} | {r['pct']}% |")
    L += ["", "**Per phase:** " + " · ".join(f"{p} {m['per_phase'][p]}%" for p in PHASES),
          "", "**Per type:** " + " · ".join(f"{t} {v}%" for t, v in m["per_type"].items()),
          "", "## Board 2 — New MK dimension classes", "",
          "| Class | " + " | ".join(s for s in STAGES) + " | % |",
          "|---|" + ":-:|" * len(STAGES) + "--:|"]
    for r in m["classes"]:
        L.append(f"| {r['id']} | " + " | ".join(_mark(r["stages"][s]) for s in STAGES) + f" | {r['pct']}% |")
    if m["shallow_W"]:
        L += ["", "> ⚠ **Shallow W flagged** (marked done but <2 personas or <2 states): "
                  + ", ".join(m["shallow_W"])]
    L += ["", "_Anti-drift: at ANY 'what next / is this done?' doubt → read this board + the roadmap §7 NEXT._", ""]
    OUT_MD.write_text("\n".join(L), encoding="utf-8")


def selftest() -> int:
    """Verify the maths on a synthetic state — the newest instrument is the least trustworthy."""
    fake = {
        "journeys": {
            "Ja": {"type": "T8", "phases": {"G": "done", "W": "done", "O": "done", "H": "done", "R": "done"},
                   "walked": {"personas": ["a", "b"], "states": ["x", "y"]}},          # 100%, not shallow
            "Jb": {"type": "T8", "phases": {"G": "partial", "W": "todo", "O": "todo", "H": "todo", "R": "todo"},
                   "walked": {}},                                                       # 10%
            "Jc": {"type": "T1", "phases": {"G": "done", "W": "done", "O": "todo", "H": "todo", "R": "todo"},
                   "walked": {"personas": ["a"], "states": ["x"]}},                     # 40%, SHALLOW W
        },
        "dim_classes": {
            "MKa": {"stages": {"harvest": "done", "define": "done", "detect": "done",
                               "sweep": "done", "fix": "done", "gate": "done"}},        # 100%
            "MKb": {"stages": {"harvest": "partial"}},                                  # 0.5/6 = 8.3%
        },
    }
    m = measure(fake)
    ok = True

    def chk(label, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {GREEN + 'PASS' + RESET if good else RED + 'FAIL' + RESET}  {label}: got {got}, want {want}")

    # journeys: (5 + 0.5 + 2) / 15 = 7.5/15 = 50.0
    # 46.7, not the 50.0 this asserted before W became DERIVED. `Jc` is the fixture's deliberately
    # SHALLOW journey — `W: done` with one persona and one state — and the old expectation encoded
    # its false green: 5.0 (Ja) + 0.5 (Jb) + 1.5 (Jc: G done + W partial) = 7.0 / 15. The number moved
    # because the rule stopped trusting a typed-in phase, which is the fix, not a regression.
    chk("journey_pct", m["journey_pct"], 46.7)
    # classes: (6 + 0.5) / 12 = 6.5/12 = 54.2
    chk("class_pct", m["class_pct"], 54.2)
    # overall: 14/27 = 51.9
    chk("overall_pct", m["overall_pct"], 50.0)   # (7.0 + 6.5) / (15 + 12)
    chk("shallow_W detected", m["shallow_W"], ["Jc"])

    # ROLE-PAIR teeth. Two personas and two states satisfy the count, so the OLD rule called this a
    # completed walk — and both personas are on the SAME SIDE of a two-sided journey. This is the
    # exact hole Ian found on the live map (2026-07-29).
    pair_state = {"journeys": {"Jp": {
        "type": "T8", "phases": {"G": "done", "W": "done", "O": "done", "H": "done", "R": "done"},
        "role_pair": ["publisher:P-provider", "watcher:P-client"],
        "walked": {"personas": ["P-client", "P-client-worker"], "states": ["x", "y"]}}},
        "dim_classes": {}}
    pm = measure(pair_state)
    chk("role-pair: two watchers do NOT complete a two-sided walk", pm["journeys"][0]["phases"]["W"], "partial")
    chk("role-pair: the missing side is NAMED", pm["missing_side"].get("Jp"), ["publisher:P-provider"])

    both = json.loads(json.dumps(pair_state))
    both["journeys"]["Jp"]["walked"]["personas"] = ["P-provider", "P-client"]
    chk("role-pair: one persona per side completes it", measure(both)["journeys"][0]["phases"]["W"], "done")
    chk("per_type T8", m["per_type"]["T8"], 55.0)     # (100 + 10)/2
    chk("per_phase G", m["per_phase"]["G"], 83.3)     # (1 + 0.5 + 1)/3
    print(f"\n  SELFTEST: {GREEN + 'PASS' + RESET if ok else RED + 'FAIL' + RESET}")
    return 0 if ok else 1


BANK = ROOT / "marketplace_test_bank.json"
LAYERS = ["S1-ui", "S2-pwa", "S3-data", "S4-db", "S5-edge",
          "S6-realtime", "S7-ai", "S8-gates", "S9-knowledge"]


ROADMAP = ROOT / "MARKETPLACE_DEEPWALK_EXPANSION_ROADMAP.md"
PILLAR_MAP = ROOT / "ufai_pillar_map.json"


def declared_dimensions() -> tuple[set[str], set[str]]:
    """(MK classes, UFAI classes) — read from the documents that DEFINE them, never enumerated here.

    The MK classes come from the roadmap's own §-table rows (`| **MK7 · …`), so adding an MK11 there
    grows the denominator by itself and the board reports the new gap instead of silently not having
    it. The UFAI classes come from the rubric file the platform already grades against, so the two
    families cannot drift apart.
    """
    # THE STATE FILE IS THE REGISTRY, NOT THE ROADMAP PROSE. `dim_classes` is what Board 2 already
    # scores, and it tracks THIRTEEN classes — MK11-error-remedy-actionability,
    # MK12-post-action-coherence and MK13-reachable-capability were added after the roadmap's §-table
    # was written, and that table still stops at MK10. Deriving from the prose looked like a fix and
    # was a NEW bug: it would have dropped three live classes out of the denominator and reported
    # 100% while three were unasserted — a short denominator, the exact failure being guarded against.
    # Read the registry the other board already uses; fall back to the prose only if it is missing.
    mk: set[str] = set()
    if STATE.exists():
        try:
            classes = json.loads(STATE.read_text(encoding="utf-8")).get("dim_classes") or {}
            mk = {k.split("-", 1)[0] for k in classes}
        except Exception:
            mk = set()
    if not mk and ROADMAP.exists():
        mk = set(re.findall(r"^\|\s*\*\*(MK\d+)\s*·", ROADMAP.read_text(encoding="utf-8"), re.M))
    # The UFAI classes come from ufai_pillar_map.json, the artifact the platform's OWN UFAI instrument
    # produces — its per-page dim keys ARE the class list (`U2_operability`, `A1_responsive`, …). The
    # rubric .js was tried first and rejected: its classes appear as bare object keys and as comment
    # markers, so a regex over it returns a plausible-looking set that nothing guarantees is the real
    # one. A denominator scraped from prose is exactly the kind of number this arc exists to stop.
    ufai: set[str] = set()
    if PILLAR_MAP.exists():
        try:
            pages = json.loads(PILLAR_MAP.read_text(encoding="utf-8")).get("pages") or {}
            first = next(iter(pages.values()), None)
            if isinstance(first, dict):
                ufai = {k.split("_")[0] for k in first if re.fullmatch(r"[A-Z]\d+_\w+", k)}
        except Exception:
            ufai = set()
    return mk, ufai


def measure_bank() -> dict | None:
    """The §10 test-bank boards. Absent bank -> None (the two original boards stand alone).

    Three questions the journey/class boards cannot answer:
      transition  is every guarded state change proven, FOR and AGAINST? (the derived denominator)
      layer       ARCHITECTURE - which stack layer does no passing cell exercise?
      dimension   DESIGN - which failure-class does no cell assert?
    A cell counts only when `covered` (a registered gate locks it, named) or `banked` (a runner
    executes it). `owed` is the honest work list and is never counted.
    """
    if not BANK.exists():
        return None
    tests = json.loads(BANK.read_text(encoding="utf-8")).get("tests", [])
    if not tests:
        return None
    done = [t for t in tests if t.get("status") in ("covered", "banked")]
    layers_hit = {l for t in done for l in (t.get("layers") or [])}
    dims_hit = {d for t in done for d in (t.get("dims") or [])}
    mk_classes, ufai_classes = declared_dimensions()
    quarantined = [t["id"] for t in tests if t.get("status") == "quarantined"]
    superseded = [t["id"] for t in tests if t.get("superseded_by")]
    lanes: dict[str, int] = {}
    for t in tests:
        lanes[t.get("lane", "?")] = lanes.get(t.get("lane", "?"), 0) + 1
    return {
        "transition_pct": _pct(len(done), len(tests)),
        "layer_pct": _pct(len(layers_hit & set(LAYERS)), len(LAYERS)),
        # DERIVED, not a floor. This read `max(len(dims_hit), 13)` — a hardcoded "MK1-MK13" that
        # invented three classes the roadmap never defines (its table names MK1-MK10 and stops). An
        # invented denominator is the mirror of a short one: the short one manufactures a false 100,
        # the invented one hides that a family is COMPLETE while quietly never measuring the OTHER
        # family the board's own label promises. Both are answered the same way — compute the
        # denominator from the source that defines it ([[feedback_short_denominator_is_a_false_100]]).
        "dimension_pct": _pct(len(dims_hit & mk_classes), len(mk_classes)) if mk_classes else 0.0,
        "mk_missing": sorted(mk_classes - dims_hit),
        "ufai_pct": _pct(len(dims_hit & ufai_classes), len(ufai_classes)) if ufai_classes else None,
        "ufai_total": len(ufai_classes),
        "counts": {"obligations": len(tests), "done": len(done),
                   "owed": len(tests) - len(done) - len(quarantined)},
        "layers_missing": [l for l in LAYERS if l not in layers_hit],
        # A layer at 0% must name WHAT would move it, or the board is a complaint rather than a work
        # list (Ian 2026-07-29: "sprout from that layers"). Each untested layer maps to the owed cell
        # sprouted for it, with the role-pair that cell requires.
        "layer_owed": {l: [{"id": t["id"], "role_pair": t.get("role_pair")}
                           for t in tests
                           if l in (t.get("layers") or []) and t.get("status") == "owed"]
                       for l in LAYERS if l not in layers_hit},
        "quarantined": quarantined,
        "superseded": superseded,
        "lanes": lanes,
    }


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    if not STATE.exists():
        print(f"{RED}FAIL{RESET}  missing {STATE.name}")
        return 1
    state = json.loads(STATE.read_text(encoding="utf-8"))
    m = measure(state)
    write_md(m)

    base = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {}
    b_j, b_c = base.get("journey_pct", 0.0), base.get("class_pct", 0.0)

    print(f"{BOLD}Marketplace Deepwalk — anti-drift %-board{RESET}")
    print(f"  journeys : {m['journey_pct']}%  ({m['counts']['journeys']} journeys x {len(PHASES)} phases)   baseline {b_j}%")
    print(f"  classes  : {m['class_pct']}%  ({m['counts']['classes']} MK classes x {len(STAGES)} stages)   baseline {b_c}%")
    print(f"  OVERALL  : {m['overall_pct']}%")
    print("  per phase: " + " · ".join(f"{p} {m['per_phase'][p]}%" for p in PHASES))
    if m["shallow_W"]:
        print(f"  {YELLOW}shallow W{RESET} (<2 personas or <2 states): {', '.join(m['shallow_W'])}")

    bank = measure_bank()
    if bank:
        b_t = base.get("transition_pct", 0.0)
        c = bank["counts"]
        print(f"\n  {BOLD}§10 TEST BANK{RESET}  {DIM}(derived denominator — a new guarded transition "
              f"grows it by itself){RESET}")
        print(f"  transition : {bank['transition_pct']}%  ({c['done']}/{c['obligations']} obligations, "
              f"{c['owed']} owed)   baseline {b_t}%")
        print(f"  layer      : {bank['layer_pct']}%  {DIM}architecture — untested: "
              f"{', '.join(bank['layers_missing']) or 'none'}{RESET}")
        for lyr, owed in (bank.get("layer_owed") or {}).items():
            if not owed:
                print(f"      {YELLOW}{lyr}{RESET} {DIM}— nothing owed yet: sprout a journey for it{RESET}")
                continue
            for o in owed[:1]:
                pair = " x ".join(o["role_pair"]) if o.get("role_pair") else "single-actor"
                print(f"      {DIM}{lyr:<14} <- {o['id']}  [{pair}]{RESET}")
        miss = bank.get("mk_missing") or []
        print(f"  dimension  : {bank['dimension_pct']}%  {DIM}design — MK classes, derived from the "
              f"state file's dim_classes registry{RESET}"
              + (f"  {YELLOW}unasserted: {', '.join(miss)}{RESET}" if miss else ""))
        if bank.get("ufai_pct") is not None:
            # Printed SEPARATELY and never folded into the MK number. The bank asserts MK classes; the
            # UFAI families are graded by their own instrument (service-ufai-deep / ufai_pillar_map),
            # and blending two denominators is how one green axis hides an untouched one
            # ([[feedback_phase_table_is_one_axis_build_the_compass]]).
            print(f"  ufai       : {bank['ufai_pct']}%  {DIM}of {bank['ufai_total']} UFAI classes "
                  f"asserted by a BANK cell (the UFAI instrument grades these separately){RESET}")
        print(f"  lanes      : " + " · ".join(f"{k} {v}" for k, v in sorted(bank["lanes"].items())))
        # Never folded into a %: debt with a name beats debt hidden in a denominator.
        if bank["quarantined"]:
            print(f"  {YELLOW}quarantined{RESET} ({len(bank['quarantined'])}, excluded from the %): "
                  f"{', '.join(bank['quarantined'][:5])}")
        if bank["superseded"]:
            print(f"  {DIM}superseded ({len(bank['superseded'])}): a guard changed; cells retired with "
                  f"a reason, never deleted{RESET}")
    print(f"  -> {OUT_MD.name}")

    if "--accept" in sys.argv:
        # A RATCHET ONLY TURNS ONE WAY (2026-07-28, found on the project-manager board). --accept
        # used to write the measurement in EITHER direction and return before the --check branch
        # below, so it could silently LOWER the floor while printing "ACCEPTED" — and the baseline
        # this very call writes claims "a FALL below these numbers FAILs the gate", which was not
        # true through this path. On the project-manager board that let a mis-typed state value
        # bank a lower floor after five phases scored 0.
        _pairs = [("journeys", b_j, m["journey_pct"]), ("classes", b_c, m["class_pct"])]
        if bank:
            _pairs.append(("transition", base.get("transition_pct", 0.0), bank["transition_pct"]))
        _dropped = [(n, b, c) for n, b, c in _pairs if c < b]

        # SCOPE GROWTH IS NOT A REGRESSION — but it must PROVE itself, not just claim it.
        # The bank's % falls whenever obligations are added (a migration adds a guarded transition, or
        # a layer sprouts a journey). Refusing that outright would block honest expansion; accepting it
        # silently would let a real regression hide behind "we added scope". So a transition-board drop
        # is allowed ONLY when the denominator demonstrably GREW, and the numerator did not shrink.
        # The JOURNEY board grows the same way: the 33 SJ service journeys are net-new scope, and
        # absorbing them drops a 100% board to whatever their phases actually earn. Same proof bar as
        # the transition board — the COUNT must have grown and the earned points must not have fallen,
        # so "we added journeys" can never be the cover story for a walk that stopped holding.
        if _dropped and all(n == "journeys" for n, _, _ in _dropped):
            prev_n = base.get("journey_count")
            prev_e = base.get("journey_earned")
            grew = prev_n is not None and m["counts"]["journeys"] > prev_n
            kept = prev_e is None or m["journey_earned"] >= prev_e
            if grew and kept:
                print(f"  {YELLOW}SCOPE GREW{RESET}  journeys {prev_n} -> {m['counts']['journeys']} "
                      f"while earned phase-points held at {m['journey_earned']} (>= {prev_e}). The % "
                      f"fell because the DENOMINATOR grew — re-baselining down deliberately.")
                _dropped = []
        if _dropped and bank and all(n == "transition" for n, _, _ in _dropped):
            prev_total = base.get("transition_obligations")
            prev_done = base.get("transition_done")
            grew = prev_total is not None and bank["counts"]["obligations"] > prev_total
            kept = prev_done is None or bank["counts"]["done"] >= prev_done
            if grew and kept:
                print(f"  {YELLOW}SCOPE GREW{RESET}  obligations {prev_total} -> "
                      f"{bank['counts']['obligations']} while done held at {bank['counts']['done']} "
                      f"(>= {prev_done}). The % fell because the DENOMINATOR grew, which is the board "
                      f"working — re-baselining down deliberately.")
                _dropped = []
        if _dropped:
            for _n, _b, _c in _dropped:
                print(f"  {RED}ACCEPT REFUSED{RESET}  {_n} {_b}% -> {_c}% is a DROP; the floor only "
                      f"moves up. Fix the state (or the walk) rather than re-baselining down.")
            return 1
        BASELINE.write_text(json.dumps(
            {"journey_pct": m["journey_pct"], "class_pct": m["class_pct"],
             "overall_pct": m["overall_pct"],
             # Banked for the same reason as the transition counters: without them a later journey
             # drop cannot PROVE it was scope growth rather than a walk that stopped holding.
             "journey_count": m["counts"]["journeys"], "journey_earned": m["journey_earned"],
             # obligations/done are banked too: without them a later drop cannot PROVE it was scope
             # growth rather than a cell that stopped passing.
             **({"transition_pct": bank["transition_pct"],
                 "transition_obligations": bank["counts"]["obligations"],
                 "transition_done": bank["counts"]["done"]} if bank else {}),
             "_doc": "Forward-only ratchet baseline for the marketplace deepwalk expansion arc. "
                     "Raised by --accept; a FALL below these numbers FAILs the gate."},
            indent=2), encoding="utf-8")
        print(f"  {GREEN}ACCEPTED{RESET}  baseline -> journeys {m['journey_pct']}% / classes {m['class_pct']}%")
        return 0

    if "--check" in sys.argv:
        drops = []
        if m["journey_pct"] < b_j: drops.append(f"journeys {m['journey_pct']}% < baseline {b_j}%")
        if m["class_pct"]  < b_c: drops.append(f"classes {m['class_pct']}% < baseline {b_c}%")
        # A baseline that RECORDS a board but never CHECKS it is decoration - the board would drift
        # down while the gate printed PASS, which is the false-green class this session kept digging
        # out. If --accept banked transition_pct, --check enforces it.
        b_t = base.get("transition_pct")
        if bank and b_t is not None and bank["transition_pct"] < b_t:
            drops.append(f"test-bank transitions {bank['transition_pct']}% < baseline {b_t}% "
                         f"(a cell stopped passing, or its guard changed — re-derive before re-accepting)")
        if drops:
            print(f"  {RED}FAIL{RESET}  forward-only ratchet regressed: " + "; ".join(drops))
            return 1
        held = f"journeys >= {b_j}%, classes >= {b_c}%"
        if bank and b_t is not None:
            held += f", test-bank >= {b_t}%"
        print(f"  {GREEN}PASS{RESET}  forward-only ratchet holds ({held})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
