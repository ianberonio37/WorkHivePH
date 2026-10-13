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


# Where "the end of <head>" is (2026-10-13). The public pages' compiled Tailwind link (tools/tw_public_build.mjs) must
# stay the LAST thing in <head>, because that is where the Play CDN used to inject its style: a block appended BELOW it
# would start winning the ties Tailwind used to win. So an append lands above that link when a page has one.
_TW_PUB_LINK = re.compile(r'^<link rel="stylesheet" href="/wh-tw-pub-[\w-]+\.css">', re.M)


def _head_end(html: str) -> int:
    m = _TW_PUB_LINK.search(html)
    end = html.find("</head>")
    return m.start() if m and (end == -1 or m.start() < end) else end

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
    # ★AND THE CELL RULE GAVE HEIGHT ONLY, SO A SHORT LINK STAYED NARROW (2026-10-13, critic batch F1). The
    # calculators guide's "FCU" and "OEE" came out 31x44 and 32x44, and the platform guide's first column was
    # squeezed to 43px wide. That is the same lesson this rule's own header records for the nav links: the
    # measure asks for both sides. min-width without centring, so a short link keeps the column's left edge and
    # the extra width trails after the word.
    "td a,th a{display:inline-flex;align-items:center;min-height:44px;min-width:44px;}"
    # the guides' .cta-btn lifts 2px on hover with no reduced-motion guard (2026-10-13). One stamp reaches all 54.
    "@media (prefers-reduced-motion:reduce){.cta-btn{transition:none;}.cta-btn:hover{transform:none;}}"
    # no guide set tabular numerals, so a column of figures (99.0%, 808, 4.2) used proportional digits and did not line
    # up (critic batch C4, 2026-10-13). Digit width only: text in a cell is unaffected.
    "td,th{font-variant-numeric:tabular-nums;}"
    "</style>"
)

# ★A MARKER MAKES A FIX IDEMPOTENT, AND IT ALSO MEANS A CHANGED RULE NEVER REACHES A PAGE THAT ALREADY HAS IT
# (2026-10-13). fix_one() returns any marked page unchanged, so editing CHROME_CSS above changed nothing on the
# 54 articles, and --check still exited 0. A marked page that lacks one of CHROME_CSS's rules is stale: --check
# reports it and fails, --apply brings that rule up to date. The tags and the wh-tap marks are left alone.
# ★RULE BY RULE, NEVER THE WHOLE BLOCK. The first version replaced the whole <style> block with CHROME_CSS and
# deleted, from 51 guides, the 320px gap rule tools/fix_learn_brand_header.py appends to this same block
# (learn-brand-header went red). tools/fix_public_pages_chrome.py had already recorded this trap for its own block:
# "it already has the marker" is not "it already has the rule", and two sweeps that share a block must each assert
# only their own rules. So each of our rules is checked verbatim; an older rule with the same selector is replaced
# in place; a missing one is added before </style>. Anything else in the block is never touched.
_STYLE_BLOCK = re.compile(r"<style data-" + MARK + r">(.*?)</style>", re.S)


def _split_rules(css: str) -> list[str]:
    """Top-level rules, braces balanced, so an @media block is one rule with its nested rules inside it."""
    out, depth, start = [], 0, 0
    for i, ch in enumerate(css):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                out.append(css[start:i + 1])
                start = i + 1
    return out


_OUR_RULES = _split_rules(CHROME_CSS[len("<style data-" + MARK + ">"):-len("</style>")])


def refresh_style(raw: str):
    """Return (new_html, n) where n is how many of our rules were added or updated in a marked page's block."""
    m = _STYLE_BLOCK.search(raw)
    if not m:
        return raw, 0
    body, n = m.group(1), 0
    for rule in _OUR_RULES:
        if rule in body:
            continue
        sel = rule[:rule.index("{")].strip()
        old = next((r for r in _split_rules(body) if r[:r.index("{")].strip() == sel), None)
        body = body.replace(old, rule, 1) if old else body + rule
        n += 1
    if not n:
        return raw, 0
    return raw[:m.start(1)] + body + raw[m.end(1):], n

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
        at = _head_end(raw)
        if at != -1:
            raw = raw[:at] + f"{CHROME_CSS}\n" + raw[at:]
    if "wh-i18n-lite.js" not in raw:
        at = _head_end(raw)
        if at != -1:
            raw = raw[:at] + f"{SCRIPT}\n" + raw[at:]
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
            new, n = refresh_style(raw)
            if not n:
                already.append(p.parent.name)
                continue
            touched.append(f"{p.parent.name} (older chrome rule)")
            if mode == "--apply":
                p.write_text(new, encoding="utf-8", newline="")
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

    # ★--check MUST EXIT NON-ZERO WHEN WORK IS PENDING, OR IT IS A GATE THAT CANNOT BITE
    # (~W46153, 2026-09-20). This returned 0 unconditionally. It was registered in
    # run_platform_checks.py as `learn-shared-chrome` on the strength of its own report -
    # and would have passed forever, including on the three pillar pages that were
    # measurably missing the chrome (breadcrumb links 41x19 against 44x44 on every
    # sibling) at the moment it was registered. A checker that prints "would change: 3"
    # and exits 0 is worse than no checker: it converts a real defect into a green tick.
    # Caught by breaking a page on purpose and watching --check still exit 0.
    if mode == "--check" and touched:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
