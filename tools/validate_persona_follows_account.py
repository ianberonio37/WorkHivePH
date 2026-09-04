#!/usr/bin/env python3
"""persona-follows-account - T85: the companion choice must cross devices (2026-08-26).

The persona lives in two places: localStorage (what every renderer and prompt-builder
reads) and worker_profiles.preferred_persona (the account-level choice). Only index.html
and voice-journal.html bridged them, each with its own copy of the query. assistant.html -
reachable directly, from the nav hub, a deep link, or simply a different browser - read
localStorage alone.

MEASURED: with the account set to hezekiah and localStorage empty, assistant.html resolved
ZANIAH. Not a wrong default - the worker's choice ignored, and silent, because the wrong
answer IS the default. Nothing errors and nothing looks broken; the companion is just not
the one they picked.

★AND THE COPY IT REPLACED CLOBBERED ON FAILURE. index's inline version destructured
`{ data: profile }` without checking the error, so a transient blip left profile null, fell
through to 'zaniah', and WROTE that to localStorage - permanently resetting a Hezekiah user
because one read failed. An absent or unreadable preference is not evidence of a preference.
Both now go through one helper, wh-persona.js hydratePersonaFromCloud(), which writes only
when the cloud actually names a choice.

The prover drives BOTH directions, since a one-way check would pass on a page that always
overwrites: the account's choice must REACH a fresh device, and a failed read must CHANGE
NOTHING. Teeth: against pre-fix HEAD direction one resolves 'zaniah' and the gate fails.

Re-drive: node tools/prove_persona_follows_the_account.mjs
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
        print("SKIP persona-follows-account - node not on PATH (live gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP persona-follows-account - local stack down")
        return 0

    def run():
        r = subprocess.run([node, str(ROOT / "tools" / "prove_persona_follows_the_account.mjs")],
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
        print("FAIL persona-follows-account - timed out at 420s")
        return 1

    for line in out.strip().splitlines()[-3:]:
        print("  " + line.strip()[:170])
    if ok is None:
        print("SKIP persona-follows-account - the probe could not set up its account fixture")
        return 0
    if not ok:
        print("FAIL persona-follows-account - the companion a worker picked did not follow them. Either")
        print("    the account's choice failed to reach a fresh device (their selection is ignored, and")
        print("    silently, since the wrong answer is the default), or a failed profile read overwrote a")
        print("    local choice - resetting them to the default because one request blipped.")
        return 1
    print("PASS persona-follows-account - the account's companion reaches a fresh device, and a failed "
          "profile read leaves the worker's choice alone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
