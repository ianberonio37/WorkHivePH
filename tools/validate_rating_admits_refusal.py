#!/usr/bin/env python3
"""rating-admits-refusal - T88: a rating that was refused must not look accepted (2026-08-26).

Every companion reply carries thumbs up/down. The tap used to lock both buttons and paint the
chosen one green or red IMMEDIATELY, then fire the insert and discard whatever came back.

★AND THE MOST LIKELY FAILURE DOES NOT THROW. supabase-js returns { error } on an RLS refusal
rather than raising, so the try/catch around that insert never fired for it - the code's own
comment records that anon callers "silently skip". A worker tapped thumbs-down, watched it turn
red, and nothing was stored. That is worse than having no thumbs at all: it teaches them their
feedback is read when it is not, on the surface whose entire purpose is to collect it.

MEASURED: with the insert answered 403 the way a real RLS denial answers, _recordReplyRating
returned undefined and the UI had already committed. It now returns false, the buttons come back,
and the worker is told to tap again; on success it returns true and only then does the button
take its accepted colour.

★BOTH DIRECTIONS, because a function that always reported failure would satisfy the first half
while silently discarding every real rating: refused -> false, allowed -> true, with the row
counted in the database.

★NOT A COSMETIC FIX. What is being protected is the honesty of a signal the owner acts on -
ai-quality aggregates these thumbs, and 3+ negatives in 7 days flags ai_quality_escalation for
supervisor outreach. Silently dropped ratings quietly bias all of it.

Probe rows are marked WH-T88-PROBE and deleted, with a re-count proving cleanup.

Re-drive: node tools/prove_rating_admits_refusal.mjs
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
        print("SKIP rating-admits-refusal - node not on PATH (live gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP rating-admits-refusal - local stack down")
        return 0

    def run():
        r = subprocess.run([node, str(ROOT / "tools" / "prove_rating_admits_refusal.mjs")],
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
        print("FAIL rating-admits-refusal - timed out at 420s")
        return 1

    for line in out.strip().splitlines()[-3:]:
        print("  " + line.strip()[:170])
    if ok is None:
        print("SKIP rating-admits-refusal - the probe could not resolve its hive fixture")
        return 0
    if not ok:
        print("FAIL rating-admits-refusal - a refused rating reported success, so the button paints as")
        print("    accepted and the worker's answer is dropped. supabase returns { error } on an RLS")
        print("    denial - it does not throw - so a try/catch alone never sees the likeliest failure.")
        return 1
    print("PASS rating-admits-refusal - a refused rating is reported and the buttons come back; a real "
          "one still lands.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
