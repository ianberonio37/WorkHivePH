#!/usr/bin/env python3
"""fix_learn_chrome.py — make the learn articles' shared chrome bilingual and thumb-sized.

Two findings from the W3-LN walk, and both live in the same three links:

  Internal Control — 53 of 54 articles carry NO bilingual labels, while 40 of 42 product pages and all 60
    calculator pages do. For a Philippine platform, the public reading surface was the one place a
    Filipino-first reader got nothing. (The 54th article has data-i markup and no translator to act on it,
    which is its own version of the same silence.)

  Adaptability — every article reports 14-31 controls under 40px at 390 while all 60 calculator pages report
    zero: the calculators were given min-height centrally in their generator and the articles never were.
    ★NOT EVERY SMALL LINK OWES 44px - WCAG 2.5.8 exempts a link INLINE IN A SENTENCE, and making a word
    inside a paragraph 44px tall would wreck the line box. The footer and breadcrumb links this touches are
    standalone controls, which do owe it; the prose links are left exactly as they are.

Both are fixed in the chrome the articles share, so this is one small edit repeated rather than 53 decisions.
It is idempotent (a marker attribute), reversible, and it changes no prose.

  python tools/fix_learn_chrome.py --check
  python tools/fix_learn_chrome.py --apply
  python tools/fix_learn_chrome.py --revert
"""
from __future__ import annotations

import glob
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARK = "wh-chrome-i18n"                 # the marker that makes this idempotent and revertible

# ★COPY THE PLATFORM'S OWN RULE, DO NOT INVENT A VARIANT OF IT. The first version put an inline
# `min-height:44px` on each link it tagged. It worked - the links became 44px TALL - and the count of small
# targets barely moved, because they were still ~35px WIDE and the measure asks for both. The calculator
# pages, which report zero, do it as a stylesheet rule with min-width and centring, covering every header,
# nav and footer link rather than the four this script happens to match by href:
#
#     nav a.nav-link { display:inline-flex; align-items:center; justify-content:center;
#                      min-height:44px; min-width:44px; padding: 0 0.25rem; }
#     header a, footer a { display:inline-flex; align-items:center; justify-content:center;
#                          min-height:44px; min-width:44px; }
#
# One rule beats seven inline styles, it is what the platform already says, and it fixes the links this
# script never named. Searching for MY spelling of a fix instead of the platform's is a mistake this project
# has made before.
#
# ★AND A CALCULATOR'S CHROME IS NOT AN ARTICLE'S CHROME. Copying the calculator rule verbatim fixed all 8
# header/nav/footer links and left 13 controls still small, because an article also has a BREADCRUMB, a
# TABLE OF CONTENTS and a back link - standalone navigation the calculator pages simply do not have. The
# count only fell from 25 to 18 (5 of those being prose links, which are exempt). Measuring the whole page
# after the change is what caught it; the diff looked complete.
#
# The breadcrumb and ToC links are already wide, so they are given HEIGHT only - forcing 44px of width on a
# 271px-wide list item would do nothing but confuse the next reader of this rule.
CHROME_CSS = (
    "<style data-" + MARK + ">"
    # ★AND THE 54 ARTICLES ARE NOT ONE TEMPLATE. Scoping this to `nav a.nav-link` - the calculator pages'
    # own selector - fixed the article I happened to measure and missed three of the next six, whose nav
    # links carry no class at all and stayed at 31x16. Verifying ONE page is not verifying the set; the
    # selector has to match the element's ROLE (a link in the nav) rather than the class one template
    # happens to use.
    "nav a,header a,footer a{display:inline-flex;align-items:center;justify-content:center;"
    "min-height:44px;min-width:44px;}"
    "nav a{padding:0 .25rem;}"
    ".breadcrumb a,.toc a{display:inline-flex;align-items:center;min-height:44px;}"
    # the breadcrumb's own links are short words ("Home", "Learn") and came out 36px wide, so they take the
    # same min-width the header and footer links do; the ToC entries are already 180-270px and need none
    ".breadcrumb a{min-width:44px;justify-content:center;}"
    # the article's back link is a standalone control in its own bordered block - 128x16 before this
    # ★AN EXACT-HREF SELECTOR DOES NOT SURVIVE THE LOCAL PATH REWRITE, SO IT MADE EVERY LOCAL
    # MEASUREMENT OF THIS LINK WRONG (2026-09-11). Each article ships an inline rewriter guarded by
    # `if (!location.pathname.startsWith('/workhive/')) return;` - it exists ONLY for the local server,
    # where the site is served from a subdirectory, and it turns href="/learn/" into
    # "/workhive/learn/index.html". In production the guard returns early and the href is untouched, so
    # `[href='/learn/']` matched and the 44px applied - the fix was real. Locally it never matched: the
    # style block was present, the marker was present, and `a.matches()` found NO rule, leaving the link
    # at 140x20. Since the rubric sweep runs LOCALLY, F1 and K2 reported "under-44: <- Back to all
    # guides" on articles that are correct in prod - a false finding that was holding critic rows open.
    # Matching the END of the href covers both environments, which is this file's own lesson one layer
    # up: match the element's ROLE, not the exact string one deployment happens to produce.
    # Kin of [[feedback_headers_file_is_prod_only_behavior]], inverted - LOCAL-only behaviour breaking a
    # prod-correct rule, which is the harder direction to notice because the page is fine where it ships.
    "a.text-sm[href$='/learn/'],a.text-sm[href$='/learn/index.html']"
    "{display:inline-flex;align-items:center;min-height:44px;}"
    # ★AND THE ONE RULE CSS CANNOT EXPRESS. 126 links across the 54 articles are the ENTIRE content of their
    # paragraph or list item - a call to action on its own line, not a word inside a sentence - so WCAG's
    # inline exemption does not cover them and at 17px tall they miss even the 24px AA floor. CSS cannot say
    # "the only content, text nodes included": `p > a:only-child` matches a link with prose beside it,
    # because :only-child ignores text. So the fixer decides it per link, statically, and marks the ones that
    # genuinely stand alone. A rule that would have caught inline prose links too is worse than none - it
    # breaks the line box the exemption exists to protect.
    ".wh-tap{display:inline-flex;align-items:center;min-height:44px;}"
    # ★A LINK IN A TABLE CELL IS NEVER "A WORD IN A SENTENCE". The last control below the AA floor across all
    # 54 articles was `<td><a>MTBF and MTTR</a>, <a>OEE</a></td>` - two links side by side at 117x17. Neither
    # fills its cell, so the standalone marker skipped both; neither sits in prose, so the inline exemption
    # does not cover them either; and being adjacent, they cannot claim WCAG's spacing exception. A cell can
    # simply grow, so cell links get the height with nothing to lose - which is why this is a rule and not
    # another special case in the marker.
    "td a,th a{display:inline-flex;align-items:center;min-height:44px;}"
    "</style>"
)

# the shared footer links, matched by their href and their exact visible text so nothing else is touched
LINKS = [
    (r'href="/"', "Home", "home"),
    (r'href="/#faq"', "FAQ", "faq"),
    (r'href="/\?signup=1"', "Join the Hive", "jointhehive"),
    (r'href="/learn/"', "Learn", "learn"),
]
SCRIPT = '<script src="/wh-i18n-lite.js" data-' + MARK + '></script>'
APPLY = ('<script data-' + MARK + '>if (typeof whI18nApply === "function" && window.WH_LANG === "fil") '
         'whI18nApply(window.WH_FIL_PUBLIC || {});</script>')


def articles():
    return sorted(p for p in glob.glob(str(ROOT / "learn" / "*" / "index.html")))


def fix_one(raw: str):
    """Return (new_html, changes). Idempotent: an already-marked file is returned unchanged."""
    if f"data-{MARK}" in raw:
        return raw, 0
    changes = 0

    # 1. tag the shared chrome links, and give the standalone ones a thumb-sized box
    for href, text, key in LINKS:
        pat = re.compile(r'(<a\s+[^>]*' + href + r'[^>]*?)(>)\s*' + re.escape(text) + r'\s*(</a>)')

        def repl(m):
            nonlocal changes
            open_tag, gt, close = m.group(1), m.group(2), m.group(3)
            if "data-i=" in open_tag:
                return m.group(0)
            changes += 1
            return f'{open_tag} data-i="{key}"{gt}{text}{close}'

        raw, n = pat.subn(repl, raw)

    # 1b. mark the links that ARE the whole content of their paragraph, list item or TABLE CELL. The cell
    #     is not an afterthought: the one link left below the WCAG AA floor across all 54 articles was
    #     a 117x17 link filling a <td> in a comparison table - standalone by any reading, and missed
    #     because the first pattern only knew about <p> and <li> — a call to action on its
    #     own line owes a tappable box; a word inside a sentence does not, and this is the difference.
    standalone = re.compile(r'(<(p|li|td|th|dd)\b[^>]*>)(\s*)(<a\b(?![^>]*\bclass="[^"]*wh-tap)[^>]*>)(.*?)(</a>)(\s*)(</\2>)',
                            re.S)

    def mark(m):
        nonlocal changes
        open_p, tag, lead, open_a, inner, close_a, trail, close_p = m.groups()
        if "<a" in inner or "<p" in inner:            # nested markup: not a simple standalone link
            return m.group(0)
        if 'class="' in open_a:
            open_a = re.sub(r'class="([^"]*)"', lambda c: f'class="{c.group(1)} wh-tap"', open_a, count=1)
        else:
            open_a = open_a[:-1] + ' class="wh-tap">'
        changes += 1
        return f"{open_p}{lead}{open_a}{inner}{close_a}{trail}{close_p}"

    raw = standalone.sub(mark, raw)

    if not changes:
        return raw, 0

    # 2. the platform's own chrome rule, and the translator in the head where the language is known before
    #    paint - so a Filipino reader is not shown English headings that then change under them
    if f'<style data-{MARK}>' not in raw:
        raw = raw.replace("</head>", f"{CHROME_CSS}\n</head>", 1)
    if "wh-i18n-lite.js" not in raw:
        raw = raw.replace("</head>", f"{SCRIPT}\n</head>", 1)
    if "whI18nApply(window.WH_FIL_PUBLIC" not in raw:
        raw = raw.replace("</body>", f"{APPLY}\n</body>", 1)
    return raw, changes


def revert_one(raw: str) -> str:
    raw = re.sub(r'\s*<script[^>]*data-' + MARK + r'[^>]*>.*?</script>', "", raw, flags=re.S)
    raw = re.sub(r'\s*<style[^>]*data-' + MARK + r'[^>]*>.*?</style>', "", raw, flags=re.S)
    raw = re.sub(r'\s*data-i="(?:home|faq|jointhehive|learn)"', "", raw)
    raw = re.sub(r'\s+class="wh-tap"', "", raw)
    raw = re.sub(r'(class="[^"]*?) wh-tap"', r'\1"', raw)
    return raw


def main() -> int:
    mode = "--check"
    for a in sys.argv[1:]:
        if a in ("--check", "--apply", "--revert"):
            mode = a

    files = articles()
    touched, already, none = [], [], []
    for f in files:
        p = Path(f)
        raw = p.read_text(encoding="utf-8", errors="replace")
        if mode == "--revert":
            if f"data-{MARK}" in raw:
                p.write_text(revert_one(raw), encoding="utf-8", newline="")
                touched.append(p.parent.name)
            continue
        if f"data-{MARK}" in raw:
            already.append(p.parent.name)
            continue
        new, n = fix_one(raw)
        if not n:
            none.append(p.parent.name)
            continue
        touched.append(f"{p.parent.name} ({n} link(s))")
        if mode == "--apply":
            p.write_text(new, encoding="utf-8", newline="")

    verb = {"--check": "would change", "--apply": "changed", "--revert": "reverted"}[mode]
    print(f"learn articles: {len(files)}")
    print(f"  {verb}: {len(touched)}")
    print(f"  already carried the fix: {len(already)}")
    print(f"  no shared chrome link found: {len(none)}")
    for s in touched[:6]:
        print(f"     {s}")
    for s in none[:6]:
        print(f"     no chrome matched: {s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
