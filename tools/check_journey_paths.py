#!/usr/bin/env python3
"""check_journey_paths.py — does each journey archetype's path follow a route the platform actually offers?

★THIS EXISTS BECAUSE A SIX-HOUR WALK DISCOVERED IT. The first archetype of the tier-A drive, J4 (audit
season), failed in all six hives with "3 hop(s) have no way onward at all". The pages genuinely do not link
onward — and the product is right: `nav-hub.js` marks five destinations `hidden: true`, one with a comment
saying *"surfaced via the 'Audit Log' button on hive.html"*, and a sixth is not a hub entry at all. The
platform deliberately parents those pages. **The archetype's path skipped the route the platform intends.**

24 of the 32 archetypes touch such a destination, so the walk was on course to record a false navigation
defect against most of 724 rows. Every one of those findings would have looked like a product bug.

A path is answerable from files, in about a second, so it should never cost a walk to find out. For each
consecutive pair in an archetype's path this asks: does the earlier page LINK to the later one, or does the
nav hub OFFER it? If neither, and the destination is one the platform parents elsewhere, the PATH is wrong
and it says which page it should route through.

  python tools/check_journey_paths.py
  python tools/check_journey_paths.py --self-test
"""
from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "trajectory_registry.json"
HUB = ROOT / "nav-hub.js"
RETIRED: dict = {}          # filled once at start-up by retired_pages(); a retired page is never a route


def signed_out_only() -> set:
    """Destinations whose ONLY route is the landing page's marketing block, which a signed-in person never sees.

    ★A LINK CAN EXIST, BE VISIBLE, AND STILL BE UNREACHABLE BY THE PERSON WALKING. `index.html` carries
    `html.wh-signed-in #mkt-wrap{display:none !important}` - the whole marketing wrapper is hidden the moment
    somebody signs in - and BOTH of its links to `public-feed.html` live inside it. The landing page renders
    14,464 characters signed out and 1,197 signed in, which is the same fact measured from the other side.
    `nav-hub.js` states the intent plainly: "public-feed.html: public read-only page - linked from
    index.html, not the app nav". So the product is right and four journey archetypes were wrong to route a
    signed-in member there. This is not a link check; it is a check about who is looking.
    """
    try:
        src = (ROOT / "index.html").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    if not re.search(r"html\.wh-signed-in\s+#mkt-wrap\s*\{[^}]*display\s*:\s*none", src):
        return set()
    start = src.find('id="mkt-wrap"')
    if start < 0:
        return set()
    hidden = src[start:]
    out = set()
    for m in re.finditer(r'<a[^>]+href="([^"]+\.html)"', hidden):
        page = m.group(1).split("#")[0].split("?")[0].lstrip("/")
        # only counts if the landing page is its ONLY inbound link
        if sum(1 for p, outs in link_graph().items() if page in outs) <= 1:
            out.add(page)
    return out


def hub_roles() -> dict:
    """Which hub modes each destination is offered to: {'alert-hub.html': ['supervisor'], …}.

    ★THE HUB OFFERS A PAGE TO A MODE, NOT TO EVERYONE. `nav-hub.js` tags each entry
    `roles: ['field'|'supervisor'|'engineer']`, and a destination the cast's own mode is not offered is a
    destination that cast cannot reach from the drawer - which is exactly how J26 failed live: a worker on
    `pm-scheduler.html` with no link to `alert-hub.html` and a hub that shows it only to supervisors.
    """
    src = HUB.read_text(encoding="utf-8", errors="replace")
    out = {}
    for m in re.finditer(r"href:\s*'([^']+\.html)'", src):
        block = src[src.rfind("{", 0, m.start()):m.end() + 260]
        r = re.search(r"roles:\s*\[([^\]]*)\]", block)
        if r:
            roles = re.findall(r"'([a-z_]+)'", r.group(1))
            if roles:
                out[m.group(1)] = roles
    return out


# ★USE THE PROVER'S OWN CASTING RULE, NOT THE REGISTRY'S `persona` FIELD. This investigation reported 28
# broken hops, then 14, then 6, and each cut was a vocabulary correction rather than a fix: the hub's word
# for a worker is `field`, not `worker`; and a row whose persona reads "worker" is walked by the SUPERVISOR
# when its `pair` names one (prove_full_journeys.mjs casts on exactly this rule). Comparing the registry's
# word against the hub's word made the LOGBOOK look forbidden to the people who live in it.
_WANTS_SUP = re.compile(r"supervisor|oversight|owner|engineer|manager", re.I)
_PAIR_SUP = re.compile(r"supervisor|admin|oversight", re.I)


def cast_mode(row: dict) -> str:
    j = row.get("journey") or {}
    return ("supervisor" if _WANTS_SUP.search(row.get("persona") or "") or _PAIR_SUP.search(j.get("pair") or "")
            else "field")



def pages_carrying_the_hub() -> set:
    """Which pages actually LOAD nav-hub.js.

    ★THE HUB IS NOT ON EVERY PAGE, AND THIS GATE CREDITED IT EVERYWHERE. It read nav-hub.js for what the
    hub offers and then treated every hop as reachable if the hub offers the destination - without asking
    whether the page the person is STANDING ON carries the hub at all. Measured 2026-09-08: 32 of 42 root
    pages load it and ZERO of the learn articles and calculators do, which is the entire public funnel.
    So this gate reported "0 hops follow no route" while the live walk reported three with no way onward
    on exactly those pages, and the live one was right: on a page with no hub, the hub offers nothing.
    """
    out = set()
    for f in sorted(ROOT.glob("*.html")):
        try:
            if "nav-hub.js" in f.read_text(encoding="utf-8", errors="replace"):
                out.add(f.name)
        except OSError:
            pass
    for pat in ("learn/*/index.html", "tools/*/index.html"):
        for f in sorted(ROOT.glob(pat)):
            try:
                if "nav-hub.js" in f.read_text(encoding="utf-8", errors="replace"):
                    out.add(str(f.relative_to(ROOT)).replace("\\", "/"))
            except OSError:
                pass
    return out


_HUB_PAGES = None

def hub_offered_and_parented() -> tuple[set, dict]:
    """What the hub offers, and where it says the hidden ones live. Read, never typed."""
    src = HUB.read_text(encoding="utf-8", errors="replace")
    offered, parented = set(), {}
    for m in re.finditer(r"href:\s*'([^']+\.html)'", src):
        block_start = src.rfind("{", 0, m.start())
        block = src[block_start:m.end() + 200]
        if "hidden: true" not in block and "hidden:true" not in block:
            offered.add(m.group(1))
            continue
        before = src[max(0, block_start - 260):block_start]
        said = (re.search(r"surfaced via[^.\n]*?\bon\s+([a-z0-9-]+\.html)", before, re.I)
                or re.search(r"surfaced (?:from|on)\s+([a-z0-9-]+\.html)", before, re.I))
        if said:
            parented[m.group(1)] = said.group(1)
    return offered, parented


def link_graph(strip_scripts: bool = False) -> dict:
    """page -> the pages it links to, from one pass over the markup.

    ★THE GRAPH HAS TO COVER THE PAGES THE PATHS NAME. A first version read only root `*.html`, so every hop
    into `tools/<calc>/index.html` or `learn/<article>/index.html` came back "no page offers this destination
    at all" - a confident claim about pages the graph had never opened. A journey that ends at a calculator
    is a normal journey on this platform; the graph, not the path, was incomplete.
    """
    out = {}
    # ★THE SECTION INDEX IS NOT MATCHED BY `learn/*/index.html` - THERE IS NO DIRECTORY IN BETWEEN. So the
    # page that carries 56 of the platform's internal links was never opened as a SOURCE, and the graph
    # reported "learn/index.html links to nothing" while the file plainly links to every article. An earlier
    # fix had already taught the graph to recognise `/learn/` as a DESTINATION; being a destination and
    # being a source are two different memberships and only one of them had been granted.
    for pat in ("*.html", "tools/*/index.html", "learn/*/index.html", "learn/index.html", "tools/index.html"):
        for f in glob.glob(str(ROOT / pat)):
            p = Path(f)
            # ★KEY IT THE WAY THE PATHS NAME IT. The journey paths say "tools/oee-calculator/index.html";
            # keying by "oee-calculator/index.html" made every hop into a calculator or an article read as a
            # destination no page offers - a mismatch of spelling reported as a missing route.
            key = p.relative_to(ROOT).as_posix()
            try:
                src = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if strip_scripts:
                # ★THE PROVER STRIPS <script> BEFORE IT COUNTS A LINK, AND A CALLER THAT DECIDES ROUTES
                # MUST SEE WHAT THE PROVER SEES (2026-09-10). A link built inside a script fires only on
                # the condition its code carries, so prove_full_journeys.mjs ignores those when it works
                # out who parents a page. This graph did not, and a seeder repair that trusted it routed
                # index.html -> achievements.html on the strength of a SCRIPTED link the walk then
                # refused to credit. Off by default so the existing gate keeps its wider view; on for
                # anyone asking "what route can a person actually count on".
                src = re.sub(r'<script\b.*?</script>', '', src, flags=re.S | re.I)
            hrefs = set()
            for m in re.finditer(r'<a[^>]+href="([^"]+)"', src):
                h = m.group(1).split("#")[0].split("?")[0].strip("/")
                # ★THE PLATFORM LINKS TO A DIRECTORY, NOT TO index.html. Learn articles say
                # href="/tools/oee-calculator/" - the clean URL a reader sees - so a normaliser that demands
                # ".html" threw away every real link into a calculator or an article and then reported those
                # destinations as ones no page offers. Fold the directory form to the file the paths name.
                # a hub's own link is `/learn/`, which strips to the bare word - so the directory form has to
                # be recognised with and without a trailing segment, or the learn index looks unreachable
                # ★A LINK TO THE SITE ROOT IS A LINK TO THE LANDING PAGE, and stripping the slashes made
                # it the empty string, which was then dropped for not ending in ".html". Every public page
                # links home as href="/" or href="/#join" - so the graph reported the calculators offering
                # no route back into the product, and this gate listed a hop the LIVE walk credits. The
                # same understanding the walk's matcher was given the same afternoon, so the two
                # instruments read one link the same way.
                if h == "":
                    h = "index.html"
                elif h in ("tools", "learn"):
                    h = h + "/index.html"
                elif h.startswith(("tools/", "learn/")) and not h.endswith(".html"):
                    h = h.rstrip("/") + "/index.html"
                if not h.endswith(".html"):
                    continue
                # a root page is named by its file; a subpage by the path the journey paths use
                hrefs.add(h if h.startswith(("tools/", "learn/")) else h.split("/")[-1])
            out[key] = hrefs
    return out


def retired_pages() -> dict:
    """Pages whose whole surface is covered by the retirement overlay, and what replaced them.

    ★A RETIRED PAGE IS NOT A DESTINATION, AND ROUTING THROUGH ONE IS WORSE THAN NOT ROUTING AT ALL. The
    repair was about to send the founder's month-end THROUGH `founder-console.html` - a page whose entire
    surface is a fixed, full-screen "moved to Grafana" card at z-index 100000. Its own banner says so, and
    says where the work went: observability to Grafana, marketplace moderation to platform-actions.html.
    Three of J32's six declared pages are retired this way. Walking that journey would have reported an
    overlay as a broken product.

    The marker is the overlay's own `id=`, never a mention of it: `platform-actions.html` names
    `#wh-retired-overlay` in the comment explaining what it inherited, and is itself perfectly live.
    """
    out = {}
    for f in glob.glob(str(ROOT / "*.html")):
        p = Path(f)
        try:
            src = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if 'id="wh-retired-overlay"' not in src:
            continue
        m = re.search(r"RETIRED \(([^)]{0,80})\)", src)
        # ★THE BANNER SAYS WHERE THE WORK WENT, so read it rather than guessing. Two of these moved to
        # another PAGE ("moderation moved to platform-actions.html") and two moved OUT OF THE PRODUCT
        # ("are now Founder-Ops Grafana panels"). Those are different repairs: one journey step is
        # re-pointed, the other cannot be walked here at all and the journey has to say so.
        head = src[max(0, src.find("RETIRED (") - 40): src.find("RETIRED (") + 900]
        moved = re.search(r"moved to\s+([a-z0-9-]+\.html)", head, re.I)
        out[p.name] = {
            "why": m.group(1) if m else "retired",
            "moved_to": moved.group(1) if moved else None,
            "external": bool(re.search(r"\bGrafana\b", head, re.I)) and not moved,
        }
    return out


def _shortest_walk(a: str, b: str, links: dict, offered: set, limit: int = 3):
    """The shortest sequence of pages between a and b, or None if the platform offers no walk at all.

    An edge is "this page links there" OR "the shared nav hub offers it", because the hub is on every page
    - so a route may leave the article, use the hub to reach a section index, and carry on from there.
    """
    from collections import deque
    seen = {a}
    q = deque([(a, [])])
    while q:
        cur, via = q.popleft()
        if len(via) >= limit:
            continue
        for n in sorted((links.get(cur, set()) | offered) - RETIRED.keys() - seen - {a, b}):
            if b in links.get(n, set()):
                return via + [n]
            seen.add(n)
            q.append((n, via + [n]))
    return None


def declared_paths() -> dict:
    """Each archetype's declared path, taken once from the first row that carries it."""
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    paths = {}
    for t in reg["trajectories"]:
        j = t.get("journey") or {}
        arch = j.get("archetype")
        pages = j.get("pages") or t.get("pages") or []
        if arch and len(pages) > 1 and arch not in paths:
            paths[arch] = pages
    return paths


def declared_casts() -> dict:
    """Which hub mode each archetype is actually walked as — the same rule the journey prover applies."""
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    casts = {}
    for t in reg["trajectories"]:
        arch = (t.get("journey") or {}).get("archetype")
        if arch and arch not in casts:
            casts[arch] = cast_mode(t)
    return casts


def role_blocked_hops(paths=None, casts=None, links=None) -> list:
    """Hops whose destination the cast's own hub mode is not offered, and no page links either."""
    if paths is None:
        paths = declared_paths()
    if casts is None:
        casts = declared_casts()
    if links is None:
        links = link_graph()
    roles = hub_roles()
    outonly = signed_out_only()
    out = []
    for arch, pages in sorted(paths.items()):
        mode = casts.get(arch, "field")
        for a, b in zip(pages, pages[1:]):
            # a destination only a signed-OUT visitor can reach is unreachable to every cast here: each of
            # them is somebody with an account, and the landing page hides that section from them
            if b in outonly:
                out.append((arch, mode, a, b, ["signed-out visitors only"], None))
                continue
            r = roles.get(b)
            if not r or mode in r:
                continue
            if b in links.get(a, set()):
                continue                       # the page itself links there, so the hub's mode is moot
            # Somewhere this cast CAN reach that does link it. Ranked the way the rest of this file ranks a
            # detour: a page the journey already visits first (the person is going there anyway), then any
            # ordinary root page, and the landing page LAST - it links to everything and names nothing.
            cands = [p for p, outs in links.items()
                     if b in outs and p != a and p != b and (p not in roles or mode in roles[p])]
            cands.sort(key=lambda p: (p in pages) * 4 + ("/" not in p) * 2 + (p != "index.html"), reverse=True)
            out.append((arch, mode, a, b, r, cands[0] if cands else None))
    return out


def broken_hops(paths=None, offered=None, parented=None, links=None) -> list:
    """Every consecutive pair that follows no route the platform offers, with the page to route through.

    Extracted from main() so the REPAIR can use exactly the reading the gate uses. A repair tool that
    re-derived "which hops are broken" would be free to disagree with the gate about what it just fixed —
    the same shape as a guard that re-derives freshness instead of asking the gate.

    ★A NEGATIVE RESULT, KEPT SO IT IS NOT RE-DERIVED (2026-09-10). This gate and
    prove_full_journeys.mjs LOOK like they judge a hop differently - the gate passes as soon as `a`
    links to `b` at all, while the prover carries a stricter notion of who "parents" a destination and
    excludes index.html from it, because the landing page links to everything and so distinguishes
    nothing. Twice in one session that looked like a reach gap worth closing, and both times the
    MEASUREMENT was wrong before the code was (the first attempt also inherited a `learn/` exclusion
    that belongs to a signed-in career story, not to the public funnel, and manufactured nine
    findings). It is NOT a gap: the prover computes its `byDesign` complaint from `noThread` - steps
    that had NO way onward at all - so the parent rule only ever decides HOW to describe a hop that
    has already failed, never whether a hop carrying a real link fails. Measured across every declared
    path with the prover's own rule, exactly one apparent divergence remained,
    `index.html -> learn/what-is-oee...`, and it cannot fire because index.html links that article, so
    the step never reaches the parent test. Do not "align" these; they already agree.
    """
    if not RETIRED:
        RETIRED.update(retired_pages())
    if offered is None or parented is None:
        offered, parented = hub_offered_and_parented()
    offered = {p for p in offered if p not in RETIRED}
    if links is None:
        links = link_graph()
    if paths is None:
        paths = declared_paths()
    out = []
    for arch, pages in sorted(paths.items()):
        for a, b in zip(pages, pages[1:]):
            global _HUB_PAGES
            if _HUB_PAGES is None:
                _HUB_PAGES = pages_carrying_the_hub()
            # the hub can only offer a way onward from a page that HAS the hub
            if b in links.get(a, set()) or (b in offered and a in _HUB_PAGES):
                continue                                  # linked from the page, or offered by a hub that is on it
            where = parented.get(b)
            if where:
                out.append((arch, a, b, [where]))
                continue
            if True:
                # ★index.html LINKS TO EVERYTHING, so it wins every tie and names nothing useful. Rank a page
                # sharing the destination's stem first (project-manager -> project-report), then one the hub
                # offers, and the landing page last - the same ranking the journey prover needed.
                # ★THE LANDING PAGE IS THE ROOT index.html, NOT EVERY index.html. Detecting it by FILENAME
                # zeroed all eight learn articles and calculators that link to a calculator - every one of
                # them is `<slug>/index.html` too - so a destination with eight real routes was reported as
                # having none. And a subpath's stem is its DIRECTORY, not the word "index".
                stem = (b.split("/")[-2] if b.endswith("/index.html") and "/" in b
                        else b.split("/")[-1].replace(".html", "")).split("-")[0]

                # ★A SECTION REACHES ITS OWN PAGES THROUGH ITS OWN INDEX. Told to reach a calculator from
                # the logbook, the ranker offered a SIBLING CALCULATOR - the two link to each other - and
                # the repair then had to explain how the person reached the sibling. `tools/index.html` is
                # how this platform hands someone a calculator, and `learn/index.html` an article.
                section = (b.split("/")[0] + "/index.html") if "/" in b else None

                def rank(pg, _stem=stem, _path=pages, _section=section):
                    if pg == "index.html":
                        return 0                       # links to everything, names nothing
                    sub = "/" in pg
                    name = pg.split("/")[-2] if pg.endswith("/index.html") and sub else pg
                    # ★A JOURNEY SHOULD ROUTE THROUGH A PAGE IT ALREADY VISITS. The founder's month-end
                    # (J32) opens on founder-console and was told to reach platform-actions "through
                    # marketplace.html" - a surface that journey never touches - because marketplace also
                    # links there and nothing preferred the story's own pages. A detour through a page the
                    # person is already in is a route; a detour through a stranger is a new journey.
                    if pg in _path:
                        return 9 + (1 if pg in offered else 0)
                    if _section and pg == _section:
                        return 8
                    # ★A JOURNEY ROUTES THROUGH PRODUCT SURFACES, NOT THROUGH ARTICLES. Ranking on the stem
                    # alone suggested "route ph-intelligence through
                    # learn/ph-industrial-benchmarks-intelligence" - a page that merely shares three letters
                    # - where analytics.html is the surface a person would actually use. A root page outranks
                    # a subpage, and a stem match only breaks ties within the same kind.
                    return ((0 if sub else 2)
                            + (3 if name.startswith(_stem) else 0)
                            + (1 if pg in offered else 0) + 1)
                # ★A PAGE IS NOT A ROUTE TO ITSELF, AND NEITHER IS THE PAGE WE ARE LEAVING. `project-report`
                # carries a link to itself, so once "a page already in this journey" was preferred it won
                # its own detour and the hop stayed broken while reading as repaired.
                # ★A ROUTE IS A WALK, NOT A SINGLE HOP. Inserting one page between a and b makes a new pair
                # (a -> that page) that nobody had asked about, and repairing THAT made another: J30
                # ping-ponged between a calculator and the article that lists it, growing its path by two
                # pages every pass and never converging. What matters is the set of pages reachable FROM a
                # - everything a links to, plus everything the shared nav hub offers from any page - so the
                # answer is the SHORTEST WALK across that graph, found once and inserted whole.
                reach = (links.get(a, set()) | offered) - RETIRED.keys() - {a, b}
                one = sorted((p for p in reach if b in links.get(p, set())), key=rank, reverse=True)
                if one and rank(one[0]) > 0:
                    out.append((arch, a, b, [one[0]]))
                    continue
                where = _shortest_walk(a, b, links, offered)
            out.append((arch, a, b, where))
    return out


def retired_in_paths(paths: dict) -> list:
    """Archetypes whose declared path names a page that is retired behind the overlay."""
    if not RETIRED:
        RETIRED.update(retired_pages())
    return [(arch, pg, RETIRED[pg]["why"]) for arch, pages in sorted(paths.items())
            for pg in pages if pg in RETIRED]


def main() -> int:
    offered, parented = hub_offered_and_parented()
    links = link_graph()
    if not RETIRED:
        RETIRED.update(retired_pages())

    if "--self-test" in sys.argv:
        fails = []
        if "founder-console.html" not in RETIRED:
            fails.append("the retirement overlay is not detected on founder-console.html")
        if "platform-actions.html" in RETIRED:
            fails.append("a page that merely MENTIONS the overlay is being read as retired")
        if len(RETIRED) < 4:
            fails.append(f"only {len(RETIRED)} retired page(s) found; four carry the overlay")
        if not offered:
            fails.append("the hub offers nothing - nav-hub.js could not be read")
        if "audit-log.html" in offered:
            fails.append("a hidden hub entry is being counted as offered")
        if parented.get("audit-log.html") != "hive.html":
            fails.append(f"the hub's own comment was not read: audit-log -> {parented.get('audit-log.html')}")
        if not links.get("index.html"):
            fails.append("the link graph is empty for index.html")
        # ★TEETH FOR THE ROLE CLASS, WHICH READ 28 THEN 14 THEN 6 BEFORE IT WAS RIGHT. Each mutation below
        # is one of the three vocabulary errors that inflated it, so none of them can come back quietly.
        hr = hub_roles()
        if hr.get("alert-hub.html") != ["supervisor"]:
            fails.append(f"the hub's roles are not being read: alert-hub -> {hr.get('alert-hub.html')}")
        if "field" not in (hr.get("logbook.html") or []):
            fails.append("the logbook reads as closed to a field worker - the hub's word for a worker is 'field'")
        if cast_mode({"persona": "worker", "journey": {}}) != "field":
            fails.append("a worker is not mapped to the hub's 'field' mode")
        if cast_mode({"persona": "worker", "journey": {"pair": "worker x supervisor"}}) != "supervisor":
            fails.append("a paired row is not cast as the SUPERVISOR, which is how the journey prover walks it")
        if cast_mode({"persona": "oversight", "journey": {}}) != "supervisor":
            fails.append("an oversight persona is not cast as a supervisor")
        _blk = role_blocked_hops({"JT": ["logbook.html", "alert-hub.html"]}, {"JT": "field"},
                                 {"logbook.html": set()})
        if not _blk:
            fails.append("a field cast routed to a supervisor-only destination is not caught")
        if role_blocked_hops({"JT": ["logbook.html", "alert-hub.html"]}, {"JT": "supervisor"},
                             {"logbook.html": set()}):
            fails.append("a SUPERVISOR cast is being blocked from a supervisor-only destination")
        if role_blocked_hops({"JT": ["logbook.html", "alert-hub.html"]}, {"JT": "field"},
                             {"logbook.html": {"alert-hub.html"}}):
            fails.append("a hop the page itself LINKS is being called role-blocked")
        if len(links.get("learn/index.html") or ()) < 20:
            fails.append(f"the learn index reads as linking to {len(links.get('learn/index.html') or ())} "
                         "page(s); it carries a link to every article and must be read as a SOURCE")
        print("FAIL journey-paths self-test - " + "; ".join(fails) if fails
              else f"self-test OK: hub offers {len(offered)}, {len(parented)} parented by its own comment, "
                   f"link graph over {len(links)} page(s)")
        return 1 if fails else 0

    paths = declared_paths()
    broken = broken_hops(paths, offered, parented, links)

    if "--json" in sys.argv:
        dest = sys.argv[sys.argv.index("--json") + 1]
        Path(dest).parent.mkdir(exist_ok=True)
        Path(dest).write_text(json.dumps(
            {"archetypes": len(paths),
             "broken": [{"archetype": arch, "from": a, "to": b, "route_through": w} for arch, a, b, w in broken]},
            indent=1), encoding="utf-8")
        print(f"  {len(broken)} broken hop(s) written to {dest}")

    # the report prints the platform's own arrows (→); on a cp1252 console that raised UnicodeEncodeError
    # and the gate died mid-report (2026-09-14, the first wave-4 seed) - a gate that crashes while
    # explaining a real finding is a gate whose finding nobody reads
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    retired_hits = retired_in_paths(paths)
    if retired_hits:
        print(f"journeys declared across a RETIRED page: {len(retired_hits)} "
              f"({len({a for a, _, _ in retired_hits})} archetype(s), "
              f"{len({p for _, p, _ in retired_hits})} page(s))")
        for arch, pg, why in retired_hits:
            print(f"  {arch:22} visits {pg[:30]:32} retired: {why[:44]}")
    blocked = role_blocked_hops(paths, None, links)
    if blocked:
        print(f"hops the CAST's own hub mode cannot reach: {len(blocked)}")
        for arch, mode, a, b, r, via in blocked:
            # ★"ROUTE IT THROUGH THE LANDING PAGE" IS NOT A ROUTE FOR SOMEBODY ALREADY SIGNED IN. When the
            # only page this cast can reach that links the destination is `index.html`, the honest reading
            # is not a missing detour - it is that the story sends this person somewhere the product does
            # not mean them to go, and the CAST or the PATH is what needs changing.
            fix = (f"route it through {via}" if via and via != "index.html"
                   else "only the landing page links it for this cast — the archetype routes this person to "
                        "a surface the product reserves for another role; re-cast or re-route it"
                   if via == "index.html" else "no page this cast can reach links it")
            print(f"  {arch:6} as {mode:10} {a[:24]:26} -> {b[:24]:26} hub offers it to {r} — {fix}")
    print(f"journey archetypes with a declared path: {len(paths)}")
    print(f"hops that follow no route the platform offers: {len(broken)}")
    show = len(broken) if "--all" in sys.argv else 14
    for arch, a, b, where in broken[:show]:
        # ★"NO PAGE OFFERS IT" AND "ONLY THE LANDING PAGE DOES" ARE DIFFERENT FACTS. public-feed.html is
        # linked from index.html and nowhere else - a thin route, not no route, and the difference is what
        # somebody would act on.
        only_home = (not where) and b in links.get("index.html", set())
        fix = ("route it through " + " -> ".join(where) if where
               else "only the landing page links to it" if only_home
               else "no page offers this destination at all")
        print(f"  {arch:6} {a[:26]:28} -> {b[:26]:28} {fix}")
    if not broken:
        print("  every hop is either linked from its own page or offered by the hub")
    # ★A JOURNEY DECLARED ACROSS A RETIRED PAGE FAILS, IT DOES NOT MERELY GET MENTIONED. Three archetypes
    # named four surfaces sitting under a full-screen "moved to Grafana" card, and walking them would have
    # reported an overlay as a broken product. Repaired now; this holds the line so the next wave cannot
    # seed a story through a page nobody can open.
    # ★AND A HOP THE CAST CANNOT REACH FAILS TOO. A link existing is not the same as this person being shown
    # it: the hub offers each destination to named modes, and J26 failed live because a worker was routed to
    # a supervisor-only surface. Repaired now; this holds the line so the next wave cannot seed a story that
    # sends somebody where the product does not show them.
    return 1 if (broken or retired_hits or blocked) else 0


if __name__ == "__main__":
    raise SystemExit(main())
