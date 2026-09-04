#!/usr/bin/env python3
"""feedback-round-trip - T157: the feedback loop actually goes somewhere (2026-08-26).

"Email us with corrections" and a feedback button are TRUST CLAIMS. A widget that
thanks somebody and stores nothing is the worst version of this: the person
believes they were heard, nobody was told, and the silence reads as being ignored
rather than as a bug.

Measured from the public /about/ page ANONYMOUSLY - the hardest case, because an
anon insert must pass RLS with no session behind it. It does: platform_feedback
carries a `feedback anon submit` policy admitting inserts only as status 'new',
not public, with no admin_note - so a stranger can report a problem and cannot
forge a resolved one.

Six assertions, and the REFUSAL half is the point. A loop that works when every
field is filled is easy; the failure that costs trust is a submit that quietly
does nothing. So: a complete submission lands as status 'new'; an incomplete one
(no kind chosen) is refused BEFORE any network call, names what is missing in a
VISIBLE element, and does not clear what was typed.

*** TWO FALSE READINGS ON THE WAY, NEITHER BANKED. *** The first run clicked send
without choosing a kind, got no row, and could have been written up as "public
feedback never reaches the table" - it reached nothing because the widget
correctly refused and said so in an element the probe was not reading. The second
reused the panel from that refusal, and WHFeedback.open(prefill) deliberately
fills only EMPTY fields (it must never clobber typed text), so the row landed
under the OLD subject and the probe again read zero. The product was right both
times; the probe was reading the wrong element, then reusing dirty state.

Re-drive: node tools/prove_feedback_round_trip.mjs
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
        print("SKIP feedback-round-trip - node not on PATH (live gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)) or not shutil.which("docker"):
        print("SKIP feedback-round-trip - local stack / docker down")
        return 0

    def run():
        r = subprocess.run([node, str(ROOT / "tools" / "prove_feedback_round_trip.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=300,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        return bool(re.search(r"^\s*PASS", out, re.M)), out

    try:
        ok, out = run()
        if not ok:
            ok, out = run()
    except subprocess.TimeoutExpired:
        print("FAIL feedback-round-trip - timed out at 300s")
        return 1

    for line in out.strip().splitlines()[-5:]:
        print("  " + line.strip()[:160])
    if not ok:
        print("FAIL feedback-round-trip - a public submission did not reach platform_feedback, or an "
              "incomplete one was refused without saying why. A feedback button that stores nothing is "
              "worse than no button.")
        return 1
    print("PASS feedback-round-trip - a stranger's report lands as 'new', and an incomplete one is "
          "refused out loud with the draft kept.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
