"""The learn articles' table-of-contents label renders UNSTYLED on 45 of 54 pages.

~W46101 (audit walk, 2026-09-20), found on
learn/connecting-workhive-to-sap-maximo-cmms/. The walk reported a nine-step type
ramp where the calculator family has seven, and the extra step was a single 16px
node among 200 - the browser's UA default, which is what an element gets when no
rule matches it at all.

WHAT IT IS. Every learn article opens with

    <div class="toc"><h4 aria-level="2">What's in this guide</h4><ol>...

and each article carries its own inline <style>. The rule that dresses that label
is `.toc h2` on 50 pages and `.toc h4` on 4. The MARKUP is <h4> on 49 and <h2> on
5. Cross the two and the result is:

    h4 markup + `.toc h2` rule -> 45 pages   UNSTYLED
    h2 markup + `.toc h2` rule ->  5 pages   styled
    h4 markup + `.toc h4` rule ->  4 pages   styled

On the 45, the label falls to the UA default: 16px, font-weight 400, margin 0, no
tracking, no uppercase - measured live. Its own list items are 15.2px, so the
heading that introduces the list is effectively the same size as the list, with no
space beneath it. What it should be is a small kicker: 12px (or 13.6px on the
second variant), weight 800 or 600, uppercase.

HOW IT HAPPENED, AND THE COMMENT THAT PREDICTED IT. Five pages carry a hand-written
note above their <h2>:

    "h2, not h4: this label is a PEER of the article's h2 sections ... The .toc h2
     rule below keeps the small-caps look identical -- the selector had to move
     with the tag, or the swap would have silently rendered a full-size heading."

That is exactly right, and exactly what happened. The SELECTOR move (h4 -> h2)
reached ~50 pages; the MARKUP move (h4 -> h2) reached 5. One half of a paired write
landed and the other did not, and because every page is well-formed on its own the
result is invisible to any single-page check - it only shows as a stray step in the
type ramp, and only when you ask why a family of 54 generated pages has nine ramp
sizes where its sibling family has seven.

A second, quieter claim was also false: tools/fix_learn_heading_order.py's docstring
states "the visual styling (which keys on the h4 tag)" is "preserved exactly". The
rule it names, `.toc h4`, exists on 4 of the 49 pages with a TOC. That docstring is
corrected in the same change as this sweep.

THE FIX, AND WHY IT IS THIS ONE. The root is that the styling was COUPLED TO THE
TAG, so moving the tag silently unstyled the element. Re-coupling them (rewriting
the markup back to <h2>, or the selector back to `.toc h4`) would fix today's
symptom and leave the same trap armed. The selector becomes `.toc h2, .toc h4`
instead, which matches whichever tag the label carries and cannot come apart again.

Tracking is also brought to 0.04em. DESIGN.md reserves all-caps for short status
labels at 0.04em or tighter, and these rules carry 0.12em and 0.08em. That is not
cosmetic housekeeping: 45 pages are about to start rendering uppercase tracked text
that renders as nothing today, and shipping them at 0.12em would raise the
`wide-tracking` count in design_detector_baseline.json and fail the anti-slop
ratchet. Every other declaration in each page's rule is left exactly as that page
has it, so both existing size/weight variants survive.

    python tools/fix_learn_toc_label.py --check
    python tools/fix_learn_toc_label.py --apply
"""
from __future__ import annotations

import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

PAGES = os.path.join(ROOT, "learn", "*", "index.html")

WANT_SELECTOR = ".toc h2, .toc h4"
WANT_TRACKING = "0.04em"

# ── Third leg, added ~W46129 ──────────────────────────────────────────────────
# The label was <h4 aria-level="2"> on 49 articles and <h2> on 5. aria-level was
# chosen by tools/fix_learn_heading_order.py as the low-blast-radius way to fix an
# h1 -> h4 outline jump, on the stated grounds that "the visual styling keys on the
# h4 tag" - a premise this sweep's own docstring already records as false.
#
# With the selector now matching BOTH tags, that premise is gone and the tag can
# simply be correct: an <h2> IS level 2, so it needs no ARIA override, the markup
# and the accessibility tree agree, and `.toc h2, .toc h4` styles it either way.
#
# It also removes a real instrument artifact rather than disproving it 49 times:
# `impeccable detect` reads the TAG and ignores aria-level, so every one of those
# articles reported `skipped-heading: <h1> followed by <h4> (missing h2)` - a
# warning that is false (the walk, which honours aria-level, measures headingSkips
# ZERO on the same pages) but that a reader of the detector output has to re-refute
# every time. Converging the tag makes both instruments agree with the truth.
TOC_H4_RE = re.compile(
    r'(<div class="toc">\s*(?:<!--.*?-->\s*)?)<h4\s+aria-level="2"\s*>(.*?)</h4>', re.S)

# the .toc heading rule, whichever selector it currently carries
RULE_RE = re.compile(
    r"(?P<sel>\.toc\s+h2\s*,\s*\.toc\s+h4|\.toc\s+h[24])\s*\{(?P<body>[^}]*)\}")
TRACK_RE = re.compile(r"(letter-spacing\s*:\s*)([^;}]+)")


def fix_block(css: str):
    """Rewrite the .toc heading rule's selector and tracking. Returns (css, changed)."""
    m = RULE_RE.search(css)
    if not m:
        return css, False
    body = m.group("body")
    new_body = body
    if TRACK_RE.search(new_body):
        new_body = TRACK_RE.sub(lambda mm: mm.group(1) + WANT_TRACKING, new_body, count=1)
    else:
        # no tracking declared: add one, preserving the trailing-semicolon style
        stripped = new_body.rstrip()
        sep = "" if stripped.endswith(";") or not stripped else ";"
        new_body = stripped + sep + f" letter-spacing: {WANT_TRACKING};"
    new_rule = f"{WANT_SELECTOR} {{{new_body}}}"
    if m.group(0) == new_rule:
        return css, False
    return css[:m.start()] + new_rule + css[m.end():], True


def page_state(html: str):
    """(has_toc, markup_tag, selector_text) for reporting."""
    tocm = re.search(r'<div class="toc">(.*?)</div>', html, re.S)
    if not tocm:
        return False, None, None
    hm = re.search(r"<(h[1-6])[^>]*>", tocm.group(1))
    styles = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html, re.S))
    sm = RULE_RE.search(styles)
    return True, (hm.group(1) if hm else None), (sm.group("sel") if sm else None)


def sweep(apply: bool) -> int:
    changed, ok, skipped = [], 0, []
    for p in sorted(glob.glob(PAGES)):
        name = os.path.basename(os.path.dirname(p))
        html = open(p, encoding="utf-8").read()
        has_toc, tag, sel = page_state(html)
        if not has_toc:
            skipped.append(name + " (no .toc)")
            continue
        if sel is None:
            skipped.append(name + " (no .toc heading rule)")
            continue

        # rewrite only inside <style> blocks
        out, hit = [], False
        pos = 0
        for m in re.finditer(r"(<style[^>]*>)(.*?)(</style>)", html, re.S):
            new_css, did = fix_block(m.group(2))
            if did:
                hit = True
                out.append(html[pos:m.start()])
                out.append(m.group(1) + new_css + m.group(3))
                pos = m.end()
        out.append(html[pos:])
        new_html = "".join(out)

        # third leg: the tag itself (see TOC_H4_RE above)
        converged, n_tag = TOC_H4_RE.subn(r"\1<h2>\2</h2>", new_html)
        if n_tag:
            hit = True
            new_html = converged

        if not hit:
            ok += 1
            continue
        changed.append((name, tag, sel))
        if apply:
            open(p, "w", encoding="utf-8").write(new_html)

    if skipped:
        print(f"  skipped {len(skipped)}: " + ", ".join(skipped[:4])
              + (" ..." if len(skipped) > 4 else ""))
    if apply:
        print(f"  rewrote {len(changed)} of {len(changed) + ok} .toc heading rules "
              f"({ok} already correct)")
        return 0
    if changed:
        print(f"  FAIL: {len(changed)} learn article(s) have a .toc heading rule that "
              f"does not match both tags or tracks wider than {WANT_TRACKING}")
        for n, tag, sel in changed[:6]:
            print(f"     - learn/{n}/  (markup <{tag}>, selector `{sel}`)")
        if len(changed) > 6:
            print(f"     ... and {len(changed) - 6} more")
        print("  fix: python tools/fix_learn_toc_label.py --apply")
        return 1
    print(f"  OK: all {ok} learn .toc heading rules match both tags at {WANT_TRACKING}")
    return 0


def unstyled_report() -> int:
    """The teeth: no page may render its TOC label unstyled."""
    bad = []
    total = 0
    for p in sorted(glob.glob(PAGES)):
        html = open(p, encoding="utf-8").read()
        has_toc, tag, sel = page_state(html)
        if not has_toc or not tag:
            continue
        total += 1
        if sel is None:
            bad.append((os.path.basename(os.path.dirname(p)), tag, "(no rule)"))
            continue
        # the selector must mention the tag the markup actually uses
        if tag not in sel:
            bad.append((os.path.basename(os.path.dirname(p)), tag, sel))
    h4s = sum(1 for p in glob.glob(PAGES)
              if TOC_H4_RE.search(open(p, encoding="utf-8").read()))
    if h4s:
        print(f"  FAIL: {h4s} article(s) still label the TOC with <h4 aria-level=\"2\"> - the tag "
              f"and the accessibility level disagree, and the detector reports a false "
              f"skipped-heading on every one")
        bad.append(("<tag convergence>", "h4", "aria-level=2"))
    print(f"  toc label: {total} article(s) with a TOC, {len(bad)} rendering UNSTYLED")
    if bad:
        print("  FAIL: the selector does not match the markup tag, so the label falls "
              "to the browser default:")
        for n, tag, sel in bad[:6]:
            print(f"     - learn/{n}/  <{tag}> vs `{sel}`")
        if len(bad) > 6:
            print(f"     ... and {len(bad) - 6} more")
    return 1 if bad else 0


def main() -> int:
    args = sys.argv[1:]
    apply = "--apply" in args
    rc = unstyled_report()
    rc |= sweep(apply)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
