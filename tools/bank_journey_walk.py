#!/usr/bin/env python3
"""bank_journey_walk.py — turn a full-journey walk into per-row bank entries (2026-09-07, W3-JN).

`tools/prove_full_journeys.mjs` writes one record per story: which steps arrived, how the thread between
them was found (the page's own link, the nav hub, or nothing), whether the identity survived, and what the
archetype's chain read AS the person. This tool writes each record into the row's basis through
`advance_trajectory.py` - which stays the only writer of status and basis - so a row's evidence is the walk
that produced it, in its own words, and never a sentence typed by hand.

★A ROW IS ONLY BANKED FROM ITS OWN WALK. A story whose steps did not arrive, whose pages never finished
rendering, or whose chain could not be READ is NOT banked: those are findings about the host, the login or
the database, and banking them as journeys would be exactly the false green this program exists to refuse.

★AND THERE ARE THREE OUTCOMES, NOT TWO (2026-09-09). A story the HOST never let us ask is neither a pass nor
a failure. When the local auth server answers `WH_DB_TIMEOUT` under load, the platform was never asked
anything: banking that green would be a false claim, and holding it as a finding would be a false accusation
against working code. Such a row is UNRUN — printed, counted apart, banked neither way, and clearable only
by walking it again on a quiet machine. It is not a skip, because it can never turn green by being ignored.

  python tools/bank_journey_walk.py .tmp/full_journeys_J2_tierA.json --dry-run
  python tools/bank_journey_walk.py .tmp/full_journeys_J2_tierA.json --status locking --pct 60
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def basis_for(r: dict, pct: str = "60", doc_tool: str = "") -> str:
    m = r.get("metrics") or {}
    # ★AN MCP RECEIPT NAMES ITS OWN INSTRUMENT (Wave 4, 2026-09-14). tools/record_mcp_walk.py writes the
    # same result shape with `instrument: playwright-mcp | chrome-devtools-mcp`, a free-text `note` and, for
    # a W4 row, a `w4` block (axis, hub_controls, effect, layer, fixture_provenance) with `fit` - the per-step
    # overlap/occlusion record - on every step. The first dry-run of this banker on such a receipt composed
    # "WALKED LIVE via tools/prove_full_journeys.mjs - the whole story None tier None in None" - a basis that
    # names an instrument that never ran and prints None for fields the receipt never had. A basis is the
    # row's account of its own evidence; it must be written from the evidence the receipt actually carries.
    if r.get("instrument"):
        w4 = r.get("w4") or {}
        steps = r.get("steps") or []
        fits = [s.get("fit") for s in steps if isinstance(s.get("fit"), dict)]
        findings = sum(int((f or {}).get("findings") or 0) for f in fits)
        # ★A SOURCE-LEVEL WITNESS IS NOT A JOURNEY, AND MUST NOT BE WRITTEN UP AS ONE (2026-09-16).
        # The layer provers are explicitly "proven at source (no browser)": they read the page's own
        # code and state a witness. Composed by the branch below, one of them read "1/4 steps arrived
        # as themselves (index.html -> hive.html -> alert-hub.html -> analytics.html); the identity
        # held across every hop; 0 per-step overlap/occlusion records" - for evidence that is one
        # regex over a file. No page was loaded and no hop was made; "0 occlusion records" is what a
        # browser that never ran reports. The receipt was honest (instrument postgres, cast
        # "(source-level)"); the write-up was not.
        # The test is STRUCTURAL: a real MCP walk carries a `fit` on every step - bank_mcp_navhub_walk
        # refuses a steps file without one - and a source-level receipt carries none, plus a witness.
        # Naming the prover keeps the row closable and honest at once: LIVE_RE matches
        # `tools/(prove|probe)_...` and MARKERS["playwright"] lists the prefix `prove_`.
        witness = str(w4.get("witness") or "").strip()
        if not fits and witness:
            where = " · ".join(x for x in (
                f"layer {w4['layer']}" if w4.get("layer") else "",
                f"axis {w4['axis']}" if w4.get("axis") else "",
                f"read as {r['cast']}" if r.get("cast") else "",
            ) if x)
            tool = str(r.get("_tool") or doc_tool or "tools/prove_w4_layer_*.py")
            return (f"pct -> {pct}. PROVEN AT SOURCE {date.today().isoformat()} via {tool} - no browser, "
                    f"no journey: this row's evidence is the page's own code and served bytes, read "
                    f"directly. {where}. WITNESS: {witness}")
        extras = " · ".join(x for x in (
            f"axis {w4['axis']}" if w4.get("axis") else "",
            f"nav-hub controls {w4['hub_controls']}/11" if w4.get("hub_controls") else "",
            f"effect: {w4['effect']}" if w4.get("effect") else "",
            f"layer {w4['layer']} provoked" if w4.get("layer") else "",
            f"file provenance: {w4['fixture_provenance']}" if w4.get("fixture_provenance") else "",
            # the design lenses (2026-09-15): the lens, both viewports, the detector file, the scores, the Figma nodes
            f"design lens {w4['lens']} at {' + '.join(w4.get('viewports') or [])}" if w4.get("lens") else "",
            f"detector {w4['detector']}" if w4.get("detector") else "",
            f"scores {json.dumps(w4['scores'], ensure_ascii=False)}" if w4.get("scores") else "",
            f"languages {'+'.join(w4.get('languages') or [])}" if w4.get("lens") == "copy" else "",
            f"figma-mcp: {w4['figma']}" if w4.get("figma") else "") if x)
        return (f"pct -> {pct}. WALKED LIVE {date.today().isoformat()} via {r['instrument']} (tools/record_mcp_walk.py) - "
                f"{m.get('arrived', 0)}/{m.get('steps', 0)} steps arrived as themselves "
                f"({' -> '.join(s.get('page', '?') for s in steps)}); the identity "
                f"{'held across every hop' if m.get('idKept') else 'did NOT survive the hops'}; "
                f"{len(fits)} per-step overlap/occlusion records, {findings} finding(s)"
                + (f"; {extras}" if extras else "")
                + (f". {r.get('note')}" if r.get('note') else ""))
    j = f"{r.get('archetype')} tier {r.get('tier')} in {r.get('vertical')}"
    cell = f"{r.get('device')} · {r.get('language')} · {r.get('condition')}"
    thread = (f"{m.get('own', 0)} hop(s) carried the next page in the page's own body, "
              f"{m.get('hubOnly', 0)} only through the nav hub, {m.get('none', 0)} not at all")
    # the chain count is None when the database could not be asked - a basis must never print "read None
    # as the person" as though that were a measurement (and such a row is held back anyway)
    eff = m.get("effect")
    chain = f"the archetype's chain read {eff} row(s) as the person" if isinstance(eff, int) \
        else "the archetype's chain could not be read"
    # ★THE BASIS MUST DECLARE THE PCT IT IS BEING BANKED AT. advance_trajectory.py enforces that a row's
    # written reason and its number agree - "a percentage without a basis is a vibe" - so a basis that opens
    # "pct -> 100" while the row is banked at 60 is refused, correctly. The prefix follows the argument.
    return (f"pct -> {pct}. WALKED LIVE {date.today().isoformat()} via tools/prove_full_journeys.mjs — the whole story {j} "
            f"({cell}), {len(r.get('pages') or [])} pages in one browser context: "
            f"{m.get('arrived', 0)}/{m.get('steps', 0)} steps arrived as themselves; {thread}; "
            f"the identity {'held across every hop' if m.get('idKept') else 'did NOT survive the hops'}; "
            f"{chain} ({' -> '.join(r.get('pages') or [])}).")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--status", default="locking")
    ap.add_argument("--pct", default="60")
    ap.add_argument("--gate", default="full-journeys")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    doc = json.loads(Path(a.results).read_text(encoding="utf-8"))

    # ★A STORY THE HOST NEVER LET US ASK IS NEITHER A PASS NOR A FAILURE. `WH_DB_TIMEOUT` from the local
    # auth server is this MACHINE under load, not the platform refusing — measured 2026-09-09, it appeared
    # the moment a second node process ran beside the walk. Banking it green would be a false claim; holding
    # it as a finding would be a false accusation. It is UNRUN: reported loudly, banked neither way, and
    # clearable only by walking it again on a quiet machine. Read here as well as in the prover, so a
    # results file written by an older run is classified the same way as a fresh one.
    # the reason is not always the first thing inside the bracket: the real note reads
    # "the cast could not sign in (auth: WH_DB_TIMEOUT)", and a pattern anchored to "(" missed every one
    HOST = re.compile(r"could not sign in \([^)]*(WH_DB_TIMEOUT|timeout|timed out|fetch failed|ECONN|socket hang up|50[234]|threw:|is not a function|undefined is not|Cannot read prop|Execution context|Target closed|detached)", re.I)

    # a chain the database never answered is the same host fact in different words, and it lands in
    # `problems` rather than `notes` - so a results file written before the prover learned this is still
    # classified correctly here, without needing the walk repeated
    CHAIN = re.compile(r"the chain could not be READ \(the database did not answer\)", re.I)

    def unrun(r):
        return (bool(r.get("unbuilt"))
                or any(HOST.search(n or "") for n in (r.get("notes") or []))
                or any(CHAIN.search(p or "") for p in (r.get("problems") or [])))

    # ★A PASS EARNED BY AN ADMIN IS NOT A PASS FOR THIS JOURNEY'S CAST (2026-09-09, J27). Three casts walked
    # the same dispute story: both ordinary supervisors stopped at marketplace.html with no way onward to
    # platform-actions.html, and the one that sailed through was a marketplace platform admin. The gating is
    # correct - that surface IS an admin's - but the green says only "an admin can walk it", and this row is
    # cast for a buyer. Held rather than banked, with the reason on the row, so a reader can tell "the
    # platform works for a buyer" from "the platform works for the person who can see everything".
    ADMIN = re.compile(r"who is a marketplace platform admin", re.I)

    def admin_cast(r):
        return any(ADMIN.search(n or "") for n in (r.get("notes") or []))

    rows = doc["results"]
    skipped = [r for r in rows if unrun(r)]
    admin_only = [r for r in rows if not unrun(r) and r.get("ok") and admin_cast(r)]
    ok = [r for r in rows if not unrun(r) and r.get("ok") and not admin_cast(r)]
    held = [r for r in rows if not unrun(r) and not r.get("ok")]
    if admin_only:
        print(f"  {len(admin_only)} pass(es) HELD because the cast is a platform admin - re-walk as the "
              f"journey's own persona before banking:")
        for r in admin_only:
            print(f"    admin {r['id']:<8} {str(r.get('vertical'))[:28]:<29} {'; '.join(r.get('notes') or [])[:100]}")
    print(f"  {len(ok)} bankable · {len(held)} held back (each keeps its findings, none is banked green)"
          f" · {len(skipped)} UNRUN (the host never let the cast sign in — re-walk, never bank)")
    for r in skipped:
        print(f"    unrun {r['id']:<8} {str(r.get('vertical'))[:28]:<29} {'; '.join(r.get('notes') or [])[:110]}")
    for r in held:
        print(f"    hold {r['id']:<8} {str(r.get('vertical'))[:28]:<29} {'; '.join(r.get('problems') or [])[:120]}")
    if not ok:
        print("  nothing to bank — a walk that found problems is a walk that found problems")
        return 0
    for r in ok:
        cmd = [sys.executable, str(ROOT / "tools" / "advance_trajectory.py"), "--id", r["id"],
               "--status", a.status, "--pct", a.pct, "--gate", a.gate, "--basis", basis_for(r, a.pct)]
        if a.dry_run:
            print(f"    bank {r['id']:<8} {basis_for(r, a.pct)[:150]}")
            continue
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(f"    {'ok  ' if p.returncode == 0 else 'FAIL'} {r['id']:<8} {(p.stdout or p.stderr).strip()[:110]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
