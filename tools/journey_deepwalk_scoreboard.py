#!/usr/bin/env python3
"""
journey_deepwalk_scoreboard.py — the ANTI-DRIFT COMPASS for the exhaustive end-to-end journey walk.

Ian (2026-07-24): "journey each of my production pages end to end, because my platform is beneficial
to my users. you have to segregate first the type of journeys using phases and percentage completion,
so that you wont be lost using anti-drift." This reads journey_deepwalk_state.json and emits the
measured % completion per journey-TYPE and per-PHASE, plus the single NEXT journey to walk — so the
sweep is driven by a measured scoreboard, never by vibes (the roadmap-% = anti-drift compass pattern).

Each journey runs 5 phases: G-ground · W-walk · O-observe · H-harvest · R-resolve. A phase is
'done' (1.0), 'partial' (0.5), or 'todo' (0.0). A journey is COMPLETE only when all 5 are 'done'.

USAGE: python tools/journey_deepwalk_scoreboard.py [--json] [--next] [--selftest]
Exit 0 always (a compass, not a gate) unless --selftest fails.
"""
from __future__ import annotations
import io, json, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[1m"; C = "\033[96m"; X = "\033[0m"
ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "journey_deepwalk_state.json"
PHASES = ["G", "W", "O", "H", "R"]
SCORE = {"done": 1.0, "partial": 0.5, "todo": 0.0}


def _bar(pct: float, width: int = 24) -> str:
    fill = int(round(pct / 100 * width))
    col = G if pct >= 100 else (Y if pct >= 34 else R)
    return col + "█" * fill + X + "·" * (width - fill)


def load() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8"))


def compute(data: dict) -> dict:
    types = data["types"]
    per_type, phase_tot = {}, {p: [0.0, 0] for p in PHASES}
    j_total = j_done = 0
    for tid, t in types.items():
        js = t["journeys"]
        jsum = 0.0
        for j in js:
            jscore = sum(SCORE[j[p]] for p in PHASES) / len(PHASES)
            jsum += jscore
            if jscore >= 1.0:
                j_done += 1
            for p in PHASES:
                phase_tot[p][0] += SCORE[j[p]]; phase_tot[p][1] += 1
        j_total += len(js)
        per_type[tid] = {"title": t["title"], "n": len(js),
                         "pct": round(jsum / len(js) * 100, 1) if js else 0.0,
                         "complete": sum(1 for j in js if all(j[p] == "done" for p in PHASES))}
    overall = round(sum(pt["pct"] * pt["n"] for pt in per_type.values())
                    / max(1, sum(pt["n"] for pt in per_type.values())), 1)
    phase_pct = {p: round(phase_tot[p][0] / max(1, phase_tot[p][1]) * 100, 1) for p in PHASES}
    return {"per_type": per_type, "overall": overall, "phase_pct": phase_pct,
            "journeys_total": j_total, "journeys_complete": j_done}


def next_journey(data: dict) -> dict | None:
    """The single next journey to walk: the first not-complete journey in type order (deterministic,
    so the sweep can't drift or double-back)."""
    for tid, t in data["types"].items():
        for j in t["journeys"]:
            if not all(j[p] == "done" for p in PHASES):
                nxt = next((p for p in PHASES if j[p] != "done"), None)
                return {"type": tid, "id": j["id"], "page": j["page"], "task": j["task"], "next_phase": nxt}
    return None


def self_test() -> bool:
    ok = True
    demo = {"types": {"X": {"title": "x", "journeys": [
        {"id": "a", "page": "p", "task": "t", "G": "done", "W": "done", "O": "done", "H": "done", "R": "done"},
        {"id": "b", "page": "p", "task": "t", "G": "done", "W": "partial", "O": "todo", "H": "todo", "R": "todo"},
    ]}}}
    c = compute(demo)
    # journey a = 100%, journey b = (1+0.5+0+0+0)/5 = 30% -> type = 65%
    if c["per_type"]["X"]["pct"] != 65.0:
        print(f"{R}selftest FAIL: type pct {c['per_type']['X']['pct']} != 65.0{X}"); ok = False
    if c["journeys_complete"] != 1:
        print(f"{R}selftest FAIL: complete {c['journeys_complete']} != 1{X}"); ok = False
    nxt = next_journey(demo)
    # journey b: G=done, W=partial -> the next phase needing work is W (a partial phase is NOT finished),
    # NOT the first 'todo'. This is the discipline: finish a half-walked journey before starting a new one.
    if not nxt or nxt["id"] != "b" or nxt["next_phase"] != "W":
        print(f"{R}selftest FAIL: next {nxt} != journey b phase W{X}"); ok = False
    print((G + "selftest PASS — journey-deepwalk scoreboard math has teeth." + X) if ok else (R + "selftest FAILED." + X))
    return ok


def main() -> int:
    if "--selftest" in sys.argv:
        return 0 if self_test() else 1
    data = load()
    c = compute(data)
    if "--json" in sys.argv:
        print(json.dumps({**c, "next": next_journey(data)}, indent=2)); return 0
    if "--next" in sys.argv:
        n = next_journey(data)
        print(json.dumps(n) if n else "ALL JOURNEYS COMPLETE"); return 0
    print(f"{B}JOURNEY DEEPWALK — anti-drift compass{X}  (Ian: journey every production page end-to-end)")
    print(f"  overall {B}{c['overall']}%{X}  ·  {c['journeys_complete']}/{c['journeys_total']} journeys complete  ·  "
          + " ".join(f"{p}:{c['phase_pct'][p]:.0f}%" for p in PHASES))
    print("  phases: G-ground W-walk O-observe H-harvest R-resolve\n")
    for tid, pt in c["per_type"].items():
        print(f"  {_bar(pt['pct'])} {pt['pct']:5.1f}%  {tid:22s} {pt['complete']}/{pt['n']}  {pt['title'][:40]}")
    n = next_journey(data)
    if n:
        print(f"\n  {C}NEXT{X}: {n['id']} ({n['type']}) — {n['page']}  [phase {n['next_phase']}]\n        {n['task']}")
    else:
        print(f"\n  {G}{B}ALL JOURNEYS COMPLETE.{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
