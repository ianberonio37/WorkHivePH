"""Five learn articles use `.callout` and never style it, so the box is not a box.

~W46113 (audit walk, 2026-09-20), found on
learn/fmea-worked-example-philippine-bottling-line/ by the same fingerprint that
found the unstyled table-of-contents label one row earlier: a UA-DEFAULT VALUE
APPEARING IN A MEASURED DISTRIBUTION. The walk reported `16px x4` in the type ramp
on a page whose body copy is 16.8px (`.prose-wh p { font-size: 1.05rem }`). 16px is
what an element gets when nothing sets its size.

WHAT IT IS. `<div class="callout">` is the article furniture that carries a
cross-reference or an aside - on this page, "Part of the maintenance metrics guide:
OEE, MTBF, MTTR and reliability". 42 learn articles define the rule:

    .callout { background: rgba(41,182,217,0.06); border: 1px solid
               rgba(41,182,217,0.28); border-radius: 8px; padding: 20px 22px;
               margin: 2rem 0; font-size: 0.95rem; line-height: 1.7;
               color: rgba(244,246,250,0.85); }
    .callout strong { color: #A4E2F2; }

FIVE pages use the class and define NOTHING for it - measured across all 54 -
so eight callout elements render with no background, no border, no radius, no
padding, no margin, and at the browser's 16px rather than the intended 15.2px.
A reader meets an aside that is visually indistinguishable from the paragraph
above it, except that it is very slightly SMALLER than the body text it interrupts,
which is the one thing it should not be. The affected pages:

    fmea-worked-example-philippine-bottling-line        x1
    loto-procedures-dole-oshs-template                  x2
    power-plant-reliability-metrics-philippines         x2
    ra-11285-energy-efficiency-plant-checklist          x2
    reliability-centered-maintenance-philippine-plants  x1

All five are among the 18 articles that carry the older chrome generation (no
breadcrumb, no "Sign Up Free" header CTA, no FAQ footer link), so this is where
the rule was dropped rather than five independent slips.

WHY THIS AND NOT A SHARED STYLESHEET. Every learn article carries its own inline
<style> by design - that is the template, not an accident, and moving 54 articles
onto a shared sheet is a different job with a different blast radius. This sweep
adds the majority rule (32 of 42 pages carry it byte-identical; the variants differ
only in padding 22 vs 24 and colour alpha 0.85 vs 0.78) to the five pages missing
it, immediately before the `.cta-box` rule where every other article keeps it.

    python tools/fix_learn_callout_rule.py --check
    python tools/fix_learn_callout_rule.py --apply
"""
from __future__ import annotations

import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PAGES = os.path.join(ROOT, "learn", "*", "index.html")

RULE = (
    "    .callout { background: rgba(41,182,217,0.06); border: 1px solid "
    "rgba(41,182,217,0.28); border-radius: 8px; padding: 20px 22px; margin: 2rem 0; "
    "font-size: 0.95rem; line-height: 1.7; color: rgba(244,246,250,0.85); }\n"
    "    .callout strong { color: #A4E2F2; }\n"
)

USE_RE = re.compile(r'class="[^"]*\bcallout\b')
DEF_RE = re.compile(r"(^|[,{}\s])\.callout\b[^{]*\{", re.M)
# The 42 correct articles keep the pair immediately before `.cta-box`. The five
# missing it are all on the older chrome generation, which has no `.cta-box` at
# all - its equivalent CTA rule is `.tool-cta`, present on every one of the five.
# Anchoring on either keeps the rule in the same neighbourhood on both templates.
# (The first version of this sweep anchored only on `.cta-box` and reported
# "added to 0 pages / COULD NOT PATCH" on all five rather than writing anything -
# which is the behaviour a sweep should have when its anchor is absent.)
ANCHOR_RE = re.compile(r"^([ \t]*)\.(?:cta-box|tool-cta)\s*\{", re.M)


def state(html: str):
    styles = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html, re.S))
    uses = len(USE_RE.findall(html))
    defined = bool(DEF_RE.search(styles))
    return uses, defined


def patch(html: str):
    """Insert the .callout pair before the CTA rule. Returns (html, ok)."""
    m = ANCHOR_RE.search(html)
    if not m:
        return html, False
    return html[:m.start()] + RULE + html[m.start():], True


def sweep(apply: bool) -> int:
    missing, styled, unused, noanchor = [], 0, 0, []
    for p in sorted(glob.glob(PAGES)):
        name = os.path.basename(os.path.dirname(p))
        html = open(p, encoding="utf-8").read()
        uses, defined = state(html)
        if not uses:
            unused += 1
            continue
        if defined:
            styled += 1
            continue
        missing.append((name, uses))
        if apply:
            new_html, ok = patch(html)
            if not ok:
                noanchor.append(name)
                continue
            open(p, "w", encoding="utf-8").write(new_html)

    if apply:
        done = len(missing) - len(noanchor)
        print(f"  added the .callout rule to {done} page(s) "
              f"({styled} already had it, {unused} do not use the class)")
        if noanchor:
            print("  COULD NOT PATCH (no .cta-box anchor): " + ", ".join(noanchor))
            return 1
        return 0

    if missing:
        total = sum(u for _, u in missing)
        print(f"  FAIL: {len(missing)} learn article(s) use .callout without styling it "
              f"- {total} element(s) render at the browser default with no box")
        for n, u in missing:
            print(f"     - learn/{n}/  ({u} callout element(s))")
        print("  fix: python tools/fix_learn_callout_rule.py --apply")
        return 1
    print(f"  OK: all {styled} learn article(s) that use .callout also style it "
          f"({unused} do not use the class)")
    return 0


if __name__ == "__main__":
    raise SystemExit(sweep("--apply" in sys.argv[1:]))
