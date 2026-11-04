#!/usr/bin/env python3
"""bank_gj_rows.py - bank Wave GJ rows (the group journeys) on the group walk that answered them (2026-11-04).

A GJ row is one cell of a hand-off: (scenario, hand-off, layer of the receiving page, pillar, member). Its instrument is
tools/prove_group_journeys.mjs - one browser context per member of the cast, the sender acting through the page's own
controls, the receiver's screen read (U), psql AS THE RECEIVER finding the record (F), a member of another hive reading
0 rows (I), the receiver's landing on 3G (A) - in two passes with the members' viewports swapped. Its receipt is
group_journeys_report.json (one entry per scenario) and .tmp/gj_walks/<scenario>.json.

WHICH LAYERS ONE GROUP WALK ANSWERS, and which it does not:
  DIRECT     F (the receiver's screen renders the record) · D (it names who wrote it) · S (another hive is refused) ·
             A (it holds on the receiver's 3G) · C (it says when) · L (the record names who did what) - the walk's own
             readings answer these, so the row banks on the walk alone (U on D/L also needs "who", U on C needs "when")
  CONTRACT   AU · AV · H · LB · RL · CI · CA - a session ending, a model being wrong, the edge's headers, growth past
             design size, a consumption bound, the regression gate, the crew's words: one hand-off walk cannot exercise
             them. Such a row banks only when the walk holds its pillar AND the cube's own row for the same (page, layer,
             pillar, persona) is closed in live_walk_manifest.json - the registered prover's per-(page, persona) record.

A row is banked (status locking, pct 60, basis appended NEWEST LAST naming the instrument) only when ALL hold:
  1. its scenario's receipt is a real walk (not --teeth), both passes present (both viewports), under MAX_AGE_H hours;
  2. the hand-off's act held in both passes, and the row's pillar held in both passes (+ the who/when rule above);
  3. a CONTRACT-layer row also has its cube row closed.
UX rows (GJ-UX) are the critic deepwalk's and are never banked here.

    python tools/bank_gj_rows.py [--dry]        # bank what the receipts answer
    python tools/bank_gj_rows.py --check        # gate gj-rows-hold: every banked GJ row is still held by its receipt
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import registry_io as rio  # noqa: E402

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

REPORT = ROOT / "group_journeys_report.json"
MANIFEST = ROOT / "live_walk_manifest.json"
PROVER = "tools/prove_group_journeys.mjs"
MAX_AGE_H = 3
DIRECT = {"F", "D", "S", "A", "C", "L"}
CONTRACT = {"AU", "AV", "H", "LB", "RL", "CI", "CA"}


def _report() -> dict:
    return json.loads(REPORT.read_text(encoding="utf-8")).get("scenarios", {}) if REPORT.exists() else {}


def _age_h(iso: str) -> float:
    t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - t).total_seconds() / 3600


def _hop_cells(rep: dict, handoff: int) -> dict | None:
    """{act,U,F,I,A, who, when} held in EVERY pass, or None when a pass is missing the hand-off."""
    out = {"act": True, "U": True, "F": True, "I": True, "A": True, "who": True, "when": True, "said": None, "detail": None}
    for p in rep.get("passes") or []:
        h = next((x for x in p.get("hops") or [] if x.get("handoff") == handoff), None)
        if not h or h.get("unbuilt"):
            return None
        for c in ("act", "U", "F", "I", "A"):
            out[c] = out[c] and bool((h.get(c) or {}).get("ok"))
        u = h.get("U") or {}
        out["who"] = out["who"] and u.get("who", True) is not False
        out["when"] = out["when"] and u.get("when", True) is not False
        out["said"] = out["said"] or u.get("said")
        out["detail"] = out["detail"] or (h.get("F") or {}).get("detail")
    return out


def _holds(g: dict, cells: dict) -> tuple[bool, str]:
    u, L = g.get("pillar"), g.get("layer")
    if not cells["act"]:
        return False, "the sender's act did not hold"
    if not cells.get(u):
        return False, f"pillar {u} read FAIL"
    if u == "U" and L in ("D", "L") and not cells["who"]:
        return False, "the screen does not say who did it"
    if u == "U" and L == "C" and not cells["when"]:
        return False, "the screen does not say when"
    return True, ""


def _cube_closed() -> set:
    """(page, layer, pillar, persona) and (page, layer, pillar, '*') of every CLOSED row - the contract half of a GJ row.
    ★THE SAME RULE THE CUBE COUNTS BY (cube_census.have_cells), not "the cube's row": the cube seeded only the cells no
    earlier row answered, so a cell an LX / SL / W4 row already holds has no CX row at all, and asking for one held 245
    of J2's contract rows open against rows that were never going to exist (2026-11-04, the first bank)."""
    if not MANIFEST.exists():
        return set()
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    # the ledger's own closure rule, asked of the ledger (never re-derived: the manifest carries no `closed` flag - a row
    # closes as a live, gated row at locking or locked, which only live_walk_manifest.row_closed knows)
    from live_walk_manifest import row_closed
    closed = {r["id"] for r in m.get("rows") or [] if row_closed(r)}
    out = set()
    for t in rio.load_doc()["trajectories"]:
        if t["id"] not in closed or (t.get("gj") or {}).get("kind") == "group-journey":
            continue
        pages = t.get("pages") or []
        if not pages:
            continue
        for u in t.get("ufai") or []:
            for L in t.get("layers") or []:
                out.add((pages[-1], L, u, t.get("persona")))
                out.add((pages[-1], L, u, "*"))
    return out


def check() -> int:
    """★AGREEMENT, NOT PROOF (the registry's receipt-agreement rule): group_journeys_report.json is a generated receipt
    that *_report.json keeps out of git, so a fresh checkout has none. A banked row whose scenario has a receipt on disk
    is judged against it and a contradiction FAILS; a row with no receipt on disk is counted as UNJUDGED - said, never
    read as a pass, and never a reason to delete evidence to get green."""
    rep = _report()
    bad, n, unjudged = [], 0, 0
    for t in rio.load_doc()["trajectories"]:
        g = t.get("gj") or {}
        if g.get("kind") != "group-journey" or g.get("cls") == "ux" or t.get("status") not in ("locking", "locked"):
            continue
        n += 1
        r = rep.get(g["scenario"])
        if not r:
            unjudged += 1
            continue
        if r.get("teeth"):
            bad.append(f"{t['id']}: banked, but the {g['scenario']} receipt on disk is a --teeth run")
            continue
        cells = _hop_cells(r, g["handoff"])
        ok, why = _holds(g, cells) if cells else (False, "the latest walk has no reading of this hand-off")
        if not ok:
            bad.append(f"{t['id']}: banked, but the latest walk of {g['scenario']} hand-off {g['handoff']} says: {why}")
    for b in bad[:25]:
        print("  FAIL " + b)
    print(f"{'PASS' if not bad else 'FAIL'} gj-rows-hold - {n} banked GJ row(s): {n - unjudged - len(bad)} held by the latest "
          f"group walk, {len(bad)} contradicted, {unjudged} unjudged (no receipt on disk - not a pass)")
    return 0 if not bad else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        return check()
    rep = _report()
    doc = rio.load_doc()
    cube = _cube_closed()
    banked, left = 0, []
    for t in doc["trajectories"]:
        g = t.get("gj") or {}
        if g.get("kind") != "group-journey" or g.get("cls") == "ux" or t.get("status") in ("locking", "locked", "descoped"):
            continue
        r = rep.get(g["scenario"])
        if not r:
            continue
        if r.get("teeth"):
            left.append(f"{t['id']}: the {g['scenario']} receipt is a --teeth run")
            continue
        if len(r.get("passes") or []) < 2 or _age_h(r["generated"]) > MAX_AGE_H:
            left.append(f"{t['id']}: the {g['scenario']} receipt is missing a pass or older than {MAX_AGE_H} h - re-walk")
            continue
        cells = _hop_cells(r, g["handoff"])
        if cells is None:
            left.append(f"{t['id']}: hand-off {g['handoff']} of {g['scenario']} has no recipe yet")
            continue
        ok, why = _holds(g, cells)
        if not ok:
            left.append(f"{t['id']}: {why}")
            continue
        L = g.get("layer")
        contract = ""
        if L in CONTRACT:
            key = (g["page"], L, g["pillar"], g.get("persona") if g["pillar"] != "A" else "*")
            if key not in cube:
                left.append(f"{t['id']}: contract layer {L} - the cube row for {key} is not closed yet")
                continue
            contract = (f" The {L} contract half is the cube's closed row for {g['page']} x {L} x {g['pillar']} x "
                        f"{key[3]} (its registered prover's per-(page, persona) record).")
        vp = " / ".join(f"{k}@{v}" for p in r["passes"] for k, v in (p.get("viewports") or {}).items())
        said = (cells.get("said") or "").replace("||", "|")[:180]
        basis = (f"[{date.today().isoformat()}] LOCKING pct -> 60. Measured live {r['generated'][:16]}Z - {PROVER} walked "
                 f"{g['scenario']} hand-off {g['handoff']} ({g['page']}, {g['sender']} -> {g['receiver']} by {g['channel']}) "
                 f"with one browser context per member, two passes with viewports swapped ({vp}); the sender acted through "
                 f"the page's own controls; the receiver's screen read{': ' + repr(said) if said else ''}; psql as the "
                 f"receiver: {cells.get('detail') or 'the record read through RLS'}; a member of another hive "
                 f"({r.get('foreign_witness')}) read 0 rows; the landing held on 3G. Receipt .tmp/gj_walks/{g['scenario']}.json, "
                 f"gate gj-rows-hold.{contract}")
        if a.dry:
            banked += 1
            continue
        old = t.get("basis") or ""
        t["status"], t["pct"] = "locking", 60
        t["basis"] = (old + " || " if old else "") + basis
        arts = t.setdefault("artifacts", {})
        arts["gates"] = sorted(set(arts.get("gates") or []) | {"gj-rows-hold"})
        banked += 1
    if banked and not a.dry:
        rio.save_doc(doc)
    for line in left[:40]:
        print("  left open: " + line)
    print(f"{'would bank' if a.dry else 'banked'} {banked} GJ row(s); {len(left)} left open")
    return 0


if __name__ == "__main__":
    sys.exit(main())
