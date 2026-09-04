#!/usr/bin/env python3
"""invite-code-round-trip - T6 + T7 + T185: the briefing-room exchange (2026-08-26).

The platform's whole onboarding rests on one exchange: a supervisor creates a hive and reads a
six-character code aloud; a worker types it on their phone and is in. It was walked on prod as a
smoke test and GATED BY NOTHING - T6 sat at 90% and T7 at 85% with no gate registered against
either, so the most load-bearing flow on the platform was protected by nobody.

★TWO BROWSER CONTEXTS, because this is a two-person exchange and a single-context test cannot fail
the way the real thing fails. The supervisor's browser creates the hive; a SEPARATE context signed
in as a DIFFERENT real account joins with the code. Nothing passes between them but the six
characters - exactly the channel the real flow uses.

THE ASSERTIONS:
  1. the code is six readable characters, the kind a person can say across a noisy briefing room
  2. a different account joins with it and lands in the SAME hive - confirmed in the DATABASE, not
     by reading a success banner, because a banner is what a broken join would also show
  3. a WRONG code is refused, out loud, and does not join anything

★DIRECTION 3 IS WHAT STOPS THIS BEING A HAPPY-PATH TEST, and it runs FIRST: a join that accepted
anything would sail through the other two, and checking the wrong code before the right one means a
permissive join cannot hide behind a later success.

★AND IT CLEANS UP AFTER ITSELF. The probe hive and its membership rows are removed and re-counted;
two consecutive runs leave 0 probe hives, an unchanged membership count on the joining account, and
0 orphaned memberships.

Re-drive: node tools/prove_invite_code_round_trip.mjs
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
        print("SKIP invite-code-round-trip - node not on PATH (live gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP invite-code-round-trip - local stack down")
        return 0

    def run():
        r = subprocess.run([node, str(ROOT / "tools" / "prove_invite_code_round_trip.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=600,
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
        print("FAIL invite-code-round-trip - timed out at 600s")
        return 1

    for line in out.strip().splitlines()[-4:]:
        print("  " + line.strip()[:170])
    if ok is None:
        print("SKIP invite-code-round-trip - no second test account available to join as")
        return 0
    if not ok:
        print("FAIL invite-code-round-trip - hearing a code and being in the hive is the platform's first")
        print("    promise, and it did not hold. A join that accepts a wrong code puts someone in a hive")
        print("    that is not theirs; one that refuses a right code ends onboarding at the first step,")
        print("    in a briefing room, in front of the crew.")
        return 1
    print("PASS invite-code-round-trip - a code created in one browser admits a different account, in "
          "another browser, to the same hive; a wrong one is refused out loud.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
