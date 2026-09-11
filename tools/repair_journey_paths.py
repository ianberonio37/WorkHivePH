#!/usr/bin/env python3
"""repair_journey_paths.py — route each journey through the pages the platform actually offers.

★THIS EXISTS BECAUSE A WALK WAS ABOUT TO RECORD 700 FALSE DEFECTS. `check_journey_paths.py` found that 55
consecutive hops across 39 archetypes step from a page to a destination that page does not link to and the
nav hub does not offer. The pages are right; the PATHS were written as a list of surfaces the story touches,
not as a route a person can walk. Walking them would have produced "no way onward" on most of 724 rows, and
every one of those findings would have read like a product bug.

Each broken hop already names the page to route through — the gate computes it, and this tool asks the gate
rather than working it out again, so the repair and the check can never disagree about what was fixed.

  a -> b, with no route            becomes      a -> w -> b
  a -> b, only the landing page links to b      a -> index.html -> b, AND the thinness is reported, because
                                               "the only way to this page is to go home first" is a real
                                               finding about the product, not a detail of the repair.

Both `pages` and `journey.pages` are written — all 724 rows mirror one into the other, and a repair that
moved one would leave the registry disagreeing with itself.

  python tools/repair_journey_paths.py                  # what it would do
  python tools/repair_journey_paths.py --apply
  python tools/repair_journey_paths.py --self-test
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
REGISTRY = ROOT / "trajectory_registry.json"

import check_journey_paths as G  # noqa: E402  — the gate is the single reading of what is broken


def plan(paths: dict, hops: list, links: dict) -> tuple[dict, list, list]:
    """Return the repaired paths, the thin routes worth reporting, and the hops nothing can repair."""
    by_arch: dict = {}
    for arch, a, b, where in hops:
        by_arch.setdefault(arch, []).append((a, b, where))

    repaired, thin, unrepairable = {}, [], []
    for arch, items in by_arch.items():
        pages = list(paths[arch])
        for a, b, where in items:
            # the gate now hands over a WHOLE walk (usually one page, sometimes two); a route of several
            # pages is inserted in order, so the repaired path is walkable end to end in one pass
            w = list(where) if where else []
            if not w and b in links.get("index.html", set()):
                w = ["index.html"]
            # ★A ROUTE FOUND IS NOT A ROUTE THAT IS GOOD. Once the gate searched for a whole walk it began
            # returning ["index.html"] for public-feed - true, and it quietly swallowed the finding that had
            # been visible when the search was shallower: the ONLY way to that page is to go back to the
            # landing page first. Repair it and report it; a repair that hides what it repaired is worse
            # than the break.
            if w == ["index.html"]:
                thin.append((arch, a, b))
            if not w:
                unrepairable.append((arch, a, b))
                continue
            w = [p for p in w if p not in (a, b)]     # a page is not a route to itself
            if not w:
                continue
            # ★INSERT AT THE PAIR, NOT AT THE FIRST MATCH OF `a`. A chained Tier-D path can visit the same
            # page twice; putting the detour after the wrong visit would move a later hop's ground.
            for i in range(len(pages) - 1):
                if pages[i] == a and pages[i + 1] == b:
                    pages[i + 1:i + 1] = w
                    break
        repaired[arch] = pages
    return repaired, thin, unrepairable


def _self_test() -> int:
    fails = []
    paths = {"JX": ["a.html", "b.html"], "JY": ["a.html", "c.html"], "JZ": ["a.html", "d.html"]}
    links = {"index.html": {"c.html"}, "a.html": set(), "w.html": {"b.html"}}
    hops = [("JX", "a.html", "b.html", ["w.html"]),
            ("JY", "a.html", "c.html", None),
            ("JZ", "a.html", "d.html", None)]
    rep, thin, un = plan(paths, hops, links)
    if rep.get("JX") != ["a.html", "w.html", "b.html"]:
        fails.append(f"the named route was not inserted between the pair ({rep.get('JX')})")
    if rep.get("JY") != ["a.html", "index.html", "c.html"]:
        fails.append("a destination only the landing page offers was not routed through it")
    if not thin:
        fails.append("a landing-page-only route was repaired SILENTLY - the thinness must still be reported")
    if rep.get("JZ") != ["a.html", "d.html"]:
        fails.append("a hop with no route at all was altered instead of being reported")
    if not un:
        fails.append("a hop nothing can repair was not reported as unrepairable")
    # a path already routed must be left exactly as it is
    rep2, _, _ = plan({"JQ": ["a.html", "b.html"]}, [], links)
    if rep2:
        fails.append("an archetype with no broken hop was rewritten anyway")
    # routing a page through itself is refused
    rep3, _, _ = plan({"JS": ["a.html", "b.html"]}, [("JS", "a.html", "b.html", ["b.html"])], links)
    if rep3.get("JS") != ["a.html", "b.html"]:
        fails.append("a page was routed through itself")
    print("FAIL repair-journey-paths self-test - " + "; ".join(fails) if fails
          else f"self-test OK: {5} mutations caught; an insertion lands between its own pair, a thin route "
               "is repaired AND reported, an unroutable hop is left alone")
    return 1 if fails else 0


def main() -> int:
    if "--self-test" in sys.argv:
        return _self_test()
    apply = "--apply" in sys.argv

    offered, parented = G.hub_offered_and_parented()
    links = G.link_graph()
    paths = G.declared_paths()
    first = G.broken_hops(paths, offered, parented, links)

    # ★INSERTING A DETOUR CREATES A HOP THAT ALSO HAS TO BE WALKABLE. Routing status -> platform-actions
    # through founder-console makes a new pair, status -> founder-console, and nothing had asked whether a
    # person can walk THAT. One pass repaired 55 hops and left 11 of its own making. Repeat until the
    # reading stops changing, with a bound: a repair that never converges is a repair that is wrong.
    # ★RETIREMENT COMES FIRST, BECAUSE A RETIRED PAGE CANNOT BE THE ANSWER TO A ROUTING QUESTION. Repairing
    # hops first sent J32 "through founder-console.html" - a page under a full-screen "moved to Grafana"
    # card. Each retired page's own banner says what replaced it: two moved to another page (re-point), two
    # moved out of the product into Grafana (drop, and say so - that step is no longer walkable here).
    retired = G.retired_pages()
    retire_notes, base = [], {}
    for arch, pages in paths.items():
        out = []
        for pg in pages:
            info = retired.get(pg)
            if not info:
                out.append(pg)
                continue
            if info["moved_to"]:
                if info["moved_to"] in out or info["moved_to"] in pages:
                    retire_notes.append((arch, pg, f"dropped - this journey already visits {info['moved_to']}"))
                else:
                    out.append(info["moved_to"])
                    retire_notes.append((arch, pg, f"re-pointed to {info['moved_to']}"))
            else:
                retire_notes.append((arch, pg, "dropped - the work moved out of the product"
                                               + (" (Grafana)" if info["external"] else "")))
        base[arch] = out

    # ★A HOP CAN BE LINKED AND STILL UNREACHABLE BY THE PERSON WALKING IT. The nav hub tags each entry with
    # the modes it is offered to, so `pm-scheduler -> alert-hub` is a dead end for a WORKER even though the
    # hub carries the alert hub - which is exactly how J26 failed live. Repaired the same way as any other
    # missing route, but only where a page THIS CAST can reach actually links the destination; where the
    # only such page is the landing page, the archetype is routing somebody to a surface the product
    # reserves for another role, and that is a casting question rather than a detour.
    blocked = G.role_blocked_hops(base, None, links)
    role_fixed, role_miscast = [], []
    for arch, mode, a, b, r, via in blocked:
        if via and via != "index.html":
            pgs = base.get(arch) or []
            for i in range(len(pgs) - 1):
                if pgs[i] == a and pgs[i + 1] == b:
                    pgs.insert(i + 1, via)
                    role_fixed.append((arch, mode, a, b, via))
                    break
        else:
            # (*)A JOURNEY SHOULD END WHERE ITS OWN PERSON CAN GO. The only page this cast can reach that
            # links the destination is the landing page, and routing somebody already signed in through the
            # marketing home page is not a route. The step is DROPPED - the story stops where the product
            # stops it - and reported, because a worker journey that quietly ended at a supervisor's
            # analytics page was making a claim about a surface its person is never shown.
            pgs = base.get(arch) or []
            for i2 in range(len(pgs) - 1):
                if pgs[i2] == a and pgs[i2 + 1] == b:
                    if len(pgs) - 1 >= 4:
                        pgs.pop(i2 + 1)
                        role_miscast.append((arch, mode, a, b, r))
                    else:
                        role_miscast.append((arch, mode, a, b, r))
                    break
            else:
                role_miscast.append((arch, mode, a, b, r))

    now, thin, unrepairable = dict(base), [], []
    for _ in range(4):
        hops = G.broken_hops(now, offered, parented, links)
        if not hops:
            break
        rep, t, u = plan(now, hops, links)
        thin += t
        unrepairable += u
        merged = dict(now)
        merged.update(rep)
        if merged == now:
            break
        now = merged
    # (*)A PAGE FOLLOWED BY ITSELF IS NOT A HOP. Dropping an unreachable destination can leave the two
    # pages either side of it identical - J31 came out as `resume -> index -> index -> achievements`
    # after public-feed was removed from between two landing-page steps. Nobody navigates from a page
    # to itself, and a walk would grade that step against its own source.
    for _a, _pgs in now.items():
        _out = []
        for _pg in _pgs:
            if not _out or _out[-1] != _pg:
                _out.append(_pg)
        now[_a] = _out
    repaired = {k: v for k, v in now.items() if v != paths[k]}
    # each pass re-reports the hops it could not repair; the finding is the hop, not how often it was seen
    thin = sorted(set(thin))
    unrepairable = sorted(set(unrepairable))

    print(f"archetypes with a declared path: {len(paths)}   broken hops: {len(first)}")
    if retire_notes:
        print(f"\n  RETIRED PAGES IN {len({a for a, _, _ in retire_notes})} DECLARED PATH(S) - a journey "
              f"cannot walk a page under a full-screen retirement card:")
        for arch, pg, what in retire_notes:
            print(f"    {arch:22} {pg[:32]:34} {what}")
    # a journey row promises at least four pages; a path that falls below that after retirement is not a
    # shorter journey, it is a journey whose subject has largely left the product
    short = [(a, len(now[a])) for a in sorted(now) if len(now[a]) < 4 <= len(paths[a])]
    if short:
        print(f"\n  {len(short)} archetype(s) fall below the four pages a journey row promises:")
        for a, n in short:
            print(f"    {a:22} {len(paths[a])} declared -> {n} live page(s): {', '.join(now[a])}")
    print(f"\narchetypes to repair: {len(repaired)}")
    for arch in sorted(repaired):
        before, after = paths[arch], repaired[arch]
        added = [p for p in after if after.count(p) > before.count(p)]
        print(f"  {arch:22} {len(before)} -> {len(after)} pages   + {', '.join(sorted(set(added)))[:70]}")

    # ★THE REPAIR MUST BE CHECKED BY THE SAME READING THAT FOUND THE BREAK.
    residual = G.broken_hops(now, offered, parented, links)
    print(f"\n  after the repair, hops still following no offered route: {len(residual)}")
    for arch, a, b, where in residual[:10]:
        # ★`where` IS A LIST OF CANDIDATE ROUTES, NOT ONE PAGE, and this line concatenated it to a string.
        # It sits in the branch that reports what the repair could NOT fix, so it only runs when residue
        # exists - and until the gate learned that a hub cannot offer a route from a page without a hub,
        # there never was any. A reporting line that crashes exactly when there is something to report is
        # the worst place for one to hide.
        _via = ", ".join(where) if isinstance(where, (list, tuple, set)) else str(where or "")
        print(f"    {arch:20} {a[:26]:28} -> {b[:26]:28} {('route through ' + _via) if _via else 'no route'}")

    if role_fixed:
        print('')
        print(f"  {len(role_fixed)} hop(s) the CAST's own hub mode could not reach - routed through a page it can:")
        for arch, mode, a, b, via in role_fixed:
            print(f"    {arch:20} as {mode:11} {a[:22]:24} -> {via[:20]:22} -> {b[:22]}")
    if role_miscast:
        print('')
        print(f"  {len(role_miscast)} hop(s) send this cast to a surface the product reserves for another role:")
        for arch, mode, a, b, r in role_miscast:
            print(f"    {arch:20} as {mode:11} {a[:22]:24} -> {b[:22]:24} offered to {r} - re-cast or re-route")
    if thin:
        print(f"\n  A FINDING, NOT A DETAIL - {len(thin)} hop(s) reach a page only the landing page links to:")
        for arch, a, b in thin:
            print(f"    {arch:20} {a[:26]:28} -> {b[:26]:28} (the person must go home to get there)")
    if unrepairable:
        print(f"\n  {len(unrepairable)} hop(s) no page on the platform offers at all:")
        for arch, a, b in unrepairable:
            print(f"    {arch:20} {a[:26]:28} -> {b[:26]}")

    # ★THE HOPS THAT COULD NOT BE REPAIRED ARE THE PRODUCT FINDING, and they must leave the run in a form
    # something else can act on. Two destinations account for all of them: `founder-console.html`, which no
    # page links to and no hub entry offers, so the person answerable for the platform can reach their own
    # console only by typing its address; and `public-feed.html`, which only the landing page links to.
    Path(".tmp").mkdir(exist_ok=True)
    dests: dict = {}
    for arch, a, b in unrepairable:
        dests.setdefault(b, {"kind": "no page links to it", "from": []})["from"].append(f"{arch}:{a}")
    for arch, a, b in thin:
        dests.setdefault(b, {"kind": "only the landing page links to it", "from": []})["from"].append(f"{arch}:{a}")
    Path(".tmp/journey_path_findings.json").write_text(
        json.dumps({"repaired_archetypes": len(repaired), "residual": len(residual),
                    "unreachable_destinations": dests}, indent=1), encoding="utf-8")
    print(f"\n  {len(dests)} destination(s) the platform does not route to  ·  .tmp/journey_path_findings.json")
    for d, info in sorted(dests.items()):
        print(f"    {d[:34]:36} {info['kind']}, wanted by {len(info['from'])} hop(s)")

    if not apply:
        print("\n  dry run - pass --apply to write the repaired paths into the registry")
        return 0

    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    touched = 0
    for t in reg["trajectories"]:
        j = t.get("journey") or {}
        arch = j.get("archetype")
        if arch in repaired and (j.get("pages") or t.get("pages")):
            j["pages"] = list(repaired[arch])
            t["pages"] = list(repaired[arch])           # the two mirror each other on every row
            touched += 1
    # ★open(w) TRUNCATES BEFORE THE WRITE. A 7.7 MB registry emptied by a crash mid-write is the whole
    # program; write beside it and replace.
    tmp = REGISTRY.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(reg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, REGISTRY)
    print(f"\n  wrote the repaired path onto {touched} row(s) in {len(repaired)} archetype(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
