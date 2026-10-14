#!/usr/bin/env python3
"""validate_gated_offers.py - a page that refuses some people is offered only to the people it admits (BRH-L, 2026-10-14).

Ian, 2026-10-14: *"founder/admin pages button should also be visible to only founder/admin. not that kind of they are
visible to all users then it says only admin has access to this, because that would be a slop."*

Walked as a worker (Bryan Garcia) at 390 and 1280: the hub offered Connections in its All and Supervisor display modes,
and the search offered Audit Log and Connections - each tap landed on "Supervisor access only". The fix is ONE rule
(utils.js): WH_PAGE_GATES names each page's own refusal, whOffers(href) asks whether this viewer is admitted, the hub
and the search filter through it, and a page link declares data-wh-requires (whApplyOfferGates withholds it, with an
optional data-wh-refused-text in its place). This gate holds that rule to the product, two ways:

  1. THE MAP IS THE MEASUREMENT  WH_PAGE_GATES equals the gates measured from the pages themselves (isPlatformAdmin ->
                                 platform-admin; a supervisors-only wall -> supervisor), so a new refusing page cannot
                                 be left out of the rule.
  2. EVERY DOOR IS GOVERNED      every control on a production page or in the shared chrome that leads to a refusing
                                 page (bug_hunt_inventory's class-L measurement: a quoted path to it, comments excluded)
                                 is governed: data-wh-requires on its line, a whOffers/whViewerAdmits call on its line, a
                                 chrome file whose offer path calls whOffers, or a `gated-offer-ok: <reason>` marker on
                                 its line or the eight above it (a page-managed reveal, or a path that is not a control).

    python tools/validate_gated_offers.py            # the gate
    python tools/validate_gated_offers.py --self-test
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from bug_hunt_inventory import CHROME, _blank_comments, page_gate, production_pages  # noqa: E402

MAP_RX = re.compile(r"var WH_PAGE_GATES = \{(.*?)\};", re.S)
PAIR_RX = re.compile(r"'([a-z0-9-]+\.html)':\s*'([a-z-]+)'")
MARKER = "gated-offer-ok:"
GOVERNED_LINE = re.compile(r"data-wh-requires=|whOffers\(|whViewerAdmits\(")
# a chrome file governs every offer it makes when its offer path asks the rule (the hub's visibility, the search filter)
CHROME_GOVERNS = {"nav-hub.js": re.compile(r"function isVisibleInMode\([^)]*\)\s*\{[^}]*?whOffers\(", re.S),
                  "search-overlay.js": re.compile(r"WHNavTools[^;]*?\.filter\(_matches\)[^;]*?whOffers\(", re.S)}


def measured_gates(read, pages) -> dict:
    out = {}
    for p in pages:
        g = page_gate(read(p))           # the one measurement the inventory and the catalog renderer share
        if g:
            out[p] = "platform-admin" if g == "admin" else g
    return out


def declared_gates(utils_src: str) -> dict:
    m = MAP_RX.search(utils_src)
    return dict(PAIR_RX.findall(m.group(1))) if m else {}


def ungoverned(name: str, src: str, gated: dict) -> list[tuple[int, str]]:
    if not gated:
        return []
    dest_rx = re.compile(r"""["'`/](%s)(?:[?#][^"'`]*)?["'`]""" % "|".join(re.escape(d) for d in sorted(gated)))
    code = _blank_comments(src)
    raw = src.splitlines()
    chrome_ok = name in CHROME_GOVERNS and bool(CHROME_GOVERNS[name].search(src))
    bad = []
    for m in dest_rx.finditer(code):
        d = m.group(1)
        if d == name or (name in gated and (gated[name] == "platform-admin" or gated[name] == gated[d])):
            continue
        line = code[:m.start()].count("\n") + 1
        here = raw[line - 1] if line - 1 < len(raw) else ""
        window = "\n".join(raw[max(0, line - 9):line])
        if chrome_ok or GOVERNED_LINE.search(here) or MARKER in window or re.search(r"whOffers\(|whViewerAdmits\(", window):
            continue
        bad.append((line, d))
    return bad


def check(read, pages: list[str], chrome: list[str], all_pages: list[str], utils_src: str) -> list[str]:
    problems = []
    measured = measured_gates(read, all_pages)
    declared = declared_gates(utils_src)
    if measured != declared:
        miss = {k: v for k, v in measured.items() if declared.get(k) != v}
        extra = {k: v for k, v in declared.items() if k not in measured}
        problems.append(f"WH_PAGE_GATES in utils.js disagrees with the pages' own gates - measured but not declared "
                        f"(or declared differently): {miss}; declared but not measured: {extra}")
    for f in pages + chrome:
        for line, d in ungoverned(f, read(f), measured):
            problems.append(f"{f}:{line} offers {d} ({measured[d]}) to everyone - route it through whOffers / "
                            f"data-wh-requires, or say why with '{MARKER} <reason>'")
    # a script that offers the HUB'S tool list names no page itself (the search overlay), so the scan above cannot see
    # it: it must filter that list through the rule, or it offers every gated tool the hub withholds
    for f in chrome:
        src = read(f)
        if f == "nav-hub.js" or "WHNavTools" not in _blank_comments(src):
            continue
        gov = CHROME_GOVERNS.get(f)
        if not (gov.search(src) if gov else re.search(r"WHNavTools[^;]*?whOffers\(", src, re.S)):
            problems.append(f"{f} offers the hub's whole tool list (window.WHNavTools) without asking whOffers - a "
                            f"worker's search would offer the pages the hub withholds")
    return problems


def main() -> int:
    def read(p: str) -> str:
        try:
            return (ROOT / p).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
    all_pages = sorted(p.name for p in ROOT.glob("*.html"))
    chrome = [c for c in CHROME if (ROOT / c).exists()]
    problems = check(read, production_pages(), chrome, all_pages, read("utils.js"))
    if problems:
        for p in problems:
            print("  FAIL " + p)
        print(f"FAIL gated-offers - {len(problems)} problem(s)")
        return 1
    print(f"PASS gated-offers - {len(declared_gates(read('utils.js')))} refusing pages, every offer of them on "
          f"{len(production_pages())} production pages and {len(chrome)} shared scripts goes through the one rule")
    return 0


def self_test() -> int:
    utils = ("var WH_PAGE_GATES = {\n  'audit.html': 'supervisor', 'admin.html': 'platform-admin'\n};\n")
    pages = {
        "utils.js": utils,
        "audit.html": "<h2>Supervisors only</h2>",
        "admin.html": "<script>if (!(await isPlatformAdmin(db))) {}</script>",
        "open.html": "<a href='audit.html'>Audit</a>",                                    # ungoverned
        "attr.html": "<a href='audit.html' data-wh-requires='supervisor'>Audit</a>",       # governed by the attribute
        "marked.html": "<!-- gated-offer-ok: revealed only by the supervisor block -->\n<a href='admin.html'>x</a>",
        "comment.html": "<!-- <a href='audit.html'> -->",                                  # not a control
        "nav-hub.js": "function isVisibleInMode(tool, mode) { if (!whOffers(tool.href)) return false; }\n"
                      "var TOOLS = [{ href: 'audit.html' }];",
        "search-overlay.js": "const hits = window.WHNavTools.filter(m); go('audit.html');",  # chrome that does not ask
    }
    read = lambda p: pages.get(p, "")  # noqa: E731
    probs = check(read, ["open.html", "attr.html", "marked.html", "comment.html"], ["nav-hub.js", "search-overlay.js"],
                  ["audit.html", "admin.html", "open.html", "attr.html", "marked.html", "comment.html"], utils)
    want_bad = {"open.html", "search-overlay.js"}
    got_bad = {re.split(r"[: ]", p, maxsplit=1)[0] for p in probs}
    ok = got_bad == want_bad
    drift = check(read, [], [], ["audit.html", "admin.html"], "var WH_PAGE_GATES = {\n  'audit.html': 'supervisor'\n};")
    ok &= any("WH_PAGE_GATES" in p for p in drift)
    print(("PASS" if ok else "FAIL") + f" gated-offers self-test - flagged {sorted(got_bad)} (want {sorted(want_bad)}); "
          f"a map missing a measured gate {'reddens' if any('WH_PAGE_GATES' in p for p in drift) else 'DOES NOT redden'}")
    return 0 if ok else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
