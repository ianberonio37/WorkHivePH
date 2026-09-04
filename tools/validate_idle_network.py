#!/usr/bin/env python3
"""idle-network — T118: what a page costs while nobody is touching it (2026-08-26).

A worker at 8% battery at the end of a shift and a tablet left running on a
workshop wall are the same measurement: what does this page do when left alone?
index had been measured once; the rest of the roster never had, and a polling
loop is exactly the cost nobody notices while developing on mains power.

MEASURED: eight pages, 8s to settle then 75s of watching with no interaction.
Seven are completely silent. alert-hub makes ~11 requests per 75s — its
setInterval(loadAll, 60000), which is correct for a board somebody is watching
and adds up to roughly 500 requests an hour if left on a wall.

★THE WINDOW MUST OUTLAST THE SLOWEST POLL, or a zero means nothing. The first run
watched for 45 SECONDS and reported ZERO on all eight pages — including
alert-hub, whose poll is 60s and simply never fired inside the window. The
cleanest-looking result in the sweep was the busiest page. The window is now 75s,
longer than every interval in the served roster.

★AND THE PAUSE IS PROVEN, NOT TRUSTED. What makes a 60s foreground poll
defensible rather than a battery leak is that it STOPS when nobody is looking,
and alert-hub does wire visibilitychange to stopRefresh. A poll that kept running
in a backgrounded tab would be invisible to every foreground measurement, so the
probe hides the tab and asserts the requests stop.

★WHAT THIS CANNOT SEE, said plainly so a zero is not misread: WEBSOCKETS. Supabase
realtime holds a socket open and its frames are not HTTP requests. A zero here
means "no polling", never "no activity" — and an already-open socket is genuinely
cheaper than repeated polling, so this is a scope note, not a gap to close by
inflating the number.

Forward-only per page.

Re-drive: node tools/prove_idle_network.mjs
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
        print("SKIP idle-network — node not on PATH (live gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP idle-network — local stack down (Flask :5000 / Supabase :54321)")
        return 0

    try:
        r = subprocess.run([node, str(ROOT / "tools" / "prove_idle_network.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=1500,
                           encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        print("FAIL idle-network — timed out at 1500s")
        return 1

    out = (r.stdout or "") + (r.stderr or "")
    for line in out.strip().splitlines()[-14:]:
        print("  " + line.strip()[:150])

    if not re.search(r"^\s*(PASS|BASELINE)", out, re.M) or re.search(r"^\s*FAIL", out, re.M):
        print("FAIL idle-network — a page got busier at rest, or a poll kept running in a hidden tab. "
              "Every request a page makes while nobody is looking is battery spent on nothing.")
        return 1
    print("PASS idle-network — no page got busier at rest, and the one page that polls stops when the "
          "tab is hidden.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
