#!/usr/bin/env python3
"""fix_public_pages_chrome.py - give the four PUBLIC pages the landmark, skip link and tap targets
the rest of the platform already has.

Found by the W46593 audit walk on privacy-policy/. These four pages - about, feedback, privacy-policy
and terms-of-service - are the platform's identity and legal surface: what a regulator, a journalist,
a partner or a first-time visitor reads before anything else. Measured live at 390 on each:

  privacy-policy    14 controls, 14 under 44px, 11 of them STANDALONE, no <main>, no skip link
  terms-of-service  17 controls, 17 under 44px, 11 standalone,          no <main>, no skip link
  about             12 controls, 12 under 44px, 11 standalone,          no <main>, no skip link
  feedback          16 controls,  4 under 44px,  4 standalone,          <main> present, no skip link

The eleven standalone controls are identical on the three unfixed pages, and the footer is the worst
of it: Home 36x16, Learn 33x16, About 36x16, Privacy 43x16, Terms 37x16 - five links less than half
the 44px floor in HEIGHT, which is the axis a thumb misses. Above them the brand link is 108x36 and
the header nav runs 31-42px WIDE.

★A PREVIOUS ROW ALREADY DID HALF OF THIS AND ITS COMMENT SAYS IT DID ALL OF IT. feedback/index.html
carries the note "Matches the same repair on about, privacy-policy and terms-of-service" beside its
.nav-link rule. The HEADER repair did land on all three - those links measure 44 tall. The FOOTER
links and the brand link did not, and feedback fixed both for itself. So the comment describes an
intent, and three pages shipped half the repair with a note saying otherwise - which is why this
sweep asserts the result rather than trusting the claim, and why it is registered as a gate.

What it does, idempotently and reversibly:

  1. <main id="wh-main-content"> around the <article>, where one is missing.
  2. The platform's skip link after <body>, matching wayfinding.js's inline look, where missing.
  3. A CSS block giving the footer links, the brand link and the header nav a real target:
     44px min-height everywhere, and min-width on the short header links.

It changes no prose, no destination and no layout above the tap floor.

  python tools/fix_public_pages_chrome.py --check
  python tools/fix_public_pages_chrome.py --apply
  python tools/fix_public_pages_chrome.py --revert
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

PAGES = ["about", "feedback", "privacy-policy", "terms-of-service"]

# ...and the 60 published calculator pages, added after the W46285 audit found that ALL SIXTY have a
# <main> landmark and NOT ONE has a skip link. They are the platform's SEO surface - the pages a
# search result lands on - and they share the same generator chrome as the pillar pages. Their main
# ships as <main class="prose-wh"> with no id, so the sweep gives it the platform's id first and the
# skip link has something to target.
CALC_GLOB = "tools/*/index.html"
MAIN_NO_ID = re.compile(r'<main(?![^>]*\bid=)([^>]*)>')

MARK = "wh-public-chrome"
MAIN_MARK = 'id="wh-main-content"'

SKIP = (
    '<a class="wh-skip-link" href="#wh-main-content" data-wh-skip="public" '
    'style="position:fixed;top:0;left:0;z-index:10001;transform:translateY(-120%);'
    'background:var(--wh-orange,#F7A21B);color:var(--wh-navy,#162032);padding:0 20px;min-height:44px;'
    'display:inline-flex;align-items:center;font-weight:700;font-size:14px;text-decoration:none;'
    'border-radius:0 0 10px 0;box-shadow:0 4px 16px rgba(0,0,0,.35);'
    'transition:transform .15s cubic-bezier(0.23,1,0.32,1);box-sizing:border-box;" '
    "onfocus=\"this.style.transform='translateY(0)'\" "
    "onblur=\"this.style.transform='translateY(-120%)'\">Skip to main content</a>\n"
)

CSS = (
    "<style data-" + MARK + ">"
    "/* W46593 audit: the four public pages are the platform's legal and identity surface and their "
    "   footer links measured 16px TALL - less than half the 44px floor - with the brand link at 36px "
    "   and the header nav 31-42px wide. inline-flex + min-height gives a real target and moves no "
    "   text, because each of these rows is already items-center. min-width covers the short header "
    "   words ('Home', 'Learn', 'Sign In') whose HEIGHT was fixed by an earlier repair and whose width "
    "   was not. */"
    "footer a,header a{display:inline-flex;align-items:center;justify-content:center;min-height:44px;}"
    "header nav a{min-width:44px;}"
    # the breadcrumb's "Home" measured 42x19 - a standalone control inside the article, not a word in
    # a sentence. This is the same rule tools/fix_learn_chrome.py gives the 54 guides, reused rather
    # than reinvented so the two public surfaces behave identically.
    ".breadcrumb a{display:inline-flex;align-items:center;justify-content:center;"
    "min-height:44px;min-width:44px;}"
    "</style>"
)

ART_OPEN = re.compile(r"<article\b[^>]*>")


def pages():
    out = [ROOT / p / "index.html" for p in PAGES if (ROOT / p / "index.html").is_file()]
    out += sorted(ROOT.glob(CALC_GLOB))
    return out


def patch(html):
    out = html
    did = []

    # 1. the main landmark - only where the page has NO main element of any kind. feedback/ already
    #    ships one, and adding a second would turn a fix into a defect: a document has one main.
    #    The wrapper carries data-wh-public-main so --revert removes exactly what was added here and
    #    never a landmark the page brought itself.
    # 1a. a landmark that exists but has no id cannot be a skip link's target. The calculator pages
    #     ship <main class="prose-wh"> with no id; give it the platform's one rather than wrapping a
    #     second landmark around it.
    if re.search(r"<main\b", out) and MAIN_NO_ID.search(out) and MAIN_MARK not in out:
        # data-wh-main-id records that the ID came from this sweep, so --revert removes exactly what
        # it added and never an id the page or another sweep brought itself.
        out = MAIN_NO_ID.sub(
            lambda m: '<main id="wh-main-content" data-wh-main-id' + m.group(1) + ">", out, count=1)
        did.append("main-id")

    if not re.search(r"<main\b", out) and '[role="main"]' not in out and "role=\"main\"" not in out:
        m = ART_OPEN.search(out)
        if m and "</article>" in out:
            out = (out[:m.start()] + '<main id="wh-main-content" data-wh-public-main>'
                   + m.group(0) + out[m.end():])
            i = out.rfind("</article>")
            out = out[:i] + "</article></main>" + out[i + len("</article>"):]
            did.append("main")

    # 2. the skip link
    if 'data-wh-skip="public"' not in out:
        bm = re.search(r"<body\b[^>]*>", out)
        if bm:
            out = out[:bm.end()] + "\n" + SKIP + out[bm.end():]
            did.append("skip")

    # 3. the tap-target rules. A marked block that does not MATCH the current rules is replaced, not
    #    skipped - "it already has the marker" is a different claim from "it already has the rule",
    #    and a sweep that cannot update its own output can only ever ship its first draft.
    cur = re.search(r"<style data-" + MARK + r">(.*?)</style>", out, re.S)
    if cur:
        # Assert the RULES are present, not that the block is byte-identical. tools/fix_learn_brand_header.py
        # appends its narrow-viewport gap rule before the LAST </style>, which is this block - so an
        # equality test makes the two sweeps overwrite each other forever, each undoing the other on
        # every run. Checking for each selector lets another owner add to the block without a fight,
        # and still fails when one of these rules goes missing.
        body = cur.group(1)
        need = ["footer a,header a{", "header nav a{", ".breadcrumb a{"]
        if not all(sel in body for sel in need):
            out = out[:cur.start()] + CSS + out[cur.end():]
            did.append("targets-refreshed")
    else:
        idx = out.rfind("</head>")
        if idx != -1:
            out = out[:idx] + CSS + "\n" + out[idx:]
            did.append("targets")

    return (out if did else None), did


def unpatch(html):
    out = html
    out = out.replace('<main id="wh-main-content" data-wh-main-id', "<main")
    if '<main id="wh-main-content" data-wh-public-main>' in out:
        out = out.replace('<main id="wh-main-content" data-wh-public-main>', "", 1)
        i = out.rfind("</article></main>")
        if i != -1:
            out = out[:i] + "</article>" + out[i + len("</article></main>"):]
    # consume the newline the insert added too, or a round trip leaves a blank line behind and
    # --revert stops being an exact inverse - which is the only property that makes it trustworthy
    out = re.sub(r'\n?<a class="wh-skip-link"[^>]*data-wh-skip="public".*?</a>\n', "", out, flags=re.S)
    out = re.sub(r"<style data-" + MARK + r">.*?</style>\n?", "", out, flags=re.S)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    todo, done = [], []
    for p in pages():
        html = io.open(p, encoding="utf-8").read()
        if a.revert:
            out = unpatch(html)
            if out != html:
                io.open(p, "w", encoding="utf-8", newline="").write(out)
                done.append(p.parent.name)
            continue
        out, did = patch(html)
        if out is None:
            continue
        todo.append("%s (%s)" % (p.parent.name, "+".join(did)))
        if a.apply:
            io.open(p, "w", encoding="utf-8", newline="").write(out)
            done.append(p.parent.name)

    verb = "reverted" if a.revert else ("patched" if a.apply else "would patch")
    n = len(done) if (a.apply or a.revert) else len(todo)
    print("%s %d of %d public page(s)" % (verb, n, len(pages())))
    for s in todo[:6]:
        print("   " + s)
    if a.check and todo:
        print("FAIL: %d public page(s) lack a landmark, a skip link or a 44px tap target" % len(todo))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
