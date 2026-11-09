#!/usr/bin/env python3
"""copy_rewrite.py - apply sentence rewrites to a page, located by the text the critic GRADED (Wave CF, 2026-11-08).

tools/copy_offenders.mjs lists the sentences the rubric's B3/B1 fail, as the reader sees them (inline tags merged, entities
decoded). This finds each one in the page SOURCE, tolerating inline tags and entities inside it, and replaces the span:

    python tools/copy_rewrite.py learn/what-is-oee-how-to-calculate/index.html .tmp/copy/what-is-oee.rw.json [--apply]

The map is a JSON list of {"old": "<graded text>", "new": "<replacement, HTML allowed>"}. Rules, all refusals not warnings:
  * the old text must match exactly ONE place outside <script>/<style>;
  * a span holding a link must keep it: every href in the old span must appear in the new HTML;
  * every sentence of the new text must pass the lens's own B3 ruler (tools/b3_ruler.mjs: <=20 words, active, grade <=8
    for 12+ words) - a rewrite that fails the ruler is not written;
  * the same plain sentence inside JSON-LD (an FAQ answer) is replaced with the new text's plain form, so the markup that
    search engines read keeps matching the page.
Dry by default: prints each span and verdict. --apply writes the page.
"""
from __future__ import annotations

import html
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENT = {"’": "(?:’|&rsquo;|&#8217;|')", "‘": "(?:‘|&lsquo;|&#8216;|')", "'": "(?:'|’|&rsquo;|&#39;|&#x27;)",
       "“": "(?:“|&ldquo;|\")", "”": "(?:”|&rdquo;|\")", '"': "(?:\"|&quot;|“|”)",
       "—": "(?:—|&mdash;)", "–": "(?:–|&ndash;)", "&": "(?:&amp;|&)", "×": "(?:×|&times;)",
       "→": "(?:→|&rarr;)", "<": "(?:&lt;|<)", ">": "(?:&gt;|>)", "…": "(?:…|&hellip;)", "·": "(?:·|&middot;)"}
TAG = r"(?:<[^>]+>)*"
GAP = r"(?:\s|&nbsp;|<[^>]+>)+"


def pattern(old: str) -> re.Pattern:
    words = old.split()
    parts = []
    for w in words:
        parts.append(TAG.join(ENT.get(ch, re.escape(ch)) for ch in w))
    return re.compile(GAP.join(parts))


class _Span:
    def __init__(self, a: int, b: int):
        self._a, self._b = a, b

    def start(self) -> int:
        return self._a

    def end(self) -> int:
        return self._b


def _all(src: str, sub: str) -> list:
    out, k = [], src.find(sub)
    while k != -1:
        out.append(k)
        k = src.find(sub, k + 1)
    return out


def protected(src: str) -> list:
    return [(m.start(), m.end()) for m in re.finditer(r"<(script|style)\b[^>]*>.*?</\1>", src, re.S | re.I)]


def plain(h: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", h))).strip()


FORMULA = (re.compile(r"\S\s*=\s*\S"), re.compile(r"[×÷*/+%]|\d"))


def ruler(text: str) -> list:
    # grade each block the way the lens does: an element whose text holds a formula ("=" with numbers or operators) is
    # not graded for B3 at all (survey_ufai_rubric.js skips it), so neither is its chunk here
    sents = []
    for chunk in re.split(r"</p>|<p\b[^>]*>|</div>|<div\b[^>]*>|</li>|<li\b[^>]*>|</td>|<td\b[^>]*>|</th>|<th\b[^>]*>", text):
        pc = plain(chunk)
        # ...and a middle-dot list (two or more "·") is a list of facts, not prose - the lens skips it too
        if not pc or (FORMULA[0].search(pc) and FORMULA[1].search(pc)) or pc.count("·") >= 2:
            continue
        sents += [s for s in re.split(r"(?<=[.!?])\s+", pc) if len(s.split()) >= 4]
    if not sents:
        return []
    r = subprocess.run(["node", str(ROOT / "tools" / "b3_ruler.mjs"), "--json", *sents], capture_output=True, text=True,
                       encoding="utf-8")
    bad = []
    for line in r.stdout.splitlines():
        try:
            j = json.loads(line)
        except ValueError:
            continue
        if j.get("fails"):
            bad.append({"words": j.get("words"), "grade": j.get("grade"), "text": j.get("sentence", ""), "why": j["fails"]})
    return bad


def main() -> int:
    page, mp = Path(sys.argv[1]), Path(sys.argv[2])
    apply = "--apply" in sys.argv
    src = page.read_text(encoding="utf-8")
    pairs = json.loads(mp.read_text(encoding="utf-8"))
    refused = 0
    for i, pr in enumerate(pairs):
        new = pr["new"]
        prot = protected(src)
        if "raw_old" in pr:
            # a whole paragraph, named by its exact SOURCE text (tags and entities as written)
            old = plain(pr["raw_old"])
            hits = [_Span(k, k + len(pr["raw_old"])) for k in _all(src, pr["raw_old"])
                    if not any(a <= k < b for a, b in prot)]
        else:
            old = pr["old"]
            hits = [m for m in pattern(old).finditer(src) if not any(a <= m.start() < b for a, b in prot)]
        if len(hits) != 1:
            print(f"  [{i}] REFUSED - {len(hits)} match(es) outside scripts: {old[:80]!r}")
            refused += 1
            continue
        m = hits[0]
        span = src[m.start():m.end()]
        hrefs = re.findall(r'href="([^"]+)"', span)
        lost = [h for h in hrefs if f'href="{h}"' not in new]
        if lost:
            print(f"  [{i}] REFUSED - the new text drops link(s) {lost}; source span: {span[:300]!r}")
            refused += 1
            continue
        # ★A SPAN THAT ENDS ON A CLOSING QUOTE JOINS THE NEXT SENTENCE (M13, 2026-11-09). The lens splits only where a
        # terminal mark is followed by whitespace, so `later." See ...` is ONE sentence to it - while this tool graded only
        # the new span, which ended at the quote and passed. UpKeep's guide failed B3 on exactly that join. When the page
        # carries more text after the span, the terminal mark must sit outside the quote.
        _tail = re.sub(r"<[^>]+>", "", new).rstrip()
        _after = re.sub(r"<[^>]+>", "", src[m.end():m.end() + 80]).lstrip()
        if re.search(r"[.!?][\"”’'](?:&rdquo;|&rsquo;)?$|[.!?](?:&rdquo;|&rsquo;|&quot;)$", _tail) and _after[:1].isalnum():
            print(f"  [{i}] REFUSED - ends on a closing quote, so the lens reads it and the next sentence as one: "
                  f"{_tail[-50:]!r} + {_after[:30]!r} - put the period outside the quote")
            refused += 1
            continue
        bad = ruler(new)
        if bad:
            print(f"  [{i}] REFUSED - fails the B3 ruler: " + " | ".join(f"{b.get('words')}w g{b.get('grade')} {b.get('text', '')[:60]!r}" for b in bad))
            refused += 1
            continue
        src = src[:m.start()] + new + src[m.end():]
        # the same sentence in JSON-LD (an FAQ answer) keeps matching the page
        po, pn = plain(old), plain(new)
        for jm in list(re.finditer(r'(<script type="application/ld\+json">)(.*?)(</script>)', src, re.S)):
            body = jm.group(2)
            if po in body:
                src = src[:jm.start(2)] + body.replace(po, pn.replace('"', '\\"')) + src[jm.end(2):]
                break
        print(f"  [{i}] ok{' (had tags: ' + ', '.join(sorted(set(re.findall(r'<(\\w+)', span)))) + ')' if '<' in span else ''}")
    print(f"{len(pairs) - refused} of {len(pairs)} rewrite(s) placed{'' if apply else ' (dry - nothing written)'}")
    if apply and refused == 0:
        page.write_text(src, encoding="utf-8", newline="")
        print(f"  wrote {page}")
    elif apply:
        print("  NOT written - fix the refused rewrites first (all or nothing)")
    return 1 if refused else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
