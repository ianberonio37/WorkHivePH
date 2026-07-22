#!/usr/bin/env python3
# DEEPWALK-CELL: * CA
"""
validate_sw_shell_membership.py - CA (Caching/CDN) deep-walk cell, 2026-07-22.
==============================================================================
The CA architectural-layer per-page cell (PER_PAGE_ARCHITECTURAL_LAYER_DEEPWALK_ROADMAP.md §4): a page in
the service-worker OFFLINE SHELL must (a) actually exist on disk (a stale SHELL_FILES entry 404s the SW
precache install → the whole offline shell breaks for every PWA user), and (b) the shell must be
cache-VERSIONED (`CACHE_NAME`), so a shell change re-primes rather than serving stale cached markup.

Emits its exact per-page pass-list to `deepwalk_layer_pages.json[CA]` (the SW-shell HTML pages), which the
deepwalk flywheel reads to score the CA cell ONLY on the cached pages (n/a for un-cached pages — caching
doesn't apply to a page the SW never precaches). This is the same gate-emitted-pass-list mechanism as
RL(D12P)/C(CP): the gate publishes its exact scope, the flywheel never regex-approximates. Static; teeth:
--selftest.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

G = "\033[92m"; R = "\033[91m"; B = "\033[1m"; X = "\033[0m"
CHECK_NAMES = ["validate_sw_shell_membership"]
ROOT = Path(__file__).resolve().parent.parent
SW = ROOT / "sw.js"


def _shell_html():
    """The HTML pages in the ACTIVE (uncommented) SHELL_FILES array + whether CACHE_NAME is set."""
    if not SW.exists():
        return [], False
    src = SW.read_text(encoding="utf-8", errors="replace")
    versioned = bool(re.search(r"(?m)^\s*const\s+CACHE_NAME\s*=\s*['\"]", src))
    m = re.search(r"(?m)^\s*const\s+SHELL_FILES\s*=\s*\[(.*?)\]", src, re.S)
    if not m:
        return [], versioned
    htmls = re.findall(r"['\"]\.?/?([a-z0-9-]+\.html)['\"]", m.group(1))
    return sorted(set(htmls)), versioned


def _emit_deepwalk_pages(dim, page_stems, all_pass):
    f = ROOT / "deepwalk_layer_pages.json"
    try:
        data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    data[dim] = {"pages": sorted(set(page_stems)), "pass": bool(all_pass)}
    try:
        f.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
    except Exception:
        pass


def self_test() -> bool:
    ok = True
    htmls, versioned = _shell_html()
    if not htmls:
        print(f"{R}self-test FAIL: parsed 0 shell HTML pages (SHELL_FILES regex broke?).{X}"); ok = False
    if not versioned:
        print(f"{R}self-test FAIL: CACHE_NAME not detected.{X}"); ok = False
    print((G + "self-test PASS - sw-shell-membership has teeth." + X) if ok else (R + "self-test FAILED." + X))
    return ok


def main() -> int:
    if "--selftest" in sys.argv or "--self-test" in sys.argv:
        return 0 if self_test() else 1
    htmls, versioned = _shell_html()
    print(f"{B}CA cache/PWA — SW offline-shell pages must exist + be cache-versioned ({len(htmls)} shell HTML){X}")
    missing = [h for h in htmls if not (ROOT / h).exists()]
    ok = versioned and not missing
    # emit the pass-list: the shell pages (stems), pass iff versioned + all exist
    _emit_deepwalk_pages("CA", [h[:-5] for h in htmls], ok)
    if not versioned:
        print(f"  {R}○{X} sw.js has no CACHE_NAME — the shell isn't cache-versioned; a change won't re-prime.")
    for h in missing:
        print(f"  {R}○{X} {h}: in SHELL_FILES but the file is MISSING — the SW precache install 404s → offline shell breaks.")
    if not ok:
        print(f"{R}FAIL: SW offline shell is invalid.{X}")
        return 1
    print(f"{G}PASS - all {len(htmls)} SW-shell pages exist and the shell is cache-versioned (CACHE_NAME set).{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
