#!/usr/bin/env python3
# DEEPWALK-CELL: * UX
"""bank_gj_ux.py - bank GJ M11's UX rows on the screens each member met IN the group walk (2026-11-06).

An M11 row (trajectory_registry_gj.json, gj.cls == 'ux') says: grade every screen THIS member meets in the scenario, on
the rubric classes, at phone-390 AND desktop-1280, as the member lives them in the group walk. bank_gj_rows.py never
banks these (its instrument reads hand-offs, not screens). The instrument here is tools/prove_group_journeys.mjs
--survey: each time the walk opens a page for a member it runs survey_ufai_rubric.js there, once per (member, viewport,
page), writing .tmp/gj_ux/<scenario>/<member>_<viewport>_<pageId>.json. Two passes swap the members' viewports, so one
walk grades every member at both widths.

A row is banked only when ALL hold:
  1. every page the row claims has a survey at EVERY viewport the row names, from a real walk (not --teeth), all made
     under MAX_AGE_H hours ago with ONE lens (the same survey_ufai_rubric.js sha);
  2. no survey is of a refusal or of somewhere else (_denied) - a denied screen is not this page's screen;
  3. at least one rubric dim was graded.
Then: no finding -> locking (pct 60); findings -> fixing (pct 40) with the findings on the row, owner Designer. A
re-grade that comes back clean moves a fixing row to locking and keeps the earlier findings as findings_before.

    python tools/bank_gj_ux.py [--dry] [--scenario J2]
    python tools/bank_gj_ux.py --check      # gate gj-ux-hold: every banked UX row still agrees with its receipts
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import registry_io as rio  # noqa: E402
from bank_critic_walk import collect, SPEC  # noqa: E402  (one grading rule for critic rows and GJ UX rows)

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

MAX_AGE_H = 3
SURVEYS = ROOT / ".tmp" / "gj_ux"

# A machine member meets no screen: an API key posts and reads replies. Its "screen" is what the functions it calls say
# back - graded by tools/critic_edge_fn_copy.py (B3 readable, E4 says what to do next, G3 leaks nothing), the same lens
# the critic deepwalk banks edge-function rows with. Which functions each scenario's machine calls (prove_group_journeys:
# postReadings -> sensor-readings-ingest, cmmsPush -> cmms-webhook-receiver):
MACHINE_FNS = {"J17": ["sensor-readings-ingest"], "G-SENSOR": ["sensor-readings-ingest"], "J15": ["cmms-webhook-receiver"]}


def machine_grade(t: dict) -> tuple[list, list, list[str]]:
    """(graded dims, findings, why-not) for a machine member's row, from the copy its functions speak."""
    from critic_edge_fn_copy import grade  # noqa: E402
    fns = MACHINE_FNS.get(t["gj"]["scenario"])
    if not fns:
        return [], [], [f"no declared function list for {t['gj']['scenario']}'s machine member (add it to MACHINE_FNS)"]
    graded, findings = set(), []
    for fn in fns:
        d = ROOT / "supabase" / "functions" / fn
        if not d.is_dir():
            return [], [], [f"function {fn} is not in the tree"]
        for dim, ok, detail in grade(d)["dims"]:
            graded.add(dim)
            if not ok:
                findings.append({"dim": dim, "layer": "heuristic", "severity": "major", "evidence": f"{fn}: {detail}"[:220],
                                 "owner": "AI Engineer", "receipt": "tools/critic_edge_fn_copy.py via tools/bank_gj_ux.py"})
    return sorted(graded), findings, []


def page_id(p: str) -> str:
    parts = str(p).split("?")[0].replace("\\", "/").split("/")
    if parts[-1] == "index.html" and len(parts) > 1:
        return parts[-2]
    return parts[-1].replace(".html", "")


RECEIVES: dict = {}   # (scenario, member) -> the pages a hand-off lands on for that member (filled in main)


def met_pages(t: dict) -> tuple[list[str], list[str]]:
    """(the pages this member MEETS, the claimed pages they never meet). A row's `pages` is the SCENARIO's page set; the
    member meets the pages a hand-off lands on for them (as receiver) plus every page the walk opened for them (a
    survey exists for it at some viewport). The first J4 dry run owed the worker surveys of audit-log, asset-hub and
    analytics-report - the supervisor's screens; the worker only ever opens the logbook."""
    g = t["gj"]
    member, scen = g.get("member"), g["scenario"]
    opened = {}   # pid -> the page as the walk opened it
    d = SURVEYS / scen
    if d.is_dir():
        for f in d.glob(f"{member}_*.json"):
            try:
                rec = json.loads(f.read_text(encoding="utf-8"))
                opened.setdefault(rec.get("pid"), rec.get("page"))
            except Exception:
                pass
    claimed = list(g.get("pages") or [])
    receives = RECEIVES.get((scen, member), set())
    # every screen the member MET: each page the walk opened for them (claimed or not - G-ESC's founder meets the founder
    # console, which the scenario's page list never named) and each page a hand-off lands on for them
    met = [pg for pg in claimed if page_id(pg) in opened or pg in receives]
    met += [opened[pid] for pid in sorted(opened) if opened[pid] and pid not in {page_id(m) for m in met}]
    met += [pg for pg in sorted(receives) if pg not in met]
    return met, [pg for pg in claimed if pg not in met]


def receipts(t: dict) -> tuple[list[dict], list[str]]:
    """The row's surveys, or the reasons it cannot be banked."""
    g = t["gj"]
    out, why = [], []
    now = datetime.now(timezone.utc)
    met, _ = met_pages(t)
    if not met:
        why.append("the walk opened no screen for this member and no hand-off lands on one - nothing graded")
    for vp in g.get("viewports") or ["phone-390", "desktop-1280"]:
        for pg in met:
            f = SURVEYS / g["scenario"] / f"{g.get('member')}_{vp}_{page_id(pg)}.json"
            if not f.exists():
                why.append(f"no survey of {pg} at {vp}")
                continue
            d = json.loads(f.read_text(encoding="utf-8"))
            at = datetime.fromisoformat(str(d.get("at", "1970-01-01T00:00:00+00:00")).replace("Z", "+00:00"))
            if d.get("teeth"):
                why.append(f"{pg} at {vp} came from a --teeth run")
            elif (now - at).total_seconds() > MAX_AGE_H * 3600:
                why.append(f"{pg} at {vp} surveyed over {MAX_AGE_H} h ago")
            elif (d.get("survey") or {}).get("_denied"):
                why.append(f"{pg} at {vp} was not the page's own screen ({(d['survey'].get('_deniedWhy') or 'access-denied')})")
            else:
                s = dict(d["survey"])
                s["pageId"] = f"{s.get('pageId') or page_id(pg)}@{vp}"
                s["_lens"], s["_at"] = d.get("lens"), d.get("at")
                out.append(s)
    lenses = {s.get("_lens") for s in out}
    if len(lenses) > 1:
        why.append(f"surveys graded by {len(lenses)} different lenses - re-walk with one")
    return out, why


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--scenario", default=None)
    a = ap.parse_args()

    spec = set(json.loads(Path(SPEC).read_text(encoding="utf-8")).keys()) - {"_meta"}
    doc = rio.load_doc()
    # where each receiver READ: the walk's own receipt says it (a re-premised hand-off reads on another page than the
    # census named - J6's provider reads the review on their console, there being no provider profile page); the census
    # page from the registry is the fallback for a scenario with no receipt that records it
    from_receipt = set()
    for f in (ROOT / ".tmp" / "gj_walks").glob("*.json"):
        try:
            rcp = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        scen = f.stem
        for ps in rcp.get("passes") or []:
            for h in ps.get("hops") or []:
                if "path" not in h:
                    continue
                who = str(h.get("receiver") or "").split(":")[0]
                pg = str(h.get("path") or h.get("page") or "").split("?")[0]
                if who and pg:
                    RECEIVES.setdefault((scen, who), set()).add(pg if not pg.endswith("/") else pg + "index.html")
                    from_receipt.add(scen)
    for t in doc["trajectories"]:
        g = t.get("gj") or {}
        if g.get("kind") == "group-journey" and g.get("handoff") and g.get("receiver") and g.get("scenario") not in from_receipt:
            RECEIVES.setdefault((g.get("scenario"), g.get("receiver")), set()).add(g.get("page"))
    rows = [t for t in doc["trajectories"] if (t.get("gj") or {}).get("cls") == "ux"
            and (a.scenario is None or t["gj"].get("scenario") == a.scenario)]

    if a.check:
        bad, unjudged, held = [], 0, 0
        for t in rows:
            if t.get("status") not in ("locking", "locked", "fixing"):
                continue
            if t["gj"].get("persona") == "machine-client":
                _, findings, why = machine_grade(t)   # static: re-graded from the tree every run, never unjudged
                if why:
                    bad.append(f"{t['id']}: " + "; ".join(why))
                    continue
            else:
                surveys, why = receipts(t)
                if not surveys and why:
                    unjudged += 1
                    continue
                _, findings, _, _ = collect(surveys, spec)
            if t.get("status") in ("locking", "locked") and findings:
                bad.append(f"{t['id']}: banked clean, but its receipts on disk grade {len(findings)} finding(s)")
            else:
                held += 1
        print(f"gj-ux-hold: {held} banked UX row(s) agree with their receipts, {len(bad)} contradicted, "
              f"{unjudged} unjudged (no fresh receipt on disk - not a pass)")
        for b in bad[:20]:
            print("  FAIL " + b)
        return 1 if bad else 0

    banked, left = 0, []
    for t in rows:
        if t.get("status") in ("locked", "descoped"):
            continue
        g = t["gj"]
        cast = (g.get("cast") or {}).get(g.get("member")) or {}
        if g.get("persona") == "machine-client":
            graded, findings, why = machine_grade(t)
            if why:
                left.append(f"{t['id']} {g['scenario']} {g.get('member')}: " + "; ".join(why))
                continue
            clean = not findings
            basis = (f"[{date.today().isoformat()}] {'LOCKING pct -> 60' if clean else 'FIXING pct -> 40'}. A machine member "
                     f"meets no screen: its screen is what the functions it calls say back. tools/critic_edge_fn_copy.py graded "
                     f"{', '.join(MACHINE_FNS[g['scenario']])} (B3 readable, E4 a next step on failure, G3 no leak): "
                     f"{len(findings)} finding(s). Gate gj-ux-hold.")
        else:
            surveys, why = receipts(t)
            if why:
                left.append(f"{t['id']} {g['scenario']} {g.get('member')}: " + "; ".join(why[:3]))
                continue
            graded, findings, per_page, _ = collect(surveys, spec)
            if not graded:
                left.append(f"{t['id']}: not one rubric dim graded - a walk that scored nothing is a failed walk")
                continue
            clean = not findings
            _, unmet = met_pages(t)
            basis = (f"[{date.today().isoformat()}] {'LOCKING pct -> 60' if clean else 'FIXING pct -> 40'}. Graded in motion "
                     f"{surveys[0].get('_at', '')[:16]}Z - tools/prove_group_journeys.mjs --survey ran survey_ufai_rubric.js "
                     f"(lens {surveys[0].get('_lens')}) on every screen {g.get('member')} ({cast.get('user')}) met in "
                     f"{g['scenario']}, at {' and '.join(g.get('viewports') or [])}: {len(graded)} rubric dim(s) graded, "
                     f"{len(findings)} finding(s). Surveyed: {' | '.join(per_page)}. "
                     + (f"Claimed by the scenario but never met by this member: {', '.join(unmet)}. " if unmet else "")
                     + f"Receipts .tmp/gj_ux/{g['scenario']}/, gate gj-ux-hold.")
        if a.dry:
            banked += 1
            print(f"  would bank {t['id']} {g['scenario']} {g.get('member')}: {'clean' if clean else str(len(findings)) + ' finding(s)'}")
            continue
        prior = list(t.get("findings") or [])
        t["status"], t["pct"] = ("locking", 60) if clean else ("fixing", 40)
        t["dims_graded"] = graded + ["IN-MOTION"]
        t["findings"] = findings
        if prior and clean:
            t["findings_before"] = prior
        t["basis"] = ((t.get("basis") or "") + " || " if t.get("basis") else "") + basis
        arts = t.setdefault("artifacts", {})
        arts["gates"] = sorted(set(arts.get("gates") or []) | {"gj-ux-hold"})
        banked += 1
    if banked and not a.dry:
        rio.save_doc(doc)
    for line in left[:40]:
        print("  left open: " + line)
    print(f"{'would bank' if a.dry else 'banked'} {banked} GJ UX row(s); {len(left)} left open")
    return 0


if __name__ == "__main__":
    sys.exit(main())
