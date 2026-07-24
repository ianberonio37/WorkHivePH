#!/usr/bin/env python3
"""
apply_c5_apca_textlift.py — resolve the C5 (APCA perceptual contrast) finding platform-wide.

The C5 dim (APCA, WCAG3 successor) found muted TEXT that passes WCAG 2.x but fails APCA Lc on the
dark theme. The offenders are inline `color:rgba(255,255,255,0.5x-0.72)` declarations. This lifts
ONLY the text-`color:` ones (never borders/backgrounds) to a hierarchy-preserving 3-tier map that
clears APCA body Lc 75 on both the navy shell and faint cards (validated in Python before shipping):

    0.55/0.56/0.62 -> 0.80   (Lc ~77)
    0.65/0.66/0.70 -> 0.83   (Lc ~81)
    0.72           -> 0.86   (Lc ~85)

Surgical (text color only), strictly-improving (higher contrast), reversible (git). --check reports
scope without writing; default applies.
"""
from __future__ import annotations
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXCLUDE = {"architecture.html", "design-system.html", "symbol-gallery.html", "validator-catalog.html",
           "llm-observability.html", "agentic-rag-observability.html", "ai-quality.html", "status.html",
           "offline-fallback.html", "promo-poster.html", "resume.html", "platform-health.html",
           "engineering-design-test.html"}
NONPROD = re.compile(r"backup|\.bak\b|-test\.|\.test\.|\.old\b|\.orig\b|copy", re.I)

# old alpha (2-decimal) -> new alpha. Only these exact muted-text bands are lifted.
AMAP = {"0.5": "0.80", "0.55": "0.80", "0.56": "0.80", "0.6": "0.80", "0.62": "0.80",
        "0.65": "0.83", "0.66": "0.83", "0.7": "0.83", "0.70": "0.83", "0.71": "0.83",
        "0.72": "0.86", "0.73": "0.86", "0.74": "0.86", "0.75": "0.86"}

# match ONLY `color:rgba(<base>, <alpha>)` for the two near-white bases the theme dims for muted
# TEXT — white (255,255,255) and --wh-cloud (244,246,250). Never border-color/background/box-shadow
# (negative lookbehind on `-`). Both bases are near-white so the same alpha map clears APCA Lc75.
# alpha may be written WITH or WITHOUT a leading zero (0.6 or .6) — CSS allows both, and .sub on
# project-manager used `.6`, which a `0\.` regex silently skipped (a straggler that kept C5 < 100).
PAT = re.compile(
    r"(?<![-\w])color:\s*rgba\(\s*(?:255\s*,\s*255\s*,\s*255|244\s*,\s*246\s*,\s*250)\s*,\s*(0?\.\d{1,2})\s*\)",
    re.I)


def lift(m: re.Match) -> str:
    a = m.group(1)
    if a.startswith("."):
        a = "0" + a           # normalise `.6` -> `0.6` for the AMAP lookup
    new = AMAP.get(a)
    if not new:
        return m.group(0)  # outside the muted band -> leave untouched
    base = "244,246,250" if "244" in m.group(0) else "255,255,255"
    return f"color:rgba({base},{new})"


def _targets():
    """HTML pages + the SHARED chrome (components.css muted classes + utils.js injected CSS). The
    first pass only touched *.html and MISSED the shared muted classes (.sc-label/.sc-sub/
    .wh-disclose/.details-toggle in components.css, and utils.js-injected chrome) that drive the
    muted secondary text on EVERY page — so C5 barely moved (79->82) until these were included."""
    for p in sorted(ROOT.glob("*.html")):
        if p.name not in EXCLUDE and not NONPROD.search(p.name):
            yield p
    for extra in ("components.css", "utils.js"):
        p = ROOT / extra
        if p.exists():
            yield p


def main() -> int:
    check = "--check" in sys.argv
    total = 0
    files = 0
    for p in _targets():
        s = p.read_text(encoding="utf-8", errors="replace")
        n = sum(1 for m in PAT.finditer(s) if m.group(1) in AMAP)
        if not n:
            continue
        total += n
        files += 1
        if not check:
            p.write_text(PAT.sub(lift, s), encoding="utf-8")
    verb = "would lift" if check else "lifted"
    print(f"C5 APCA text-lift: {verb} {total} muted color: declarations (white + cloud base) across {files} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
