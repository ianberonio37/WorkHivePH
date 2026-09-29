"""The two hub pages have no skip link; the learn hub has no <main> landmark either.

~W46281 (audit walk, 2026-09-20), walked on learn/index.html. Every one of the 54
learn ARTICLES carries `<a class="wh-skip-link" href="#wh-main-content">Skip to main
content</a>` and `<main id="wh-main-content">`. The hub that links to all of them
carries NEITHER - measured live: skipLinks [], mainLandmarks 0, and the first four
focusables are WorkHive / Home / Learn / My Hive, i.e. a keyboard reader lands in
the site nav and has to tab through it and the whole category filter row before
reaching a guide. The site ROOT is the same story with one half already done: it has
a real <main> and no way to jump to it.

    learn/index.html   skip link MISSING · <main> MISSING
    index.html         skip link MISSING · <main> present (needs an id)
    about/index.html   both present
    learn/*/index.html both present, 54 of 54

This is the same defect ~W46285 fixed across the 60 calculator pages - a landmark
nothing can target, or no landmark at all - now found on the two pages with the most
traffic and the most navigation to skip past.

★TWO COMMENT TRAPS ON index.html, BOTH REAL, BOTH CAUGHT BEFORE EDITING. That file
is 377KB and carries long explanatory comments that quote markup. A plain search
finds `<body>` at one offset and `<main>` at another, and BOTH of those first
matches are inside comments - the real ones are `<body class="bg-navy-wh text-white
antialiased overflow-x-hidden">` immediately followed by `<main>`. Anchoring on the
first match would have inserted the skip link into a comment, where it would render
as nothing and measure as done. This sweep therefore blanks comments before locating
its anchors and edits the original text at the resolved offsets.

    python tools/fix_hub_skip_link.py --check
    python tools/fix_hub_skip_link.py --apply
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

MAIN_ID = "wh-main-content"

# byte-identical to the link the 54 learn articles carry, except data-wh-skip
SKIP = (
    '<a class="wh-skip-link" href="#{mid}" data-wh-skip="{tag}" '
    'style="position:fixed;top:0;left:0;z-index:10001;transform:translateY(-120%);'
    'background:var(--wh-orange,#F7A21B);color:var(--wh-navy,#162032);padding:0 20px;'
    'min-height:44px;display:inline-flex;align-items:center;font-weight:700;'
    'font-size:14px;text-decoration:none;border-radius:0 0 10px 0;'
    'box-shadow:0 4px 16px rgba(0,0,0,.35);'
    'transition:transform .15s cubic-bezier(0.23,1,0.32,1);box-sizing:border-box;" '
    "onfocus=\"this.style.transform='translateY(0)'\" "
    "onblur=\"this.style.transform='translateY(-120%)'\">Skip to main content</a>"
)

PAGES = ("learn/index.html", "index.html")


def blank_comments(html: str) -> str:
    """Same length as the original, comments replaced by spaces, so offsets align."""
    return re.sub(r"<!--.*?-->", lambda m: " " * len(m.group(0)), html, flags=re.S)


def has_skip(html: str) -> bool:
    return 'class="wh-skip-link"' in blank_comments(html)


def main_tag(html: str):
    """(match, has_id) for the first <main> in real markup, or (None, False)."""
    m = re.search(r"<main\b[^>]*>", blank_comments(html))
    if not m:
        return None, False
    real = html[m.start():m.end()]
    return m, ('id="' in real)


def patch(path: str, html: str):
    """Returns (html, notes)."""
    notes = []
    masked = blank_comments(html)
    tag = "learn-hub" if path.startswith("learn/") else "home"

    # 1. the landmark
    m, had_id = main_tag(html)
    if m is None:
        # learn hub: wrap the sections between </header> and <footer
        hdr = re.search(r"</header>", masked)
        ftr = re.search(r"<footer\b", masked)
        if not (hdr and ftr and hdr.end() < ftr.start()):
            return html, ["NO ANCHOR: could not locate </header> ... <footer> in markup"]
        html = (html[:hdr.end()]
                + f'\n<main id="{MAIN_ID}">'
                + html[hdr.end():ftr.start()]
                + f"</main>\n"
                + html[ftr.start():])
        notes.append(f"wrapped the content between </header> and <footer> in "
                     f'<main id="{MAIN_ID}">')
    elif not had_id:
        html = html[:m.start()] + f'<main id="{MAIN_ID}">' + html[m.end():]
        notes.append(f'added id="{MAIN_ID}" to the existing <main>')

    # 2. the skip link, first thing inside the real <body>
    if not has_skip(html):
        masked = blank_comments(html)
        b = re.search(r"<body\b[^>]*>", masked)
        if not b:
            return html, notes + ["NO ANCHOR: no <body> in real markup"]
        link = SKIP.format(mid=MAIN_ID, tag=tag)
        html = html[:b.end()] + "\n" + link + html[b.end():]
        notes.append("inserted the skip link as the first element inside <body>")
    return html, notes


def run(apply: bool) -> int:
    bad = []
    for rel in PAGES:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            bad.append((rel, ["MISSING FILE"]))
            continue
        html = open(p, encoding="utf-8").read()
        m, had_id = main_tag(html)
        problems = []
        if not has_skip(html):
            problems.append("no skip link")
        if m is None:
            problems.append("no <main> landmark")
        elif not had_id:
            problems.append(f'<main> has no id for a skip link to target')
        if not problems:
            continue
        if apply:
            new_html, notes = patch(rel, html)
            if any(n.startswith("NO ANCHOR") for n in notes):
                bad.append((rel, notes))
                continue
            open(p, "w", encoding="utf-8").write(new_html)
            print(f"  {rel}: " + "; ".join(notes))
        else:
            bad.append((rel, problems))

    if apply:
        return 1 if bad else 0
    if bad:
        print(f"  FAIL: {len(bad)} hub page(s) cannot be skipped past into their own content")
        for rel, problems in bad:
            print(f"     - {rel}: " + ", ".join(problems))
        print("  fix: python tools/fix_hub_skip_link.py --apply")
        return 1
    print(f"  OK: all {len(PAGES)} hub page(s) carry a skip link and a targetable <main>")
    return 0


if __name__ == "__main__":
    raise SystemExit(run("--apply" in sys.argv[1:]))
