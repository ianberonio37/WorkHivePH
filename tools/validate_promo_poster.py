#!/usr/bin/env python3
"""validate_promo_poster.py — T489's lock: the promo poster is a VALID, complete asset.

promo-poster.html is a static marketing asset a person downloads and prints/shares. "Valid asset"
has three checkable properties, each a way it could silently ship broken:
  1. COMPLETE CONTENT — the headline and all FIVE product pillars (Digital Logbook, PM Scheduler,
     Spare-Parts Inventory, Engineering Calculators, AI Work Assistant) must be present; a poster
     missing a pillar misrepresents the product.
  2. NO BROKEN IMAGES — every local <img src> must resolve to a file that exists; a poster with a
     broken image is worthless as a shareable asset (the whole point is that it renders standalone).
  3. WELL-FORMED SVG — every <svg> is balanced; an unbalanced graphic corrupts the render.

Verified 2026-09-01: headline + 5 pillars present, 4/4 images resolve, 11/11 svg balanced. This
gate holds the line so an edit that drops a pillar, breaks an image path, or leaves an unclosed
<svg> reddens before the poster ships.

Static (file reads only), browser-free. Registered in run_platform_checks (Platform).
"""
from __future__ import annotations

import io
import os
import re
import sys

CHECK_NAMES = ["promo-poster-valid"]
POSTER = "promo-poster.html"
PILLARS = ["Digital Logbook", "PM Scheduler", "Spare-Parts Inventory", "Engineering Calculators", "AI Work Assistant"]


def _read() -> str | None:
    try:
        return io.open(POSTER, encoding="utf-8").read()
    except Exception:
        return None


def check(html: str) -> list[str]:
    problems: list[str] = []
    text = re.sub(r"<[^>]+>", " ", html)
    for p in PILLARS:
        if p.lower() not in text.lower():
            problems.append(f"missing product pillar '{p}' (poster misrepresents the product)")
    if not re.search(r"track every machine", text, re.I):
        problems.append("missing the headline 'Track Every Machine' (poster has no hook)")
    for src in re.findall(r'<img[^>]*\ssrc="([^"]+)"', html):
        if src.startswith(("data:", "http://", "https://")):
            continue
        local = src.split("?")[0].split("#")[0].lstrip("/")
        if not os.path.exists(local):
            problems.append(f"broken image src '{src}' — file does not exist (invalid downloadable asset)")
    if html.count("<svg") != html.count("</svg>"):
        problems.append(f"unbalanced <svg> tags ({html.count('<svg')} open vs {html.count('</svg>')} close) — corrupt graphic")
    return problems


def main() -> int:
    html = _read()
    if html is None:
        print(f"FAIL promo-poster-valid — {POSTER} not found or unreadable."); return 1
    problems = check(html)
    if problems:
        print("FAIL promo-poster-valid — the poster is not a valid, complete asset:")
        for p in problems:
            print(f"    {p}")
        return 1
    imgs = len(re.findall(r'<img[^>]*\ssrc="([^"]+)"', html))
    print(f"PASS promo-poster-valid — headline + all {len(PILLARS)} pillars present, {imgs} images resolve, "
          f"{html.count('<svg')} svg balanced: a complete, renderable downloadable asset.")
    return 0


def self_test() -> int:
    fails = []
    good = ('<h1>Track Every Machine</h1>' + "".join(f"<div>{p}</div>" for p in PILLARS)
            + '<img src="brand_assets/workhive-logo-tight.png"><svg></svg>')
    if check(good):
        fails.append("a complete poster should PASS")
    if not any("pillar" in p for p in check(good.replace("PM Scheduler", "X"))):
        fails.append("a missing pillar should FAIL")
    if not any("broken image" in p for p in check(good.replace("brand_assets/workhive-logo-tight.png", "no-such-file.png"))):
        fails.append("a broken image should FAIL")
    if not any("unbalanced" in p for p in check(good.replace("</svg>", ""))):
        fails.append("an unbalanced svg should FAIL")
    if not any("headline" in p for p in check(good.replace("Track Every Machine", "X"))):
        fails.append("a missing headline should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_promo_poster self-test (missing pillar / broken image / unbalanced svg / missing headline redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
