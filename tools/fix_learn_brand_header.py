#!/usr/bin/env python3
"""fix_learn_brand_header.py - stop the public library's brand link crushing its own wordmark.

Found by the W46077 audit walk on learn/asset-brain-360-one-machine-history-philippine-plant/.
Three defects, all in the shared learn header, all measured live at 320/390/640:

  1. THE BRAND LINK IS CRUSHED AND PAINTS OUTSIDE ITSELF (19 pages, the "variant B" header).
     tools/fix_learn_chrome.py injects `nav a,header a,footer a{...min-width:44px}` to guarantee a
     44px tap target. On a flex row that rule REPLACES flex's default `min-width:auto`, which is the
     only thing keeping a flex item from shrinking below its own content - so the one nav anchor whose
     content is 139px wide (logo + "WorkHive") is free to collapse to 44px, and `justify-content:center`
     then spills the overflow out BOTH sides. Measured on asset-brain-360:
         320px: anchor box 20->64, logo drawn from x = -9.6 (off the left edge of the screen),
                wordmark text 26.4->93.6 painted ON TOP of the "Learn" link, whose text starts at 69.6
                - a 24px collision of word on word.
         390px: spill 9.2px, the wordmark's tail inside the first nav link's box.
         414px: clean. So every phone narrower than ~410px shows it.
     The other 32 learn pages already solve this the conventional way - their wordmark span carries
     `hidden sm:inline`, so a phone shows the 36px logo alone. This sweep gives the 19 outliers the
     platform's own existing pattern rather than inventing a second one.

  2. THE NAV OVERFLOWS 320px (the "variant A" header). Measured: documentElement.scrollWidth 328 on a
     320 viewport - "Sign Up Free" ends at 327.7. 320px is the platform's stated floor, so a public
     guide handing a horizontal scrollbar to the narrowest phone is a responsive defect. Four 24px gaps
     cost 96px there; at .75rem the row measures inside the viewport with room to spare.

  3. THE BRAND LINK IS ANNOUNCED TWICE (all 54). <img alt="WorkHive"> sits beside <span>WorkHive</span>,
     so the accessible name computes to "WorkHive WorkHive" wherever the word is visible (variant B at
     every width, variant A from 640 up). The image is the brand mark and the text repeats it, so the
     span is marked aria-hidden and the alt keeps naming the link - which also means the name stays
     "WorkHive" at the widths where the span is display:none.

The three generated pillar pages get the same treatment IN THE TEMPLATE (tools/build_pillar_pages.py),
because the W46073 row measured what happens otherwise: a rebuild silently reverts a swept file.

Idempotent (each edit checks for its own marker), reversible, and it changes no destination, no copy
and no layout above 640px.

  python tools/fix_learn_brand_header.py --check
  python tools/fix_learn_brand_header.py --apply
  python tools/fix_learn_brand_header.py --revert
"""
import argparse
import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

LOGO = "workhive-logo-transparent.png"

# marks a wordmark span this sweep taught to yield on phones (see patch_span)
WORD_MARK = "wh-brand-word"

# The narrow-viewport gap relief for the variant-A nav, appended to the chrome style block.
# `nav.flex` and not `nav`: the gap it must beat is Tailwind's `gap-6` UTILITY CLASS, and a media
# query adds no specificity - `header nav` (0,0,2) loses to `.gap-6` (0,1,0) at every width, which is
# exactly how the first version of this rule measured 328px on a 320 viewport after "fixing" it.
# `header nav.flex` is (0,1,2) and wins.
GAP_MARK = "wh-brand-header-gap"
GAP_CSS = (
    "/*" + GAP_MARK + "*/@media (max-width:399px){header nav.flex{gap:.75rem;}}"
)
GAP_RE = re.compile(r"/\*" + GAP_MARK + r"\*/@media[^{]*\{[^}]*\}\}")

SPAN_OPEN = re.compile(r"<span\b([^>]*)>\s*WorkHive\s*</span>")

# The anchor that HOLDS the logo - not merely the first mention of the file. Every learn page names the
# same png in its og:image meta long before the header, so a bare `html.find(LOGO)` lands in <head>,
# finds no enclosing anchor, and silently patches nothing. `(?:(?!</a>).)*?` keeps the match inside one
# anchor so a later </a> cannot be borrowed to close it.
BRAND_A = re.compile(
    r"<a\b[^>]*>(?:(?!</a>).)*?" + re.escape(LOGO) + r"(?:(?!</a>).)*?</a>", re.S)


def pages():
    """Both origins of the shared header, because fixing one leaves a silent half.

    tools/build_pillar_pages.py's SITE_HEADER / HEAD_ASSETS are imported by tools/build_calc_pages.py
    too, so the 60 published calculator pages under tools/<slug>/index.html carry the same brand link
    as the 54 guides. They are variant A (their wordmark already yields on phones) so only the
    duplicate accessible name and the 320px gap reach them - but a template fix that waits for a
    rebuild would leave those 60 shipping the defect meanwhile, which is exactly what the W46073 row
    measured when a generator and its output disagreed.
    """
    out = [p for p in (ROOT / "learn").glob("*/index.html") if p.is_file()]
    out += [p for p in (ROOT / "tools").glob("*/index.html") if p.is_file()]
    # ...and the four PUBLIC pages, added after the W46593 audit measured the identical defect on
    # privacy-policy: span.font-black "WorkHive" spilling 18px past its own anchor and an accessible
    # name of "WorkHive WorkHive". The first version of this sweep globbed learn/ and tools/ because
    # those were the two origins it had measured - which made the glob a claim about where the header
    # ships, and the header ships here too.
    out += [ROOT / d / "index.html" for d in ("about", "feedback", "privacy-policy", "terms-of-service")
            if (ROOT / d / "index.html").is_file()]
    return sorted(out)


def brand_anchor_span(html):
    """Return (span_match, offset) for the wordmark span inside the anchor that holds the logo."""
    am = BRAND_A.search(html)
    if not am:
        return None, 0
    m = SPAN_OPEN.search(am.group(0))
    if not m:
        return None, 0
    return m, am.start()


def patch_span(html):
    """aria-hidden the wordmark, and give it `hidden sm:inline` when it has no hidden class."""
    m, off = brand_anchor_span(html)
    if not m:
        return html, "no brand wordmark span"
    attrs = m.group(1)
    _cm = re.search(r'class="([^"]*)"', attrs)
    _classes = _cm.group(1).split() if _cm else []
    # "hidden" is checked against the CLASS LIST, never the attribute string - `aria-hidden` contains
    # the substring "hidden" and would report a span as already responsive when it is not.
    if 'aria-hidden="true"' in attrs and "hidden" in _classes:
        return html, None  # already done

    new_attrs = attrs
    cm = re.search(r'class="([^"]*)"', new_attrs)
    if cm:
        classes = cm.group(1)
        if "hidden" not in classes.split():
            # WORD_MARK records that THIS sweep added the responsive pair, so --revert strips it only
            # from the pages it was added to - the 32 pages that already shipped `hidden sm:inline`
            # must keep theirs.
            classes = (classes + " " + WORD_MARK + " hidden sm:inline").strip()
            new_attrs = new_attrs[:cm.start(1)] + classes + new_attrs[cm.end(1):]
    else:
        new_attrs = new_attrs + ' class="' + WORD_MARK + ' hidden sm:inline"'
    if 'aria-hidden="true"' not in new_attrs:
        new_attrs = new_attrs + ' aria-hidden="true"'

    s, e = off + m.start(1), off + m.end(1)
    return html[:s] + new_attrs + html[e:], None


def patch_gap(html):
    # An earlier revision of this rule shipped a selector that could not win against the utility
    # class, so a marked-but-stale block is REPLACED rather than left alone - "already has the marker"
    # is not the same claim as "already has the rule that works".
    cur = GAP_RE.search(html)
    if cur:
        if cur.group(0) == GAP_CSS:
            return html
        return html[:cur.start()] + GAP_CSS + html[cur.end():]
    idx = html.rfind("</style>")
    if idx == -1:
        return html
    return html[:idx] + GAP_CSS + html[idx:]


def unpatch(html):
    m, off = brand_anchor_span(html)
    if m:
        attrs = m.group(1)
        new = attrs.replace(' aria-hidden="true"', "")
        cm = re.search(r'class="([^"]*)"', new)
        if cm and WORD_MARK in cm.group(1).split():
            drop = (WORD_MARK, "hidden", "sm:inline")
            cls = " ".join(c for c in cm.group(1).split() if c not in drop)
            new = new[:cm.start(1)] + cls + new[cm.end(1):]
        html = html[:off + m.start(1)] + new + html[off + m.end(1):]
    return GAP_RE.sub("", html)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    todo, done, skipped = [], [], []
    for p in pages():
        html = io.open(p, encoding="utf-8").read()
        if a.revert:
            out = unpatch(html)
            if out != html:
                io.open(p, "w", encoding="utf-8", newline="").write(out)
                done.append(p)
            else:
                skipped.append((p, "not patched"))
            continue
        out, why = patch_span(html)
        out = patch_gap(out)
        if out == html:
            skipped.append((p, why or "already patched"))
            continue
        todo.append(p)
        if a.apply:
            io.open(p, "w", encoding="utf-8", newline="").write(out)
            done.append(p)

    verb = "reverted" if a.revert else ("patched" if a.apply else "would patch")
    n = len(done) if (a.apply or a.revert) else len(todo)
    print("%s %d of %d learn page(s)" % (verb, n, len(pages())))
    for p, why in skipped[:5]:
        print("   skipped %s - %s" % (p.relative_to(ROOT), why))
    if len(skipped) > 5:
        print("   ... and %d more skipped" % (len(skipped) - 5))
    if a.check and todo:
        print("FAIL: %d learn page(s) still crush the brand wordmark or lack the 320px gap relief" % len(todo))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
