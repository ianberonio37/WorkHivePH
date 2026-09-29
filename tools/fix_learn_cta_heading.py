"""The learn CTA/related headings declare aria-level="3" on an <h4> tag.

~W46129 (audit walk, 2026-09-20), the sibling of the TOC-label convergence in
tools/fix_learn_toc_label.py and found the same way: `impeccable detect` reported
`skipped-heading: <h2> ... followed by <h4> ... (missing h3)` while the walk, which
honours aria-level, measured headingSkips ZERO on the same page. The ARIA level is
CORRECT and the TAG is not, so every reader that trusts the tag re-raises a finding
that every reader honouring ARIA correctly dismisses.

tools/fix_learn_heading_order.py chose aria-level deliberately, to avoid breaking
styling keyed to the tag. That was the right call at the time. It stops being
necessary once the selector matches both tags, and leaving it in place means the
false finding has to be re-refuted on every future walk of all 27 articles.

★BOTH HALVES, OR THIS REPEATS THE DEFECT IT IS CLEANING UP. The TOC label spent an
unknown stretch rendering at the browser default precisely because a selector moved
and a tag did not. Before writing anything here, every selector in the learn family
that targets an h4 was enumerated - there are exactly three:

    .toc h2, .toc h4     x54   (already converged)
    .cta-box h4          x27
    .related-group h4    x1

A static grep for the obvious one would have found `.cta-box h4` and silently
unstyled the five `.related-group` headings on
what-is-workhive-complete-platform-guide, which a live probe showed rendering at
12px/800/cyan - a different treatment entirely from the 20px/800 CTA heading. Both
selectors are extended here, and the live check that found the second one is the
reason this sweep is safe.

    33 elements across 27 articles: <h4 aria-level="3"> -> <h3>
    .cta-box h4       -> .cta-box h3, .cta-box h4
    .related-group h4 -> .related-group h3, .related-group h4

    python tools/fix_learn_cta_heading.py --check
    python tools/fix_learn_cta_heading.py --apply
"""
from __future__ import annotations

import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PAGES = os.path.join(ROOT, "learn", "*", "index.html")

TAG_RE = re.compile(r'<h4(\s[^>]*?)?\s*aria-level="3"\s*([^>]*)>(.*?)</h4>', re.S)

# every selector in the family that targets one of these headings, enumerated live
SELECTORS = (
    (re.compile(r"(?m)^(\s*)\.cta-box\s+h4\s*\{"), r"\1.cta-box h3, .cta-box h4 {"),
    (re.compile(r"(?m)^(\s*)\.related-group\s+h4\s*\{"),
     r"\1.related-group h3, .related-group h4 {"),
)
DONE = (re.compile(r"\.cta-box\s+h3\s*,\s*\.cta-box\s+h4\s*\{"),
        re.compile(r"\.related-group\s+h3\s*,\s*\.related-group\s+h4\s*\{"))


def patch(html: str):
    """Returns (html, tags_converged, selectors_widened)."""
    # selectors first: the style must be able to reach the new tag before it exists
    widened = 0
    for pat, repl in SELECTORS:
        html, n = pat.subn(repl, html)
        widened += n

    def _tag(m):
        pre = (m.group(1) or "").strip()
        post = (m.group(2) or "").strip()
        attrs = " ".join(x for x in (pre, post) if x)
        return f"<h3{(' ' + attrs) if attrs else ''}>{m.group(3)}</h3>"

    html, tags = TAG_RE.subn(_tag, html)
    return html, tags, widened


def sweep(apply: bool) -> int:
    pending, clean = [], 0
    for p in sorted(glob.glob(PAGES)):
        name = os.path.basename(os.path.dirname(p))
        html = open(p, encoding="utf-8").read()
        tags = len(TAG_RE.findall(html))
        stale_sel = any(pat.search(html) for pat, _ in SELECTORS)
        if not tags and not stale_sel:
            clean += 1
            continue
        pending.append((name, tags, stale_sel))
        if apply:
            new_html, n_tag, n_sel = patch(html)
            open(p, "w", encoding="utf-8").write(new_html)

    if apply:
        print(f"  converged {sum(t for _, t, _ in pending)} heading(s) across "
              f"{len(pending)} article(s) ({clean} already clean)")
        return 0
    if pending:
        total = sum(t for _, t, _ in pending)
        print(f"  FAIL: {total} CTA/related heading(s) across {len(pending)} article(s) still "
              f"use <h4 aria-level=\"3\">, or style one with a tag-coupled selector - the tag and "
              f"the accessibility level disagree, so the detector reports a false skipped-heading")
        for n, t, s in pending[:6]:
            print(f"     - learn/{n}/  ({t} tag(s){', stale selector' if s else ''})")
        if len(pending) > 6:
            print(f"     ... and {len(pending) - 6} more")
        print("  fix: python tools/fix_learn_cta_heading.py --apply")
        return 1
    print(f"  OK: all {clean} learn article(s) - no <h4 aria-level=\"3\">, no tag-coupled selector")
    return 0


if __name__ == "__main__":
    raise SystemExit(sweep("--apply" in sys.argv[1:]))
