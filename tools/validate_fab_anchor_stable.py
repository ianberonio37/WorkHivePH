#!/usr/bin/env python3
"""fab-anchor-stable - T184: the one control that must never move (2026-08-26).

The nav-hub FAB is on every page in the same corner, and it is the platform's single
piece of muscle memory: a worker's thumb goes there without looking. Every other
inconsistency between 24 pages costs a moment of thought; this one costs a MISSED TAP,
repeatedly, on the control whose whole job is getting you out of wherever you are.

MEASURED AT 390: x = 303, 312 and 318 across eight pages - a 15px spread - while every
page carried an identical `#wh-hub { right: 16px }` and an identical 56px FAB.

★THREE HYPOTHESES WERE WRONG BEFORE THE MEASUREMENT SETTLED IT, and that is the part
worth keeping: "a scrollbar is narrowing the viewport" (refuted - innerWidth minus
clientWidth was 0 on every page), "an ancestor transform is creating a containing
block" (refuted - the hub is a child of BODY everywhere, no ancestor carried
transform/filter/contain/will-change), "inventory sets scrollbar-width: thin" (refuted
- no such declaration). What settled it was a virgin `fixed; right:0; width:0` probe
reporting where the containing block's right edge ACTUALLY sits: 375 on community, 384
on inventory, 390 on logbook - while documentElement.clientWidth read 390 on all
three, which is precisely why nothing in the DOM revealed it.

THE CAUSE: a fixed right-anchored element is measured from the SCROLLPORT, and the
reserved gutter narrows it whether or not a bar is drawn. The spread was the
CROSS-PRODUCT of two unrelated per-page decisions - `html { scrollbar-gutter: stable }`
(components.css:231, linked by some pages) and `::-webkit-scrollbar { width: 6px }`
(declared inline by others). Reserve 15px -> 303, 6px -> 312, nothing -> 318.

THE FIX belongs at the altitude that owns the stack: nav-hub.js now injects both
halves on every page, beside the reserve and lift rules already there for exactly this
reason ("this is one shared bar, so it takes one shared reserve"). Both halves are
required together - the gutter alone still leaves 303-vs-312, because the gutter's
width IS the scrollbar's width. Spread is now 0 across all eight pages.

★y IS DELIBERATELY NOT REQUIRED TO MATCH. The stack is lifted by --wh-fab-lift on pages
with a fixed bottom element (pm-scheduler rides 65px higher). That is collision
avoidance, not drift, and forcing it down would put the hub on top of that page's own
bottom bar - so the gate asserts x and REPORTS y with its lift.

Also asserts zero pageerrors, because the rule now ships from a file on all 24 pages:
a regression here can be a script that stopped running, not just a rule that changed.

Re-drive: node tools/prove_fab_anchor_stable.mjs
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
        print("SKIP fab-anchor-stable - node not on PATH (live gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP fab-anchor-stable - local stack down")
        return 0

    def run():
        r = subprocess.run([node, str(ROOT / "tools" / "prove_fab_anchor_stable.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=420,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        return bool(re.search(r"^\s*PASS", out, re.M)), out

    try:
        ok, out = run()
        if not ok:
            ok, out = run()
    except subprocess.TimeoutExpired:
        print("FAIL fab-anchor-stable - timed out at 420s")
        return 1

    for line in out.strip().splitlines()[-4:]:
        print("  " + line.strip()[:160])
    if not ok:
        print("FAIL fab-anchor-stable - the hub FAB does not land in the same column on every page. It is")
        print("    the platform's one piece of muscle memory; a page that moves it costs a missed tap.")
        print("    Check the reserved scrollbar gutter, not the hub's own CSS - both halves of the rule")
        print("    (scrollbar-gutter AND scrollbar width) must be identical platform-wide.")
        return 1
    print("PASS fab-anchor-stable - the hub FAB lands in one column on every page, and the only page "
          "that sits higher is the one deliberately clearing its own bottom bar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
