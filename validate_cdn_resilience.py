#!/usr/bin/env python3
"""validate_cdn_resilience.py - Arc S (Resilience/DR) F-lens cell `cdn_resilience`.
================================================================================
A page that HARD-depends on a third-party CDN lib (Plotly for charts) throws a
ReferenceError into a silent failure when the CDN 404s/times out: the lib global
is undefined and the call dies in a deferred callback, leaving an empty chart with
no user message.

This gate asserts every page that calls a CDN-global API guards it first
(`typeof <Global> === 'undefined'` -> show a "library unavailable" message before
calling it). Today the one such dependency is Plotly in analytics.html.

Exit 0 = CDN-dependent calls are guarded; 1 = an unguarded CDN dependency. Stdlib, $0.
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
G = "\033[92m"; R = "\033[91m"; B = "\033[1m"; X = "\033[0m"

# (page, cdn-global, the call that must be guarded)
CDN_DEPS = [
    ("analytics.html", "Plotly", "Plotly.newPlot"),
]


def main() -> int:
    print(f"{B}Arc S - CDN resilience (F-lens, no silent dead lib){X}")
    print("=" * 60)
    issues = []
    for page, glob, call in CDN_DEPS:
        try:
            t = (ROOT / page).read_text(encoding="utf-8", errors="replace")
        except OSError:
            print(f"  {R}FAIL{X}  {page} not found")
            issues.append(page)
            continue
        uses = call in t
        if not uses:
            print(f"  {G}PASS{X}  {page} no longer calls {call} (dependency removed)")
            continue
        guarded = bool(re.search(rf"typeof\s+{re.escape(glob)}\s*===?\s*['\"]undefined['\"]", t))
        print(f"  {(G+'PASS'+X) if guarded else (R+'FAIL'+X)}  {page} guards `typeof {glob} === 'undefined'` before {call}")
        if not guarded:
            issues.append(page)

    if issues:
        print(f"\n{R}{B}  CDN-RESILIENCE: FAIL{X} - unguarded CDN dependency in: {', '.join(issues)}")
        return 1
    print(f"\n{G}{B}  CDN-RESILIENCE: PASS{X} - CDN-dependent calls degrade gracefully when the lib is missing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
