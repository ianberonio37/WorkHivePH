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
layer's closure (weakest first). MILESTONES are blocks of the open book, and every block ends in a production push (the
runbook's procedure): M1..M6 are the tier boundaries (when T1 has no row left to build, then T2 ...); every later wave
declares its own blocks in its rows (Wave GJ, 2026-11-04: `gj.milestone`, M7..M11, named in
tools/group_journey_census.GJ_MILESTONES - Ian: "the open trajectories are set in milestones, and at every milestone we
push"). A row's TIER is its rank; its MILESTONE is its block. The queue is block-major, so a later block's rows come after
every earlier block's, and inside a block the order is the score below.

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
RUNBOOK = ROOT / "PRODUCTION_DEPLOY_RUNBOOK.md"   # the milestones released, read from its DEPLOYED headings

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
    gj = r.get("gj") or {}
    if gj:
        # the group journeys (GJ, 2026-11-04): a hand-off on a production page is a journey walked start to end by its
        # people (T4); founder and public hand-offs wait with their cube (T5); the group's UX face is the long tail (T6).
        # The tier is the row's rank; its milestone (M7..M11) is its block - milestone_of
        if gj.get("cls") == "ux":
            return 6, "group journeys: the group's UX face"
        if gj.get("cls") == "production":
            return 4, "group journeys: a hand-off on a production page"
        return 5, f"group journeys: a hand-off on a {gj.get('cls')} page"
    if wave.startswith("BRH") or wave.startswith("BRP"):
        return 1, "a measured defect site (bug-hunt / bug-repro)"
    ed = r.get("ed") or {}
    if ed:
        # engineering design, one calculator at a time (ED, 2026-10-31): a calculator whose Guide says it is not built yet,
        # the guide renderer's measured sites, a form value its engine never reads (I1) and a calculator answered by the
        # unchecked TypeScript fallback (E1) are defects a person meets today (T1); every other calculator lens is the
        # production page where the person works (T3)
        measured = ed.get("key", "").startswith("GR") or ed.get("key") in ("I1", "E1")
        if measured or (ed.get("key") == "G1" and "No guide available yet" in ed.get("detail", "")):
            return 1, f"engineering design: {ed.get('lens')}"
        return 3, f"engineering design: {ed.get('lens')}"
    od = r.get("od") or {}
    if od:
        # the open-source design lens (OD, 2026-11-03): a production page typing its own colours, sizes or z-indexes is a
        # page the person works on looking unlike its neighbours (T3); the system tokens are the design system's own
        # health (T4); founder/public drift waits with their cube (T5); the Penpot comps are the canvas mirror (T6)
        key = od.get("key")
        if key == "S":
            return 4, "open design: the design system owns what the pages improvise"
        if key == "D":
            return (3, "open design: a production page's own CSS bypasses tokens.css") if pc == 0 else \
                   (5, "open design: a founder or public page's own CSS bypasses tokens.css")
        return 6, "open design: the page's comp in the WorkHive Penpot file"
    hs = r.get("hs") or {}
    if hs:
        # the hive at thirty (HS, 2026-10-29): a cluttered list, a role's actions and a lost concurrent change are what a
        # person in a full hive meets today on a production page (community's cards were all three) - T1; the other
        # lenses join the lane's health (T4); a founder page reads across hives, so its rows wait with the founder cube
        if hs.get("page_class") == "founder":
            return 5, "the hive at thirty: a founder list"
        if hs.get("key") in ("L1", "L2", "W1"):
            return 1, f"the hive at thirty: {hs.get('lens')}"
        return 4, f"the hive at thirty: {hs.get('lens')}"
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


def milestone_of(r: dict, tier: int) -> str:
    """The block a row closes in: its wave's declared milestone (GJ: gj.milestone), else its tier's (M1..M6)."""
    return (r.get("gj") or {}).get("milestone") or f"M{tier}"


def _gj_blocks() -> dict:
    try:
        from group_journey_census import GJ_MILESTONES
        return {m: v["name"] for m, v in GJ_MILESTONES.items()}
    except Exception:
        return {}


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
    mile = {}
    for r in open_rows:
        tier, why = tier_of(r, classes, trip_units)
        mile[r["id"]] = milestone_of(r, tier)
        ranked.append((tier, score_of(r, tier, classes, layer_pct, persona_rank), r["id"], why))
    # block-major: M1..M6 are the tiers themselves, so for every row before Wave GJ this is the order it always had
    ranked.sort(key=lambda x: (int(mile[x[2]][1:]), x[0], x[1]))
    tiers = []
    by_tier = defaultdict(list)
    for tier, score, rid, why in ranked:
        by_tier[tier].append((rid, why))
    status = {r["id"]: r.get("status") for r in open_rows}
    for t in range(1, 7):
        items = by_tier.get(t, [])
        tiers.append({"tier": f"T{t}", "name": TIER_NAMES[t], "count": len(items),
                      "locking": sum(1 for rid, _w in items if status.get(rid) == "locking"),
                      "first": [rid for rid, _w in items[:40]],
                      "why": dict(Counter(w for _r, w in items).most_common(6))})
    blocks = _gj_blocks()
    in_block = Counter(mile.values())
    locking_in = Counter(mile[rid] for rid in mile if status.get(rid) == "locking")
    cumulative, milestones = 0, []
    tier_ms = [f"M{n}" for n in range(1, 7)]
    for m in tier_ms + [b for b in blocks if b not in tier_ms]:
        cumulative += in_block.get(m, 0)
        n = int(m[1:])
        milestones.append({"milestone": m, "name": TIER_NAMES[n] if n <= 6 else blocks[m],
                           "when": (f"T{n} has no row left to build" if n <= 6 else f"{blocks[m]} have no row left to build"),
                           "count": in_block.get(m, 0), "locking": locking_in.get(m, 0), "rows_to_close": cumulative,
                           "then": "the release, run through PRODUCTION_DEPLOY_RUNBOOK.md and reported after"})
    return {
        "_doc": "GENERATED by tools/trajectory_priority.py - the open book in the order it is worked, the less important last; "
                "tiers from what a row IS, the score inside a tier from the registry's own facts (never typed)",
        "generated": date.today().isoformat(),
        "open": len(open_rows), "in_scope": len(scoped), "closed": len(scoped) - len(open_rows),
        "tiers": tiers, "milestones": milestones,
        "order": [rid for _t, _s, rid, _w in ranked],
        "rows": {rid: {"tier": t, "rank": i + 1, "milestone": mile[rid]} for i, (t, _s, rid, _w) in enumerate(ranked)},
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
    # A tier's rows at locking wait on the board or the push, so "empty" was never how a milestone came: M1 and M2 shipped
    # with T1's locking rows still open. The releases themselves are read from the runbook's DEPLOYED headings.
    done = released()
    said = " · ".join(f"{m} {d}" for m, d in sorted(done.items()))
    rule = ("the release is mine to run at each milestone, through PRODUCTION_DEPLOY_RUNBOOK.md, reported after - Ian, "
            "2026-10-27: \"we deploy functions and push frontend to production when we achieved considerable important "
            "closed trajectories\"")
    pending = [m for m in doc["milestones"] if m["milestone"] not in done]
    if not pending:
        lines.append(f"- **MILESTONE → push**: released {said or 'none yet'}; every milestone is out.")
        return lines
    m = pending[0]
    build = m.get("count", 0) - m.get("locking", 0)
    if build == 0:
        state = (f"{m['milestone']} is DUE - {m['when']}"
                 + (f" ({m['count']} at locking - the board's)" if m.get("count") else ""))
    else:
        state = (f"next {m['milestone']} ({m.get('name', '')}) when {m['when']} ({m.get('count', 0)} open, "
                 f"{m.get('locking', 0)} of them at locking - the board's)")
    later = [f"{x['milestone']} {x.get('count', 0)}" for x in pending[1:]]
    if later:
        state += "; then " + " · ".join(later)
    lines.append(f"- **MILESTONE → push** ({rule}): released {said or 'none yet'}; {state}.")
    return lines


def released() -> dict[str, str]:
    """{"M1": "2026-10-27", ...} from PRODUCTION_DEPLOY_RUNBOOK.md's headings that say a milestone DEPLOYED."""
    out: dict[str, str] = {}
    if RUNBOOK.exists():
        for line in RUNBOOK.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("#"):
                for m, d in re.findall(r"\b(M\d+)(?: release)? \((\d{4}-\d{2}-\d{2})\) ✅ DEPLOYED", line):
                    out.setdefault(m, d)
    return out


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
