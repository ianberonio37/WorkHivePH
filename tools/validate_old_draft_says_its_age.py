#!/usr/bin/env python3
"""old-draft-says-its-age - T57: a leftover is not an interruption (2026-08-26).

whAutoSaveDraft is X2 interruption resilience: a worker's typed note survives a phone call, an app
switch, a dead battery. It is careful work - it refuses a draft belonging to another worker (the
shared-device leak), detects an untouched SELECT by its default rather than by emptiness (the
"Critical" urgency that silently reverted to "Normal"), and says where drafts live.

★BUT IT CARRIED NO AGE. A draft typed three months ago restored into the form exactly like one
typed three minutes ago: silently, into fields the worker is about to submit. On a logbook entry
that means filing a stale reading against today's shift, with nothing having said the text was old.
Interruption resilience is measured in minutes and hours; a draft that survives a WEEK has stopped
being an interruption and become a leftover.

★IT SAYS THE AGE RATHER THAN DISCARDING THE TEXT. The work is still the worker's to keep or clear,
and throwing a note away because it is old would be the opposite failure - X2 exists precisely so
typed work is never lost.

FOUR AGES ARE DRIVEN, because a notice that always fired would be noise and one that never fired
would be the bug: 0d and 6d restore silently, 8d and 90d restore and say how old they are.

★THE PROBE MUST SIGN IN. The owner check compares against wh_last_worker; unauthenticated, logbook
redirects to index and the owner reads null, so the draft is correctly refused and nothing restores
at all. An earlier run reported restored:false four times and looked like a broken fix.

Re-drive: node tools/prove_old_draft_says_its_age.mjs
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
        print("SKIP old-draft-says-its-age - node not on PATH (live gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP old-draft-says-its-age - local stack down")
        return 0

    def run():
        r = subprocess.run([node, str(ROOT / "tools" / "prove_old_draft_says_its_age.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=480,
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
        print("FAIL old-draft-says-its-age - timed out at 480s")
        return 1

    for line in out.strip().splitlines()[-3:]:
        print("  " + line.strip()[:170])
    if ok is None:
        print("SKIP old-draft-says-its-age - no active hive for the test account")
        return 0
    if not ok:
        print("FAIL old-draft-says-its-age - a months-old draft either failed to restore, or filled the")
        print("    form silently. Silence invites a stale entry against today's shift; refusing to")
        print("    restore throws away work X2 exists to protect. Keep the text and say its age.")
        return 1
    print("PASS old-draft-says-its-age - recent drafts restore quietly; a forgotten one restores and "
          "says how old it is.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
