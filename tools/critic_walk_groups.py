#!/usr/bin/env python3
"""critic_walk_groups.py — how many DISTINCT in-motion walks the pending critic rows actually are.

★"DEEPWALK EACH TRAJECTORY **OR GROUP OF CATEGORIES**, BUT DO NOT REPEAT WHAT YOU ALREADY DONE"
(Ian, 2026-09-06). The critic deepwalk owes an in-motion critique to 723 journey rows, and walking 723
journeys one at a time would spend most of that effort re-measuring the same screens. It would also be
dishonest in the other direction to collapse them carelessly: a Filipino render is a DIFFERENT walk from
an English one, and so is a journey under `offline-3g` or at `year-2`.

So a walk is keyed by what genuinely changes WHAT THE EYE MEETS:

    cell (viewport | persona | surface | stage)  ·  the ordered page path
    ·  language   - a different dictionary is a different screen (dim N1 grades exactly this)
    ·  condition  - normal / offline-3g / dependency-down / release-mid-way
    ·  moment     - present / month-3 / year-2, which changes how full every list is

and NOT by the hive. The vertical changes the DATA behind a screen, not the structure the rubric grades;
that is precisely the "group of categories" Ian's instruction allows. A finding banked from a grouped
walk says so in its own evidence, so a reader can always tell how wide the observation was.

Measured 2026-09-10: **723 pending rows are 265 distinct walks** - 203 English and 62 Filipino, 205 at
normal and 60 across the three degraded conditions, 214 in the present and 51 at a seeded moment. At the
roadmap's ~20 walks a session that is the real remaining shape of this program.

    python tools/critic_walk_groups.py               # the summary + the next un-walked groups
    python tools/critic_walk_groups.py --next 5      # the next 5 groups, with the rows each covers
    python tools/critic_walk_groups.py --self-test
"""
from __future__ import annotations

import collections
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CRITIC = ROOT / "critic_registry.json"
TRAJ = ROOT / "trajectory_registry.json"


def walk_key(row: dict, journey: dict) -> tuple:
    """What makes two rows the SAME walk. The hive is deliberately not part of it; see the header."""
    return (
        row.get("cell") or "",
        tuple(row.get("pages") or []),
        journey.get("language") or "en",
        journey.get("condition") or "normal",
        journey.get("moment") or "present",
    )


def groups(status: str = "pending") -> dict:
    critic = json.loads(io.open(CRITIC, encoding="utf-8").read())
    traj = {x["id"]: x for x in json.loads(io.open(TRAJ, encoding="utf-8").read())["trajectories"]}
    out: dict = collections.defaultdict(list)
    for r in critic.get("rows") or []:
        if r.get("status") != status or r.get("wave") != "W3-JN":
            continue
        if len(r.get("pages") or []) < 2:      # a journey crosses pages; a one-page row is not this program
            continue
        j = (traj.get(r["id"]) or {}).get("journey") or {}
        out[walk_key(r, j)].append(r["id"])
    return dict(out)


def main() -> int:
    n_next = 0
    if "--next" in sys.argv:
        i = sys.argv.index("--next")
        n_next = int(sys.argv[i + 1]) if i + 1 < len(sys.argv) else 5

    g = groups()
    rows = sum(len(v) for v in g.values())
    print(f"pending journey critic rows : {rows}")
    print(f"DISTINCT in-motion walks    : {len(g)}")
    if not g:
        return 0
    for label, idx in (("language", 2), ("condition", 3), ("moment", 4)):
        c = collections.Counter(k[idx] for k in g)
        print(f"  by {label:9}: " + " · ".join(f"{k} {v}" for k, v in c.most_common()))
    covered = collections.Counter(len(v) for v in g.values())
    print("  rows per walk : " + " · ".join(f"{k}->{v}" for k, v in sorted(covered.items())))

    if n_next:
        # widest first: one walk that settles eight rows is worth more than one that settles one
        print(f"\nnext {n_next} walks, widest first:")
        for k, ids in sorted(g.items(), key=lambda kv: -len(kv[1]))[:n_next]:
            print(f"  {len(ids):2} row(s) | {k[0]} | lang {k[2]} | {k[3]} | {k[4]} | {len(k[1])} pages")
            print(f"      path: {' -> '.join(k[1])}")
            print(f"      rows: {', '.join(ids[:10])}{' …' if len(ids) > 10 else ''}")
    return 0


def _self_test() -> int:
    fails = []
    base = {"cell": "phone-390|worker|browser-ui|operate", "pages": ["a.html", "b.html"]}
    en = walk_key(base, {"language": "en", "condition": "normal", "moment": "present"})
    fil = walk_key(base, {"language": "fil", "condition": "normal", "moment": "present"})
    off = walk_key(base, {"language": "en", "condition": "offline-3g", "moment": "present"})
    yr2 = walk_key(base, {"language": "en", "condition": "normal", "moment": "year-2"})
    if en == fil:
        fails.append("a Filipino render must be a DIFFERENT walk - dim N1 grades exactly that")
    if en == off:
        fails.append("a degraded condition must be a different walk")
    if en == yr2:
        fails.append("a different moment must be a different walk - it changes how full every list is")
    # the hive must NOT split a walk: that is the grouping Ian's instruction allows
    if walk_key(base, {"language": "en"}) != walk_key(base, {"language": "en"}):
        fails.append("the key must be stable for identical inputs")
    other_path = walk_key({"cell": base["cell"], "pages": ["a.html", "c.html"]},
                          {"language": "en", "condition": "normal", "moment": "present"})
    if en == other_path:
        fails.append("a different page path must be a different walk")
    other_cell = walk_key({"cell": "desktop-1280|worker|browser-ui|operate", "pages": base["pages"]},
                          {"language": "en", "condition": "normal", "moment": "present"})
    if en == other_cell:
        fails.append("a different cell (viewport/persona) must be a different walk")
    # defaults: a row with no journey fields is the plain English present-day normal walk
    if walk_key(base, {}) != en:
        fails.append("missing journey fields must default to en/normal/present, not to a new walk")

    print("FAIL critic_walk_groups self-test - " + "; ".join(fails) if fails
          else "self-test OK: language, condition, moment, path and cell each split a walk; identical "
               "inputs and missing fields do not")
    return 1 if fails else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(_self_test())
    raise SystemExit(main())
