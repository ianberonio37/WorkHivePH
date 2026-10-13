"""No placeholder written as a bare tag in served markup (critic batch, 2026-10-13).

marketplace-seller told sellers: Buyers see a "Message on Messenger" button that opens m.me/<your-handle> directly.
In HTML source, <your-handle> is not text: the parser reads it as an element named your-handle, renders it empty,
and the seller read "opens m.me/ directly" - the one word they needed was gone. No reviewer reading the source sees
it, because in the source the word is there. The critic walk caught it only because the sentence it graded made no
sense.

The rule: every start tag in a served page must be an element a browser knows (HTML, SVG or MathML). A name the
browser does not know is either a typo or, as here, a placeholder that should have been written &lt;like-this&gt;.
The platform defines no custom elements (no customElements.define anywhere it serves), so there is no legitimate
unknown tag to allow. Scripts, styles and comments are skipped: a template string or a comment may hold anything.

    python tools/validate_no_swallowed_placeholder_tags.py [--self-test]
"""
from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {"node_modules", "_fixtures", "test-data-seeder", "video_marketing_app", "test-results", "playwright-report"}

HTML_TAGS = set("""
a abbr address area article aside audio b base bdi bdo blockquote body br button canvas caption cite code col colgroup
data datalist dd del details dfn dialog div dl dt em embed fieldset figcaption figure footer form h1 h2 h3 h4 h5 h6 head
header hgroup hr html i iframe img input ins kbd label legend li link main map mark menu meta meter nav noscript object
ol optgroup option output p param picture portal pre progress q rp rt ruby s samp script search section select slot
small source span strong style sub summary sup table tbody td template textarea tfoot th thead time title tr track u ul
var video wbr center font big tt strike marquee nobr acronym
""".split())
SVG_TAGS = {t.lower() for t in """
svg g defs desc title symbol use image switch path rect circle ellipse line polyline polygon text tspan textPath
linearGradient radialGradient stop pattern clipPath mask marker filter feBlend feColorMatrix feComponentTransfer
feComposite feConvolveMatrix feDiffuseLighting feDisplacementMap feDistantLight feDropShadow feFlood feFuncA feFuncB
feFuncG feFuncR feGaussianBlur feImage feMerge feMergeNode feMorphology feOffset fePointLight feSpecularLighting
feSpotLight feTile feTurbulence foreignObject metadata view animate animateMotion animateTransform set mpath
""".split()}
MATHML_TAGS = set("""
math mi mn mo ms mtext mspace mrow mfrac msqrt mroot mstyle merror mpadded mphantom msub msup msubsup munder mover
munderover mmultiscripts mtable mtr mtd semantics annotation annotation-xml
""".split())
KNOWN = HTML_TAGS | SVG_TAGS | MATHML_TAGS


class _Tags(HTMLParser):
    """Collects (tag, line) for every start tag outside script/style. html.parser already treats script and style
    content as raw text, and comments arrive through handle_comment, which is ignored."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.found: list[tuple[str, int]] = []

    def handle_starttag(self, tag, attrs):
        self.found.append((tag.lower(), self.getpos()[0]))

    handle_startendtag = handle_starttag


def unknown_tags(html: str, defined: set[str]) -> list[tuple[str, int]]:
    p = _Tags()
    p.feed(html)
    p.close()
    return [(t, ln) for t, ln in p.found if t not in KNOWN and t not in defined]


def served_pages() -> list[Path]:
    out = []
    for f in ROOT.rglob("*.html"):
        rel = f.relative_to(ROOT)
        if any(part.startswith(".") or part in SKIP_DIRS for part in rel.parts[:-1]):
            continue
        out.append(f)
    return sorted(out)


def defined_elements() -> set[str]:
    names: set[str] = set()
    for f in ROOT.glob("*.js"):
        for m in re.finditer(r"customElements\.define\(\s*['\"]([a-z][a-z0-9-]*)['\"]", f.read_text(encoding="utf-8", errors="replace")):
            names.add(m.group(1))
    return names


def main() -> int:
    defined = defined_elements()
    pages = served_pages()
    bad = []
    for f in pages:
        for tag, ln in unknown_tags(f.read_text(encoding="utf-8", errors="replace"), defined):
            bad.append(f"{f.relative_to(ROOT).as_posix()}:{ln} <{tag}>")
    if bad:
        print(f"FAIL swallowed-placeholder-tags - {len(bad)} unknown tag(s) a browser renders as nothing; write a "
              f"placeholder as &lt;name&gt;: " + " · ".join(bad[:12]))
        return 1
    print(f"PASS swallowed-placeholder-tags - {len(pages)} served pages, every start tag is an element the browser "
          f"knows (HTML/SVG/MathML{', + ' + ', '.join(sorted(defined)) if defined else ''})")
    return 0


def self_test() -> int:
    fails = []
    bad = unknown_tags('<p>Buyers reach you at m.me/<your-handle> directly.</p>', set())
    if [t for t, _ in bad] != ["your-handle"]:
        fails.append(f"a bare <your-handle> placeholder must be flagged, got {bad}")
    if unknown_tags('<p>Buyers reach you at m.me/&lt;your-handle&gt;.</p>', set()):
        fails.append("an escaped placeholder must pass")
    if unknown_tags('<script>const t = `<your-handle>`;</script><style>a::after{content:"<x-y>"}</style><!-- <z-w> -->', set()):
        fails.append("script, style and comment content must be ignored")
    if unknown_tags('<svg viewBox="0 0 1 1"><linearGradient id="g"><stop/></linearGradient><path d="M0 0"/></svg>', set()):
        fails.append("SVG elements (mixed case in source) must pass")
    if unknown_tags('<wh-card>x</wh-card>', {"wh-card"}):
        fails.append("a defined custom element must pass")
    if fails:
        print("FAIL self-test - " + " | ".join(fails))
        return 1
    print("PASS self-test - a bare placeholder tag is flagged; escaped text, script/style/comment content, SVG and "
          "defined custom elements pass")
    return 0


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else main())
