#!/usr/bin/env python3
"""validate_precache_coverage.py - Arc S (Resilience/DR) D-lens cell `precache_coverage`.
================================================================================
Only ~7 pages are in the service-worker precache shell; opening any OTHER page
offline would resolve to a network error = blank tab. The fix isn't to precache all
37 pages (heavy, stale-cache risk) but to give the SW a NAVIGATION FALLBACK: when an
offline navigation misses the cache and the fetch fails, serve a branded offline
shell that explains the state + links the surfaces that DO work offline.

This gate asserts sw.js: (1) precaches /offline-fallback.html, (2) the fetch handler
has a navigation fallback to it (caches.match('/offline-fallback.html')) on fetch
failure, and (3) the offline-fallback.html file exists and is self-contained (no CDN
dependency, since it must render with no network).

Exit 0 = no blank-tab-offline; 1 = a navigation could dead-end. Stdlib, $0.
"""
from __future__ import annotations
import io, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
G = "\033[92m"; R = "\033[91m"; B = "\033[1m"; X = "\033[0m"


def main() -> int:
    print(f"{B}Arc S - precache / offline navigation fallback (D-lens){X}")
    print("=" * 60)
    sw = ""
    try:
        sw = (ROOT / "sw.js").read_text(encoding="utf-8", errors="replace")
    except OSError:
        pass
    fb = ROOT / "offline-fallback.html"
    fb_txt = fb.read_text(encoding="utf-8", errors="replace") if fb.exists() else ""

    checks = {
        "offline-fallback.html exists":                 fb.exists(),
        "fallback is self-contained (no CDN <script src>)":
            fb.exists() and "src=\"https://" not in fb_txt and "src='https://" not in fb_txt,
        "sw.js precaches /offline-fallback.html":        "/offline-fallback.html" in sw,
        "sw.js fetch handler has a navigation fallback":
            "offline-fallback.html" in sw and ("navigate" in sw) and (".catch(" in sw),
    }
    for k, ok in checks.items():
        print(f"  {(G+'PASS'+X) if ok else (R+'FAIL'+X)}  {k}")
    if not all(checks.values()):
        print(f"\n{R}{B}  PRECACHE-COVERAGE: FAIL{X} - an offline navigation could show a blank tab.")
        return 1
    print(f"\n{G}{B}  PRECACHE-COVERAGE: PASS{X} - offline navigations land on the branded fallback shell.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
