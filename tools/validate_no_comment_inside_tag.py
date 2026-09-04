""" -*- coding: utf-8 -*-
Is there an HTML comment opened INSIDE a tag? (2026-08-28)

Writing `<div class="x"  <!-- why --›  data-y="z">` is not a syntax error to a browser. It parses
the comment's words as BOGUS ATTRIBUTES on the element and carries on: nothing throws, the console
stays clean, and the attributes after it may or may not survive. That silence is the whole problem
— the failure mode of this mistake is a page that looks fine and an element that quietly lost a
property something else depends on.

★THIS GATE EXISTS BECAUSE I MADE THE MISTAKE TWICE IN ONE SESSION. Once on pm-scheduler's deferral
button, where the comment landed between the button's attributes; once on alert-hub's AMC stat
tile, between data-rag-tile and data-rag-label — the second time while fixing a defect in that very
attribute. Both were caught by reading the file back afterwards, which is luck dressed as
discipline: the browser will not tell you, and neither will a page-loads-clean smoke.

WHAT IT DOES NOT FLAG: a comment BETWEEN elements (the normal, correct place), a comment inside
<script> or <style> (that is JS/CSS, with its own comment syntax and its own meaning for `<`), and
a `<!--` that appears inside a quoted attribute VALUE, which is legal text.

USAGE:  python tools/validate_no_comment_inside_tag.py
Exit 1 the moment one exists — the tree is clean today, so this is a floor, not a ratchet.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".emoji_bak", ".hexvar_bak",
             ".leftover_bak", ".palette_bak", ".tmp", "_fixtures"}

BLOCKS = re.compile(r"<script\b.*?</script>|<style\b.*?</style>", re.S | re.I)


def offenders(src: str) -> list[int]:
    """Line numbers where a comment opens while a tag is still unclosed."""
    # Blank out script/style bodies but KEEP their newlines, so line numbers stay true.
    src = BLOCKS.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), src)
    hits, i, n = [], 0, len(src)
    while i < n:
        lt = src.find("<", i)
        if lt == -1:
            break
        # only element tags, not comments/doctype/closing marks
        if not re.match(r"<[a-zA-Z]", src[lt:lt + 2]):
            i = lt + 1
            continue
        j, quote = lt + 1, None
        while j < n:
            ch = src[j]
            if quote:
                if ch == quote:
                    quote = None
            elif ch in "\"'":
                quote = ch          # a <!-- inside a quoted VALUE is legal text
            elif ch == ">":
                break
            elif src.startswith("<!--", j):
                hits.append(src[:j].count("\n") + 1)
                break
            j += 1
        i = j + 1
    return hits


# ★THE PARSER CHECKS ITSELF BEFORE IT CHECKS THE TREE. This is a hand-rolled scanner, and a
# hand-rolled scanner that quietly stops matching reports a clean tree — the same permanent-false-
# green shape this codebase keeps meeting. These eight cases pin the behaviour that matters: the
# marker is legal inside a quoted VALUE and inside a script body, a bare `<` or `>` in text is not a
# tag boundary, and the mistake is caught in all three ways it has actually been written (plain,
# multi-line, single-quoted attributes). If the scanner is broken, the run says so instead of
# passing.
SELFTEST = [
    ("<!-- a normal comment --><div>x</div>", 0, "comment between elements"),
    ('<div title="a <!-- b">x</div>', 0, "marker inside a quoted value"),
    ('<div class="a" <!-- bad --> id="b">x</div>', 1, "the mistake, plain"),
    ('<div title="5 > 3">x</div>', 0, "a > inside a quoted value"),
    ("<script>if (a <!--b) {}</script>", 0, "inside a script body"),
    ("<p>2 < 3 and 5 > 4</p>", 0, "bare comparison text"),
    ('<a href="x"\n  <!-- multi\n  line --> id="y">z</a>', 1, "the mistake, multi-line"),
    ("<div data-x='a' <!-- c --> b>x</div>", 1, "the mistake, single-quoted attrs"),
]


def selftest() -> list[str]:
    return [f"{note}: expected {want}, got {len(offenders(src))}"
            for src, want, note in SELFTEST if len(offenders(src)) != want]


def main() -> int:
    print("no-comment-inside-tag - a comment between attributes becomes bogus attributes\n")
    broken = selftest()
    if broken:
        print("FAIL no-comment-inside-tag - the SCANNER is wrong, so its reading of the tree means nothing:")
        for b in broken:
            print(f"    {b}")
        return 1
    print(f"  scanner self-test: {len(SELFTEST)}/{len(SELFTEST)} cases correct")
    files = [p for p in ROOT.rglob("*.html")
             if not any(part in SKIP_DIRS for part in p.parts)]
    bad, scanned = [], 0
    for f in files:
        try:
            src = io.open(f, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        scanned += 1
        for ln in offenders(src):
            bad.append(f"{f.relative_to(ROOT).as_posix()}:{ln}")

    print(f"  {scanned} html files scanned | {len(bad)} comment(s) opened inside a tag")
    for b in bad[:20]:
        print(f"    {b}")
    print()
    if bad:
        print("FAIL no-comment-inside-tag - the browser will not error on these. It will read the")
        print("  comment's words as attributes and keep going, so the element quietly loses whatever")
        print("  came after it. Move the comment ABOVE the element.")
        return 1
    print("PASS no-comment-inside-tag - every comment sits between elements, not inside one.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
