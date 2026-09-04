#!/usr/bin/env python3
"""journey-na-is-earned - a NOT-MEASURED journey cell must have had nothing to measure (2026-08-27, T29).

prove_journey ranks a page's outgoing links (a link carrying a query param is the most interesting
handoff, a labelled navigation next, the bare logo-to-home link last), then walks the winner and
checks it landed where it promised. It picked that winner with a `reduce` over ALL candidates and
only afterwards asked whether the winner was in the roster - declaring the WHOLE cell not-measured
when it was not.

So hive, which carries THIRTEEN in-app links including pm-scheduler, inventory, logbook and
alert-hub, recorded "no usable in-app link to another product page" because an off-roster
marketplace-seller link outranked all of them. skillmatrix and community reported the same, and the
roadmap carried the result as owed product work - "no usable in-app link" reads like a page with no
wayfinding, so the fix looks like adding links that were already there. Nine persona-cells across
three pages were excluded from the denominator by an instrument, not by the product.

That is a fallback chain that gives up after one link ([[feedback_a_fallback_chain_needs_the_whole_chain]])
and an exclusion that silently shrinks coverage ([[feedback_four_exclusions_shrank_the_denominator]]).
The prover now filters candidates to the roster BEFORE choosing, and still prefers the richest link:
skillmatrix walks "Achievements ->" rather than the logo.

THE INVARIANT THIS LOCKS: a handoff cell may be declared not-measured only when NO candidate was in
the roster. The N/A message itself lists the candidate files, so the artifact carries everything
needed to check it - no browser, no re-walk. Run against the pre-fix report, this fails on all three
pages naming a roster page among their candidates, which is the teeth.

Self-test: `--selftest`.
"""
import io
import json
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "journey_report.json"
PROVER = ROOT / "tools" / "prove_journey.mjs"


def roster_from_prover() -> set:
    """Read the roster from the prover itself so the two can never drift apart.

    A hardcoded copy here would be a second source of truth, and the first thing to rot: the gate
    would keep passing against a roster the prover no longer uses.
    """
    src = io.open(PROVER, encoding="utf-8", errors="replace").read()
    m = re.search(r"const ROSTER = new Set\(\[(.*?)\]\)", src, re.S)
    if not m:
        return set()
    return set(re.findall(r"'([^']+)'", m.group(1)))


def scan(report: dict, roster: set) -> list:
    problems = []
    seen = set()

    def walk(node, page=None):
        if isinstance(node, dict):
            page = node.get("page", page)
            na = node.get("handoffNa")
            if na and (page, na) not in seen:
                seen.add((page, na))
                # the message spells the candidates as "to: a/b/c"
                m = re.search(r"to:\s*([A-Za-z0-9\-/_]+)", na)
                cands = set(m.group(1).split("/")) if m else set()
                reachable = sorted(cands & roster)
                if reachable:
                    n = len(reachable)
                    problems.append(
                        f"{page}: handoff declared not-measured, but "
                        f"{'1 of its candidates IS' if n == 1 else f'{n} of its candidates ARE'} "
                        f"in the roster ({', '.join(reachable)}) - the cell was walkable "
                        f"and got excluded")
            # ★THE SECOND CELL, SAME INVARIANT. abandonNa blamed the OPENER for every failed
            # click, so three cells read "the opener #fab-post never became clickable" - the exact
            # sentence a dead button produces, which cost a real investigation to disprove. All
            # three were anon personas REDIRECTED TO THE AUTH WALL: they never reached the page.
            # A control absent because the persona never arrived is not a control that is broken.
            ana = node.get("abandonNa")
            if ana and (page, ana) not in seen:
                seen.add((page, ana))
                blames_opener = "the opener" in ana and "never became clickable" in ana
                redirected = bool(node.get("redirectedTo")) or "redirected to" in json.dumps(node)[:2000]
                if blames_opener and redirected:
                    problems.append(
                        f"{page}: the abandon cell blames its opener for never becoming clickable, "
                        f"but this persona was redirected away - it never reached the page")
            for v in node.values():
                walk(v, page)
        elif isinstance(node, list):
            for v in node:
                walk(v, page)

    walk(report)
    return problems


def selftest() -> int:
    ok = True

    def chk(name, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  {name}: got {got}, want {want}")

    roster = roster_from_prover()
    chk("roster reads from the prover", ("hive" in roster and "pm-scheduler" in roster), True)

    # the exact shape the bug produced
    bad = {"page": "hive", "handoffNa": 'no usable in-app link to another product page '
           '(13 candidate(s), to: index/pm-scheduler/inventory/logbook/marketplace-seller/alert-hub; '
           'best was "marketplace-seller" which is not in the roster)'}
    chk("a roster page among the candidates fails", len(scan(bad, roster)), 1)

    # a genuinely unwalkable page: nothing it links to is in the roster
    good = {"page": "marketplace", "handoffNa": 'no usable in-app link to another product page '
            '(2 candidate(s), to: marketplace-seller/marketplace-admin; none of them in the roster, '
            'best was "marketplace-seller")'}
    chk("no roster candidate is an earned N/A", len(scan(good, roster)), 0)

    chk("a measured handoff is out of scope", len(scan({"page": "x", "handoff": {"ok": True}}, roster)), 0)

    # the abandon half
    blamed = {"page": "community", "redirectedTo": "index",
              "abandonNa": "the opener #fab-post never became clickable - the composer could not be opened"}
    chk("blaming the opener after a redirect fails", len(scan(blamed, roster)), 1)
    honest = {"page": "community", "redirectedTo": "index",
              "abandonNa": "this persona never reached community - it was sent to \"index\""}
    chk("naming the redirect is an earned N/A", len(scan(honest, roster)), 0)
    onpage = {"page": "resume",
              "abandonNa": "the opener #btn-resumes is present but disabled - the composer could not be opened"}
    chk("a genuinely stuck opener on the right page is earned", len(scan(onpage, roster)), 0)

    if REPORT.exists():
        live = scan(json.load(io.open(REPORT, encoding="utf-8")), roster)
        chk("the live report is clean", live, [])
    print(f"\n  SELFTEST: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    if not REPORT.exists():
        print("SKIP journey-na-is-earned - journey_report.json not present")
        return 0
    roster = roster_from_prover()
    if not roster:
        print("FAIL journey-na-is-earned - could not read ROSTER from prove_journey.mjs")
        return 1
    problems = scan(json.load(io.open(REPORT, encoding="utf-8")), roster)
    print("a not-measured handoff must have had nothing to walk")
    print(f"  roster pages: {len(roster)}  ·  unearned N/A cells: {len(problems)}")
    if not problems:
        print("\n  PASS - every handoff N/A had no roster-reachable link to walk.")
        return 0
    print("\n  FAIL - these cells were walkable and got excluded from the denominator:")
    for p in problems:
        print(f"    {p}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
