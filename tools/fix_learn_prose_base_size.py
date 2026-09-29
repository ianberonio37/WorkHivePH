"""19 learn articles never set a base size on `.prose-wh`, so their bullet lists
render 0.8px smaller than their own paragraphs.

~W46113 (audit walk, 2026-09-20). Third find in three rows from the same
fingerprint - A UA-DEFAULT VALUE APPEARING IN A MEASURED DISTRIBUTION. The walk
reported `16px` nodes in the type ramp; 16px is the root default, which is what an
element inherits when no ancestor sets a size.

THE MECHANISM, measured rather than inferred. 35 learn articles carry

    .prose-wh { overflow-wrap: anywhere; word-break: break-word;
                color: rgba(244,246,250,0.85); font-size: 1.05rem; line-height: 1.8; }

19 carry NO bare `.prose-wh` rule at all - only the descendant rules
(`.prose-wh p`, `.prose-wh h2`, `.prose-wh a`, ...). Paragraphs are therefore
correct everywhere, because `.prose-wh p` sets `font-size: 1.05rem` itself. Anything
inside the article body WITHOUT its own rule falls back to the root 16px - most
visibly every `<li>` in a bulleted list, which is a large share of the reading
surface in a how-to article. Measured live on
power-plant-reliability-metrics-philippines: paragraphs 16.8px, list items 16px.

The first reading of this looked like "no page defines a list font-size", which is
true of all 54 and is NOT the mechanism - the 35 correct pages never needed one,
because their lists inherit 16.8px from the container. Checking the two pages that
measured clean is what separated the real cause from the plausible one.

WHAT THE FIX CHANGES, simulated in the live DOM before applying: list items go
16px -> 16.8px with line-height 28px -> 29.4px (the same 1.75 ratio, now of the
right size) and gain `overflow-wrap: anywhere`, which matters on these pages
because they carry long identifiers (EAF, EFOR, kcal/kWh, SAP view names). Body
paragraphs are byte-identical before and after - they have their own rule. Colour
is unchanged. So the rule only reaches the elements that were wrong.

All 19 are the older chrome generation (no breadcrumb, no "Sign Up Free" header
CTA, no FAQ footer link, no `.cta-box`). The rule is inserted immediately before
`.prose-wh p`, where the 35 correct articles keep it.

    python tools/fix_learn_prose_base_size.py --check
    python tools/fix_learn_prose_base_size.py --apply
"""
from __future__ import annotations

import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PAGES = os.path.join(ROOT, "learn", "*", "index.html")

RULE = ("    .prose-wh { overflow-wrap: anywhere; word-break: break-word; "
        "color: rgba(244,246,250,0.85); font-size: 1.05rem; line-height: 1.8; }\n")

BARE_RE = re.compile(r"(?m)^\s*\.prose-wh\s*\{([^}]*)\}")
ANCHOR_RE = re.compile(r"(?m)^([ \t]*)\.prose-wh\s+p\s*\{")


def has_base_size(html: str) -> bool:
    styles = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html, re.S))
    m = BARE_RE.search(styles)
    return bool(m and "font-size" in m.group(1))


def uses_prose(html: str) -> bool:
    return bool(re.search(r'class="[^"]*\bprose-wh\b', html))


def sweep(apply: bool) -> int:
    missing, ok, noanchor = [], 0, []
    for p in sorted(glob.glob(PAGES)):
        name = os.path.basename(os.path.dirname(p))
        html = open(p, encoding="utf-8").read()
        if not uses_prose(html):
            continue
        if has_base_size(html):
            ok += 1
            continue
        missing.append(name)
        if apply:
            m = ANCHOR_RE.search(html)
            if not m:
                noanchor.append(name)
                continue
            open(p, "w", encoding="utf-8").write(html[:m.start()] + RULE + html[m.start():])

    if apply:
        done = len(missing) - len(noanchor)
        print(f"  added a .prose-wh base size to {done} page(s) ({ok} already had one)")
        if noanchor:
            print("  COULD NOT PATCH (no `.prose-wh p` anchor): " + ", ".join(noanchor))
            return 1
        return 0

    if missing:
        print(f"  FAIL: {len(missing)} learn article(s) set no base font-size on .prose-wh, "
              f"so every unsized element inside the article - bullet lists above all - "
              f"renders at the root 16px instead of 16.8px")
        for n in missing[:6]:
            print(f"     - learn/{n}/")
        if len(missing) > 6:
            print(f"     ... and {len(missing) - 6} more")
        print("  fix: python tools/fix_learn_prose_base_size.py --apply")
        return 1
    print(f"  OK: all {ok} learn article(s) set a base font-size on .prose-wh")
    return 0


if __name__ == "__main__":
    raise SystemExit(sweep("--apply" in sys.argv[1:]))
