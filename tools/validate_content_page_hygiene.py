#!/usr/bin/env python3
# DEEPWALK-CELL: content:* D4
# DEEPWALK-CELL: content:* D5
# DEEPWALK-CELL: content:* D7
# DEEPWALK-CELL: content:* D17
r"""validate_content_page_hygiene.py — the static /learn article presentation floor (D4/D5/D7/D17).

The 45 `learn/<slug>/index.html` marketing/education articles are PURE STATIC content (no app
shell — no utils.js / Supabase client / writes / interactive JS). So their quality axis is
presentation hygiene, and each property is statically decidable per page ($0, no browser):

  D4  accessibility   — `<html lang>` set · exactly one <h1> · no skipped heading level
                        (h1→h3 with no h2) · every <img> has an alt attribute.
  D5  mobile          — a responsive `<meta name="viewport" content="width=device-width...">`.
  D7  xss/escHtml     — NO unescaped dynamic-HTML sink (`innerHTML =`, `document.write`,
                        `dangerouslySetInnerHTML`); a static article has no reason to build DOM
                        from a string, so any such sink is a new injection surface to review.
  D17 smoke           — the page is structurally whole: a <head>, a non-empty <title>, and a
                        <main>/<article>/role=main content root (loads to real content, not a shell).

Forward-only floor: EVERY learn page must pass EVERY property; a new article that regresses any
one FAILs. Exit 0 = PASS, 1 = FAIL. No file is edited.
"""
from __future__ import annotations
import io
import os
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
GRN, RED, YEL, BLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m"

_IMG = re.compile(r"<img\b[^>]*>", re.I)
# capture the whole opening tag so we can honor an aria-level override (axe/AT use the ARIA level
# for heading-order, not the tag — e.g. `<h4 aria-level="2">` counts as level 2).
_HEADING = re.compile(r"<h([1-6])\b([^>]*)>", re.I)
_ARIA_LEVEL = re.compile(r"aria-level\s*=\s*[\"']?\s*([1-6])", re.I)
_SINK = re.compile(r"\.innerHTML\s*=|document\.write\s*\(|dangerouslySetInnerHTML", re.I)


def _effective_levels(src: str) -> list[int]:
    """Heading levels as assistive tech / axe compute them: aria-level overrides the tag level."""
    out = []
    for m in _HEADING.finditer(src):
        aria = _ARIA_LEVEL.search(m.group(2))
        out.append(int(aria.group(1)) if aria else int(m.group(1)))
    return out


def check_page(src: str) -> list[str]:
    """Return the list of hygiene violations for one learn page ('' = clean)."""
    v = []
    # D4 — lang / single h1 / heading order / img alt
    if not re.search(r"<html\b[^>]*\blang\s*=", src, re.I):
        v.append("D4:no <html lang>")
    h1 = len(re.findall(r"<h1\b", src, re.I))
    if h1 == 0:
        v.append("D4:no <h1>")
    elif h1 > 1:
        v.append(f"D4:{h1} <h1> (must be exactly 1)")
    levels = _effective_levels(src)  # honors aria-level (axe/AT semantics)
    for a, b in zip(levels, levels[1:]):
        if b > a + 1:
            v.append(f"D4:heading jump {a}->{b} (skipped a level, aria-level-adjusted)")
            break
    if any("alt=" not in tag for tag in _IMG.findall(src)):
        v.append("D4:<img> without alt")
    # D5 — responsive viewport
    if not re.search(r'<meta\b[^>]*name\s*=\s*["\']viewport["\'][^>]*width\s*=\s*device-width', src, re.I):
        v.append("D5:no responsive viewport meta")
    # D7 — no unescaped dynamic-HTML sink on a static page
    if _SINK.search(src):
        v.append("D7:dynamic-HTML sink on a static article")
    # D17 — structurally whole (head + non-empty title + a content root)
    if not re.search(r"<head\b", src, re.I):
        v.append("D17:no <head>")
    if not re.search(r"<title\b[^>]*>\s*\S", src, re.I):
        v.append("D17:empty/absent <title>")
    if not re.search(r"<main\b|<article\b|role\s*=\s*[\"']main[\"']", src, re.I):
        v.append("D17:no <main>/<article> content root")
    return v


def main() -> int:
    print(f"{BLD}CONTENT PAGE HYGIENE (D4/D5/D7/D17) — static /learn article presentation floor{RST}")
    print("=" * 80)
    # The static content surfaces: learn/<slug> articles + the top-level about/legal pages.
    pages = sorted((ROOT / "learn").glob("*/index.html"))
    for _d in ("about", "privacy-policy", "terms-of-service"):
        _p = ROOT / _d / "index.html"
        if _p.is_file():
            pages.append(_p)
    if not pages:
        print(f"{YEL}SKIP{RST}: no content (learn/about/legal) index.html pages found")
        return 0
    breaches = {}
    for p in pages:
        try:
            src = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        v = check_page(src)
        if v:
            breaches[os.path.relpath(p.parent, ROOT).replace(os.sep, "/")] = v
    print(f"  learn articles scanned: {len(pages)} · clean: {len(pages) - len(breaches)} · "
          f"with violations: {len(breaches)}")
    if breaches:
        print(f"\n{RED}FAIL{RST}: {len(breaches)} learn page(s) breach the content-hygiene floor:")
        for surf, vs in list(breaches.items())[:20]:
            print(f"  {RED}✗{RST} {surf}: {', '.join(vs)}")
        return 1
    print(f"\n{GRN}PASS{RST}: all {len(pages)} static /learn articles pass the presentation floor "
          f"(D4 a11y · D5 mobile-viewport · D7 no-dynamic-sink · D17 structurally-whole).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
