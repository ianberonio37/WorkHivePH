#!/usr/bin/env python3
"""cube_census.py - the cube's cells, measured (Wave CX, 2026-10-26).

Ian, 2026-10-26: "we have to add more appropriate number of open trajectories to the existing trajectories roadmap, for
the U x F x A x I x UI x UX x each architectural full stack saas layers x each production pages x each public pages x
personas x journey scenarios." Decided the same day (AskUserQuestion): EVERY GATE-ADMITTED PERSONA.

THE CELL, AND WHERE EACH AXIS'S APPLICABILITY COMES FROM - nothing typed:
  pages     sublayer_inventory.page_classes(): production / founder / public (served_pages() minus LX_NON_PRODUCTION;
            edge functions are not pages - their contracts are W3-FN's)
  layers    a layer applies to a page when the inventory's sub-layer roster puts the page in it (sublayer_inventory.collect())
  personas  production/founder: a persona is admitted when the journey-paths gate accepts ITS OWN ROUTE to the page
            (_path -> role_blocked_hops + broken_hops, the readers casts() uses); a founder surface the hub offers nobody
            keeps `oversight` as its single cast (casts()' rule); public: the personas the registry already casts on
            public pages at >= PUBLIC_CAST_FLOOR rows
  pillars   U, F, I per persona (role x experience is I's own definition; U and F differ by what each role sees and may
            do); A once per (page, layer) - viewport, network and offline do not change with the cast
  UI/UX     the critic registry grades every row's cell on the 33-class rubric; per page, the classes no row on that
            page has ever graded (ufai-rubric-spec.json `class`, applicable to a page class when some page of that
            class has graded it) are the CX-UX cells

THE NUMBER IS DERIVED, NEVER TYPED (the BRP rule): every function below reads the live registry, the inventory and
the gate; seed_expansion_wave4.py --add-cube imports this module, so one place decides the size and the registry
validator derives its expected ids from the same place.

    python tools/cube_census.py            # the table (cells / EMPTY per class, walk cells)
    python tools/cube_census.py --json     # the machine population (what the seeder reads)
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "trajectory_registry.json"
CRITIC = ROOT / "critic_registry.json"
RUBRIC = ROOT / "ufai-rubric-spec.json"
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

SIGNED_IN = ("worker", "supervisor", "fleet-supervisor", "oversight", "solo-owner", "returner", "buyer", "seller",
             "new-user", "driver-worker", "adversary", "assistive-tech", "machine-client")
PUBLIC_CAST_FLOOR = 50          # a persona counts as a public cast when the registry already walks it there this often
PERSONA_PILLARS = ("U", "F", "I")
LAYER_ONLY_PILLARS = ("A",)


def _force_utf8_stdout() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def _target(r: dict):
    p = r.get("pages") or []
    return p[-1] if p else None


def registry_rows() -> list[dict]:
    return [t for t in json.loads(REGISTRY.read_text(encoding="utf-8"))["trajectories"] if t.get("status") != "descoped"]


def page_classes() -> dict:
    import sublayer_inventory as si
    return si.page_classes()


def applicable_layers(classes: dict) -> dict:
    """{page: sorted layer codes} - the inventory's own cells, so a layer applies exactly where its roster says."""
    import sublayer_inventory as si
    out: dict[str, set] = defaultdict(set)
    for c in si.collect(classes=classes):
        out[c["page"]].add(c["layer"])
    return {p: sorted(v) for p, v in out.items()}


def admitted_personas(classes: dict, rows: list[dict]) -> dict:
    """{page: [persona, ...]} - every persona whose own route the journey-paths gate accepts (production, founder),
    `oversight` alone on a founder surface the hub offers nobody, and the measured cast on public pages."""
    from check_journey_paths import broken_hops, hub_offered_and_parented, link_graph, role_blocked_hops, signed_out_only
    from seed_expansion_wave4 import _cast_of, _hub_roles, _path, _start
    roles = _hub_roles()
    outonly = signed_out_only()
    cand: dict[str, list[str]] = {}
    fixed: dict[str, list[str]] = {}
    for cls in ("production", "founder"):
        for pg in classes.get(cls, []):
            if pg in outonly:
                fixed[pg] = ["anon", "assistive-tech", "machine-client"]
            elif cls == "founder" and not roles.get(pg):
                fixed[pg] = ["oversight"]
            else:
                cand[pg] = list(SIGNED_IN) + (["anon"] if pg == "index.html" else [])
    paths = {f"{pg}|{p}": _path(_start(pg), pg, [], cast=_cast_of(p)) for pg, ps in cand.items() for p in ps}
    links = link_graph()
    offered, parented = hub_offered_and_parented()
    bad = {a for a, *_r in role_blocked_hops(paths, {k: _cast_of(k.split("|")[1]) for k in paths}, links)}
    bad |= {a for a, *_r in broken_hops(paths, offered, parented, links)}
    out = {pg: [p for p in ps if f"{pg}|{p}" not in bad] for pg, ps in cand.items()}
    out.update(fixed)
    pub = set(classes.get("public", []))
    dom = Counter(r.get("persona") for r in rows if _target(r) in pub)
    public_cast = sorted(p for p, n in dom.items() if n >= PUBLIC_CAST_FLOOR and p and p != "any")
    for pg in pub:
        out[pg] = list(public_cast)
    return out


def have_cells(rows: list[dict], pages: set) -> dict:
    """{page: {(pillar, layer, persona)}} with persona '*' meaning any persona (for the A x layer cells)."""
    have: dict[str, set] = defaultdict(set)
    for r in rows:
        p = _target(r)
        if p not in pages:
            continue
        for u in r.get("ufai") or []:
            for L in r.get("layers") or []:
                have[p].add((u, L, r.get("persona")))
                have[p].add((u, L, "*"))
    return have


def cube_cells(rows: list[dict], classes: dict, layers: dict, personas: dict) -> list[dict]:
    """Every EMPTY applicable cell: {cls, page, pillar, layer, persona|None}, class-major, page, layer, pillar, persona."""
    pages = {p for ps in classes.values() for p in ps}
    have = have_cells(rows, pages)
    out: list[dict] = []
    for cls, ps in classes.items():
        for page in ps:
            for L in layers.get(page, []):
                for u in LAYER_ONLY_PILLARS:
                    if (u, L, "*") not in have[page]:
                        out.append({"cls": cls, "page": page, "pillar": u, "layer": L, "persona": None})
                for u in PERSONA_PILLARS:
                    for c in personas.get(page, []):
                        if (u, L, c) not in have[page]:
                            out.append({"cls": cls, "page": page, "pillar": u, "layer": L, "persona": c})
    return out


def ux_cells(rows: list[dict], classes: dict) -> list[dict]:
    """(page, rubric class) cells no row on the page has ever graded - the UI x UX face."""
    spec = json.loads(RUBRIC.read_text(encoding="utf-8"))
    dimcls = {k: v.get("class") for k, v in spec.items() if k != "_meta" and isinstance(v, dict)}
    crit = {r["id"]: r for r in json.loads(CRITIC.read_text(encoding="utf-8"))["rows"]}
    graded: dict[str, set] = defaultdict(set)
    pages = {p for ps in classes.values() for p in ps}
    for r in rows:
        p = _target(r)
        c = crit.get(r["id"])
        if p in pages and c:
            for d in c.get("dims_graded") or []:
                if d in dimcls:
                    graded[p].add(dimcls[d])
    out: list[dict] = []
    for cls, ps in classes.items():
        seen = set().union(*(graded[p] for p in ps)) if ps else set()
        for page in ps:
            for k in sorted(seen):
                if k not in graded[page]:
                    out.append({"cls": cls, "page": page, "rubric_class": k})
    return out


def census() -> dict:
    rows = registry_rows()
    classes = page_classes()
    layers = applicable_layers(classes)
    personas = admitted_personas(classes, rows)
    cells = cube_cells(rows, classes, layers, personas)
    ux = ux_cells(rows, classes)
    table = {}
    for cls, ps in classes.items():
        mine = [c for c in cells if c["cls"] == cls]
        table[cls] = {
            "pages": len(ps),
            "walk_cells": sum(len(personas.get(p, [])) for p in ps),
            "persona_cells": sum(len(layers.get(p, [])) * len(PERSONA_PILLARS) * len(personas.get(p, [])) for p in ps),
            "persona_empty": sum(1 for c in mine if c["persona"]),
            "layer_cells": sum(len(layers.get(p, [])) * len(LAYER_ONLY_PILLARS) for p in ps),
            "layer_empty": sum(1 for c in mine if not c["persona"]),
            "ux_empty": sum(1 for c in ux if c["cls"] == cls),
        }
    return {"classes": classes, "layers": layers, "personas": personas, "cells": cells, "ux": ux, "table": table,
            "total_rows": len(cells), "total_ux": len(ux),
            "walk_cells": sum(v["walk_cells"] for v in table.values())}


def main() -> int:
    _force_utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="emit the machine population")
    a = ap.parse_args()
    c = census()
    if a.json:
        print(json.dumps({k: v for k, v in c.items() if k != "layers"}, indent=1, ensure_ascii=False))
        return 0
    print("\nTHE CUBE (U/F/I x layer x persona, A x layer; UI/UX = page x rubric class never graded) - measured, never typed")
    print("=" * 100)
    print(f"  {'class':<11} {'pages':>5} {'walk cells':>10} {'U/F/I cells':>12} {'EMPTY':>7} {'A cells':>8} {'EMPTY':>6} {'UX empty':>9}")
    for cls, t in c["table"].items():
        print(f"  {cls:<11} {t['pages']:>5} {t['walk_cells']:>10} {t['persona_cells']:>12} {t['persona_empty']:>7} "
              f"{t['layer_cells']:>8} {t['layer_empty']:>6} {t['ux_empty']:>9}")
    print(f"  = {c['total_rows']} cube rows + {c['total_ux']} UX rows; {c['walk_cells']} walk cells (one walk of a page as "
          f"one persona answers every layer x pillar row of that cell)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
