#!/usr/bin/env python3
"""fix_breadcrumb_contrast.py — the breadcrumb on 95 public pages sat below WCAG AA.

FOUND 2026-09-10, walking J30 as a solo owner arriving from search. The rubric's C2 flagged
"Free engineering calcula..." at 4.13:1 against a 4.5 requirement. It is the BREADCRUMB - the
trail that tells a search arrival where in the site they have landed, which is the one navigation
aid that audience has - rendered at rgba(244,246,250,0.45), 13.6px, on #162032.

THE ARITHMETIC, not a guess. Compositing #F4F6FA at alpha a over #162032 and applying the WCAG
relative-luminance formula:

    a = 0.45  ->  4.12:1   (matches the rubric's measured 4.13 - the model is calibrated)
    a = 0.50  ->  4.76:1   (passes, thin margin)
    a = 0.55  ->  5.47:1   (passes with room)

0.55 is chosen: it clears AA with margin while keeping the breadcrumb visibly secondary to the
headline, which is the whole reason it was dimmed. `--verify` re-derives the ratio from the file
rather than trusting this docstring.

All 95 pages carry the IDENTICAL rule, so this is one line in one place, 95 times. The 20 public
pages with no breadcrumb rule are untouched.

  python tools/fix_breadcrumb_contrast.py --check
  python tools/fix_breadcrumb_contrast.py --apply
  python tools/fix_breadcrumb_contrast.py --verify
"""
from __future__ import annotations

import glob
import io
import re
import sys

OLD = 'color: rgba(244,246,250,0.45)'
NEW = 'color: rgba(244,246,250,0.55)'
BLOCK = re.compile(r'\.breadcrumb \{[^}]*\}')
BG = (22, 32, 50)          # #162032, the page ground
FG = (244, 246, 250)       # #F4F6FA


def _lin(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _lum(rgb) -> float:
    r, g, b = (_lin(x) for x in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(alpha: float) -> float:
    comp = tuple(FG[i] * alpha + BG[i] * (1 - alpha) for i in range(3))
    hi, lo = _lum(comp) + 0.05, _lum(BG) + 0.05
    return round(max(hi, lo) / min(hi, lo), 2)


def pages() -> list[str]:
    return sorted(glob.glob('learn/*/index.html') + glob.glob('tools/*/index.html')
                  + ['learn/index.html'])


def targets() -> list[str]:
    out = []
    for f in pages():
        try:
            s = io.open(f, encoding='utf-8').read()
        except OSError:
            continue
        m = BLOCK.search(s)
        if m and OLD in m.group(0):
            out.append(f)
    return out


def apply_to(path: str) -> bool:
    s = io.open(path, encoding='utf-8').read()
    m = BLOCK.search(s)
    if not m or OLD not in m.group(0):
        return False
    fixed = m.group(0).replace(OLD, NEW)
    io.open(path, 'w', encoding='utf-8', newline='').write(s[:m.start()] + fixed + s[m.end():])
    return True


def verify() -> int:
    bad, ok = [], 0
    for f in pages():
        s = io.open(f, encoding='utf-8').read()
        m = BLOCK.search(s)
        if not m:
            continue
        a = re.search(r'rgba\(244,246,250,([0-9.]+)\)', m.group(0))
        if not a:
            bad.append((f, 'no rgba alpha in the .breadcrumb rule'))
            continue
        r = ratio(float(a.group(1)))
        if r < 4.5:
            bad.append((f, f'alpha {a.group(1)} -> {r}:1, below AA 4.5'))
        else:
            ok += 1
    print(f'{ok} breadcrumb rule(s) at or above WCAG AA 4.5:1; {len(bad)} below')
    for f, why in bad[:10]:
        print('  ' + f + ' — ' + why)
    return 1 if bad else 0


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else '--check'
    if mode == '--verify':
        return verify()
    t = targets()
    if mode == '--check':
        print(f'{len(t)} page(s) render the breadcrumb at alpha 0.45 ({ratio(0.45)}:1, below AA 4.5)')
        print(f'  -> alpha 0.55 gives {ratio(0.55)}:1')
        for f in t[:6]:
            print('  ' + f)
        if len(t) > 6:
            print(f'  ... and {len(t) - 6} more')
        return 0
    if mode != '--apply':
        print('usage: fix_breadcrumb_contrast.py [--check|--apply|--verify]')
        return 2
    n = sum(1 for f in t if apply_to(f))
    print(f'fixed {n} of {len(t)} page(s)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
