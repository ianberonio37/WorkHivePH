#!/usr/bin/env python3
"""freshness-stamp-tracks-content - T39: a stamp is a claim about what is under it (2026-08-26).

alert-hub's AMC card serves the stored 6am brief instantly and then calls analytics-orchestrator as
a background UPGRADE. renderAmcCard stamps the meta line "stored brief, generated <time>", which is
exactly right while the stored copy is what is showing.

★THE UPGRADE REPLACED THE SUMMARY AND LEFT THE STAMP. On success the pane held a freshly composed
action brief under a line saying it came from this morning's stored row. Not a stale number - a
stale CLAIM ABOUT a number, which is harder to catch because everything on screen looks internally
consistent, and it lands on a supervisor deciding what to do with their shift.

★THE FAILURE PATH WAS ALREADY HONEST and is deliberately untouched: it keeps the stored summary AND
the stored stamp, which agree - the silent keep is the right behaviour for a background upgrade,
since the reader still has a brief. Only the success path needed saying.

BOTH DIRECTIONS, because a fix that stamped "live" unconditionally would satisfy the first while
making the second one lie: upgrade succeeds -> says refreshed live and no longer says stored;
upgrade 429s -> still says stored brief with its generation time.

Also recorded while censusing this class: 11 of 12 AI-invoking surfaces already distinguish a quota
refusal from a network failure. This was the twelfth, and its answer turned out to be a stamp
rather than a message.

Re-drive: node tools/prove_freshness_stamp_tracks_content.mjs
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
        print("SKIP freshness-stamp-tracks-content - node not on PATH (live gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP freshness-stamp-tracks-content - local stack down")
        return 0

    def run():
        r = subprocess.run([node, str(ROOT / "tools" / "prove_freshness_stamp_tracks_content.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=420,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        if re.search(r"^\s*SKIP", out, re.M):
            return None, out
        return bool(re.search(r"^\s*PASS", out, re.M)), out

    try:
        ok, out = run()
        if ok is False:
            ok, out = run()
    except subprocess.TimeoutExpired:
        print("FAIL freshness-stamp-tracks-content - timed out at 420s")
        return 1

    for line in out.strip().splitlines()[-3:]:
        print("  " + line.strip()[:170])
    if ok is None:
        print("SKIP freshness-stamp-tracks-content - no brief for today, so there is no stamp to track")
        return 0
    if not ok:
        print("FAIL freshness-stamp-tracks-content - the freshness stamp does not match what it labels.")
        print("    Leaving \"stored brief\" over a live compose, or stamping \"live\" over the stored one,")
        print("    makes the label the lie - and a label is what a supervisor trusts when the content")
        print("    itself looks perfectly reasonable either way.")
        return 1
    print("PASS freshness-stamp-tracks-content - a live-upgraded brief says live; a refused upgrade still "
          "says stored.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
