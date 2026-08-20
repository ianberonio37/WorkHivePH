"""
content_mobile_gate.py — mobile fitness for the CONTENT surface (V3 §6, SXO).
=============================================================================
`validate_mobile.py` targets the app pages and always has. Its checks — safe-area
insets, overscroll containment, animation cascade order — are about a stateful
JS surface and false-positive on static articles, so extending it was the wrong
move. This is the content-surface equivalent: the mobile properties that actually
decide whether a phone visitor arriving from a search result can read the page.

WHAT IT CHECKS (all statically decidable, so no flake):
  viewport          a viewport meta carrying width=device-width
  responsive        at least one @media breakpoint — proof the layout adapts
  readable_body     the body prose is >= 16px equivalent (1rem); below that iOS
                    zooms and the reader pinches
  no_fixed_width    no fixed `width: NNNpx` on a layout container outside a media
                    query, which is what forces horizontal scroll at 320px

WHAT IT DELIBERATELY DOES NOT FLAG, because measuring found both and both were wrong:
  · `max-width` / `min-width` — a breakpoint is the OPPOSITE of a fixed layout.
    The first version of this probe matched `\\bwidth` inside `max-width` (the
    hyphen is a non-word character) and reported 27 "defects" that were all
    `@media (max-width: 640px)`.
  · small type on LABELS — `.audience-label` at 11px is an eyebrow, not body
    text. Only the prose measure matters for readability.

At first honest run the content surface passed on all four: it inherits one shared
responsive template. This gate exists to keep it that way, not to find a fire.

CLI:
    python tools/content_mobile_gate.py
    python tools/content_mobile_gate.py --self-test
"""
from __future__ import annotations

import re
import sys
import json
from pathlib import Path
from datetime import datetime, timezone

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

REPORT = ROOT / "content_mobile_report.json"
BASELINE = ROOT / "content_mobile_baseline.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# `width:` but NOT max-width / min-width. A plain fixed width on a container is the
# thing that forces horizontal scroll; a breakpoint is how a layout adapts.
FIXED_W = re.compile(r"(?<!max-)(?<!min-)(?<![\w-])width\s*:\s*(\d{3,4})px")
MEDIA_Q = re.compile(r"@media[^{]*\(")
# Tailwind pages carry NO @media block of their own — the breakpoints are generated
# at runtime from `sm:` / `md:` / `lg:` / `xl:` utility classes. Judging responsiveness
# by @media alone scored 27/114 on a site built from one shared responsive template,
# which is the same wrong-proxy error as matching `\bwidth` inside `max-width`.
TW_BREAKPOINTS = (" sm:", " md:", " lg:", " xl:", " 2xl:")
VIEWPORT = re.compile(r'<meta[^>]+name=["\']viewport["\'][^>]*content=["\']([^"\']+)', re.I)
PROSE_FS = re.compile(r"\.prose-wh\s*\{[^}]*font-size\s*:\s*([\d.]+)(rem|px)", re.S)


def _strip_media_blocks(css: str) -> str:
    """Remove @media {...} bodies so a breakpoint's widths are not read as fixed."""
    out, i = [], 0
    while True:
        m = MEDIA_Q.search(css, i)
        if not m:
            out.append(css[i:])
            break
        out.append(css[i:m.start()])
        brace = css.find("{", m.end())
        if brace == -1:
            break
        depth, j = 1, brace + 1
        while j < len(css) and depth:
            depth += (css[j] == "{") - (css[j] == "}")
            j += 1
        i = j
    return "".join(out)


def analyze(html: str) -> dict:
    m = VIEWPORT.search(html)
    viewport = bool(m and "width=device-width" in m.group(1))
    responsive = bool(MEDIA_Q.search(html)) or any(b in html for b in TW_BREAKPOINTS)
    fs = PROSE_FS.search(html)
    if fs:
        val, unit = float(fs.group(1)), fs.group(2)
        readable = (val >= 1.0) if unit == "rem" else (val >= 16)
    else:
        readable = True                      # no prose block on this page
    fixed = bool(FIXED_W.search(_strip_media_blocks(html)))
    return {"viewport": viewport, "responsive": responsive,
            "readable_body": readable, "no_fixed_width": not fixed}


def _pages() -> list[str]:
    try:
        import seo_technical_gate as st
        return [p for p in st.indexable_pages() if p.startswith(("learn/", "tools/"))]
    except Exception:
        return [str(p.relative_to(ROOT).as_posix()) for p in ROOT.glob("learn/*/index.html")]


def audit() -> dict:
    keys = ("viewport", "responsive", "readable_body", "no_fixed_width")
    tally = {k: 0 for k in keys}
    fails: list[dict] = []
    pages = _pages()
    for rel in pages:
        f = ROOT / rel
        if not f.exists():
            continue
        v = analyze(f.read_text(encoding="utf-8", errors="replace"))
        for k in keys:
            tally[k] += bool(v[k])
        bad = [k for k in keys if not v[k]]
        if bad:
            fails.append({"page": rel, "failing": bad})
    return {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "pages": len(pages), "tally": tally, "failures": len(fails), "fail_rows": fails[:20]}


def run() -> int:
    rep = audit()
    REPORT.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    base = {}
    if BASELINE.exists():
        try:
            base = json.loads(BASELINE.read_text(encoding="utf-8"))
        except Exception:
            base = {}
    prior = base.get("failures", rep["failures"])
    print("=" * 64)
    print("  CONTENT-SURFACE MOBILE — SXO (V3 §6)")
    print("=" * 64)
    n = rep["pages"]
    for k, v in rep["tally"].items():
        print(f"    {'OK  ' if v == n else 'FAIL'}  {k:<16} {v}/{n}")
    for r in rep["fail_rows"][:8]:
        print(f"      - {r['page']}: {', '.join(r['failing'])}")
    print("=" * 64)
    if rep["failures"] > prior:
        print(f"  FAIL — regressed {prior} -> {rep['failures']} page(s)")
        return 1
    BASELINE.write_text(json.dumps({"failures": min(prior, rep["failures"]),
                                    "established": base.get("established", rep["generated_at"])},
                                   indent=2), encoding="utf-8")
    print(f"  PASS — {n - rep['failures']}/{n} pages mobile-clean.")
    return 0


def self_test() -> int:
    ok = True

    def ck(c, m):
        nonlocal ok
        ok &= bool(c)
        print(f"  {'PASS' if c else 'FAIL'}  {m}")

    good = ('<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<style>.prose-wh{font-size:1.05rem;} @media (max-width: 640px){ .x{width:300px;} }</style>')
    v = analyze(good)
    ck(v["viewport"] and v["responsive"] and v["readable_body"], "a well-formed page passes")
    ck(analyze('<div class="text-4xl sm:text-6xl">x</div>')["responsive"],
       "Tailwind sm:/lg: utilities count as responsive (no @media block is shipped)")
    ck(not analyze('<div class="text-4xl">x</div>')["responsive"],
       "a page with neither @media nor a breakpoint utility is caught")
    ck(v["no_fixed_width"], "a width INSIDE a media query is a breakpoint, not a fixed layout")
    ck(analyze('<style>.x{max-width:640px;}</style>')["no_fixed_width"],
       "max-width is not a fixed width (the bug that produced 27 false defects)")
    ck(not analyze('<style>.hero{width:960px;}</style>')["no_fixed_width"],
       "a real fixed width outside a media query IS caught")
    ck(not analyze('<meta name="viewport" content="width=1024">')["viewport"],
       "a non-responsive viewport is caught")
    ck(not analyze('<style>.prose-wh{font-size:12px;}</style>')["readable_body"],
       "body prose below 16px is caught")
    ck(analyze('<style>.audience-label{font-size:11px;}</style>')["readable_body"],
       "small type on a LABEL is not a readability defect")
    r = audit()
    ck(r["pages"] > 100, f"audits the content surface ({r['pages']} pages)")
    print("  self-test", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(self_test() if "--self-test" in sys.argv[1:] else run())
