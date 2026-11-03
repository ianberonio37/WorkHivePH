#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared-chrome parity (rubric S2), measured PER PAGE: does this page render the shared chrome its family declares?

WHY (2026-11-04, CX-UX). S2 - "the same nav / footer / skip-link components render across pages" (NN/g #4, internal
consistency) - had no per-page instrument. rubric_coverage.py reported one platform number for it, borrowed from the
lens's W2 (companion + avatar + hub, a different dim), so 15 CX-UX rows asking "was S graded on THIS page" could never
close: nothing had ever looked at this page's chrome and said so. This is that instrument.

WHAT IS MEASURED, AND AGAINST WHAT. The public families - the learn hub and its articles, the calculators, and the four
public-root pages (about, feedback, privacy-policy, terms-of-service) - carry their chrome as static markup. Their
DECLARED chrome is the generator's: tools/build_pillar_pages.py SITE_HEADER and site_footer(), which
tools/build_calc_pages.py imports for all sixty calculators. It is read from that module here, never typed, so the
ruler moves when the template does. ★The canonical is the declared template, not a vote over pages (the S1 rule:
"never the platform MODE" - un-driven pages would outvote the design system).

Five parts per page, each the shared component or not:
  skip-link    an a.wh-skip-link whose #target exists, placed before the banner (the first stop for a keyboard reader)
  banner       a <header> (the banner landmark) holding the brand link: href="/" with the WorkHive logo
  primary-nav  inside that header, the template's nav links in the template's order, each with its label; a page may
               add a link of its own (the hub's "My Hive", the roadmap's own entry) - additions do not break parity,
               a missing, renamed or reordered shared link does
  main         exactly one <main>, and it is the skip link's target
  footer       a <footer> carrying every link the template's footer carries (a page may carry more)
S2 = parts that match / 5, MEASURED. The note names each part that does not match and why.

WHAT IS NOT MEASURED HERE. The app pages (root *.html) draw their chrome at RUNTIME (nav-hub.js, wayfinding.js, the
companion): a static read of their markup would see none of it. The lens's W2 measures that chrome live per page. This
instrument writes NO record for them rather than an empty one - an absent record is "not measured", an empty one would
be a false 0.

A static read is honest for these pages because their chrome IS static markup: no script on them builds a header,
nav or footer (wh-i18n-lite.js swaps the text of [data-i] nodes, the feedback FAB adds a floating button). It cannot see
a part hidden by CSS; the lens and the walks see the rendered page.

USAGE
  python tools/prove_shared_chrome_parity.py             measure and print (writes nothing)
  python tools/prove_shared_chrome_parity.py --write     measure and write shared_chrome_parity.json (tracked)
  python tools/prove_shared_chrome_parity.py --check     the gate: the self-test, then the written record must equal a
                                                         fresh measurement (a stale record is evidence of nothing)
  python tools/prove_shared_chrome_parity.py --self-test
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

OUT = ROOT / "shared_chrome_parity.json"
TOOL = "tools/prove_shared_chrome_parity.py"
TEMPLATE = "tools/build_pillar_pages.py (SITE_HEADER, site_footer)"
PARTS = ("skip-link", "banner", "primary-nav", "main", "footer")
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


# ── a small DOM, stdlib only ──────────────────────────────────────────────────────────────────────────────────────
class Node:
    __slots__ = ("tag", "attrs", "children", "parent", "text", "order")

    def __init__(self, tag, attrs, parent, order):
        self.tag, self.attrs, self.parent, self.order = tag, attrs, parent, order
        self.children, self.text = [], []

    def iter(self):
        yield self
        for c in self.children:
            yield from c.iter()

    def find_all(self, tag):
        return [n for n in self.iter() if n.tag == tag and n is not self]

    def inner_text(self):
        out = list(self.text)
        for c in self.children:
            out.append(c.inner_text())
        return " ".join(" ".join(out).split())

    def ancestors(self):
        p = self.parent
        while p is not None:
            yield p
            p = p.parent


class _Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#document", {}, None, 0)
        self.cur = self.root
        self.n = 0

    def handle_starttag(self, tag, attrs):
        self.n += 1
        node = Node(tag, {k: (v if v is not None else "") for k, v in attrs}, self.cur, self.n)
        self.cur.children.append(node)
        if tag not in VOID:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        self.n += 1
        self.cur.children.append(Node(tag, {k: (v if v is not None else "") for k, v in attrs}, self.cur, self.n))

    def handle_endtag(self, tag):
        # close back to the nearest open element of this tag; a stray end tag with no open match is ignored
        p = self.cur
        while p is not None and p.tag != tag:
            p = p.parent
        if p is not None and p.parent is not None:
            self.cur = p.parent

    def handle_data(self, data):
        if data.strip():
            self.cur.text.append(data)


_STRIP = re.compile(r"<script\b.*?</script\s*>|<style\b.*?</style\s*>|<!--.*?-->|<template\b.*?</template\s*>", re.S | re.I)


def parse(html: str) -> Node:
    """The page's markup as a tree, without scripts, styles, comments or templates: a template literal inside a script
    that spells <header> is not a header the page renders."""
    b = _Builder()
    b.feed(_STRIP.sub(" ", html))
    b.close()
    return b.root


def _norm(s: str) -> str:
    return " ".join(str(s or "").split()).casefold()


# ── the declared chrome, read from the generator ──────────────────────────────────────────────────────────────────
def _brand_link(scope: Node):
    for a in scope.find_all("a"):
        if a.attrs.get("href") == "/" and any(i.attrs.get("alt", "").strip().casefold() == "workhive"
                                              for i in a.find_all("img")):
            return a
    return None


def canonical() -> dict:
    """The template's nav (href, label) in order and its footer hrefs, from build_pillar_pages itself."""
    import build_pillar_pages as bpp
    head = parse(bpp.SITE_HEADER)
    foot = parse(bpp.site_footer(bpp.PUB))
    return canonical_from(head, foot)


def canonical_from(head: Node, foot: Node) -> dict:
    hdr = (head.find_all("header") or [head])[0]
    brand = _brand_link(hdr)
    nav = [(a.attrs.get("href", ""), a.inner_text()) for n in hdr.find_all("nav") for a in n.find_all("a")
           if a is not brand]
    fl = [a.attrs.get("href", "") for a in (foot.find_all("footer") or [foot])[0].find_all("a")]
    if not brand or not nav or not fl:
        raise SystemExit("the template's chrome did not parse (no brand link, nav or footer) - "
                         "tools/build_pillar_pages.py changed shape; fix the reader before trusting any reading")
    return {"source": TEMPLATE, "nav": [list(x) for x in nav], "footer": fl}


# ── one page ──────────────────────────────────────────────────────────────────────────────────────────────────────
def _outside_content(n: Node) -> bool:
    return not any(a.tag in ("main", "article") for a in n.ancestors())


def _ordered_subsequence(want: list, have: list) -> tuple[bool, str]:
    """Is every (href, label) of `want` in `have`, in order? Returns (ok, why-not)."""
    i = 0
    for href, label in want:
        while i < len(have) and not (have[i][0] == href and _norm(have[i][1]) == _norm(label)):
            i += 1
        if i == len(have):
            present = [h for h in have if h[0] == href]
            if not present:
                return False, f"no {label!r} link to {href}"
            if all(_norm(h[1]) != _norm(label) for h in present):
                return False, f"the link to {href} reads {present[0][1]!r}, the shared nav says {label!r}"
            return False, f"{label!r} ({href}) is out of the shared order {[w[1] for w in want]}"
        i += 1
    return True, ""


def measure_page(html: str, canon: dict) -> dict:
    doc = parse(html)
    parts: dict = {}
    anchors = doc.find_all("a")
    ids = {n.attrs.get("id") for n in doc.iter() if n.attrs.get("id")}

    headers = [h for h in doc.find_all("header") if _outside_content(h)]
    header = headers[0] if headers else None

    # skip-link: present, its target exists, and it comes before the banner
    skip = next((a for a in anchors if "wh-skip-link" in a.attrs.get("class", "").split()), None)
    target = (skip.attrs.get("href", "") if skip else "")
    if not skip:
        parts["skip-link"] = (False, "no a.wh-skip-link")
    elif not target.startswith("#") or target[1:] not in ids:
        parts["skip-link"] = (False, f"its target {target!r} is not an id on the page")
    elif header is not None and skip.order > header.order:
        parts["skip-link"] = (False, "it comes after the banner, so it is not the first stop")
    else:
        parts["skip-link"] = (True, "")

    # banner: a header landmark with the brand link
    if header is None:
        bars = [n for n in doc.find_all("nav") if _outside_content(n) and _brand_link(n)]
        parts["banner"] = (False, "no <header> landmark" + (" - the brand bar is a bare <nav>" if bars else ""))
    elif not _brand_link(header):
        parts["banner"] = (False, "the <header> holds no brand link (href=\"/\" with the WorkHive logo)")
    else:
        parts["banner"] = (True, "")

    # primary nav: the template's links, in its order, each with its label, inside the header
    scope = header
    if scope is None:
        bars = [n for n in doc.find_all("nav") if _outside_content(n) and _brand_link(n)]
        scope = bars[0] if bars else None
    if scope is None:
        parts["primary-nav"] = (False, "no site nav at all")
    else:
        brand = _brand_link(scope)
        navs = [scope] if scope.tag == "nav" else scope.find_all("nav")
        have = [(a.attrs.get("href", ""), a.inner_text()) for n in navs for a in n.find_all("a") if a is not brand]
        ok, why = _ordered_subsequence([tuple(x) for x in canon["nav"]], have)
        if ok and header is None:
            ok, why = False, "the shared links are there but not in a <header> banner"
        parts["primary-nav"] = (ok, why)

    # main: exactly one, with an id, and - when there is a skip link - its target (a missing skip link is the
    # skip-link part's failure, not this one's too)
    mains = doc.find_all("main")
    if len(mains) != 1:
        parts["main"] = (False, f"{len(mains)} <main> elements")
    elif not mains[0].attrs.get("id"):
        parts["main"] = (False, "<main> has no id, so nothing can skip to it")
    elif skip and (not target.startswith("#") or mains[0].attrs.get("id") != target[1:]):
        parts["main"] = (False, f"<main id={mains[0].attrs.get('id')!r}> is not the skip link's target {target!r}")
    else:
        parts["main"] = (True, "")

    # footer: carries every link the template's footer carries
    footers = [f for f in doc.find_all("footer") if _outside_content(f)]
    if not footers:
        parts["footer"] = (False, "no <footer> landmark")
    else:
        have = {a.attrs.get("href", "") for a in footers[-1].find_all("a")}
        lacks = [h for h in canon["footer"] if h not in have]
        parts["footer"] = (not lacks, f"the footer lacks {', '.join(lacks)}" if lacks else "")

    n_ok = sum(1 for p in PARTS if parts[p][0])
    bad = [f"{p}: {parts[p][1]}" for p in PARTS if not parts[p][0]]
    note = (f"{n_ok}/{len(PARTS)} shared-chrome parts match the declared template ({TEMPLATE})"
            + ("" if not bad else " - " + "; ".join(bad)))
    return {"S2": {"verdict": "MEASURED", "pct": round(100 * n_ok / len(PARTS)), "note": note},
            "parts": {p: {"ok": parts[p][0], **({"why": parts[p][1]} if parts[p][1] else {})} for p in PARTS}}


# ── the page set ──────────────────────────────────────────────────────────────────────────────────────────────────
def public_pages() -> dict:
    """{page: family} - the cube's own served set (seed_expansion_wave4.served_pages, which sublayer_inventory's
    page_classes() reads), its static-chrome families only."""
    from seed_expansion_wave4 import served_pages
    sp = served_pages()
    out = {}
    for fam in ("learn", "calc", "public"):
        for p in sp.get(fam) or []:
            if (ROOT / p).is_file():
                out[p] = fam
    return dict(sorted(out.items()))


def measure_all(pages: dict | None = None, canon: dict | None = None) -> dict:
    canon = canon or canonical()
    pages = pages if pages is not None else public_pages()
    recs = {}
    for p, fam in pages.items():
        html = (ROOT / p).read_text(encoding="utf-8", errors="replace")
        recs[p] = dict({"family": fam}, **measure_page(html, canon))
    pcts = [r["S2"]["pct"] for r in recs.values()]
    by_part = {part: sum(1 for r in recs.values() if not r["parts"][part]["ok"]) for part in PARTS}
    return {
        "_doc": "Shared-chrome parity (rubric S2) per page, static, against the declared public template. Written by "
                f"{TOOL} --write; held by its --check (the record must equal a fresh measurement). The app pages draw "
                "their chrome at runtime and are measured live by the lens's W2 - no record here.",
        "instrument": TOOL,
        "canonical": canon,
        "summary": {"pages": len(recs), "at_100": sum(1 for x in pcts if x == 100),
                    "mean": round(sum(pcts) / len(pcts), 1) if pcts else None, "pages_failing_part": by_part},
        "pages": recs,
    }


def _dump(doc: dict) -> str:
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


# ── self-test: synthetic pages, each part given teeth ─────────────────────────────────────────────────────────────
def _self_test() -> int:
    fails = []
    canon = canonical_from(parse(
        '<header><a href="/"><img alt="WorkHive"></a><nav><a href="/">Home</a><a href="/learn/">Learn</a>'
        '<a href="/?signin=1">Sign In</a><a href="/?signup=1">Sign Up Free</a></nav></header>'),
        parse('<footer><a href="/">Home</a><a href="/#faq">FAQ</a><a href="/?signup=1">Join</a></footer>'))
    good = ('<body><a class="wh-skip-link" href="#m">Skip</a>'
            '<header><a href="/"><img alt="WorkHive"></a><nav><a href="/">Home</a><a href="/learn/">Learn</a>'
            '<a href="/?signin=1">Sign In</a><a href="/?signup=1">Sign Up Free</a></nav></header>'
            '<main id="m"><p>x</p></main>'
            '<footer><a href="/">Home</a><a href="/#faq">FAQ</a><a href="/?signin=1">Sign In</a>'
            '<a href="/?signup=1">Sign Up Free</a></footer></body>')
    r = measure_page(good, canon)
    if r["S2"]["pct"] != 100:
        fails.append(f"the template's own chrome must read 100, got {r['S2']}")

    def expect(name, html, part, pct, needle):
        x = measure_page(html, canon)
        if x["S2"]["pct"] != pct or x["parts"][part]["ok"] or needle not in x["parts"][part].get("why", ""):
            fails.append(f"{name}: expected {part} to fail ({needle!r}) at {pct}, got {x['S2']} {x['parts'][part]}")

    # a page-specific ADDITION keeps parity (the hub's "My Hive")
    added = good.replace('<a href="/?signin=1">', '<a href="/hive.html">My Hive</a><a href="/?signin=1">')
    if measure_page(added, canon)["S2"]["pct"] != 100:
        fails.append("an extra link of the page's own must not break nav parity")
    # teeth, one part at a time
    expect("no skip link", good.replace('class="wh-skip-link" ', ""), "skip-link", 80, "no a.wh-skip-link")
    expect("skip to nowhere", good.replace('href="#m"', 'href="#gone"'), "skip-link", 60, "not an id")
    expect("bare nav bar (the 19-article variant)",
           good.replace("<header>", "<nav class=bar>").replace("</nav></header>", "</nav></nav>"), "banner", 60,
           "no <header> landmark")
    expect("bare nav bar, nav part", good.replace("<header>", "<nav class=bar>").replace("</nav></header>", "</nav></nav>"),
           "primary-nav", 60, "not in a <header> banner")
    expect("main with no id", good.replace('<main id="m">', "<main>"), "main", 60, "has no id")
    expect("reordered nav", good.replace('<a href="/">Home</a><a href="/learn/">Learn</a>',
                                         '<a href="/learn/">Learn</a><a href="/">Home</a>'), "primary-nav", 80,
           "out of the shared order")
    expect("renamed door", good.replace(">Sign Up Free</a></nav>", ">Join</a></nav>"), "primary-nav", 80,
           "reads 'Join'")
    expect("missing door", good.replace('<a href="/?signin=1">Sign In</a><a href="/?signup=1">Sign Up Free</a></nav>',
                                        '<a href="/?signup=1">Sign Up Free</a></nav>'), "primary-nav", 80,
           "no 'Sign In' link")
    expect("two mains", good.replace("</main>", "</main><main></main>"), "main", 80, "2 <main>")
    expect("legal-only footer", good.replace('<a href="/#faq">FAQ</a>', ""), "footer", 80, "lacks /#faq")
    expect("no footer", re.sub(r"<footer>.*</footer>", "", good), "footer", 80, "no <footer>")
    # a header spelled inside a script is not a header the page renders
    scripted = good.replace("<header>", "<script>const t = `<header>`;</script><header>")
    if measure_page(scripted, canon)["S2"]["pct"] != 100:
        fails.append("markup inside a <script> must not be read as chrome")
    # the reader of the REAL template must find its nav and footer (a template that changed shape is a hard stop)
    try:
        real = canonical()
        if [h for h, _ in real["nav"]][:2] != ["/", "/learn/"] or "/?signup=1" not in real["footer"]:
            fails.append(f"the real template's chrome read oddly: {real}")
    except SystemExit as e:
        fails.append(str(e))
    # the record round-trips: a mutated written record is stale against a fresh measurement
    doc = measure_all({}, canon)
    if json.loads(_dump(doc)) != doc:
        fails.append("the record must round-trip through JSON unchanged")
    print("FAIL prove_shared_chrome_parity self-test - " + "; ".join(fails) if fails else
          "self-test OK: the template reads 100; a page's own extra link keeps parity; a missing skip link, a skip link "
          "to nowhere, a bare <nav> bar with no banner, a reordered / renamed / missing shared nav link, two mains, a "
          "footer without the shared links and no footer each fail their own part; markup inside a script is ignored; "
          "the real template parses")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return _self_test()
    if a.check:
        if _self_test():
            return 1
        fresh = measure_all()
        if not OUT.is_file():
            print(f"FAIL shared-chrome-parity - {OUT.name} is not on disk; run {TOOL} --write")
            return 1
        try:
            held = json.loads(OUT.read_text(encoding="utf-8"))
        except ValueError as e:
            print(f"FAIL shared-chrome-parity - {OUT.name} does not parse: {e}")
            return 1
        stale = sorted(set(fresh["pages"]) ^ set(held.get("pages") or {}))
        stale += sorted(p for p in fresh["pages"] if p in (held.get("pages") or {})
                        and held["pages"][p] != fresh["pages"][p])
        if held.get("canonical") != fresh["canonical"]:
            stale.insert(0, "(the template itself)")
        if stale:
            print(f"FAIL shared-chrome-parity - {OUT.name} no longer matches the pages it describes ({len(stale)}): "
                  + ", ".join(stale[:12]) + f"; re-run {TOOL} --write")
            return 1
        s = fresh["summary"]
        print(f"PASS shared-chrome-parity - {s['pages']} public page(s) measured against the declared template; "
              f"{s['at_100']} at 100, mean {s['mean']}; record current")
        return 0
    doc = measure_all()
    s = doc["summary"]
    print(f"S2 shared-chrome parity - {s['pages']} public page(s), {s['at_100']} at 100, mean {s['mean']}")
    print("  pages failing each part: " + ", ".join(f"{k} {v}" for k, v in s["pages_failing_part"].items()))
    for p, r in doc["pages"].items():
        if r["S2"]["pct"] < 100:
            print(f"  {r['S2']['pct']:>3}  {p}  {r['S2']['note'].split(' - ', 1)[-1][:150]}")
    if a.write:
        OUT.write_text(_dump(doc), encoding="utf-8")
        print(f"wrote {OUT.name}")
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")
    sys.exit(main())
