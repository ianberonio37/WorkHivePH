#!/usr/bin/env python3
"""trajectory_priority.py - the open book, in the order it is worked: the less important last (Ian, 2026-10-26).

Ian: "we have to prioritize the open trajectories roadmap because we have massive open trajectories, so we put in the
roadmap, we have to push to production when we achieve a considerable milestone of our trajectories roadmap, but first we
have to reprioritize the open trajectories, with less important one to be on the last."

20,000 open rows are honest only if their ORDER is derived, never felt. Every open row (in scope, not closed by the
ledger's own rule - live_walk_manifest.row_closed) gets a TIER from what the row IS, and a SCORE inside its tier from
facts the registry already carries:

  T1  defects a person meets today            the bug-hunt and bug-repro waves (BRH, BRP); the OWN lenses that are
                                              defect-shaped on production pages (jobs, dependencies, AI failure modes,
                                              WebKit, two devices, Back, search, low-end phones); the keep-abreast rows
                                              behind a trip past grace (the overdue pillars/comparisons, the push)
  T2  the person's belief and the outcomes    Wave SE (self-efficacy) and Wave OUT (use / return / repeat use) - the
                                              dependent variables of Ian's model, once seeded
  T3  the cube where the person works         CX on production pages - weakest layer first (the ledger's closure per
                                              layer), F before I before U before A, the persona most rows stand for first
  T4  the journeys and the lane's health      the journey waves (W3-JN, W4, JS, CX-J), the evidence spine (KA-E), the
                                              public refresh and push rows (KA-R articles/calculators, KA-S)
  T5  the cube on founder and public pages    CX-FND, then CX-PUB (anon first, then the signed-in reader, then assistive)
  T6  the long tail                           CX-UX (a rubric class never graded on a page), the accessibility-mode OWN
                                              rows, Back on public pages, KA-V (the engines' voice, Ian's monthly sheet),
                                              and anything left

Inside a tier the score is lexicographic: evidence first (fixing 0 · walked 1 · locking-but-open 2 · specced 3), then
the page class (production 0 · founder 1 · public 2), then the pillar (F 0 · I 1 · U 2 · A 3: what a worker loses money
on before what merely slows them), then the persona by how many rows the program already found worth walking as it
(worker before supervisor before ... before machine-client - a measured proxy, not a ranking of people), then the
layer's closure (weakest first). MILESTONES are tier boundaries: when T1 is empty the roadmap proposes a production push
(the push itself is Ian's gate and the runbook's procedure), and again at each tier after it.

    python tools/trajectory_priority.py            # the table; writes trajectory_priority.json
    python tools/trajectory_priority.py --head 40  # the next 40 ids in order
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))
MANIFEST = ROOT / "live_walk_manifest.json"
OUT = ROOT / "trajectory_priority.json"
TRIP = ROOT / "seo_trip_report.json"

TIER_NAMES = {
    1: "defects a person meets today",
    2: "the person's belief and the outcomes",
    3: "the cube where the person works (production, weakest layer first)",
    4: "the journeys and the lane's health",
    5: "the cube on founder and public pages",
    6: "the long tail (rubric classes never graded, accessibility modes, the engines' voice)",
}
PILLAR_RANK = {"F": 0, "I": 1, "U": 2, "A": 3}
STATUS_RANK = {"fixing": 0, "walked": 1, "locking": 2, "specced": 3}
DEFECT_LENSES = ("scheduled work", "dependency", "AI failure mode", "WebKit primary action", "two devices, one account",
                 "in-app search", "low-end phone")
PUBLIC_PERSONA_RANK = {"anon": 0, "worker": 1, "assistive-tech": 2, "machine-client": 3}


def _force_utf8_stdout() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def _target(r: dict):
    p = r.get("pages") or []
    return p[-1] if p else None


def _page_class(page: str | None, classes: dict) -> int:
    if not page:
        return 1
    if page in classes.get("production", ()):
        return 0
    if page in classes.get("founder", ()):
        return 1
    return 2


def load_inputs(rows=None, manifest=None):
    import registry_io as _rio
    rows = rows or _rio.load_doc()["trajectories"]
    if manifest is None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    closed = set()
    for m in manifest.get("rows") or []:
        if m.get("closed") is True or (m.get("kind") == "live" and m.get("gated") and m.get("status") in ("locked", "locking")):
            closed.add(m["id"])
    layer_pct = {k: v.get("pct_closed", 100.0) for k, v in (manifest.get("by_layer") or {}).items()}
    try:
        from sublayer_inventory import page_classes
        classes = {k: set(v) for k, v in page_classes().items()}
    except Exception:
        classes = {}
    return rows, closed, layer_pct, classes


def tier_of(r: dict, classes: dict, trip_units: set) -> tuple[int, str]:
    wave = str(r.get("wave") or "")
    page = _target(r)
    pc = _page_class(page, classes)
    own = r.get("own") or {}
    ka = r.get("ka") or {}
    cx = r.get("cx") or {}
    if wave.startswith("BRH") or wave.startswith("BRP"):
        return 1, "a measured defect site (bug-hunt / bug-repro)"
    if own:
        lens = own.get("lens", "")
        if lens in DEFECT_LENSES:
            return 1, f"OWN defect lens: {lens}"
        if lens == "browser Back" and pc == 0:
            return 1, "OWN defect lens: Back on a production page"
        return 6, f"OWN long-tail lens: {lens}"
    if ka:
        lens = ka.get("lens")
        if lens == "R" and (str(ka.get("detail", "")).startswith(("pillar", "comparison")) or ka.get("unit") in trip_units):
            return 1, "keep-abreast: a refresh behind a trip (pillar / comparison window)"
        if lens == "B" and "push" in (ka.get("trips") or []):
            return 1, "keep-abreast: the push and the board's own truth"
        if lens == "V":
            return 6, "keep-abreast: the engines' voice (Ian's monthly sheet)"
        return 4, f"keep-abreast lens {lens}: the lane's health"
    if wave.startswith("SE") or wave.startswith("OUT"):
        return 2, "self-efficacy / outcomes - the model's dependent variables"
    if cx:
        if cx.get("kind") == "cube-ux":
            return 6, "the cube's UI x UX face: a rubric class never graded on the page"
        if cx.get("cls") == "production":
            return 3, "the cube on a production page"
        return 5, f"the cube on a {cx.get('cls')} page"
    if wave.startswith(("W3-JN", "W4", "JS", "CX-J")) or r.get("journey", {}).get("condition", "normal") != "normal":
        return 4, "a journey walked start to end"
    # the older waves' rows still open: where the person works first
    if pc == 0:
        return 3, "an open row on a production page"
    if page is None:
        return 4, "an open row with no page (a contract)"
    return 5, "an open row on a founder or public page"


def score_of(r: dict, tier: int, classes: dict, layer_pct: dict, persona_rank: dict) -> tuple:
    page = _target(r)
    pc = _page_class(page, classes)
    st = STATUS_RANK.get(r.get("status"), 3)
    pillars = r.get("ufai") or []
    pr = min((PILLAR_RANK.get(p, 4) for p in pillars), default=4)
    persona = r.get("persona") or "any"
    if tier == 5 and pc == 2:
        per = PUBLIC_PERSONA_RANK.get(persona, 4)
    else:
        per = persona_rank.get(persona, 99)
    layers = r.get("layers") or []
    lp = min((layer_pct.get(L, 100.0) for L in layers), default=100.0)
    return (st, pc, pr, per, lp, str(r.get("id")))


def compute(rows=None, manifest=None) -> dict:
    rows, closed, layer_pct, classes = load_inputs(rows, manifest)
    scoped = [r for r in rows if r.get("status") != "descoped"]
    open_rows = [r for r in scoped if r["id"] not in closed and r.get("status") != "locked"]
    counts = Counter(r.get("persona") for r in scoped)
    persona_rank = {p: i for i, (p, _n) in enumerate(counts.most_common())}
    trip_units = set()
    if TRIP.exists():
        try:
            trip_units = {t.get("unit") for t in (json.loads(TRIP.read_text(encoding="utf-8")).get("trips") or []) if t.get("kind") == "refresh"}
        except Exception:
            trip_units = set()
    ranked = []
    for r in open_rows:
        tier, why = tier_of(r, classes, trip_units)
        ranked.append((tier, score_of(r, tier, classes, layer_pct, persona_rank), r["id"], why))
    ranked.sort(key=lambda x: (x[0], x[1]))
    tiers = []
    by_tier = defaultdict(list)
    for tier, score, rid, why in ranked:
        by_tier[tier].append((rid, why))
    for t in range(1, 7):
        items = by_tier.get(t, [])
        tiers.append({"tier": f"T{t}", "name": TIER_NAMES[t], "count": len(items),
                      "first": [rid for rid, _w in items[:40]],
                      "why": dict(Counter(w for _r, w in items).most_common(6))})
    cumulative, milestones = 0, []
    for t in tiers:
        cumulative += t["count"]
        milestones.append({"milestone": f"M{t['tier'][1]}", "when": f"{t['tier']} is empty", "rows_to_close": cumulative,
                           "then": "propose a production push (Ian's gate; PRODUCTION_DEPLOY_RUNBOOK.md procedure)"})
    return {
        "_doc": "GENERATED by tools/trajectory_priority.py - the open book in the order it is worked, the less important last; "
                "tiers from what a row IS, the score inside a tier from the registry's own facts (never typed)",
        "generated": date.today().isoformat(),
        "open": len(open_rows), "in_scope": len(scoped), "closed": len(scoped) - len(open_rows),
        "tiers": tiers, "milestones": milestones,
        "order": [rid for _t, _s, rid, _w in ranked],
        "rows": {rid: {"tier": t, "rank": i + 1} for i, (t, _s, rid, _w) in enumerate(ranked)},
    }


def header_lines(doc: dict | None = None) -> list[str]:
    doc = doc or (json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else compute())
    lines = ["**PRIORITY QUEUE** (the open book in the order it is worked, the less important LAST - "
             "`tools/trajectory_priority.py`, derived from the registry's own facts, never typed; Ian, 2026-10-26: "
             "\"reprioritize the open trajectories, with less important one to be on the last ... push to production when we "
             "achieve a considerable milestone\"):"]
    for t in doc["tiers"]:
        head = " · ".join(t["first"][:8])
        lines.append(f"- **{t['tier']} · {t['name']}** — {t['count']} open · next: {head}")
    nxt = next((m for m, t in zip(doc["milestones"], doc["tiers"]) if t["count"]), None)
    if nxt:
        lines.append(f"- **MILESTONE → push**: {nxt['milestone']} when {nxt['when']} ({nxt['rows_to_close']} rows to close); "
                     f"the push is Ian's gate, the runbook's procedure.")
    else:
        lines.append("- **MILESTONE → push**: every tier is empty - the book is closed.")
    return lines


def main() -> int:
    _force_utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--head", type=int, default=0, help="print the next N ids in order")
    a = ap.parse_args()
    doc = compute()
    OUT.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"\nPRIORITY QUEUE - {doc['open']} open of {doc['in_scope']} in scope (closed {doc['closed']}), less important last")
    print("=" * 100)
    for t in doc["tiers"]:
        print(f"  {t['tier']} {t['name']:<75} {t['count']:>6}")
        for w, n in list(t["why"].items())[:4]:
            print(f"       {n:>6}  {w}")
    print("  milestones: " + " · ".join(f"{m['milestone']} @ {m['rows_to_close']}" for m in doc["milestones"]))
    if a.head:
        print("  next in order: " + " · ".join(doc["order"][:a.head]))
    print(f"  wrote {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
