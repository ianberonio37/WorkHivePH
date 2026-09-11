#!/usr/bin/env python3
"""i18n_wrap_sentences.py — wrap each authored English sentence as _t(en, fil) wherever a page's JavaScript
carries it (EX-TL, 2026-09-07).

The table is tools/i18n_tl_wave.json: exact English literal -> Filipino. utils.js defines _t on every page,
so a wrapped string reads English under WH_LANG=en and Filipino under fil - the mechanism the bilingual
pages already use. Two modes, both idempotent:

  1. WHOLE LITERAL in an expression position - `'Could not save'` becomes `_t('Could not save', 'Hindi ma-save')`
     when the character before the opening quote is one a JS expression can follow: ( , : = [ ? + || && or
     `return`. An = glued to an attribute name (`title="..."`) is HTML, not JS, and is left alone.
  2. SENTENCE INSIDE A FRAGMENT STRING - `'<p class="x">Could not load your parts.</p>'` becomes
     `'<p class="x">' + _t('Could not load your parts.', '...') + '</p>'`, and inside a backtick template it
     becomes `${_t(...)}`. The sentence must sit between > and < (or the string's own edges), so a word inside
     an attribute or a longer sentence is never cut. This is where most failure copy lives: innerHTML.

A sentence in a plain HTML text node or attribute is reported as "left in markup", never silently skipped.

  python tools/i18n_wrap_sentences.py --dry-run
  python tools/i18n_wrap_sentences.py
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "tools" / "i18n_tl_wave.json"
SKIP = {"design-system.html", "symbol-gallery.html", "validator-catalog.html", "promo-poster.html", "offline-fallback.html", "terms.html"}
EXPR_BEFORE = re.compile(r"(?:[(,:=\[?+]|\|\||&&|\breturn|\bthrow|=>)\s*$")
ATTR_BEFORE = re.compile(r"[\w-]=$")
ALREADY = (re.compile(r"_t\(\s*$"), re.compile(r"_t\(\s*['\"`][^'\"`]*['\"`]\s*,\s*$"))
# every quoted JS string, with its quote, over a comment-blanked copy of the source (same length, so offsets map 1:1)
# a backtick template may span lines (community's empty-state block does); a quoted string may not
QUOTED = re.compile(r"`((?:\\.|[^\\`])*)`|(['\"])((?:\\.|(?!\2)[^\\\n])*)\2")


def quoted_parts(m: re.Match) -> tuple[str, str, int]:
    """(quote, text, text_start) for either alternative of QUOTED."""
    if m.group(1) is not None:
        return "`", m.group(1), m.start(1)
    return m.group(2), m.group(3), m.start(3)


def roster() -> list[str]:
    return [f for f in sorted(p.name for p in ROOT.glob("*.html")) if f not in SKIP and not f.startswith("_")]


def blank_comments(s: str) -> str:
    """Comments replaced by spaces of the same length: an apostrophe in `// don't` must not open a string."""
    def sp(m: re.Match) -> str:
        return re.sub(r"[^\n]", " ", m.group(0))
    s = re.sub(r"<!--[\s\S]*?-->", sp, s)
    s = re.sub(r"/\*[\s\S]*?\*/", sp, s)
    s = re.sub(r"^[ \t]*//.*$", sp, s, flags=re.M)
    s = re.sub(r"[ \t]// .*$", sp, s, flags=re.M)
    return s


def js_quote(s: str, q: str) -> str:
    return q + s.replace("\\", "\\\\").replace(q, "\\" + q) + q


def inner_quote(en: str, fil: str, outer: str) -> str:
    """The quote for the _t() arguments inside a string opened with `outer`: prefer one neither text uses."""
    for q in ("'", '"'):
        if q != outer and q not in en and q not in fil:
            return q
    return "'" if outer != "'" else '"'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    table = {k: v for k, v in json.loads(TABLE.read_text(encoding="utf-8")).items() if not k.startswith("_")}
    # longest keys first, so a sentence that contains a shorter table sentence is wrapped whole
    keys = sorted(table, key=len, reverse=True)
    grand = 0
    for f in roster():
        path = ROOT / f
        src = path.read_text(encoding="utf-8")
        wrapped, markup = 0, set()

        # mode 1 - whole literal in an expression position
        for en in keys:
            fil = table[en]
            for q in ("'", '"', "`"):
                if q == "`" and "${" in en:
                    continue
                lit = q + en + q
                start = 0
                while True:
                    i = src.find(lit, start)
                    if i < 0:
                        break
                    before = src[max(0, i - 40):i]
                    if any(r.search(before) for r in ALREADY):
                        start = i + len(lit); continue
                    if ATTR_BEFORE.search(before) or not EXPR_BEFORE.search(before):
                        markup.add(en[:50]); start = i + len(lit); continue
                    repl = f"_t({lit}, {js_quote(fil, q)})"
                    src = src[:i] + repl + src[i + len(lit):]
                    wrapped += 1
                    start = i + len(repl)

        # mode 2 - the sentence between > and < (or the string's edges) inside a fragment string.
        # Only strings inside <script> blocks: an apostrophe in HTML prose (`<p>Don't`) would open a fake
        # string, and a rewrite there would print `' + _t(` to the person.
        changed = True
        while changed:
            changed = False
            blanked = blank_comments(src)
            scripts = [(s.start(), s.end()) for s in re.finditer(r"<script\b[^>]*>[\s\S]*?</script>", blanked, re.I)]
            for m in QUOTED.finditer(blanked):
                q, text, t0 = quoted_parts(m)
                in_script = any(a <= m.start() < b for a, b in scripts)
                # a `</script>` spelled inside a JS string ends the naive block early (inventory's fragment read as
                # "outside any script"); a string that carries its own tag edges on one line is a fragment either way
                looks_like_fragment = ">" in text and "<" in text and "\n" not in text
                if not in_script and not looks_like_fragment:
                    continue
                for en in keys:
                    if en not in text or len(en) == len(text):
                        continue
                    j = text.find(en)
                    left, right = text[:j], text[j + len(en):]
                    # boundaries: the string's edges, a tag edge, or (in a template) an interpolation edge -
                    # `${saved} from your saved copy` / `report${n > 1 ? 's' : ''} failed to generate.`
                    l_ok = left == "" or left.endswith(">") or (q == "`" and left.endswith("}"))
                    r_ok = right == "" or right.startswith("<") or (q == "`" and right.startswith("${"))
                    if not (l_ok and r_ok):
                        continue
                    a = t0 + j
                    iq = inner_quote(en, table[en], q)
                    call = f"_t({js_quote(en, iq)}, {js_quote(table[en], iq)})"
                    # `'<p>' + _t(...) + '</p>'`; at a string's edge this leaves a harmless `'' +` / `+ ''`
                    repl = "${" + call + "}" if q == "`" else f"{q} + {call} + {q}"
                    src = src[:a] + repl + src[a + len(en):]
                    wrapped += 1
                    changed = True
                    break
                if changed:
                    break

        if wrapped and not args.dry_run:
            path.write_text(src, encoding="utf-8", newline="")
        grand += wrapped
        note = f" · left in markup: {len(markup)}" if markup else ""
        if wrapped or markup:
            print(f"  {f:<34} wrapped {wrapped}{note}")
    print(f"\n  {grand} sentence(s) wrapped as _t(en, fil)" + (" (dry run)" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
