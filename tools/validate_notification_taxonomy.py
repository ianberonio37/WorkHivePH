#!/usr/bin/env python3
"""notification-taxonomy — T107's "for me" is ONE honest concept (2026-08-26).

THE FINDING THIS LOCKS. The hive board's bell held four entries on the live
board — "PM Due Soon", "Assets With PM Overdue", "Open work orders", "Low
stock" — every one a PLANT CONDITION already painted as a tile on the same
page and again in alert-hub, blended in with the approval entries, which are
the only ones actually about the person reading them. One bell, two concepts,
no way to tell which you were looking at. And the only unread signal was a 3%
white tint on a dark surface: present in code, invisible in use.

WHAT THIS ASSERTS (structure, not prose — a lint that guesses at wording
produces false reds):

  1. TWO LANES NAMED. The tray splits its entries by a for-you predicate and
     prints a heading for each lane. A future producer that adds a fifth
     plant condition lands in the plant lane by default; one that adds a
     personal event must be added to the predicate to reach "Waiting on you"
     — which is exactly the decision this gate wants a human to make.
  2. THE PLANT LANE POINTS HOME. It names where the same conditions live
     (alert-hub), so the summary is a summary rather than a rival surface.
  3. UNREAD IS PERCEIVABLE. The unread branch must carry more than a
     background tint — a border or a dot — AND a screen-reader word, because
     an unread marker that only sighted users can find is half a marker (and
     one only readers can find is the aria-label-only class inverted).
  4. EVERY PRODUCER IS CLASSIFIED. Each pushNotif type string must be known
     to the predicate or to the plant set. A type that is in neither is an
     unclassified event: it would render, silently, in whichever lane the
     predicate's default sends it.

★NOT ASSERTED: how many notifications there are, or their wording. The count
is live data and the wording is judgement; what must not regress is that the
bell distinguishes work waiting on a person from a restatement of the board.

Usage: python tools/validate_notification_taxonomy.py
"""
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "hive.html"

# The personal lane's members, as the page defines them. Kept here so a change to
# either side has to face the other.
FOR_YOU = {"approval", "approval-in"}
PLANT = {"stock-out", "stock-low", "open-wo", "pm-overdue", "pm-duesoon"}


def main() -> int:
    src = io.open(PAGE, encoding="utf-8", errors="replace").read()
    fails = []

    # 1 — two lanes, each with a heading
    has_pred = re.search(r"_isForYou\s*=\s*t\s*=>", src) is not None
    lanes = re.search(r"forYou\s*=\s*ordered\.filter", src) and re.search(r"plant\s*=\s*ordered\.filter", src)
    heads = src.count("head('Waiting on you'") >= 1 and src.count("head('Plant conditions'") >= 1
    if not (has_pred and lanes and heads):
        fails.append(
            f"the tray no longer names two lanes (predicate={bool(has_pred)} split={bool(lanes)} headings={heads})"
        )

    # 2 — the plant lane points at the surface that owns these conditions
    if not re.search(r"notif-list[\s\S]{0,80}|alert-hub\.html", src) or "Open the alert hub" not in src:
        fails.append("the plant lane no longer links to alert-hub, so it reads as a rival surface")

    # 3 — unread is perceivable to BOTH audiences
    unread_block = re.search(r"const isUnread[\s\S]{0,1200}", src)
    ub = unread_block.group(0) if unread_block else ""
    visible = ("border-left:3px solid var(--wh-orange)" in ub) or ("border-radius:50%" in ub and "isUnread" in ub)
    spoken = "(unread)" in ub
    if not (visible and spoken):
        fails.append(f"unread lost a marker (visible={visible} announced={spoken}) — a 3% tint alone is invisible")

    # 4 — every producer classified
    produced = set(re.findall(r"pushNotif\(\s*'([a-z\-]+)'", src))
    unknown = sorted(produced - FOR_YOU - PLANT)
    if unknown:
        fails.append(
            "unclassified notification type(s) " + ", ".join(unknown)
            + " — add each to FOR_YOU or PLANT here and to _isForYou in hive.html, deliberately"
        )

    print(f"  producers: {len(produced)} types ({', '.join(sorted(produced))})")
    if fails:
        print("FAIL notification-taxonomy:")
        for f in fails:
            print("    - " + f)
        return 1
    print("PASS notification-taxonomy — two lanes named, plant lane points home, unread seen and spoken, "
          f"{len(produced)} producers all classified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
