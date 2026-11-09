#!/usr/bin/env python3
"""validate_public_markup_balance.py - every public page's <main> closes every element it opens (Wave CF M13, 2026-11-09).

★WHY THIS EXISTS. M13 rewrites the learn guides' sentences through tools/copy_rewrite.py, which locates the text the
critic GRADED in the page source while tolerating inline tags inside it. Graded text crosses tag boundaries:
"Choose MaintainX if ..." is `<strong>Choose MaintainX</strong> if ...` in the source, so the matched span began INSIDE a
<strong> and held its closing tag. Three committed guides then carried `<strong><strong>Choose ...` (a rewrite that
re-opened the tag) and two list items lost their `</strong>` (a rewrite that dropped it) - the rest of each item rendered
bold and the page's tree was malformed. A browser repairs it silently, so no walk, no screenshot and none of the 40-odd
gates run on the batch noticed. copy_rewrite now refuses a rewrite that changes a span's tag balance; this is the
page-level check behind it, for any hand edit or generator that touches the same pages.

What it reads: <main> of every public page (index, learn guides and hub, calculators, about/privacy/terms/feedback).
What it counts: for each tracked element, opens minus closes, walking a stack - an end tag that does not close the
innermost open element of its kind is a mismatch. Void elements are ignored. A page passes at zero mismatches and
nothing left open.

    python tools/validate_public_markup_balance.py            # report; FAIL on any page that is not balanced
    python tools/validate_public_markup_balance.py --self-test
"""
from __future__ import annotations

import glob
import io
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
TRACKED = ("p", "ul", "ol", "li", "div", "section", "article", "aside", "details", "summary", "table", "thead", "tbody",
           "tr", "td", "th", "strong", "em", "b", "i", "a", "abbr", "code", "span", "small", "blockquote", "figure",
           "figcaption", "h1", "h2", "h3", "h4", "dl", "dt", "dd")


class _Balance(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, tuple]] = []
        self.bad: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in TRACKED:
            self.stack.append((tag, self.getpos()))

    def handle_endtag(self, tag):
        if tag not in TRACKED:
            return
        if self.stack and self.stack[-1][0] == tag:
            self.stack.pop()
            return
        open_names = [t for t, _ in self.stack]
        self.bad.append(f"</{tag}> at line {self.getpos()[0]} while <{open_names[-1] if open_names else 'nothing'}> is open")
        if tag in open_names:                      # recover the way a browser would: close down to it
            while self.stack and self.stack[-1][0] != tag:
                self.stack.pop()
            self.stack.pop()


def check(html: str) -> list[str]:
    m = re.search(r"<main\b[\s\S]*?</main>", html)
    if not m:
        return []
    body = re.sub(r"<(script|style)\b[\s\S]*?</\1>", "", m.group(0))
    p = _Balance()
    p.feed(body)
    p.close()
    return p.bad + [f"<{t}> opened at line {pos[0]} is never closed" for t, pos in p.stack]


def pages() -> list[Path]:
    out = [ROOT / "index.html", ROOT / "learn" / "index.html"]
    for pat in ("learn/*/index.html", "tools/*/index.html", "about/index.html", "privacy-policy/index.html",
                "terms-of-service/index.html", "feedback/index.html"):
        out += [Path(p) for p in sorted(glob.glob(str(ROOT / pat)))]
    return [p for p in dict.fromkeys(out) if p.exists()]


def _self_test() -> int:
    fails = []
    ok = "<main><p><strong>Choose X</strong> if Y.</p><ul><li>a</li></ul><img src=x><br></main>"
    if check(ok):
        fails.append("a balanced page with void elements must pass")
    doubled = "<main><div><strong><strong>Choose X</strong> if Y.</div></main>"
    if not check(doubled):
        fails.append("a doubled opening <strong> (the M13 rewrite) must fail")
    dropped = "<main><ul><li><strong>Public: workers can read it.</li></ul></main>"
    if not check(dropped):
        fails.append("a dropped </strong> inside a list item must fail")
    scripted = "<main><script>var s='<strong>';</script><p>ok</p></main>"
    if check(scripted):
        fails.append("tags inside a script string are not markup")
    print("FAIL public-markup-balance self-test - " + "; ".join(fails) if fails
          else "self-test OK: balanced passes, a doubled open and a dropped close both fail, script strings are ignored")
    return 1 if fails else 0


def main() -> int:
    if "--self-test" in sys.argv:
        return _self_test()
    bad = {}
    ps = pages()
    for p in ps:
        errs = check(p.read_text(encoding="utf-8", errors="replace"))
        if errs:
            bad[p.relative_to(ROOT).as_posix()] = errs
    for f, errs in sorted(bad.items()):
        print(f"  BAD {f}: {len(errs)} - {errs[0]}")
    if bad:
        print(f"FAIL public-markup-balance - {len(bad)} of {len(ps)} public page(s) open an element they never close, "
              f"or close one they never opened, inside <main>")
        return 1
    print(f"PASS public-markup-balance - {len(ps)} public page(s): every element opened inside <main> is closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
