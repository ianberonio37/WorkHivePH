#!/usr/bin/env python3
"""fix_cta_specificity.py — a prose-link rule was out-specifying the primary CTA on 27 public pages.

FOUND 2026-09-10, walking J30 as a solo owner arriving from search. On
learn/free-engineering-calculators-philippine-plants the page's own primary button, `.cta-btn`
("Open Engineering Design"), computed to color #5FCCE8 - light blue on its orange gradient,
measured 1.11:1 against a 4.5 requirement - and rendered UNDERLINED.

THE MECHANISM IS PURE CASCADE, NOT A WRONG COLOUR. `.cta-btn { color:#162032 }` is specificity
(0,1,0). The button sits inside the article body, and `.prose-wh a { color:#5FCCE8;
text-decoration:underline }` is (0,1,1). The later, more specific rule wins, so every page that
puts its call to action inside its own prose paints that button's label as a link. The declared
navy was never wrong; it was never applied.

THE FIX RAISES THE BUTTON'S SPECIFICITY TO MATCH, and does not touch the prose rule - ordinary
in-article links must keep looking like links. `.prose-wh a.cta-btn` is (0,2,1), which beats
(0,1,1) without !important and without reordering anything.

27 of 115 public pages carry a `.cta-btn` inside prose; all 27 declare the identical rule, so the
insertion is the same line in the same place. The remaining 88 have no `.cta-btn` at all and are
left untouched.

  python tools/fix_cta_specificity.py --check
  python tools/fix_cta_specificity.py --apply
"""
from __future__ import annotations

import glob
import io
import re
import sys

ANCHOR = re.compile(r'^(\s*)(\.cta-btn \{[^}]*\})\s*$', re.M)

FIX = ('.prose-wh a.cta-btn { color: #162032; text-decoration: none; }'
       '  /* (0,2,1) beats .prose-wh a (0,1,1): a button inside the article body keeps its own'
       ' colour instead of being painted as a prose link (measured 1.11:1 before this) */')


def targets() -> list[str]:
    files = sorted(glob.glob('learn/*/index.html') + glob.glob('tools/*/index.html')
                   + ['learn/index.html'])
    out = []
    for f in files:
        try:
            s = io.open(f, encoding='utf-8').read()
        except OSError:
            continue
        if 'class="cta-btn"' in s and '.prose-wh a.cta-btn' not in s and ANCHOR.search(s):
            out.append(f)
    return out


def apply_to(path: str) -> bool:
    s = io.open(path, encoding='utf-8').read()
    m = ANCHOR.search(s)
    if not m:
        return False
    indent = m.group(1)
    new = s[:m.end()] + '\n' + indent + FIX + s[m.end():]
    io.open(path, 'w', encoding='utf-8', newline='').write(new)
    return True


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else '--check'
    t = targets()
    if mode == '--check':
        print(f'{len(t)} page(s) put a .cta-btn inside .prose-wh and lack the specificity fix')
        for f in t:
            print('  ' + f)
        return 0
    if mode != '--apply':
        print('usage: fix_cta_specificity.py [--check|--apply]')
        return 2
    n = sum(1 for f in t if apply_to(f))
    print(f'fixed {n} of {len(t)} page(s)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
