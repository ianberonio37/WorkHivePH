"""
fix_callout_accent_border.py — the thick coloured left bar DESIGN.md forbids, on the learn callouts.
=====================================================================================================
DESIGN.md, Shapes:

    Hairlines `1px solid rgba(255,255,255,0.07-0.10)`; accent borders are 1 px tints of the status
    hue, NEVER a thick coloured `border-left`.

Impeccable's craft floor says the same thing from the other side, listing under Refuse: "A colored
`border-left` or `border-right` above 1px on cards, list items, callouts, or alerts."

THIS CORRECTS A PIN OF MY OWN. On 2026-09-16 I pinned 183 `side-tab` findings as "the platform's
consistent vocabulary for a notice", arguing from what the code does. That is backwards: the code
being consistent is exactly what a drift looks like from the inside, and the committed visual record
- which the craft floor says overrides every default in it - had already decided against it in one
sentence. The detector was right. The pins are retracted and this is the fix.

SCOPE, decided by what the two rules actually NAME rather than by the detector's label. Both name
cards, list items, callouts and alerts:

    .callout       background rgba(41,182,217,0.06)  border-left: 3px solid #29B6D9   border-radius: 8px
    .answer-first  background rgba(247,162,27,0.08)  border-left: 3px solid #F7A21B   border-radius: 8px

Both are rounded callouts wearing a thick coloured bar, so both are in scope. `.prose-wh blockquote`
is NOT: a blockquote is none of the four element types either rule names, and a left rule on a pull
quote is a typographic convention older than the web. Swinging from a self-serving pin to an
over-correction would be the same failure wearing the other sign.

WHAT REPLACES IT. A 1px tint of the same status hue on ALL four sides, which is what DESIGN.md
prescribes and what the platform's own chip component already does ("selected = amber 15% face, amber
text, 40% border"). The tinted face stays - it already carries the hue - so the callout keeps its
meaning and loses the costume.

These are public learn articles, not precached shell, so no CACHE_NAME bump is required.

Usage:  python tools/fix_callout_accent_border.py [--check] [--self-test]
"""
from __future__ import annotations
import io, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))
from served_page_set import served_pages as _served_pages   # ONE definition of the page set


# ★THE REPLACEMENT MUST BE SELECTOR-AWARE, NOT A STRING SWAP. `.answer-first` and
# `.prose-wh blockquote` carry the BYTE-IDENTICAL declaration `border-left: 3px solid #F7A21B;`, so a
# plain text replace would rewrite the blockquote too - the one construct this tool deliberately
# leaves alone. Scoping to the rule body is the whole reason this is a tool and not a sed line.
RULES = [
    (".callout",      "border-left: 3px solid #29B6D9;",  "border: 1px solid rgba(41,182,217,0.28);"),
    (".answer-first", "border-left: 3px solid #F7A21B;",  "border: 1px solid rgba(247,162,27,0.30);"),
]


def _rule_span(text: str, selector: str):
    """The `{...}` body of `selector { ... }`, or None. Matches the selector at a rule boundary."""
    i = 0
    while True:
        i = text.find(selector, i)
        if i < 0:
            return None
        before = text[i - 1] if i else "\n"
        after = text[i + len(selector):i + len(selector) + 2]
        # a rule boundary: not part of a longer class name, and followed by ` {`
        if before not in "-_abcdefghijklmnopqrstuvwxyzABCDEZ0123456789." and after.lstrip().startswith("{"):
            o = text.index("{", i)
            depth, j = 1, o + 1
            while j < len(text) and depth:
                if text[j] == "{":
                    depth += 1
                elif text[j] == "}":
                    depth -= 1
                j += 1
            return (o, j)
        i += len(selector)


def patch(text: str):
    n = {}
    for selector, old, new in RULES:
        span = _rule_span(text, selector)
        if not span:
            continue
        a, b = span
        body = text[a:b]
        if old not in body:
            continue
        text = text[:a] + body.replace(old, new) + text[b:]
        n[selector] = n.get(selector, 0) + 1
    return text, n


def targets():
    # ★THE SAME COVERAGE MISTAKE, TWICE IN ONE DAY (2026-09-16). The first run of this tool globbed
    # only `learn/*/index.html`, and the 60 CALCULATOR pages carry the identical `.callout` and
    # `.answer-first` rules from the same shared prose template - so 120 borders were left behind by a
    # glob that described where I had been looking rather than where the construct lives. Earlier the
    # type-floor sweep made the same error in the other direction, missing `learn/index.html` because
    # its glob demanded a subdirectory.
    # The lesson both times: a glob is a CLAIM about coverage, and it needs the same proof as any
    # other claim - census the construct across the tree, then write the glob to match the census.
    return _served_pages(ROOT)


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    check = "--check" in sys.argv
    files, total = [], 0
    for p in targets():
        t = p.read_text(encoding="utf-8", errors="replace")
        new, n = patch(t)
        if not n:
            continue
        files.append((p, sum(n.values())))
        total += sum(n.values())
        if not check:
            p.write_text(new, encoding="utf-8")
    verb = "WOULD replace" if check else "replaced"
    print("callout accent: %s %d thick coloured left border(s) with a 1px tint across %d public page(s)."
          % (verb, total, len(files)))
    for p, n in files[:5]:
        print("   %-52s %d" % (p.relative_to(ROOT).as_posix(), n))
    if len(files) > 5:
        print("   ... and %d more" % (len(files) - 5))
    if check and files:
        return 1
    return 0


def self_test() -> int:
    ok = True
    src = ".callout { background: rgba(41,182,217,0.06); border-left: 3px solid #29B6D9; border-radius: 8px; }"
    got, n = patch(src)
    if "border-left: 3px" in got:
        print("FAIL: the thick bar survived"); ok = False
    if "border: 1px solid rgba(41,182,217,0.28)" not in got:
        print("FAIL: the 1px tint was not applied"); ok = False
    if "rgba(41,182,217,0.06)" not in got:
        print("FAIL: the tinted face was disturbed - the callout must keep its hue"); ok = False

    # THE POINT OF THE SELECTOR SCOPING: a blockquote carries the byte-identical declaration and is
    # deliberately OUT of scope, because neither DESIGN.md nor the craft floor names a blockquote.
    bq = ".prose-wh blockquote { border-left: 3px solid #F7A21B; font-style: italic; }"
    got2, n2 = patch(bq)
    if got2 != bq or n2:
        print("FAIL: the blockquote was rewritten - it shares .answer-first's declaration and must not be"); ok = False

    # and the two must be separable in ONE file, which is the real-world case
    both = (".answer-first { border-left: 3px solid #F7A21B; }\n"
            ".prose-wh blockquote { border-left: 3px solid #F7A21B; }")
    got3, n3b = patch(both)
    if got3.count("border-left: 3px solid #F7A21B;") != 1:
        print("FAIL: expected exactly the blockquote's bar to survive in a file holding both"); ok = False
    if "border: 1px solid rgba(247,162,27,0.30)" not in got3:
        print("FAIL: .answer-first was not converted when a blockquote sat beside it"); ok = False

    _, n3 = patch(got)
    if n3:
        print("FAIL: not idempotent"); ok = False
    print("self-test: %s" % ("PASS - bar replaced by a 1px tint, face preserved, idempotent" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
