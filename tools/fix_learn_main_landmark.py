#!/usr/bin/env python3
"""fix_learn_main_landmark.py — give every learn article a <main> and a skip link.

Found by the W46073 audit walk on learn/ai-work-assistant-maintenance-technicians/. Measured on the
running page: document.querySelector('main') null, [role="main"] null, no skip link, and the FIRST
focusable element is the WorkHive wordmark. So a keyboard or screen-reader reader arriving at any
guide in the library had to travel the whole header and nav before reaching the article, every time,
with no landmark to jump to.

Two things make it worth a sweep rather than a note:

  * It is the PUBLIC library - 54 guides, the pages this platform publishes to be found. A first-time
    visitor using assistive tech is more likely to meet the product here than anywhere behind the
    sign-in, and this is the one surface where the platform's own skip link (wayfinding.js) does not
    reach, because these pages deliberately load none of the app chrome.

  * The three pillar pages built by tools/build_pillar_pages.py were fixed IN THE TEMPLATE in the same
    change, so a rebuild keeps them. The other 51 are static files and need this.

The skip link matches the shared one in wayfinding.js - amber on navy, 44px, hidden until focused -
rather than inventing a second look, and is inlined because these pages load no shared JS.

Idempotent (it checks for the marker), reversible, and it changes no prose and no layout: <main> is a
semantic wrapper with no styles, and the skip link is off-screen until focused.

  python tools/fix_learn_main_landmark.py --check
  python tools/fix_learn_main_landmark.py --apply
  python tools/fix_learn_main_landmark.py --revert
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

MARK = 'id="wh-main-content"'

SKIP = (
    '<a class="wh-skip-link" href="#wh-main-content" data-wh-skip="learn" '
    'style="position:fixed;top:0;left:0;z-index:10001;transform:translateY(-120%);'
    'background:var(--wh-orange,#F7A21B);color:var(--wh-navy,#162032);padding:0 20px;min-height:44px;'
    'display:inline-flex;align-items:center;font-weight:700;font-size:14px;text-decoration:none;'
    'border-radius:0 0 10px 0;box-shadow:0 4px 16px rgba(0,0,0,.35);'
    'transition:transform .15s cubic-bezier(0.23,1,0.32,1);box-sizing:border-box;" '
    "onfocus=\"this.style.transform='translateY(0)'\" "
    "onblur=\"this.style.transform='translateY(-120%)'\">Skip to main content</a>\n"
)

ART_OPEN = re.compile(r'<article\b[^>]*>')


def pages():
    return sorted(p for p in (ROOT / "learn").glob("*/index.html") if p.is_file())


def patch(html):
    """Return (new_html, reason) - reason is None when nothing to do."""
    if MARK in html:
        return None, "already has a main landmark"
    m = ART_OPEN.search(html)
    if not m:
        return None, "no <article> to wrap"
    if "</article>" not in html:
        return None, "no </article> to close"
    out = html[:m.start()] + '<main id="wh-main-content">' + m.group(0) + html[m.end():]
    # close it at the LAST </article>, so a nested one cannot strand the wrapper
    i = out.rfind("</article>")
    out = out[:i] + "</article></main>" + out[i + len("</article>"):]
    if 'data-wh-skip="learn"' not in out:
        bm = re.search(r'<body\b[^>]*>', out)
        if not bm:
            return None, "no <body> to put the skip link after"
        out = out[:bm.end()] + "\n" + SKIP + out[bm.end():]
    return out, None


def unpatch(html):
    if MARK not in html:
        return None
    out = html.replace('<main id="wh-main-content">', "", 1)
    i = out.rfind("</article></main>")
    if i != -1:
        out = out[:i] + "</article>" + out[i + len("</article></main>"):]
    out = re.sub(r'<a class="wh-skip-link" href="#wh-main-content" data-wh-skip="learn".*?</a>\n', "", out, flags=re.S)
    return out


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
            if out is None:
                skipped.append((p, "not patched"))
            else:
                if a.apply or a.revert:
                    io.open(p, "w", encoding="utf-8", newline="").write(out)
                done.append(p)
            continue
        out, why = patch(html)
        if out is None:
            skipped.append((p, why))
            continue
        todo.append(p)
        if a.apply:
            io.open(p, "w", encoding="utf-8", newline="").write(out)
            done.append(p)

    verb = "reverted" if a.revert else ("patched" if a.apply else "would patch")
    print("%s %d of %d learn page(s)" % (verb, len(done) if (a.apply or a.revert) else len(todo), len(pages())))
    for p, why in skipped[:6]:
        print("   skipped %s - %s" % (p.relative_to(ROOT), why))
    if len(skipped) > 6:
        print("   ... and %d more skipped" % (len(skipped) - 6))
    if a.check and todo:
        print("FAIL: %d learn page(s) still have no <main> landmark" % len(todo))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
