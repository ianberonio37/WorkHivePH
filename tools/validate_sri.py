#!/usr/bin/env python3
"""
validate_sri.py - Arc R (S-lens, OWASP A08): Subresource Integrity on third-party CDN scripts.
==============================================================================================
A <script src="https://cdn.../lib.js"> with no `integrity=` lets a CDN compromise inject arbitrary
JS into every authenticated page (token/RLS-session theft). The platform had ZERO `integrity=`
attributes anywhere (Hunter S, Arc R).

Two tiers:
  PINNED  - URL carries an exact version (e.g. plotly-basic-2.26.0, html2pdf.js@0.10.1). These CAN be
            SRI-hashed today => a pinned third-party CDN script WITHOUT integrity is a hard FAIL.
  FLOATING- URL has no exact version (@supabase/supabase-js@2, cdn.tailwindcss.com, mermaid@11). SRI
            requires pinning first (a behaviour-affecting change = Ian-reviewable). Reported as a
            tracked backlog (NOTE), not a hard fail.
Exempt: Google Fonts CSS (fonts.googleapis/gstatic) + Google gtag - Google-managed, SRI not applied.

Self-test (--self-test): a pinned tag w/o integrity FAILs; w/ integrity passes; a floating tag is a NOTE.
Exit 0 = no pinned CDN script lacks SRI. Exit 1 = a pinned script is unprotected (or self-test fail).
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; X = "\033[0m"

CHECK_NAMES = ["validate_sri"]

TAG = re.compile(r"<(script|link)\b[^>]*>", re.IGNORECASE)
SRC = re.compile(r'(?:src|href)\s*=\s*"(https://[^"]+)"', re.IGNORECASE)
HAS_INTEGRITY = re.compile(r'\bintegrity\s*=', re.IGNORECASE)
# Exempt hosts: Google-managed fonts/analytics (SRI not applicable).
EXEMPT_HOST = re.compile(r"fonts\.googleapis\.com|fonts\.gstatic\.com|googletagmanager\.com|google-analytics\.com")
# Same-origin / own domain - not third-party.
OWN_HOST = re.compile(r"workhiveph\.com|supabase\.co/storage|hzyvnjtisfgbksicrouu\.supabase\.co")
# A version pin: @x.y.z  OR /x.y.z/  OR -x.y.z. (e.g. plotly-basic-2.26.0)
PINNED = re.compile(r"@\d+\.\d+\.\d+|/\d+\.\d+\.\d+/|-\d+\.\d+\.\d+")
# Tailwind Play CDN: a runtime JIT compiler with NO versioned artifact — it cannot be SRI-hashed at all
# (pinning is not the fix; migrating to a built static CSS file is). Reported DISTINCTLY from pin-first so
# the backlog line doesn't imply "just add a hash." (Arc R R3, 2026-07-03.)
PLAY_CDN = re.compile(r"cdn\.tailwindcss\.com")


def classify_tag(tag: str) -> str | None:
    """Return 'pinned-no-sri' | 'floating-no-sri' | None (ok/exempt)."""
    if "stylesheet" in tag.lower() and "<link" in tag.lower():
        pass  # CSS link still counts if third-party JS-adjacent; fonts excluded below
    m = SRC.search(tag)
    if not m:
        return None
    url = m.group(1)
    if EXEMPT_HOST.search(url) or OWN_HOST.search(url):
        return None
    if HAS_INTEGRITY.search(tag):
        return None
    return "pinned-no-sri" if PINNED.search(url) else "floating-no-sri"


def scan(text: str) -> tuple[list[str], list[str]]:
    pinned, floating = [], []
    for m in TAG.finditer(text):
        tag = m.group(0)
        cls = classify_tag(tag)
        url_m = SRC.search(tag)
        url = url_m.group(1) if url_m else "?"
        if cls == "pinned-no-sri":
            pinned.append(url)
        elif cls == "floating-no-sri":
            floating.append(url)
    return pinned, floating


def self_test() -> bool:
    ok = True
    p, _ = scan('<script src="https://cdn.plot.ly/plotly-basic-2.26.0.min.js"></script>')
    if not p:
        print(f"{R}self-test FAIL: missed pinned-no-SRI.{X}"); ok = False
    p2, _ = scan('<script src="https://cdn.plot.ly/plotly-basic-2.26.0.min.js" integrity="sha384-x" crossorigin="anonymous"></script>')
    if p2:
        print(f"{R}self-test FAIL: flagged a tag that HAS integrity.{X}"); ok = False
    _, fl = scan('<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>')
    if not fl:
        print(f"{R}self-test FAIL: did not classify floating tag.{X}"); ok = False
    p3, _ = scan('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?x">')
    if p3:
        print(f"{R}self-test FAIL: flagged exempt Google Fonts.{X}"); ok = False
    print((G + "self-test PASS - SRI detector has teeth." + X) if ok else (R + "self-test FAILED." + X))
    return ok


def main() -> int:
    if "--self-test" in sys.argv:
        return 0 if self_test() else 1

    pinned_hits: dict[str, list] = {}
    pin_first_urls: list[str] = []   # floating but pinnable+SRI-able (freeze to current-resolved)
    play_cdn_urls: list[str] = []    # floating AND un-SRI-able (Tailwind Play CDN — migrate to built CSS)
    for p in sorted(ROOT.glob("*.html")):
        if "backup" in p.name or "-test" in p.name:
            continue
        pinned, floating = scan(p.read_text(encoding="utf-8", errors="replace"))
        if pinned:
            pinned_hits[p.name] = pinned
        for u in floating:
            (play_cdn_urls if PLAY_CDN.search(u) else pin_first_urls).append(u)

    pinned_n = sum(len(v) for v in pinned_hits.values())
    print(f"{B}SRI gate (Arc R / S-lens, OWASP A08){X}")
    for fn, urls in pinned_hits.items():
        for u in urls:
            print(f"  {R}FAIL{X} {fn}: pinned CDN script w/o SRI -> {u}")
    print(f"  pinned-without-SRI: {pinned_n}  ·  pin-first backlog (Ian-reviewable): {len(pin_first_urls)}"
          f"  ·  Play-CDN un-SRI-able (migrate to built CSS): {len(play_cdn_urls)}")
    if pin_first_urls:
        print(f"  {Y}NOTE{X} {len(pin_first_urls)} floating tag(s) CAN be pinned+SRI'd (freeze to current-resolved, "
              f"hash-verify): " + ", ".join(sorted(set(pin_first_urls))))
    if play_cdn_urls:
        print(f"  {Y}NOTE{X} {len(play_cdn_urls)}x cdn.tailwindcss.com — Tailwind Play CDN is a runtime JIT with no "
              f"versioned artifact; SRI is not the lever, migrating to a built static CSS file is (own Ian-gated unit).")
    if pinned_n:
        print(f"{R}FAIL: {pinned_n} version-pinned third-party CDN script(s) lack integrity= .{X}")
        return 1
    print(f"{G}PASS - every version-pinned CDN script has SRI.{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
