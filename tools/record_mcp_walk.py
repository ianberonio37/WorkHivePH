#!/usr/bin/env python3
"""record_mcp_walk.py - write the receipt for a journey walked through the MCPs, by hand, as the person.

★THE LEDGER COULD ONLY SEE THE LIBRARY (Ian, 2026-09-10: "what I said, we should always use MCPs for
walks"). `live_walk_manifest._red_receipt_ids()` and `validate_trajectory_registry`'s receipt-agreement
check both read exactly one namespace - `.tmp/full_journeys_*.json`, written by prove_full_journeys.mjs.
So the doctrine and the instrument disagreed: SS-LW.1 rule 4 says a persona JOURNEY is walked with the
MCP because each step's snapshot decides the next, and yet a journey walked that way could never be
banked, because nothing wrote a receipt the ledger would read. Worse, a row whose scripted receipt was
red stayed red forever - re-walking it correctly, by hand, through the MCP, moved nothing.

This closes that half. An MCP walk writes `.tmp/mcp_walks/<id>.json` in the SAME shape the ledger
already understands, and the ledger takes the newest receipt across BOTH namespaces, so an MCP re-walk
supersedes an older scripted one exactly as a scripted re-walk supersedes an older scripted one.

SIGNING IN AS THE PERSON, WHICH IS THE WHOLE POINT AND HAS ONE TRAP. A gated page redirects to
`index.html?signin=1&return=<page>`, and that wall asks for a USERNAME, not an email - index.html builds
the account as `username.toLowerCase().replace(/[^a-z0-9_]/g,'') + '@auth.workhiveph.com'`. So the
username is the LOCAL PART OF THE ACCOUNT, not the person's display name. For 18 of the 23 seeded
memberships those coincide; for four they do not, and all four are the fleet accounts:

    Rosa dela Cruz -> delacruzfleet       Oscar Ramos -> jeepney.oscarph
    Gloria Tan     -> vanfleet.gloriaph   Ben Ocampo  -> driverben

Typing "Rosa dela Cruz" is correctly refused with "Wrong username or password." That is the product
working, and it was nearly filed as a defect - read the account's email from the database and use its
local part.

WHAT THIS IS NOT: it is not a way to hand-write a pass. The receipt records what was actually observed -
per step, the page, its rendered character count, whether identity survived, and the routes onward - and
it carries `instrument: "chrome-devtools-mcp"` (or playwright-mcp) so a reader can always tell a walk
driven by a person from a walk driven by a script. A receipt with no steps is refused.

  python tools/record_mcp_walk.py --id W3122 --instrument chrome-devtools-mcp \
      --condition offline-3g --cast "Romeo Beltran" --note "..." --steps steps.json
  python tools/record_mcp_walk.py --self-test
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / ".tmp" / "mcp_walks"
KNOWN_INSTRUMENTS = ("chrome-devtools-mcp", "playwright-mcp")


def build_receipt(rid: str, instrument: str, condition: str, cast: str,
                  steps: list, note: str, generated: str, unproven: str = "") -> dict:
    """The receipt, in the shape the ledger already reads (`results: [{id, ok, ...}]`).

    `unproven` is for the walk that RAN cleanly and still does not settle the row - a pair with only one
    half castable, a condition the instrument cannot apply. It forces ok=false, because a green receipt
    is a claim about the ROW, not about whether the pages painted.
    """
    if not steps:
        raise ValueError("a walk with no steps is not a receipt - refusing to write one")
    if instrument not in KNOWN_INSTRUMENTS:
        raise ValueError(f"unknown instrument {instrument!r}: use one of {KNOWN_INSTRUMENTS}")
    arrived = [s for s in steps if int(s.get("chars") or 0) >= 120 and not s.get("loadError")]
    kept = all(s.get("identityKept", True) for s in steps)
    problems = []
    for s in steps:
        if s.get("loadError"):
            problems.append(f"{s.get('page')}: {str(s['loadError'])[:80]}")
        elif int(s.get("chars") or 0) < 120:
            problems.append(f"{s.get('page')}: rendered {s.get('chars')} characters")
    if not kept:
        problems.append("identity did not survive every hop")
    # ★EVERY STEP RENDERING IS NOT THE SAME AS THE ROW BEING PROVEN (2026-09-10). W3530's five steps all
    # rendered, and the row was still unproven: J19 declares a worker x supervisor PAIR whose last step
    # belongs to the supervisor, and Baguio Textile Mills has no non-admin supervisor to cast. Without a
    # way to say that, this file would have written ok=true over a half-walk and let the ledger close a
    # row nobody had finished - which is the precise failure the whole receipt system exists to prevent.
    # A caller who knows the walk is partial says so, and the receipt carries it as a problem.
    if unproven:
        problems.append(f"NOT PROVEN: {unproven}")
    return {
        "_doc": ("A journey walked through the MCPs by hand, as the person - SS-LW.1 rule 4. Written by "
                 "tools/record_mcp_walk.py; the `instrument` field is how a reader tells this from a "
                 "scripted walk."),
        "generated": generated,
        "instrument": instrument,
        "results": [{
            "id": rid,
            "ok": not problems,
            "unbuilt": False,
            "instrument": instrument,
            "condition": condition,
            "cast": cast,
            "problems": problems,
            "note": note,
            "metrics": {"arrived": len(arrived), "steps": len(steps), "idKept": kept},
            "steps": steps,
        }],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--instrument", default="chrome-devtools-mcp")
    ap.add_argument("--condition", default="normal")
    ap.add_argument("--cast", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--steps", required=True, help="path to a JSON list of step objects")
    ap.add_argument("--generated", default="", help="ISO stamp; defaults to now")
    ap.add_argument("--unproven", default="", help="force ok=false: the walk ran but does not settle the row")
    args = ap.parse_args()

    steps = json.loads(io.open(args.steps, encoding="utf-8").read())
    if not isinstance(steps, list):
        print("the --steps file must hold a JSON LIST of steps")
        return 1
    import datetime as _dt
    stamp = args.generated or _dt.datetime.now().isoformat(timespec="seconds")
    try:
        doc = build_receipt(args.id, args.instrument, args.condition, args.cast, steps, args.note, stamp,
                            args.unproven)
    except ValueError as e:
        print(f"refused: {e}")
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{args.id}.json"
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, out)
    r = doc["results"][0]
    print(f"wrote {out.relative_to(ROOT)} - {args.id} ok={r['ok']} "
          f"{r['metrics']['arrived']}/{r['metrics']['steps']} arrived, instrument {args.instrument}"
          + (f", problems: {'; '.join(r['problems'])[:120]}" if r["problems"] else ""))
    return 0


def _self_test() -> int:
    fails = []
    good = [{"page": "a.html", "chars": 2000, "identityKept": True},
            {"page": "b.html", "chars": 3000, "identityKept": True}]
    r = build_receipt("T1", "chrome-devtools-mcp", "offline-3g", "A Worker", good, "n", "s")["results"][0]
    if not r["ok"]:
        fails.append("a walk where every step rendered must read ok")
    if r["metrics"]["arrived"] != 2:
        fails.append("both steps should count as arrived")

    thin = [{"page": "a.html", "chars": 69, "identityKept": True}]
    r = build_receipt("T1", "chrome-devtools-mcp", "offline-3g", "A Worker", thin, "n", "s")["results"][0]
    if r["ok"] or "69" not in " ".join(r["problems"]):
        fails.append("a 69-character step must redden and say so - that is the sign-in wall")

    lost = [{"page": "a.html", "chars": 2000, "identityKept": False}]
    r = build_receipt("T1", "chrome-devtools-mcp", "normal", "A Worker", lost, "n", "s")["results"][0]
    if r["ok"]:
        fails.append("a walk that lost identity must not read ok")

    for bad, why in (([], "a walk with NO steps must be refused, never written as a pass"),
                     (None, "a non-list steps value must be refused")):
        try:
            build_receipt("T1", "chrome-devtools-mcp", "normal", "x", bad or [], "n", "s")
            fails.append(why)
        except ValueError:
            pass
    try:
        build_receipt("T1", "a-script", "normal", "x", good, "n", "s")
        fails.append("an unknown instrument must be refused - the field is how a reader tells walks apart")
    except ValueError:
        pass

    r = build_receipt("T1", "chrome-devtools-mcp", "normal", "x", good, "n", "s",
                      unproven="the supervisor half cannot be cast in this hive")["results"][0]
    if r["ok"]:
        fails.append("an --unproven walk must read ok=false even when every step rendered")
    if not any("NOT PROVEN" in p for p in r["problems"]):
        fails.append("an --unproven walk must say WHY in its problems")

    print("FAIL record_mcp_walk self-test - " + "; ".join(fails) if fails
          else "self-test OK: a full walk passes; a 69-char step, a lost identity, an empty walk and an "
               "unknown instrument are each refused or reddened, and an --unproven walk cannot read green")
    return 1 if fails else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(_self_test())
    raise SystemExit(main())
