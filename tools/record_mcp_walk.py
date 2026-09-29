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
# the browser instruments a person-shaped walk uses, plus the non-browser instruments a CONTRACT layer answers
# with (2026-09-14): postgres/PostgREST-as-the-person for S/AU/L/D, invoke for a function contract, raw-http for
# the served headers (H), grafana for ops liveness. The `instrument` field still lets a reader tell how a
# receipt was earned; a contract layer names the instrument that actually witnessed its claim.
KNOWN_INSTRUMENTS = ("chrome-devtools-mcp", "playwright-mcp", "postgres-mcp", "postgres",
                     "invoke-postgrest", "invoke", "raw-http", "raw-http-headers", "grafana-mcp", "mail-catcher",
                     # the design lenses (2026-09-15): the figma lens walks the page in the browser AND writes/reads
                     # its design source through the Figma MCP
                     "figma-mcp", "playwright-mcp + figma-mcp",
                     # the audit lens is measured by BOTH browsers: Playwright for the rendered page and the
                     # Chrome DevTools MCP for what only a trace can see - forced reflow, non-composited
                     # animations, CLS culprits by element, LCP breakdown on a throttled phone (2026-09-15)
                     "playwright-mcp + chrome-devtools-mcp",
                     # the wave-4 ACTION rows (2026-09-23). live_walk_manifest.MARKERS has required exactly this
                     # string for a "Lived start to end:" row since 2026-09-14 - the recorder simply never learned
                     # it, so the gate demanded an instrument the recorder refused to write and every action-row
                     # receipt bounced. Both halves are real: Playwright MCP walks the path and records every
                     # response the person's session receives; the postgres MCP resolves the cast, the hive ids,
                     # the pg_proc volatility that decides which RPCs the walk may call at all, and the persisted
                     # effect a writing row needs. (A guard's target-bind must grow WITH the program it gates -
                     # memory feedback_the_target_grew_and_the_bind_did_not.)
                     "playwright-mcp + postgres-mcp")
DESIGN_VIEWPORTS = {"phone-390", "desktop-1280"}


def build_receipt(rid: str, instrument: str, condition: str, cast: str,
                  steps: list, note: str, generated: str, unproven: str = "",
                  w4: dict | None = None) -> dict:
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
    # ★A WAVE-4 RECEIPT MUST CARRY WHAT WAVE 4 ASKS FOR (2026-09-14): the axis it was walked at (width + language)
    # and the per-step overlap/occlusion record (`fit`, from tools/phone_fit_audit.mjs) on EVERY step; where the row
    # writes, the persisted effect (`--effect`); for a layer story, the layer provoked; for the nav-hub, the count of
    # control groups exercised; for an upload, the real file's provenance. live_walk_manifest._w4_missing keeps a row
    # OPEN without these, so a receipt that could never close its row is refused here rather than written thin.
    if rid.startswith("W4"):
        w4 = w4 or {}
        if not w4.get("axis"):
            raise ValueError("a W4 receipt needs --axis '<device> <language>' (e.g. 'phone-390 en')")
        # ★A CONTRACT LAYER ANSWERS WITH A WITNESS, NOT A BROWSER fit (2026-09-14). The overlap/occlusion
        # record is the right evidence for what a person SEES (Frontend F, the copy CA, the nav-hub, an
        # action's render); an S/AU refusal, an L trail, a D provenance, an H header, an A/AV/C/CI/LB/RL
        # degraded-behaviour receipt is not browser-shaped and carries no `fit`. Require `--witness` of a
        # contract-layer receipt and `fit`-on-every-step of a browser one - matching live_walk_manifest._w4_missing.
        _layer = w4.get("layer")
        if _layer and _layer not in ("F", "CA"):
            if not w4.get("witness"):
                raise ValueError(f"a W4 {_layer}-layer receipt needs --witness (the refusal / trail / "
                                 "provenance / headers / limit evidence that answers this contract layer)")
        else:
            thin = [s.get("page") for s in steps if not isinstance(s.get("fit"), dict)]
            if thin:
                raise ValueError("a W4 browser receipt needs the per-step overlap/occlusion record ('fit') "
                                 f"on every step; missing on {thin}")
        # ★A DESIGN-LENS RECEIPT CARRIES THE LENS'S OWN EVIDENCE (2026-09-15): the lens walked, BOTH viewports
        # (Impeccable's one batched round at mobile and desktop), the detector's JSON for the page (the mechanical
        # anti-slop witness), the before/after scores for the scored lenses, both languages for the copy lens,
        # and the Figma file + node ids for the figma lens. live_walk_manifest._w4_missing keeps the row open
        # without them, so a receipt that could never close its row is refused here.
        if w4.get("lens"):
            vps = w4.get("viewports")
            if isinstance(vps, str):
                vps = [v.strip() for v in vps.split(",") if v.strip()]
            if not DESIGN_VIEWPORTS <= set(vps or []):
                raise ValueError("a W4 design receipt needs --viewports phone-390,desktop-1280 (both, one batched round)")
            w4["viewports"] = list(vps)
            det = w4.get("detector")
            if not det or not (ROOT / det).exists():
                raise ValueError("a W4 design receipt needs --detector <the page's `impeccable detect --json` output file>")
            langs = w4.get("languages")
            if isinstance(langs, str):
                w4["languages"] = [x.strip() for x in langs.split(",") if x.strip()]
            if w4["lens"] == "figma" and not w4.get("figma"):
                raise ValueError("a W4 figma-lens receipt needs --figma '<fileKey> <node ids at 390 and 1280>'")
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
            **({"w4": w4} if w4 else {}),
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
    # wave 4 (2026-09-14): what the ledger asks a W4 receipt to carry
    ap.add_argument("--axis", default="", help="W4: '<device> <language>', e.g. 'phone-390 en' / 'narrow-320 en' / 'phone-390 fil'")
    ap.add_argument("--effect", default="", help="W4: the persisted effect, e.g. 'logbook id 8f2c.. RETURNING, reversed'")
    ap.add_argument("--layer", default="", help="W4 layer story: the layer provoked and observed (F/D/A/CA/AU/AV/C/S/H/L/LB/RL/CI)")
    ap.add_argument("--hub-controls", type=int, default=0, help="W4 nav-hub story: control groups exercised (11 = all)")
    ap.add_argument("--fixture-provenance", default="", help="W4 upload story: _fixtures/<kind>/manifest.json entry (source URL)")
    ap.add_argument("--witness", default="", help="W4 contract-layer story (S/AU/L/D/A/AV/C/CI/LB/RL): the non-browser evidence - the refusal received as the person, the trail row, the provenance, the served headers, the limit met")
    ap.add_argument("--lens", default="", help="W4 design story: the lens walked (slop/craft/audit/copy/motion/figma/critique)")
    ap.add_argument("--viewports", default="", help="W4 design story: 'phone-390,desktop-1280' - both, one batched round")
    ap.add_argument("--detector", default="", help="W4 design story: path to the page's `impeccable detect --json` output")
    ap.add_argument("--detector-disproven", default="",
                    help="W4 design story: JSON {antipattern: {count, why}} the banker pinned - findings a LIVE "
                         "measurement disproves, carried into the receipt so the gate can re-check them")
    ap.add_argument("--scores", default="", help="W4 design story: JSON {before:{...}, after:{...}} for audit/critique")
    ap.add_argument("--languages", default="", help="W4 design story: 'en,fil' for the copy lens")
    ap.add_argument("--figma", default="", help="W4 figma lens: '<fileKey> <node id @390> <node id @1280>'")
    args = ap.parse_args()
    scores = json.loads(args.scores) if args.scores else None
    w4 = {k: v for k, v in (("axis", args.axis), ("effect", args.effect), ("layer", args.layer),
                            ("hub_controls", args.hub_controls), ("fixture_provenance", args.fixture_provenance),
                            ("witness", args.witness), ("lens", args.lens), ("viewports", args.viewports),
                            ("detector", args.detector),
                            # findings a LIVE measurement disproved, each pinned to its exact count by the
                            # banker, so prove_w4_design_receipts can re-check them on every run (2026-09-15)
                            ("detectorDisproven", json.loads(args.detector_disproven) if args.detector_disproven else None),
                            ("scores", scores), ("languages", args.languages),
                            ("figma", args.figma)) if v}

    steps = json.loads(io.open(args.steps, encoding="utf-8").read())
    if not isinstance(steps, list):
        print("the --steps file must hold a JSON LIST of steps")
        return 1
    import datetime as _dt
    stamp = args.generated or _dt.datetime.now().isoformat(timespec="seconds")
    try:
        doc = build_receipt(args.id, args.instrument, args.condition, args.cast, steps, args.note, stamp,
                            args.unproven, w4 or None)
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

    # wave 4: a W4 receipt without its axis, or with a step lacking the overlap record, is refused; a complete one
    # carries its w4 block and every step's record
    fit = {"findings": 0, "occlusion": [], "overflowEl": []}
    w4steps = [{"page": "a.html", "chars": 2000, "identityKept": True, "fit": fit},
               {"page": "b.html", "chars": 3000, "identityKept": True, "fit": fit}]
    try:
        build_receipt("W41", "playwright-mcp", "normal", "x", w4steps, "n", "s")
        fails.append("a W4 receipt with no --axis must be refused")
    except ValueError:
        pass
    try:
        build_receipt("W41", "playwright-mcp", "normal", "x", good, "n", "s", w4={"axis": "phone-390 en"})
        fails.append("a W4 receipt whose steps carry no overlap record must be refused")
    except ValueError:
        pass
    r = build_receipt("W41", "playwright-mcp", "normal", "x", w4steps, "n", "s",
                      w4={"axis": "phone-390 en", "effect": "logbook id 1 RETURNING, reversed"})["results"][0]
    if not r["ok"] or r.get("w4", {}).get("axis") != "phone-390 en":
        fails.append("a complete W4 receipt must read ok and carry its w4 block")
    # a CONTRACT-layer receipt (H) needs a --witness, not per-step fit; a browser layer (F) still needs fit
    plainsteps = [{"page": "a.html", "chars": 2000, "identityKept": True},
                  {"page": "b.html", "chars": 2000, "identityKept": True}]
    try:
        build_receipt("W42", "invoke", "normal", "x", plainsteps, "n", "s", w4={"axis": "phone-390 en", "layer": "H"})
        fails.append("a W4 H-layer receipt with no --witness must be refused")
    except ValueError:
        pass
    r = build_receipt("W42", "invoke", "normal", "x", plainsteps, "n", "s",
                      w4={"axis": "phone-390 en", "layer": "H", "witness": "served CSP + Cache-Control on 4 pages"})["results"][0]
    if not r["ok"]:
        fails.append("a W4 H-layer receipt WITH a witness and no fit must read ok")
    try:
        build_receipt("W43", "playwright-mcp", "normal", "x", plainsteps, "n", "s", w4={"axis": "phone-390 en", "layer": "F"})
        fails.append("a W4 F-layer (browser) receipt with no per-step fit must be refused")
    except ValueError:
        pass
    # ★EVERY INSTRUMENT THE GATE CAN DEMAND MUST BE ONE THIS RECORDER CAN WRITE (2026-09-23).
    # live_walk_manifest.MARKERS pairs a row-title pattern with the instrument that closes it; KNOWN_INSTRUMENTS
    # decides what may be recorded at all. Two halves of one rule in two files - and they were found NINE DAYS
    # out of sync: MARKERS had required `playwright-mcp + postgres-mcp` for every "Lived start to end:" row since
    # 2026-09-14 and KNOWN_INSTRUMENTS had never heard of it, so the gate demanded an instrument the recorder
    # refused to write and every action-row receipt bounced with "unknown instrument". Nothing surfaced the
    # disagreement until something finally tried to use it. Kin of feedback_the_target_grew_and_the_bind_did_not.
    # Scope, measured rather than assumed: of the 16 instruments MCP_FOR_KIND names, 8 are ANNOTATED prose
    # variants of a base instrument - "playwright-mcp (three host pages: phone, desktop, wall display)",
    # "raw-http fetch (no JS - what a crawler receives)". Those are documentation of HOW the instrument is
    # pointed, not new recordable strings, and asserting the whole table against KNOWN_INSTRUMENTS would fire
    # on all 8 by design. So the check covers the CANONICAL entries only - the ones carrying no "(" - which is
    # exactly the class `playwright-mcp + postgres-mcp` belonged to, and NOT_CONNECTED names the instruments
    # whose MCP genuinely is not wired up yet (the table says so itself: "axe-mcp (MISSING - connect)").
    NOT_CONNECTED = {"sentry-mcp"}
    try:
        import live_walk_manifest as _m
        canonical = {i for i, _pat in _m.MCP_FOR_KIND if "(" not in i} - NOT_CONNECTED
        unwritable = sorted(canonical - set(KNOWN_INSTRUMENTS))
        if unwritable:
            fails.append("live_walk_manifest.MCP_FOR_KIND demands instrument(s) this recorder cannot write: "
                         + ", ".join(repr(x) for x in unwritable))
    except Exception as e:   # the manifest is the gate's file, not this one's - say so rather than pass silently
        fails.append(f"could not cross-check MCP_FOR_KIND against KNOWN_INSTRUMENTS: {e}")
    print("FAIL record_mcp_walk self-test - " + "; ".join(fails) if fails
          else "self-test OK: a full walk passes; a 69-char step, a lost identity, an empty walk and an "
               "unknown instrument are each refused or reddened, an --unproven walk cannot read green, and "
               "every instrument live_walk_manifest.MARKERS can demand is one this recorder can write")
    return 1 if fails else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(_self_test())
    raise SystemExit(main())
