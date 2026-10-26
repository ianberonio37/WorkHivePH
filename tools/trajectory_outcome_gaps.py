#!/usr/bin/env python3
"""trajectory_outcome_gaps.py - the cells the outcome waves fill, measured (Waves SE, OUT, JS; 2026-10-26).

Ian's model (2026-10-26): the five lenses (UFAI, UI/UX, the full-stack layers, the personas, the journey scenarios)
improve the person's SELF-EFFICACY and the platform's SYSTEM CHARACTERISTICS, which raise INTENTION TO USE and
SATISFACTION, which lead to better USAGE. The roadmap proved the platform correct and well designed; it could not yet
show the outcomes. These three waves add them - and this module is the ONE place that decides their size:

  SE   self-efficacy: a first-timer completes the page's primary task, and the page helped them believe they could -
       per (production page) x the four sources (Bandura: mastery, vicarious, verbal persuasion, emotional state);
       per calculator x 2 (mastery: a stranger computes unaided; vicarious: a worked example before the first input);
       per learn article x 1 (mastery: a stranger reads to the answer and reaches the tool the article names)
  OUT  outcomes as figures: per production page x 3 (use - every primary action records a feature_use; return - the
       account used the page again within 7 and 30 days; satisfaction - inferred from repeat use within 7 days, never a
       new control; Ian's decision), plus the console's three figure surfaces and the three never-typed gates
  JS   journey scenarios where they are thin: every stage degraded (archetype x condition not yet walked), the daily
       archetypes aged (x moment), the two-sided marketplace archetypes recast from the seller's side, and the seller on
       the layer floor (12 rows per layer, only on pages the gate routes a seller to)

Decided with Ian 2026-10-26: satisfaction from behaviour only; self-efficacy over product pages AND the public funnel;
every stage degraded and aged; the seller as recasts plus the layer floor.

    python tools/trajectory_outcome_gaps.py          # the table
    python tools/trajectory_outcome_gaps.py --json   # the machine population (what the seeder reads)
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
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

SOURCES = [
    ("mastery", "a person who has never used this page completes its primary action without leaving the page for help, within "
                "the page's own guidance (a fresh account, never on the page; steps counted)"),
    ("vicarious", "before the first action the page shows what a finished one looks like - a template, a sample, a peer's record, "
                  "a worked example - so the person can see it done (the empty state and the form's first paint)"),
    ("verbal persuasion", "the completed action is confirmed in words that name what was done and what it now enables (the L4 told "
                          "sentence / the success microinteraction; the onboarding step flips)"),
    ("emotional state", "the person can act without fear: the action can be undone or recovered, and its error path names a remedy "
                        "(Recently deleted / forgiveness on the page's destructive acts; validation names the fix)"),
]
OUTCOMES = [
    ("use", "every primary action on the page records a feature_use event (the L3 whUse lane), read per page per week on the console"),
    ("return", "accounts that used the page again within 7 and 30 days, computed from analytics_events page_view + feature_use by "
               "auth_uid - shown as a console figure with its period, held by a gate that it is computed from the ledger, never typed"),
    ("satisfaction", "repeat use of the same page by the same account within 7 days, stated as 'repeat use' wherever shown (never "
                     "'satisfied'); the feedback form stays the only direct voice and its Review ratings are shown per page when any exist"),
]
OUT_CONSOLE = [
    ("console: use per page per week", "founder-console's outcome card reads use per page per week through a bounded admin-only read"),
    ("console: return within 7 / 30 days", "the return figure per page, with its period and basis beside it"),
    ("console: repeat use within 7 days", "the repeat-use figure per page, labelled as repeat use"),
    ("gate: use figures from the ledger", "tools/prove_outcome_figures.py recomputes use per page through psql and compares it with the console"),
    ("gate: return figures from the ledger", "the return figures recomputed through psql equal the console's"),
    ("gate: repeat-use figures from the ledger", "the repeat-use figures recomputed through psql equal the console's"),
]
DAILY_STAGES = ("operate", "maintain")
THIN_STAGES = ("trade", "comply", "grow", "integrate")
SELLER_PAGES = ("marketplace-seller.html", "marketplace-seller-profile.html", "marketplace.html", "public-feed.html", "resume.html", "index.html")
SELLER_FLOOR = 12
TWO_SIDED = re.compile(r"\bx\b|×| and |\+", re.I)


def _force_utf8_stdout() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def _target(r: dict):
    p = r.get("pages") or []
    return p[-1] if p else None


def rows() -> list[dict]:
    import registry_io as _rio
    return [t for t in _rio.load_doc()["trajectories"] if t.get("status") != "descoped"]


def pages() -> dict:
    from seed_expansion_wave4 import served_pages
    from sublayer_inventory import casts, page_classes
    cls = page_classes()
    sp = served_pages()
    existing = rows()
    cast = casts(existing, cls)
    return {"production": list(cls["production"]), "calc": sorted(sp.get("calc") or []), "learn": sorted(p for p in (sp.get("learn") or [])
            if p != "learn/index.html"), "cast": cast}


def se_cells(existing: list[dict], pg: dict) -> list[dict]:
    from seed_expansion_wave4 import page_actions
    have = {((x.get("se") or {}).get("page"), (x.get("se") or {}).get("source")) for x in existing if (x.get("se") or {}).get("kind") == "self-efficacy"}
    out = []
    for p in pg["production"]:
        try:
            acts = page_actions(p)
        except Exception:
            acts = []
        if not acts and p not in ("index.html",):
            continue
        primary = acts[0][0] if acts else "the page's primary action"
        for src, ask in SOURCES:
            if (p, src) in have:
                continue
            out.append({"wave": "SE", "page": p, "source": src, "ask": ask, "persona": pg["cast"].get(p) or "worker", "primary": primary,
                        "fixture": "a fresh seeded member of the row's hive, never on this page before, removed after the walk"})
    for p in pg["calc"]:
        for src in ("mastery", "vicarious"):
            if (p, src) in have:
                continue
            ask = ("a stranger computes a result unaided: inputs explained, units stated, the result readable without the app" if src == "mastery"
                   else "a worked example stands before the first input - the generator's reserved block, asked of every served calculator")
            out.append({"wave": "SE", "page": p, "source": src, "ask": ask, "persona": "anon", "primary": "compute",
                        "fixture": "a fresh anonymous context"})
    for p in pg["learn"]:
        if (p, "mastery") in have:
            continue
        out.append({"wave": "SE", "page": p, "source": "mastery", "ask": "a stranger reads to the answer and reaches the tool the article names "
                    "unaided - the article IS the vicarious source", "persona": "anon", "primary": "read to the answer", "fixture": "a fresh anonymous context"})
    return out


def out_cells(existing: list[dict], pg: dict) -> list[dict]:
    have = {((x.get("out") or {}).get("page"), (x.get("out") or {}).get("outcome")) for x in existing if (x.get("out") or {}).get("kind") == "outcomes"}
    out = []
    for p in pg["production"]:
        for oc, ask in OUTCOMES:
            if (p, oc) in have:
                continue
            out.append({"wave": "OUT", "page": p, "outcome": oc, "ask": ask, "persona": pg["cast"].get(p) or "worker"})
    for name, ask in OUT_CONSOLE:
        if ("founder-console.html", name) in have:
            continue
        out.append({"wave": "OUT", "page": "founder-console.html", "outcome": name, "ask": ask, "persona": "oversight"})
    return out


def js_cells(existing: list[dict], pg: dict) -> list[dict]:
    import seed_expansion_wave3 as w3
    archetypes = {a[0]: a for a in w3.ARCHETYPES}
    conditions = [c for c, _d in w3.CONDITIONS]
    moments = [m for m, _d in w3.MOMENTS]
    walked_cond: dict = defaultdict(set)
    walked_mom: dict = defaultdict(set)
    recast_have = set()
    for t in existing:
        j = t.get("journey") or {}
        a = j.get("archetype")
        if not a or not re.match(r"^J\d+$", str(a)):
            continue
        if j.get("condition") and j.get("condition") != "normal":
            walked_cond[a].add(j["condition"])
        if j.get("moment") and j.get("moment") != "present":
            walked_mom[a].add(j["moment"])
        if (t.get("js") or {}).get("kind") == "seller-recast":
            recast_have.add((a, (t.get("js") or {}).get("vertical")))
    have_js = {((x.get("js") or {}).get("archetype"), (x.get("js") or {}).get("axis"), (x.get("js") or {}).get("value"))
               for x in existing if (x.get("js") or {}).get("kind") in ("condition", "moment")}
    out = []
    for code, a in archetypes.items():
        stage = a[1]
        if stage in DAILY_STAGES + THIN_STAGES:
            for c in conditions:
                if c in walked_cond.get(code, set()) or (code, "condition", c) in have_js:
                    continue
                out.append({"wave": "JS", "archetype": code, "axis": "condition", "value": c, "title": a[3], "stage": stage, "pages": list(a[4]),
                            "layers": list(a[5]), "ufai": list(a[6]), "persona": a[7], "pair": a[8], "entry": a[9]})
        if stage in DAILY_STAGES:
            for m in moments:
                if m in walked_mom.get(code, set()) or (code, "moment", m) in have_js:
                    continue
                out.append({"wave": "JS", "archetype": code, "axis": "moment", "value": m, "title": a[3], "stage": stage, "pages": list(a[4]),
                            "layers": list(a[5]), "ufai": list(a[6]), "persona": a[7], "pair": a[8], "entry": a[9]})
    # the seller's side of the two-sided marketplace archetypes, one row per applicable vertical pair
    for code, a in archetypes.items():
        if a[1] != "trade" or not TWO_SIDED.search(a[8] or "") or a[7] == "seller":
            continue
        for x, y in w3.PAIRS:
            if (code, f"{x} x {y}") in recast_have:
                continue
            out.append({"wave": "JS", "archetype": code, "axis": "recast", "value": "seller", "title": a[3], "stage": a[1], "pages": list(a[4]),
                        "layers": list(a[5]), "ufai": list(a[6]), "persona": "seller", "pair": a[8], "entry": a[9], "vertical": f"{x} x {y}"})
    # the seller on the layer floor: 12 rows per layer, on the pages the gate routes a seller to
    from sublayer_inventory import collect, page_classes
    cls = page_classes()
    layer_pages: dict = defaultdict(set)
    for c in collect(classes=cls):
        if c["page"] in SELLER_PAGES:
            layer_pages[c["layer"]].add(c["page"])
    seller_rows = Counter()
    for t in existing:
        if t.get("persona") == "seller":
            for L in t.get("layers") or []:
                seller_rows[L] += 1
    for L, pgs in sorted(layer_pages.items()):
        need = SELLER_FLOOR - seller_rows.get(L, 0)
        if need <= 0:
            continue
        have_floor = {((x.get("js") or {}).get("layer"), (x.get("js") or {}).get("page")) for x in existing if (x.get("js") or {}).get("kind") == "seller-floor"}
        for i, p in enumerate(sorted(pgs) * ((need // max(1, len(pgs))) + 1)):
            if i >= need:
                break
            if (L, p) in have_floor and i >= len(pgs):
                continue
            out.append({"wave": "JS", "archetype": f"JS-floor:{L}", "axis": "seller-floor", "value": L, "title": f"the seller on the {L} layer floor",
                        "stage": "trade", "pages": [p], "layers": [L], "ufai": ["F", "I"], "persona": "seller", "pair": "", "entry": "hub-nav", "page": p})
    return out


def census() -> dict:
    existing = rows()
    pg = pages()
    se, out_, js = se_cells(existing, pg), out_cells(existing, pg), js_cells(existing, pg)
    return {
        "population": {"production pages": len(pg["production"]), "calculators": len(pg["calc"]), "learn articles": len(pg["learn"])},
        "se": se, "out": out_, "js": js,
        "by": {"SE": dict(Counter(c["source"] for c in se)), "OUT": dict(Counter(c["outcome"] for c in out_)),
               "JS": dict(Counter(f"{c['axis']}:{c['value']}" if c["axis"] != "seller-floor" else "seller-floor" for c in js))},
        "total": len(se) + len(out_) + len(js),
    }


def main() -> int:
    _force_utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    c = census()
    if a.json:
        print(json.dumps(c, indent=1, ensure_ascii=False))
        return 0
    print("\nTHE OUTCOME WAVES (SE · OUT · JS) - the cells no row carries, measured")
    print("=" * 96)
    print("  population: " + " · ".join(f"{k} {v}" for k, v in c["population"].items()))
    print(f"  SE  {len(c['se']):>5}  " + " · ".join(f"{k} {v}" for k, v in c["by"]["SE"].items()))
    print(f"  OUT {len(c['out']):>5}  " + " · ".join(f"{k} {v}" for k, v in c["by"]["OUT"].items()))
    print(f"  JS  {len(c['js']):>5}  " + " · ".join(f"{k} {v}" for k, v in sorted(c["by"]["JS"].items())))
    print(f"  = {c['total']} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
