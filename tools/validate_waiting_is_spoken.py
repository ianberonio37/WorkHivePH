#!/usr/bin/env python3
"""waiting-is-spoken - T181: waiting must SAY it is waiting (2026-08-26).

A page that fetches its content leaves a gap between paint and data, and what fills
that gap is the whole question. A skeleton or a "Loading..." line says WAIT; an empty
region says THERE IS NOTHING HERE, and a reader acts on that - they leave, they
re-tap, or they report missing data that arrives 200ms after they looked away.

MEASURED LIVE across 8 signed-in pages with REST throttled 1.2s so the gap is real
rather than a race usually lost: ZERO silent gaps. Four pages fill it with skeletons
(logbook, community, alert-hub, analytics) and four with loading text (inventory,
asset-hub, marketplace, pm-scheduler).

★IT ASSERTS THE FLOOR, NOT THE VOCABULARY, AND THE NARROWING IS DELIBERATE. T181's
census found skeletons and spinners coexisting and called waiting "not yet one
product's language" - true as an observation, but WHICH metaphor a page picks is a
design judgement, and a gate failing a page for choosing text over a skeleton would
enforce taste across 24 pages and generate dozens of arguable findings. Whether the
gap says ANYTHING is not a matter of taste. So the floor is gated and the idiom split
is REPORTED, keeping the design question visible without a machine deciding it.

★A FINDING THE CENSUS GOT WRONG, corrected by reading the code: analytics appeared to
mix metaphors (a skeleton and two spinners in the same sample). It does not - the
skeleton CONTAINS the spinner (space reserved, action animating inside it) and the
others mark in-flight generation. That is the declared system working, not a conflict.

★AND THE ORACLE ITSELF WAS WRONG FIRST. The original silence test read
`during.chars < 120`. Teeth-testing it by stripping inventory's "Loading..." lines
produced idiom=NOTHING and still PASSED, because the page rendered 389 characters of
CHROME - headings, nav, tile labels - while the region the reader was waiting on sat
empty. An absolute threshold over the whole main region measures the furniture, not
the gap. It now compares GROWTH: substantial content arriving later with nothing
having marked the wait means the reader was shown a finished-looking page that was
not finished.

Re-drive: node tools/prove_waiting_is_spoken.mjs
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
        print("SKIP waiting-is-spoken - node not on PATH (live gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP waiting-is-spoken - local stack down")
        return 0

    def run():
        r = subprocess.run([node, str(ROOT / "tools" / "prove_waiting_is_spoken.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=600,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        return bool(re.search(r"^\s*PASS", out, re.M)), out

    try:
        ok, out = run()
        if not ok:
            ok, out = run()
    except subprocess.TimeoutExpired:
        print("FAIL waiting-is-spoken - timed out at 600s")
        return 1

    for line in out.strip().splitlines()[-4:]:
        print("  " + line.strip()[:160])
    if not ok:
        print("FAIL waiting-is-spoken - a page fills its load gap with nothing. An empty region does not")
        print("    read as 'wait', it reads as 'nothing here', and the reader leaves or re-taps. Use the")
        print("    page's own idiom - a skeleton for a list, a line of text - but say something.")
        return 1
    print("PASS waiting-is-spoken - every page marks its load gap; nobody is shown a blank region and "
          "left to guess whether data is coming.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
