#!/usr/bin/env python3
"""watchlist-says-what-it-does - T95: a bookmark must not imply a subscription.

Tapping a star on a listing looks like "tell me when this changes". On this platform it is a
BOOKMARK: nothing consumes marketplace_watchlist to send price or stock alerts. A buyer who believes
otherwise stops checking the listing and misses the change they were watching for - the feature does
harm precisely by seeming to work.

★THE PLATFORM ALREADY HANDLES THIS THE RIGHT WAY, which is why the gate is a PARITY check rather
than a defect report: marketplace.html says outright "WorkHive doesn't send watchlist alerts yet."
Stating an absence plainly is the honest answer to a capability you have not built.

★AND IT IS ASSERTED IN BOTH DIRECTIONS, which most claim-checks are not:
  1. while nothing consumes the watchlist, the DISCLOSURE must be present - deleting the sentence
     silently restores the implied promise;
  2. once something DOES consume it, the disclosure must go - a stale "doesn't send alerts yet"
     under a feature that now sends them is the same defect pointing the other way, and it teaches
     users to ignore the one place the product tells them the truth.
A claim and a capability drift apart in either direction; a gate that only watches one of them is
half a gate.

Re-drive: python tools/validate_watchlist_says_what_it_does.py
"""
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DISCLOSURE = re.compile(r"do(?:es)?n['’]?t send watchlist alerts|no watchlist alerts", re.I)


def main() -> int:
    page = ROOT / "marketplace.html"
    if not page.exists():
        print("SKIP watchlist-says-what-it-does - marketplace.html not found")
        return 0
    src = io.open(page, encoding="utf-8", errors="replace").read()
    has_disclosure = bool(DISCLOSURE.search(src))

    # Does anything actually CONSUME the watchlist to notify? Edge functions and crons are where a
    # subscription would live; a page reading its own list to render stars is not a consumer.
    consumers = []
    fns = ROOT / "supabase" / "functions"
    if fns.exists():
        for f in fns.rglob("*.ts"):
            body = io.open(f, encoding="utf-8", errors="replace").read()
            if "marketplace_watchlist" in body:
                consumers.append(f"supabase/functions/{f.relative_to(fns)}")

    failures = []
    if not consumers and not has_disclosure:
        failures.append("nothing consumes marketplace_watchlist for alerts, and the page no longer "
                        "says so - a star that looks like 'tell me when this changes' and tells "
                        "nobody anything. The buyer stops checking and misses the change they were "
                        "watching for")
    if consumers and has_disclosure:
        failures.append(f"the page still says watchlist alerts are not sent, but {len(consumers)} "
                        f"function(s) now consume the watchlist ({', '.join(consumers)}) - a stale "
                        f"disclaimer under a working feature teaches people to ignore the one place "
                        f"the product tells them the truth")

    if failures:
        print("FAIL watchlist-says-what-it-does:")
        for f in failures:
            print("    - " + f)
        return 1

    state = (f"{len(consumers)} consumer(s), disclosure removed" if consumers
             else "no consumer, disclosure present")
    print(f"  watchlist: {state}")
    print("PASS watchlist-says-what-it-does - what the star promises and what the platform does are "
          "the same thing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
