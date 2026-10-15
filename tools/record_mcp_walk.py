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
                     "playwright-mcp + postgres-mcp",
                     # the LLM layer's Grounding and Routing rows (§LM, 2026-10-07). The seeder declared this
                     # instrument for every LM-G / LM-R row on 2026-10-06 and the recorder never learned it - the
                     # same miss as the action rows above, found the first time a G receipt was written. Playwright
                     # walks the page and asks; the live model answers (the receipt's --live-model names the model
                     # and the tokens it spent, read from the edge runtime's own "served by" log line).
                     "playwright-mcp + live-model")
DESIGN_VIEWPORTS = {"phone-390", "desktop-1280"}


def _sparse_wait(s: dict) -> bool:
    """★A LOADING STEP IS SPARSE BY DESIGN (SL F1, 2026-10-16). The 120-character floor below exists to catch the
    sign-in wall - a step that rendered 69 characters because the person was no longer signed in. A step whose CONDITION
    is a held load is a different thing: Platform Actions fills its queues before it reveals them, so for those seconds
    its whole page is its heading and "Loading the action queues: listings to review, top-ups, receipts and feedback…"
    - 99 characters, honest, and with the admin still signed in. Such a step arrives when it carries the wait it NAMED
    (`said`) and kept its identity; a thin step with no named wait, or any thin step of another condition, still fails."""
    return (s.get("condition") == "loading" and bool(str(s.get("said") or "").strip())
            and s.get("identityKept", True) is True)


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
    arrived = [s for s in steps if (int(s.get("chars") or 0) >= 120 or _sparse_wait(s)) and not s.get("loadError")]
    kept = all(s.get("identityKept", True) for s in steps)
    problems = []
    for s in steps:
        if s.get("loadError"):
            problems.append(f"{s.get('page')}: {str(s['loadError'])[:80]}")
        elif int(s.get("chars") or 0) < 120 and not _sparse_wait(s):
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
    # ★AN LXP RECEIPT NAMES THE PERSON AND CARRIES BOTH VIEWPORTS (2026-09-30). The LAYER-UX x PERSONA wave
    # exists because the wave before it asked what A PERSON feels when a layer misbehaves and answered with
    # persona:"any" on 289 of 335 rows - so a receipt that does not say WHICH person signed in cannot close
    # one of these rows, whatever else it proves. And the roadmap's §LXP states that a row closes only when
    # measured at phone-390 AND desktop-1280: the registry showed desktop-class rows at under 9% of the
    # program, so the desktop half is the half that gets skipped. A promise in a document that nothing
    # enforces is not a mechanism ([[feedback_a_declared_mechanism_is_not_a_mechanism]]) - this is the
    # enforcement, refusing the thin receipt here rather than letting the ledger close a phone-only walk.
    # ...and the two waves seeded 2026-10-06 carry the same contract: LXC (the persona x layer floor) is LXP's
    # sentence on a thin cell, and LM (the LLM layer) is a persona asking a page's AI - both close only as a named
    # person at both viewports.
    # ...and BRH (the bug-hunt wave, 2026-10-14): a defect reproduced as a named person at both viewports.
    # ...and the three waves of 2026-10-14 - SL (a page's sub-layer), ENH (an enhancement built), OPC (a panel in the
    # one operator console): the same contract, plus the SUB-LAYER on an SL receipt and the ENGINE wherever the walk
    # ran in WebKit. The engine is the whole lesson of the night they were seeded: WebKit threw on the logbook's
    # realtime socket while every Chromium walk passed, so a receipt that does not say which engine proves nothing
    # about the other one. live_walk_manifest._sl_missing holds an engine-sensitive row open without it.
    _wave_1014 = (rid.startswith(("ENH", "OPC")) or (rid.startswith("SL") and rid[2:].isdigit()))
    if w4 and w4.get("engine") and w4["engine"] not in ("chromium", "webkit"):
        raise ValueError("--engine is chromium or webkit")
    if _wave_1014:
        w4 = w4 or {}
        if rid.startswith("SL") and not w4.get("sublayer"):
            raise ValueError("an SL receipt needs --sublayer <the sub-layer walked, e.g. H1, A3, AV1>")
        # no MCP drives WebKit: the MCP walk is the Chromium half and a Playwright WebKit run is the engine's half, so a
        # receipt that claims the engine must NAME that run - a claim with no run behind it is a declared mechanism
        if w4.get("engine") == "webkit" and "webkit" not in str(w4.get("witness") or "").lower():
            raise ValueError("a WebKit receipt needs --witness naming the WebKit run that walked the page "
                             "(e.g. tools/prove_page_survives_optional_failures.mjs and its results file)")
    if rid.startswith(("LXP", "LXC", "BRH")) or (rid.startswith("LM") and rid[2:].isdigit()) or _wave_1014:
        w4 = w4 or {}
        if not w4.get("layer"):
            raise ValueError("an LXP receipt needs --layer <the architectural layer the walk provoked>")
        if not w4.get("as_persona"):
            raise ValueError("an LXP receipt needs --as-persona <the persona signed in as> - a row whose "
                             "whole point is WHICH person cannot close on an anonymous walk")
        vps = w4.get("viewports")
        if isinstance(vps, str):
            vps = [v.strip() for v in vps.split(",") if v.strip()]
        if not DESIGN_VIEWPORTS <= set(vps or []):
            raise ValueError("an LXP receipt needs --viewports phone-390,desktop-1280 - both, one batched "
                             "round; §LXP closes a row only when it was measured at both")
        w4["viewports"] = list(vps)
        _seen = {str(st.get("viewport") or st.get("device") or "") for st in (steps or [])}
        _missing = {v for v in DESIGN_VIEWPORTS if not any(v in s0 for s0 in _seen)}
        if _missing:
            raise ValueError(f"an LXP receipt needs STEPS at both viewports - none recorded at "
                             f"{', '.join(sorted(_missing))}; declaring the viewports is not walking them")
        # ★AN LM RECEIPT NAMES ITS SUB-LAYER AND HOW IT WAS SETTLED (2026-10-06). Grounding and Routing are walked
        # against the LIVE model (Ian's choice), so their receipt must say which model and what it spent; every
        # other sub-layer is settled locally and must name the witness that settled it.
        if rid.startswith("LM"):
            if w4.get("layer") != "LM":
                raise ValueError("an LM receipt needs --layer LM")
            sub = w4.get("sublayer")
            if sub not in ("X", "G", "S", "R", "P", "A", "V", "L", "E", "O"):
                raise ValueError("an LM receipt needs --sublayer <X|G|S|R|P|A|V|L|E|O>")
            if sub in ("G", "R"):
                if not w4.get("live_model"):
                    raise ValueError("an LM-G / LM-R receipt needs --live-model '<model> <tokens spent>' - a stub "
                                     "cannot answer whether the answer was grounded or the fallback held")
            elif not w4.get("witness"):
                raise ValueError("an LM receipt needs --witness <the local eval harness / gateway debug echo / AI "
                                 "gate result that settles this sub-layer>")
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
    ap.add_argument("--walked-at", default="", help="local ISO time the walk RAN (its records file); a red receipt from a "
                                                    "walk older than an existing green receipt is refused")
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
    ap.add_argument("--sublayer", default="", help="LM story: the LLM sub-layer walked (X G S R P A V L E O); "
                                                   "SL story: the full-stack sub-layer walked (F1..CI4)")
    ap.add_argument("--engine", default="", help="SL/ENH/OPC: the engine the walk ran in (chromium | webkit) - an "
                                                 "engine-sensitive row closes only on a WebKit receipt")
    ap.add_argument("--live-model", default="", help="LM-G / LM-R story: '<model> <tokens spent>'")
    ap.add_argument("--as-persona", default="", help="LXP story: the persona the walk signed in AS (worker, assistive-tech, driver-worker, returner, oversight, adversary, new-user, any)")
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
                            ("as_persona", args.as_persona),
                            ("sublayer", args.sublayer), ("live_model", args.live_model), ("engine", args.engine),
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
    # ★AN OLDER WALK NEVER OVERWRITES A NEWER GREEN RECEIPT (2026-10-12). A kind batch is banked when the NEXT batch is
    # written, so a batch walked at 11:5x was banked at 12:22 - after a write walk at 12:19 had proven the same rows -
    # and its NOT PROVEN receipts replaced eight green ones (W4214 ... W4707). A receipt now carries the time its walk
    # ran (--walked-at, the walk's records file), and a red receipt from a walk older than an existing green one is
    # refused here, for every driver at once.
    if args.walked_at:
        doc["walked_at"] = args.walked_at
        if out.exists() and not doc["results"][0]["ok"]:
            try:
                old = json.loads(out.read_text(encoding="utf-8"))
                old_ok = bool((old.get("results") or [{}])[0].get("ok"))
                old_when = str(old.get("walked_at") or old.get("generated") or "")
                if old_ok and old_when and old_when > args.walked_at:
                    print(f"KEPT {out.relative_to(ROOT)} - {args.id}: a green receipt from {old_when} is newer than this "
                          f"walk ({args.walked_at}); an older walk does not overwrite it")
                    return 0
            except (OSError, ValueError, IndexError, AttributeError):
                pass   # an unreadable old receipt is replaced, as before
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

    # a held load is sparse by design: it arrives when it names its wait and kept the person - and only then
    wait = [{"page": "a.html", "chars": 99, "identityKept": True, "condition": "loading", "said": "Loading the action queues…"}]
    if not build_receipt("T1", "playwright-mcp", "normal", "A Worker", wait, "n", "s")["results"][0]["ok"]:
        fails.append("a 99-character loading step that names its wait must read ok")
    for bad, why in (({"condition": "loading", "said": ""}, "a loading step that names no wait"),
                     ({"condition": "empty", "said": "No parts yet."}, "a thin step of another condition"),
                     ({"condition": "loading", "said": "Loading…", "identityKept": False}, "a loading step that lost the person")):
        step = {"page": "a.html", "chars": 99, "identityKept": True, **bad}
        if build_receipt("T1", "playwright-mcp", "normal", "A Worker", [step], "n", "s")["results"][0]["ok"]:
            fails.append(f"{why} must still redden at 99 characters")

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
    # ★THE LXP GUARD MUST BITE, OR §LXP's "both viewports" IS PROSE (2026-09-30). The roadmap states that a
    # LAYER-UX x PERSONA row closes only when it was measured at phone-390 AND desktop-1280, as a NAMED
    # person. Desktop-class rows were under 9% of the program when that wave was seeded, so the desktop half
    # is the half that gets dropped - which makes this the one guard whose absence would be invisible.
    _BOTH = "phone-390,desktop-1280"
    _sb = [{"step": "sign in as assistive-tech", "viewport": "phone-390", "fit": {"findings": 0}},
           {"step": "reach alert-hub", "viewport": "desktop-1280", "fit": {"findings": 0}}]
    _phone_only = [_sb[0]]

    def _lxp_refused(w4, steps):
        try:
            build_receipt("LXP1", "playwright-mcp + postgres-mcp", "normal", "Gloria Tan",
                          steps, "note", "2026-09-30T00:00:00Z", w4=w4)
            return False
        except ValueError:
            return True

    _lxp_cases = [
        ("an LXP receipt with no --layer", {"as_persona": "assistive-tech", "viewports": _BOTH}, _sb, True),
        ("an LXP receipt with no --as-persona", {"layer": "AU", "viewports": _BOTH}, _sb, True),
        ("an LXP receipt declaring one viewport",
         {"layer": "AU", "as_persona": "assistive-tech", "viewports": "phone-390"}, _sb, True),
        ("an LXP receipt declaring both but WALKING phone-only",
         {"layer": "AU", "as_persona": "assistive-tech", "viewports": _BOTH}, _phone_only, True),
        ("a complete LXP receipt",
         {"layer": "AU", "as_persona": "assistive-tech", "viewports": _BOTH}, _sb, False),
    ]
    for _label, _w4, _steps, _want in _lxp_cases:
        if _lxp_refused(_w4, _steps) != _want:
            fails.append(f"{_label} was {'accepted' if _want else 'refused'} - the LXP guard does not bite")

    print("FAIL record_mcp_walk self-test - " + "; ".join(fails) if fails
          else "self-test OK: a full walk passes; a 69-char step, a lost identity, an empty walk and an "
               "unknown instrument are each refused or reddened, an --unproven walk cannot read green, and "
               "every instrument live_walk_manifest.MARKERS can demand is one this recorder can write, and "
               "an LXP receipt is refused without its layer, its persona, or STEPS at both viewports")
    return 1 if fails else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(_self_test())
    raise SystemExit(main())
