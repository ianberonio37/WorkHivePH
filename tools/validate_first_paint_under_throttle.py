#!/usr/bin/env python3
"""first-paint-throttled - T37: something must be on screen fast (2026-08-26).

Plant wifi at its worst is the condition this platform is actually used in, and the
first second decides whether a worker believes the app is working at all. PP1's bar is
that SOMETHING paints quickly - chrome, a heading, a skeleton - rather than a white
screen while data is fetched.

It measures FIRST CONTENTFUL PAINT, not settle time, and the distinction is the point:
a page that takes 6s to fill with data but paints its frame in 400ms feels alive, while
one that paints nothing for 2s feels broken even if it finishes sooner. The companion
gate (waiting-is-spoken) proves the GAP is filled with something honest; this proves the
gap starts quickly. REST is throttled 1.5s so the measurement is about the SHELL - a
page whose first paint waits on data is exactly the failure being looked for.

MEASURED 2026-08-26: all 8 core signed-in pages paint in 208-456ms against a 1800ms
budget.

★AND THE FIRST VERSION OF THIS PROVER MANUFACTURED A FINDING. Reusing one browser
context and walking the pages in sequence, analytics.html - the SIXTH in the run -
reported 2220ms against 212-292ms for everything else. It looked exactly like a page
whose paint waits on a slow read, and 2220 is suspiciously close to the 1500ms injected
delay plus overhead. Measured ALONE it paints in 400ms unthrottled and 368ms THROTTLED.
The 2220ms was contention from the five pages before it, still holding delayed routes
and competing for one renderer: the number described the HARNESS, not the page.

So the prover now closes each page before opening the next, and - the part that matters -
RE-MEASURES anything over budget in a fresh context before reporting it. Only a page
still slow BY ITSELF is a finding. A performance gate without that step will eventually
accuse a healthy page, and the accusation is expensive because someone then goes looking
for a cause that is not there.

Re-drive: node tools/prove_first_paint_under_throttle.mjs
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
        print("SKIP first-paint-throttled - node not on PATH (live gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP first-paint-throttled - local stack down")
        return 0

    def run():
        r = subprocess.run([node, str(ROOT / "tools" / "prove_first_paint_under_throttle.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=900,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        return bool(re.search(r"^\s*PASS", out, re.M)), out

    try:
        ok, out = run()
        if not ok:
            ok, out = run()          # a timing gate gets a second look before it accuses
    except subprocess.TimeoutExpired:
        print("FAIL first-paint-throttled - timed out at 900s")
        return 1

    for line in out.strip().splitlines()[-4:]:
        print("  " + line.strip()[:160])
    if not ok:
        print("FAIL first-paint-throttled - a page shows a white screen past the budget while its data")
        print("    loads, and it stayed slow when re-measured alone. Paint the shell first and let the")
        print("    data arrive into it - every other page here paints in about a quarter of a second.")
        return 1
    print("PASS first-paint-throttled - every core page paints its shell fast with reads throttled, so "
          "a slow connection never shows a blank screen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
