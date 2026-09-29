"""The breadcrumb's CURRENT-PAGE label renders at 1.98:1 on 98 public pages.

~W46153 (audit walk, 2026-09-20), found on
learn/maintenance-metrics-reliability-guide/. This is the second half of a defect
whose first half was fixed on 2026-09-10 by tools/fix_breadcrumb_contrast.py, and
the second half survived because the two live in different CSS properties.

THE COMPOUNDING NOBODY FIXED. The breadcrumb rules are:

    .breadcrumb      { font-size: 0.85rem; color: rgba(244,246,250,0.55); ... }
    .breadcrumb a    { color: rgba(244,246,250,0.55); ... }
    .breadcrumb span { margin: 0 8px; opacity: 0.4; }      <- 98 pages, identical

The 2026-09-10 sweep raised the COLOUR alpha from 0.45 to 0.55, taking the ratio
from 4.13:1 to 5.47:1, and it verifies 95 rules at or above AA. That is true of the
LINKS. It is not true of the SPANS, because `opacity` multiplies the composite
after the colour alpha has already been applied:

    links : alpha 0.55, opacity 1.0  -> effective 0.55 -> 5.47:1   PASS
    spans : alpha 0.55, opacity 0.4  -> effective 0.22 -> 1.98:1   FAIL

Measured in the live DOM by walking the breadcrumb subtree and compounding each
ancestor's opacity, not by reading the stylesheet.

WHAT IS IN A SPAN. Both the "/" separators AND the trailing CURRENT-PAGE label -
on the page that surfaced this, `<span>Maintenance metrics guide</span>`. That
label is the most informative element in the whole trail for the audience the
breadcrumb exists to serve: someone arriving from a search engine who needs to know
where in the site they have landed. It is rendering at 1.98:1 against a 4.5:1
requirement for 13.6px text.

★THE WALK UNDER-REPORTED THIS AND THAT IS WORTH RECORDING. Its contrast sampler
read the element's computed colour (alpha 0.45 before the fix) and reported 4.11:1;
the true figure was 0.45 x 0.4 = 0.18 effective, far worse. A contrast reading that
does not compound ancestor `opacity` is optimistic wherever a page dims a subtree
that way, so `contrastLow 0` elsewhere in this bank means "no element whose own
colour is too faint", not "no faint text".

THE FIX AND WHY THERE IS NO MIDDLE GROUND. The separator could stay visually
quieter than the label only if some opacity below 1 still cleared AA, and it does
not: 0.55 x 0.82 = 0.45 effective = 4.12:1, already failing, and that is barely a
dimming at all. So the opacity is removed and the spans inherit the breadcrumb's
own 0.55, which the earlier sweep already chose precisely because it "clears AA with
margin while keeping the breadcrumb visibly secondary to the headline". The trail
stays secondary; its parts stop being invisible relative to each other.

    python tools/fix_breadcrumb_span_opacity.py --check
    python tools/fix_breadcrumb_span_opacity.py --apply
"""
from __future__ import annotations

import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

RULE_RE = re.compile(r"(\.breadcrumb\s+span\s*\{)([^}]*)(\})")
OPACITY_RE = re.compile(r"\s*opacity\s*:\s*([\d.]+)\s*;?")


def targets():
    pats = [os.path.join(ROOT, "learn", "*", "index.html"),
            os.path.join(ROOT, "tools", "*", "index.html")]
    out = []
    for p in pats:
        out += sorted(glob.glob(p))
    for rel in ("index.html", "about/index.html", "feedback/index.html",
                "privacy-policy/index.html", "terms-of-service/index.html"):
        f = os.path.join(ROOT, rel)
        if os.path.exists(f):
            out.append(f)
    return out


def offending(html: str):
    """Return the opacity value < 1 on `.breadcrumb span`, or None."""
    styles = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html, re.S))
    m = RULE_RE.search(styles)
    if not m:
        return None
    o = OPACITY_RE.search(m.group(2))
    if not o:
        return None
    v = float(o.group(1))
    return v if v < 1 else None


def patch(html: str):
    def repl(m):
        body = OPACITY_RE.sub("", m.group(2))
        body = re.sub(r";\s*;", ";", body).rstrip()
        if body and not body.endswith(";"):
            body += ";"
        return m.group(1) + " " + body.strip() + " " + m.group(3)

    out, pos, n = [], 0, 0
    for sm in re.finditer(r"(<style[^>]*>)(.*?)(</style>)", html, re.S):
        css, cnt = RULE_RE.subn(repl, sm.group(2))
        if cnt:
            n += cnt
            out.append(html[pos:sm.start()])
            out.append(sm.group(1) + css + sm.group(3))
            pos = sm.end()
    out.append(html[pos:])
    return "".join(out), n


def run(apply: bool) -> int:
    bad, clean, norule = [], 0, 0
    for p in targets():
        html = open(p, encoding="utf-8").read()
        v = offending(html)
        if v is None:
            styles = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html, re.S))
            if RULE_RE.search(styles):
                clean += 1
            else:
                norule += 1
            continue
        bad.append((os.path.relpath(p, ROOT), v))
        if apply:
            new_html, n = patch(html)
            if n:
                open(p, "w", encoding="utf-8").write(new_html)

    if apply:
        print(f"  removed the compounding opacity from {len(bad)} page(s) "
              f"({clean} already clean, {norule} have no .breadcrumb span rule)")
        return 0
    if bad:
        worst = min(v for _, v in bad)
        print(f"  FAIL: {len(bad)} page(s) dim the breadcrumb's separators AND its "
              f"current-page label with a compounding opacity (lowest {worst}); at the "
              f"breadcrumb's 0.55 colour alpha that is 1.98:1 against a 4.5:1 floor")
        for rel, v in bad[:5]:
            print(f"     - {rel}  (opacity {v})")
        if len(bad) > 5:
            print(f"     ... and {len(bad) - 5} more")
        print("  fix: python tools/fix_breadcrumb_span_opacity.py --apply")
        return 1
    print(f"  OK: {clean} page(s) carry a .breadcrumb span rule and none of them "
          f"compounds an opacity onto the colour alpha")
    return 0


if __name__ == "__main__":
    raise SystemExit(run("--apply" in sys.argv[1:]))
