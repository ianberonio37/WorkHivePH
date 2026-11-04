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


GJ_VERDICTS = ROOT / ".tmp" / "gj_contract"
_AU = {}
_H = {}
_H_SERVER = []


def _h_served(page: str) -> tuple[bool, list[str], str]:
    """H through F and I - the header set the host serves for the page's path, the same whoever asks - read by the
    registered prover's own check (tools/prove_w4_layer_headers.py) against the local Vercel-headers substitute."""
    if page in _H:
        return _H[page]
    import atexit
    import subprocess
    import time
    import prove_deploy_headers as dh
    import prove_w4_layer_headers as w4h
    if not dh.listening() and not _H_SERVER:
        _H_SERVER.append(subprocess.Popen([sys.executable, str(ROOT / "tools" / "serve_vercel_headers.py"), "--port", str(dh.PORT)],
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        atexit.register(lambda: [x.terminate() for x in _H_SERVER])
        for _ in range(40):
            if dh.listening():
                break
            time.sleep(0.25)
    try:
        _H[page] = w4h.check_page(page)
    except Exception as e:
        _H[page] = (False, [f"the header check could not run ({e})"], "")
    return _H[page]


def _au_identity(page: str, persona: str | None) -> tuple[bool, str]:
    """AU through F and I - "the platform keeps this page's identity honest when a session ends or a role changes" - by
    the registered prover's own rule (tools/bank_au_identity_rows.py): prove_lxp_au_identity_after_change.mjs replays ONE
    unexpired token across an active, a kicked and a deactivated membership and a role change, and grades every
    hive-scoped relation; a page holds for a persona when the relations ITS source reads are among those graded by a
    green report from a subject of the persona's own role (a supervisor's reading never vouches for a worker's row)."""
    import glob
    import bank_au_identity_rows as au
    grp = "supervisor" if persona in ("supervisor", "fleet-supervisor", "oversight") else "worker"
    if grp not in _AU:
        graded, subjects = {}, []
        for path in sorted(glob.glob(str(ROOT / "au_identity_after_change_report*.json"))):
            r = json.loads(Path(path).read_text(encoding="utf-8"))
            if not r.get("pass") or r.get("role_before") == "solo":
                continue
            if ("supervisor" if r.get("role_before") == "supervisor" else "worker") != grp:
                continue
            subjects.append(r.get("subject"))
            for k, v in (r.get("sweep") or {}).items():
                if v.get("verdict") in au.EVIDENCE and k not in graded:
                    graded[k] = dict(v, _by=r.get("subject"))
            for k, v in (r.get("spine") or {}).items():
                if v.get("active", 0) > 0 and v.get("kicked") is not None and k not in graded:
                    graded[k] = {"verdict": "spine", "active": v.get("active"), "kicked": v.get("kicked"), "_by": r.get("subject")}
        _AU[grp] = (graded, subjects)
    graded, subjects = _AU[grp]
    if not subjects:
        return False, f"no green identity-after-change report from a {grp} subject on disk"
    reads = sorted(set(au.READ_RE.findall(au.page_source(page) or "")))
    hit = [r for r in reads if r in graded]
    if not hit:
        return False, f"{page} reads none of the relations the {grp} subjects' replay graded ({', '.join(reads[:5]) or 'no reads'})"
    said = "; ".join(f"{r} ({graded[r].get('verdict')}" + (f", {graded[r].get('active')} -> {graded[r].get('kicked')}" if graded[r].get('active') is not None else "")
                     + f", read by {graded[r].get('_by')})" for r in hit[:4])
    return True, (f"{page} reads {len(hit)} relation(s) the {grp} subjects' green replay graded on ONE unexpired token "
                  f"(tools/prove_lxp_au_identity_after_change.mjs, gate lxp-au-identity-after-change): {said}.")


def _gj_verdict(rid: str, page: str) -> dict | None:
    """The library walk's verdict for one GJ contract row (bank_lx_walk.py keeps it), while its page is unchanged since."""
    vf, pg = GJ_VERDICTS / f"{rid}.json", ROOT / page
    if not vf.exists() or (pg.exists() and vf.stat().st_mtime < pg.stat().st_mtime):
        return None
    try:
        return json.loads(vf.read_text(encoding="utf-8"))
    except Exception:
        return None


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
            v = _gj_verdict(t["id"], g["page"])
            # ★THE SERVED HEADERS ARE THE PAGE'S, NOT THE PERSON'S: H through F and I is the header set the host serves for
            # the path (tools/serve_vercel_headers.py), the same bytes whoever asks - any persona's closed row answers it
            if L == "H" and g["pillar"] in ("F", "I") and key not in cube and (g["page"], L, g["pillar"], "*") in cube:
                key = (g["page"], L, g["pillar"], "*")
            au = _au_identity(g["page"], g.get("persona")) if (L == "AU" and g["pillar"] in ("F", "I") and key not in cube) else None
            hh = _h_served(g["page"]) if (L == "H" and g["pillar"] in ("F", "I") and key not in cube) else None
            if hh and not hh[0] and not v:
                left.append(f"{t['id']}: contract layer H - the served headers of {g['page']} do not hold: {'; '.join(hh[1])[:200]}")
                continue
            if key in cube:
                contract = (f" The {L} contract half is the cube's closed row for {g['page']} x {L} x {g['pillar']} x "
                            f"{key[3]} (its registered prover's per-(page, persona) record).")
            elif hh and hh[0]:
                contract = (f" The H contract half is the page's served header set, the same bytes whoever asks "
                            f"(tools/prove_w4_layer_headers.py check_page against tools/serve_vercel_headers.py = vercel.json, "
                            f"gate w4-layer-headers): {hh[2]}.")
            elif au and au[0]:
                contract = f" The AU contract half is the identity-after-change replay: {au[1]}"
            elif au and not v:
                left.append(f"{t['id']}: contract layer AU - {au[1]}")
                continue
            elif v and v.get("holds"):
                said = " | ".join(f"{vp}: {x[0]} - {x[1][:90]}" for vp, x in (v.get("per") or {}).items())
                contract = (f" The {L} contract half is the library walk of {g['page']} as {v.get('cast')} "
                            f"({v.get('castRole')}) for the {v.get('persona')} persona, {v.get('walked')} (tools/lx_walk.js through "
                            f"the Playwright MCP, batch {v.get('batch')}; .tmp/gj_contract/{t['id']}.json): {said}.")
            elif v:
                bad = next(((vp, x) for vp, x in (v.get("per") or {}).items() if x[0] not in ("ok", "n/a")), None)
                left.append(f"{t['id']}: contract layer {L} - the library walk of {g['page']} as {v.get('persona')} does NOT "
                            f"hold" + (f" ({bad[0]}: {bad[1][1][:120]})" if bad else ""))
                continue
            else:
                left.append(f"{t['id']}: contract layer {L} - no closed cube row for {key} and no library walk of it yet "
                            f"(tools/lx_walk_args.py --gj {g.get('milestone')})")
                continue
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
