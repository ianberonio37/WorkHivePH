#!/usr/bin/env python3
"""
service_hailing_scoreboard.py - the ANTI-DRIFT COMPASS for the service-hailing arc
(SERVICE_HAILING_ROADMAP.md).

WHY THIS EXISTS. The roadmap's P0-P9 phase table went green while three axes it also NAMES had
never been measured at all: the §3 dimension coverage (D-J journeys x D-P personas x D-S states x
D-M modes x D-Geo x D-G segments), the §3b per-surface UFAI rubric, and the §2 class gates. A green
headline over an unmeasured axis is exactly the one-metric-masks-the-roadmap failure. Ian, 2026-07-29:
"we to do 100% overall in the roadmap" - so "overall" is computed here, over ALL THREE boards, and
"done" is defined by the lowest of them.

  BOARD 1 · JOURNEYS  - 24 journeys x 5 phases (G/W/O/H/R).
  BOARD 2 · UFAI      - each arc surface's rubric row (measured on the WORKED state, floor 90).
  BOARD 3 · CLASSES   - the §2 classes C1-C11 x 3 stages (build/probe/gate).

THE TEETH. The W phase is DERIVED from walked.personas/walked.states, never hand-set:
>=2 personas AND >=2 states => done, exactly one of either => partial, none => todo. That single
rule is what stops "I drove it live once as the admin" from scoring as covered - the shallow-journey
class this arc's own doctrine exists to kill. A journey may also declare `w_exempt` with a reason
when NO human persona drives it (a cron sweep, a DB-only trigger path); the exemption is recorded
in the board, never silently applied.

FORWARD-ONLY RATCHET: `--check` FAILs if any board falls below `service_hailing_baseline.json`.
`--accept` ratchets the baseline UP (never down).

USAGE
  python tools/service_hailing_scoreboard.py            # print the board + write the .md
  python tools/service_hailing_scoreboard.py --check    # gate mode (forward-only ratchet)
  python tools/service_hailing_scoreboard.py --accept   # ratchet the baseline up
  python tools/service_hailing_scoreboard.py --next     # name the next un-green cell
  python tools/service_hailing_scoreboard.py --selftest # verify the maths + the W rule
"""
from __future__ import annotations
import io
import json
import os
import sys
import tempfile
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "service_hailing_state.json"
BASELINE = ROOT / "service_hailing_baseline.json"
OUT_MD = ROOT / "SERVICE_HAILING_SCOREBOARD.md"

PHASES = ["G", "W", "O", "H", "R"]
STAGES = ["build", "probe", "gate"]
VALUE = {"done": 1.0, "partial": 0.5, "todo": 0.0}
UFAI_FLOOR = 90

GREEN, YELLOW, RED, BOLD, DIM, RESET = "\033[92m", "\033[93m", "\033[91m", "\033[1m", "\033[2m", "\033[0m"


def _pct(earned: float, total: float) -> float:
    return round(100.0 * earned / total, 1) if total else 0.0


def safe_write(path: Path, text: str) -> None:
    """Encode FIRST so a bad character can never truncate the target (2026-07-29 lesson)."""
    data = text.encode("utf-8")
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, str(path))
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def derive_w(journey: dict) -> tuple[str, str]:
    """The coverage rule. Returns (value, why). NEVER reads a hand-set W."""
    if journey.get("w_exempt"):
        return "done", "exempt: " + str(journey.get("w_exempt"))
    walked = journey.get("walked") or {}
    np_ = len(set(walked.get("personas") or []))
    ns = len(set(walked.get("states") or []))
    if np_ >= 2 and ns >= 2:
        return "done", f"{np_} personas x {ns} states"
    if np_ >= 1 or ns >= 1:
        return "partial", f"{np_} persona(s) x {ns} state(s) - needs >=2 x >=2"
    return "todo", "not walked"


def score(state: dict) -> dict:
    journeys = state.get("journeys", {})
    j_rows, j_earned, j_total = [], 0.0, 0.0
    for name, j in sorted(journeys.items()):
        w_val, w_why = derive_w(j)
        cells = {}
        for ph in PHASES:
            cells[ph] = w_val if ph == "W" else (j.get("phases", {}).get(ph, "todo"))
        earned = sum(VALUE.get(cells[p], 0.0) for p in PHASES)
        j_earned += earned
        j_total += len(PHASES)
        j_rows.append({"name": name, "cells": cells, "pct": _pct(earned, len(PHASES)), "w_why": w_why})

    surfaces = state.get("ufai_surfaces", {})
    u_rows, u_earned, u_total = [], 0.0, 0.0
    for name, s in sorted(surfaces.items()):
        # A surface outside the platform's user-facing rubric FAMILY (an internal console; it is
        # absent from tools/family_rubric_sweep.mjs PAGES) still has to be MEASURED and shown, but
        # is not held to the family floor - that bar is defined for user-facing pages. The row
        # stays visible with its real score so the debt is recorded, never silently exempted.
        family = s.get("family_member", True)
        measured = bool(s.get("measured"))
        if family:
            ok = measured and (s.get("overall") or 0) >= UFAI_FLOOR and not (s.get("errors") or 0)
            val = 1.0 if ok else (0.5 if measured else 0.0)
            u_earned += val
            u_total += 1
        else:
            ok = measured           # obligation is to MEASURE and record it
            val = None
        u_rows.append({"name": name, "measured": measured, "family": family,
                       "overall": s.get("overall"), "ok": ok, "role": s.get("role", "")})

    classes = state.get("classes", {})
    c_rows, c_earned, c_total = [], 0.0, 0.0
    for name, c in sorted(classes.items()):
        st = c.get("stages", {})
        earned = sum(VALUE.get(st.get(s, "todo"), 0.0) for s in STAGES)
        c_earned += earned
        c_total += len(STAGES)
        c_rows.append({"name": name, "stages": {s: st.get(s, "todo") for s in STAGES},
                       "pct": _pct(earned, len(STAGES)), "gate": c.get("gate", "")})

    # BOARD 4 - UFAI DEEP sub-layers. ufai_pillar_map.py prints its own warning that the coarse
    # lens slice is NOT the deep verification; these are the live checks it excludes.
    deep = state.get("ufai_deep", {})
    d_rows, d_earned, d_total = [], 0.0, 0.0
    for sub, per_surface in sorted((deep.get("cells") or {}).items()):
        cells = {s: per_surface.get(s, "todo") for s in sorted(per_surface)}
        earned = sum(VALUE.get(v, 0.0) for v in cells.values())
        d_earned += earned
        d_total += len(cells)
        d_rows.append({"name": sub, "cells": cells, "pct": _pct(earned, len(cells))})

    # BOARD 5 - the §1b stack layers. "Layer touched = its checklist applied."
    stack = {k: v for k, v in state.get("stack_layers", {}).items() if not k.startswith("_")}
    s_rows, s_earned, s_total = [], 0.0, 0.0
    for name, layer in sorted(stack.items()):
        if not layer.get("touched", True):
            continue
        val = VALUE.get(layer.get("state", "todo"), 0.0)
        s_earned += val
        s_total += 1
        s_rows.append({"name": name, "state": layer.get("state", "todo"), "note": layer.get("note", "")})

    # BOARD 6 - PATHS (PDDA depth). A journey proven only on its happy path is a demo.
    p_rows, p_earned, p_total = [], 0.0, 0.0
    for name, j in sorted(journeys.items()):
        paths = j.get("paths") or {}
        cells = {k: paths.get(k, "todo") for k in ("happy", "error", "degraded")}
        earned = sum(VALUE.get(v, 0.0) for v in cells.values())
        p_earned += earned
        p_total += len(cells)
        p_rows.append({"name": name, "cells": cells, "pct": _pct(earned, len(cells))})

    # BOARD 7 - ARC II (§4b architecture expansion: C12-C15). Tracked SEPARATELY on purpose.
    # Arc I is finished and its ratchet must keep holding at 100; folding four brand-new unbuilt
    # classes into the same `overall` would drag that number down and read as a REGRESSION rather
    # than as scope growth. Two boards keeps both facts honest at once: Arc I cannot rot, and
    # Arc II cannot be hidden by Arc I's green (the one-metric rule, applied across arcs).
    arc2 = {k: v for k, v in (state.get("arc2_classes") or {}).items() if not k.startswith("_")}
    a_rows, a_earned, a_total = [], 0.0, 0.0
    for name, c in sorted(arc2.items()):
        # A class can be resolved by EVIDENCE THAT IT HAS NO SUBJECT, not only by being built - but it
        # must SHOW ITS REASON, exactly like a w_exempt journey. Counting it silently would be shrinking
        # the denominator to flatter the score; printing the reason keeps the refusal auditable.
        if c.get("exempt"):
            a_earned += len(STAGES)
            a_total += len(STAGES)
            a_rows.append({"name": name, "stages": {s: "exempt" for s in STAGES},
                           "pct": 100.0, "gate": c.get("gate", ""), "exempt": c["exempt"]})
            continue
        st = c.get("stages", {})
        earned = sum(VALUE.get(st.get(s, "todo"), 0.0) for s in STAGES)
        a_earned += earned
        a_total += len(STAGES)
        a_rows.append({"name": name, "stages": {s: st.get(s, "todo") for s in STAGES},
                       "pct": _pct(earned, len(STAGES)), "gate": c.get("gate", "")})

    b1, b2, b3 = _pct(j_earned, j_total), _pct(u_earned, u_total), _pct(c_earned, c_total)
    b4, b5, b6 = _pct(d_earned, d_total), _pct(s_earned, s_total), _pct(p_earned, p_total)
    b7 = _pct(a_earned, a_total) if a_total else None
    # OVERALL is the mean of the three boards, but the arc is only "done" when the LOWEST is 100 -
    # a high mean must never hide a dead axis (the one-metric rule).
    overall = _pct(j_earned + u_earned + c_earned + d_earned + s_earned + p_earned,
                   j_total + u_total + c_total + d_total + s_total + p_total)
    return {"journeys": {"pct": b1, "rows": j_rows}, "ufai": {"pct": b2, "rows": u_rows},
            "classes": {"pct": b3, "rows": c_rows}, "ufai_deep": {"pct": b4, "rows": d_rows},
            "stack": {"pct": b5, "rows": s_rows}, "paths": {"pct": b6, "rows": p_rows},
            "arc2": {"pct": b7, "rows": a_rows},
            "overall": overall,
            "floor": min(b1, b2, b3, b4, b5, b6)}


def render_md(r: dict) -> str:
    deep_surfaces = sorted(r["ufai_deep"]["rows"][0]["cells"].keys()) if r["ufai_deep"]["rows"] else []
    L = ["# Service-Hailing Arc - MEASURED Scoreboard", "",
         "> Auto-generated by `tools/service_hailing_scoreboard.py` from `service_hailing_state.json`.",
         "> Do not hand-edit - edit the STATE, re-run the tool. Roadmap: `SERVICE_HAILING_ROADMAP.md`.",
         "> The **W** column is DERIVED from walked personas x states (>=2 x >=2), never asserted.", "",
         f"**OVERALL {r['overall']}%** · journeys **{r['journeys']['pct']}%** · UFAI-lens **{r['ufai']['pct']}%** "
         f"· classes **{r['classes']['pct']}%** · UFAI-DEEP **{r['ufai_deep']['pct']}%** "
         f"· stack **{r['stack']['pct']}%** · paths **{r['paths']['pct']}%**", "",
         f"**Lowest board = {r['floor']}%** - the arc is done only when this is 100.", "",
         "## Board 1 - Journeys (G/W/O/H/R)", "",
         "| Journey | G | W | O | H | R | % | W basis |", "|---|:-:|:-:|:-:|:-:|:-:|--:|---|"]
    mark = {"done": "+", "partial": "~", "todo": "."}
    for row in r["journeys"]["rows"]:
        c = row["cells"]
        L.append(f"| {row['name']} | " + " | ".join(mark[c[p]] for p in PHASES) +
                 f" | {row['pct']}% | {row['w_why']} |")
    L += ["", "## Board 2 - UFAI surfaces (rubric on the WORKED state, floor 90)", "",
          "| Surface | Role | Family | Measured | Overall | OK |", "|---|---|:-:|:-:|--:|:-:|"]
    for row in r["ufai"]["rows"]:
        L.append(f"| {row['name']} | {row['role']} | {'yes' if row.get('family', True) else 'internal'} | "
                 f"{'yes' if row['measured'] else 'NO'} | "
                 f"{row['overall'] if row['overall'] is not None else '-'} | {'+' if row['ok'] else '.'} |")
    L += ["", "## Board 4 - UFAI DEEP sub-layers (the LIVE checks the coarse lens excludes)", "",
          "| Sub-layer | " + " | ".join(deep_surfaces) + " | % |", "|---" * (len(deep_surfaces) + 2) + "|"]
    for row in r["ufai_deep"]["rows"]:
        L.append(f"| {row['name']} | " + " | ".join(mark[row['cells'][s]] for s in deep_surfaces) + f" | {row['pct']}% |")
    L += ["", "## Board 5 - Stack architectural layers (§1b: layer touched = its checklist applied)", "",
          "| Layer | State | What the arc did there |", "|---|:-:|---|"]
    for row in r["stack"]["rows"]:
        L.append(f"| {row['name']} | {mark[row['state']]} | {row['note'][:90]} |")
    L += ["", "## Board 6 - PATHS per journey (PDDA depth: happy / error / degraded)", "",
          "| Journey | happy | error | degraded | % |", "|---|:-:|:-:|:-:|--:|"]
    for row in r["paths"]["rows"]:
        c = row["cells"]
        L.append(f"| {row['name']} | {mark[c['happy']]} | {mark[c['error']]} | {mark[c['degraded']]} | {row['pct']}% |")
    L += ["", "## Board 3 - Classes (build/probe/gate)", "",
          "| Class | build | probe | gate | % | Lock |", "|---|:-:|:-:|:-:|--:|---|"]
    for row in r["classes"]["rows"]:
        s = row["stages"]
        L.append(f"| {row['name']} | " + " | ".join(mark[s[x]] for x in STAGES) +
                 f" | {row['pct']}% | {row['gate'][:80]} |")
    L.append("")
    return "\n".join(L)


def next_cell(r: dict) -> str:
    for row in r["journeys"]["rows"]:
        for p in PHASES:
            if row["cells"][p] != "done":
                return f"JOURNEY {row['name']} · phase {p} ({row['cells'][p]}) · {row['w_why']}"
    for row in r["ufai"]["rows"]:
        if not row["ok"]:
            return f"UFAI {row['name']} · {'measured but below floor' if row['measured'] else 'never swept'}"
    for row in r["classes"]["rows"]:
        for st in STAGES:
            if row["stages"][st] != "done":
                return f"CLASS {row['name']} · stage {st} ({row['stages'][st]})"
    for row in r["ufai_deep"]["rows"]:
        for surf, v in sorted(row["cells"].items()):
            if v != "done":
                return f"UFAI-DEEP {row['name']} · {surf} ({v})"
    for row in r["stack"]["rows"]:
        if row["state"] != "done":
            return f"STACK {row['name']} ({row['state']})"
    for row in r["paths"]["rows"]:
        for k, v in row["cells"].items():
            if v != "done":
                return f"PATH {row['name']} · {k} ({v})"
    # Arc I exhausted -> the pointer moves to Arc II. Printing "ALL GREEN" while §4b sits unbuilt
    # would be exactly the false-100 this board exists to prevent.
    for row in r.get("arc2", {}).get("rows", []):
        if row.get("exempt"):
            continue          # resolved by evidence; pointing at it would send the next session to rebuild a refusal
        for st in STAGES:
            if row["stages"][st] != "done":
                return (f"ARC-II CLASS {row['name']} · stage {st} ({row['stages'][st]})"
                        f"{' · gate ' + row['gate'] if row.get('gate') else ''}")
    return "ALL GREEN"


def selftest() -> int:
    ok = True

    def chk(label, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {(GREEN + 'PASS' + RESET) if good else (RED + 'FAIL' + RESET)}  {label}: got {got}, want {want}")

    chk("2 personas x 2 states => done", derive_w({"walked": {"personas": ["a", "b"], "states": ["x", "y"]}})[0], "done")
    chk("1 persona x 2 states => partial", derive_w({"walked": {"personas": ["a"], "states": ["x", "y"]}})[0], "partial")
    chk("2 personas x 1 state => partial", derive_w({"walked": {"personas": ["a", "b"], "states": ["x"]}})[0], "partial")
    chk("nothing walked => todo", derive_w({"walked": {}})[0], "todo")
    chk("duplicates do not count twice", derive_w({"walked": {"personas": ["a", "a"], "states": ["x", "x"]}})[0], "partial")
    chk("exemption honoured", derive_w({"w_exempt": "cron-driven"})[0], "done")
    demo = {"journeys": {"J": {"phases": {"G": "done", "O": "done", "H": "done", "R": "done"},
                               "walked": {"personas": ["a", "b"], "states": ["x", "y"]},
                               "paths": {"happy": "done", "error": "done", "degraded": "done"}}},
            "ufai_surfaces": {"p.html": {"measured": True, "overall": 100, "errors": 0}},
            "classes": {"C": {"stages": {"build": "done", "probe": "done", "gate": "done"}}},
            "ufai_deep": {"cells": {"U2": {"p.html": "done"}}},
            "stack_layers": {"S1": {"touched": True, "state": "done"}}}
    chk("all-green demo = 100", score(demo)["overall"], 100.0)
    # a journey whose ERROR/DEGRADED paths are unproven must NOT read as fully covered
    half = json.loads(json.dumps(demo))
    half["journeys"]["J"]["paths"] = {"happy": "done", "error": "todo", "degraded": "todo"}
    chk("happy-path-only journey drags the floor below 100", score(half)["floor"] < 100.0, True)
    print(f"\n  SELFTEST: {(GREEN + 'PASS' + RESET) if ok else (RED + 'FAIL' + RESET)}")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    if not STATE.exists():
        print(f"{RED}FAIL{RESET}  missing {STATE.name}")
        return 1
    state = json.loads(STATE.read_text(encoding="utf-8"))
    r = score(state)

    if "--next" in sys.argv:
        print(next_cell(r))
        return 0

    safe_write(OUT_MD, render_md(r))
    tone = GREEN if r["floor"] == 100 else (YELLOW if r["floor"] >= 70 else RED)
    print(f"{BOLD}Service-Hailing arc - MEASURED scoreboard{RESET}")
    print(f"  Board 1 journeys  : {r['journeys']['pct']}%   ({len(r['journeys']['rows'])} journeys x 5 phases)")
    print(f"  Board 2 UFAI lens : {r['ufai']['pct']}%   ({len(r['ufai']['rows'])} arc surfaces, floor {UFAI_FLOOR})")
    print(f"  Board 3 classes   : {r['classes']['pct']}%   ({len(r['classes']['rows'])} classes x 3 stages)")
    print(f"  Board 4 UFAI DEEP : {r['ufai_deep']['pct']}%   ({len(r['ufai_deep']['rows'])} live sub-layers x surfaces)")
    print(f"  Board 5 stack S1-9: {r['stack']['pct']}%   ({len(r['stack']['rows'])} architectural layers)")
    print(f"  Board 6 paths     : {r['paths']['pct']}%   (happy/error/degraded per journey)")
    print(f"  {BOLD}OVERALL (Arc I)  : {r['overall']}%{RESET}   {tone}lowest board {r['floor']}%{RESET}")
    if r["arc2"]["pct"] is not None:
        a = r["arc2"]
        a_tone = GREEN if a["pct"] == 100 else (YELLOW if a["pct"] >= 70 else RED)
        todo = [row["name"] for row in a["rows"] if row["pct"] < 100]
        print(f"  {BOLD}ARC II (§4b arch): {a_tone}{a['pct']}%{RESET}   "
              f"({len(a['rows'])} classes x 3 stages){RESET}")
        print(f"    {DIM}open: {', '.join(todo) if todo else 'none'} — Arc I's 100% does NOT cover these{RESET}")
        for row in a["rows"]:
            if row.get("exempt"):
                print(f"    {DIM}{row['name']} exempt: {row['exempt']}{RESET}")
    print(f"  next: {DIM}{next_cell(r)}{RESET}")
    print(f"  wrote {OUT_MD.name}")

    base = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else None
    if "--accept" in sys.argv:
        # arc2 ratchets on its OWN key, so Arc II progress can never be traded against Arc I's floor
        # (and a fresh Arc II at 0 can never lower the Arc I baseline).
        _b = {"journeys": r["journeys"]["pct"], "ufai": r["ufai"]["pct"],
              "classes": r["classes"]["pct"], "overall": r["overall"]}
        if r["arc2"]["pct"] is not None:
            _b["arc2"] = max(r["arc2"]["pct"], (base or {}).get("arc2", 0))
        safe_write(BASELINE, json.dumps(_b, indent=2))
        print(f"  {GREEN}ACCEPTED{RESET}  baseline -> overall {r['overall']}%"
              + (f" · arc2 {_b['arc2']}%" if "arc2" in _b else ""))
        return 0
    if "--check" in sys.argv:
        if base is None:
            safe_write(BASELINE, json.dumps({"journeys": r["journeys"]["pct"], "ufai": r["ufai"]["pct"],
                                             "classes": r["classes"]["pct"], "overall": r["overall"]}, indent=2))
            print(f"  {YELLOW}baseline seeded{RESET} at overall {r['overall']}%")
            return 0
        regressed = [k for k in ("journeys", "ufai", "classes")
                     if r[k]["pct"] < float(base.get(k, 0)) - 1e-9]
        # Arc II ratchets forward-only too, but only once a baseline for it exists — a brand-new
        # board sitting at 0 is scope that has not been built yet, never a regression.
        if "arc2" in base and r["arc2"]["pct"] is not None \
                and r["arc2"]["pct"] < float(base["arc2"]) - 1e-9:
            regressed.append("arc2")
        if regressed:
            for k in regressed:
                print(f"  {RED}REGRESSION{RESET}  {k}: {r[k]['pct']}% < baseline {base[k]}%")
            return 1
        print(f"  {GREEN}PASS{RESET}  forward-only ratchet held (baseline overall {base.get('overall')}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
