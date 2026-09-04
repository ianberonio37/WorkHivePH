#!/usr/bin/env python3
"""public-feed-dated - T158: the public window does not pretend to be fresh (2026-08-26).

public-feed is the shop window: an anon visitor's first sight of whether anyone is
actually here. A community feed's worst failure is not being QUIET - it is being
quiet while LOOKING live, because a reader who cannot date what they are reading
assumes it is current.

MEASURED 2026-08-26: 15 public posts, newest 42 DAYS old, ZERO published publicly
in the last 30 days; 111 posts exist and 14% are public. On a seeded fixture those
numbers say nothing about the product - but they are exactly the state in which a
feed either tells the truth or flatters itself. This one tells the truth: every
card carries its date ("Jul 16, 2026"), so a reader judges for themselves.

THE ASSERTION: every rendered card shows a date. NOT "the feed is fresh" - freshness
is a community outcome no gate can honestly demand - but that the page never hides
HOW fresh it is.

*** WHY GATE SOMETHING THAT ALREADY PASSES. *** The timestamp is the smallest and
most droppable element on a card. A redesign that tightens the layout and loses it
costs nothing visible, and quietly converts an honest quiet feed into one that
looks live - the single change that would turn this surface from truthful to
misleading. TEETH PROVEN by replacing the date span with a literal: 15/15 cards
undated, exit 1.

Re-drive: node tools/prove_public_feed_dated.mjs
"""
import io
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("SKIP public-feed-dated - node not on PATH (live gate)")
        return 0
    if not _port_open(5000):
        print("SKIP public-feed-dated - seeder down")
        return 0

    def run():
        r = subprocess.run([node, str(ROOT / "tools" / "prove_public_feed_dated.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=180,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        return bool(re.search(r"^\s*PASS", out, re.M)), out

    try:
        ok, out = run()
        if not ok:
            ok, out = run()
    except subprocess.TimeoutExpired:
        print("FAIL public-feed-dated - timed out at 180s")
        return 1

    for line in out.strip().splitlines()[-4:]:
        print("  " + line.strip()[:160])
    if not ok:
        print("FAIL public-feed-dated - a public post rendered with no date. A quiet feed that hides its "
              "age reads as a live one; the timestamp is what keeps it honest.")
        return 1
    print("PASS public-feed-dated - every public post carries its date, so a visitor can judge the "
          "community's freshness for themselves.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
