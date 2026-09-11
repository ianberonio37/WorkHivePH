#!/usr/bin/env python3
"""validate_cdn_client_canary.py — a page that hard-depends on the CDN Supabase client must carry the
canary that explains its absence.

WHY (W3-JN, 2026-09-10). 35 pages load the client that does all auth and all data from
`https://cdn.jsdelivr.net/npm/@supabase/supabase-js@…`. Three facts, each checked rather than assumed:

  * it is in NO `SHELL_FILES` entry - there are no cross-origin entries at all;
  * the cache-on-visit path added 2026-09-09 is `new URL(url).origin === self.location.origin`, so
    jsdelivr can never qualify;
  * no page carries an `onerror` on that tag.

So the service worker can never hold a copy, and losing that one request - a brownout, a blocked CDN, an
SRI mismatch, a lossy link dropping one request in twelve - leaves every page painting its shell and then
throwing `getDb() called before @supabase/supabase-js loaded` into the console while the person looks at a
blank screen with nothing to act on.

That single fact sits under three findings filed separately: W3627 and W3579 (recorded as cold-start
artifacts), the offline-3g cluster (40% closed against 75-83% for every other condition), and the blank
`hive.html` in W3512/W3654.

`browser-floor.js` now carries a second canary that says what happened, that saved work is safe, and to
reload. It lives there because that file is PRECACHED and pure ES5 - the one script guaranteed to be
present and parseable at the moment the CDN is not.

THIS GATE holds the pairing: any page that hard-depends on the client must also load the canary, and the
canary must still exist. It does NOT assert the real fix (vendoring the client to the origin, which
removes the dependency instead of describing it) - that is a supply-chain decision and Ian's call. If it
ever lands, this gate is retired with it.

    python tools/validate_cdn_client_canary.py
    python tools/validate_cdn_client_canary.py --selftest
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOOR = ROOT / "browser-floor.js"

CLIENT_TAG = re.compile(r"""<script[^>]+src=["'][^"']*supabase[^"']*\.js""", re.I)
FLOOR_TAG = re.compile(r"""<script[^>]+src=["'][^"']*browser-floor\.js""", re.I)
# the canary's two load-bearing halves: it must ASK whether the page wants the client, and it must
# only then check whether the client ARRIVED. Either half alone is not the property.
# ★THE SELECTOR HAS QUOTES INSIDE IT, so a `[^'"]*` run can never reach the word it is looking for:
# the real call is `querySelectorAll('script[src*="supabase-js"], …')` and the inner `"` stops the scan
# dead. The gate's first version failed its own self-test on the very canary it was written to protect -
# which is the cheapest possible place to learn it. Match to the closing paren instead.
CANARY_SCOPE = re.compile(r"""querySelectorAll\([^)]{0,120}supabase""", re.I)
CANARY_TEST = re.compile(r"""if\s*\(\s*window\.supabase\s*\)\s*return""", re.I)


def canary_present(src: str) -> tuple[bool, str]:
    if not CANARY_SCOPE.search(src):
        return False, "it never asks whether the page loads the client, so it would warn on the 114 public learn/ and tools/ pages too"
    if not CANARY_TEST.search(src):
        return False, "it never checks whether the client ARRIVED, so it cannot tell a missing client from a present one"
    return True, ""


def run() -> int:
    try:
        floor = io.open(FLOOR, encoding="utf-8", errors="replace").read()
    except OSError as e:
        print(f"FAIL cdn-client-canary: cannot read browser-floor.js ({e})")
        return 1
    ok, why = canary_present(floor)
    if not ok:
        print(f"FAIL cdn-client-canary: browser-floor.js no longer carries the client-missing canary - {why}")
        return 1

    needs, unguarded = 0, []
    for f in sorted(ROOT.glob("*.html")):
        src = io.open(f, encoding="utf-8", errors="replace").read()
        if not CLIENT_TAG.search(src):
            continue                       # a public page that never asks for the client cannot lose it
        needs += 1
        if not FLOOR_TAG.search(src):
            unguarded.append(f.name)

    print(f"cdn-client-canary: {needs} page(s) hard-depend on the CDN Supabase client; "
          f"{needs - len(unguarded)} carry the canary")
    if not unguarded:
        print("  every dependent page can explain the client's absence instead of showing a blank screen")
        return 0
    print(f"FAIL cdn-client-canary: {len(unguarded)} page(s) load the client but NOT browser-floor.js:")
    for n in unguarded:
        print(f"  {n}")
    print("  Losing that one CDN request leaves this page blank with a console throw and no way for the\n"
          "  person to know what happened. Add <script src=\"browser-floor.js\"></script> early in the page.")
    return 1


def selftest() -> int:
    fails = 0
    good = ('document.querySelectorAll(\'script[src*="supabase-js"]\').length;\n'
            'if (window.supabase) return;')
    for name, src, want in [
        ("a complete canary passes", good, True),
        ("a canary that never scopes to the client is caught",
         "if (window.supabase) return;", False),
        ("a canary that never checks arrival is caught",
         "document.querySelectorAll('script[src*=\"supabase-js\"]').length;", False),
    ]:
        got, _ = canary_present(src)
        if got != want:
            print(f"  FAIL {name}"); fails += 1
        else:
            print(f"  ok   {name}")
    # the page-pairing half: a dependent page without the floor tag must be caught
    dep = '<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/dist/umd/supabase.min.js"></script>'
    if not CLIENT_TAG.search(dep):
        print("  FAIL a real CDN client tag is not recognised"); fails += 1
    else:
        print("  ok   a real CDN client tag is recognised")
    if FLOOR_TAG.search(dep):
        print("  FAIL a page with no browser-floor tag reads as guarded"); fails += 1
    else:
        print("  ok   a page with no browser-floor tag reads as unguarded")
    print("selftest:", "PASS" if not fails else f"{fails} FAILED")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else run())
