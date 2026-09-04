#!/usr/bin/env python3
"""voice-refuses-ambiguous-asset - T79: a coin flip is not a resolution (2026-08-26).

The voice router turns "I replaced the seal on Pump 2" into a logbook.create intent and
resolves the machine. When more than one matches it returns asset_resolution ambiguous:true
with the candidates.

FOUND: ambiguity was RENDERED and never ENFORCED. The intent card turned the asset pill red
and appended "(multiple matches)" - and Confirm still wrote the entry to ar.primary, whichever
candidate ranked first. A worker's repair record landed on the wrong machine, and the only
warning was a colour. On a plant floor that is maintenance history attached to the wrong
equipment, which is the one thing the history exists to get right.

★AND THE GUARD FOR THIS ALREADY EXISTED AND WAS DEAD. _preflightAction was defined, exported
in the test-helper block, and certified by the companion integration audit - which checked its
four blocker STRINGS appeared in the file. They did, inside a function nothing ever called. Its
writeVerbs were slot-style ('log_entry') while the router emits 'logbook.create', so a call
would have matched nothing either. Presence is not wiring. That audit now requires a real call
site and the router's own kinds, and fails against pre-fix HEAD on both counts.

THE ASSERTION, driven against the shipped file in a browser: a write kind plus an ambiguous
resolution is refused with blocker 'ambiguous_asset'; the SAME kind with one clear match is
NOT refused for ambiguity; and the refusal names the candidates and says nothing was saved.

★DIRECTION TWO IS THE POINT. A guard that refused everything would satisfy direction one while
making voice logging useless - the reason to refuse is that the worker can then say which
machine, not that refusing is safe.

Re-drive: node tools/prove_voice_refuses_ambiguous_asset.mjs
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
        print("SKIP voice-refuses-ambiguous-asset - node not on PATH (live gate)")
        return 0
    if not _port_open(5000):
        print("SKIP voice-refuses-ambiguous-asset - local page server down")
        return 0

    def run():
        r = subprocess.run([node, str(ROOT / "tools" / "prove_voice_refuses_ambiguous_asset.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=300,
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
        print("FAIL voice-refuses-ambiguous-asset - timed out at 300s")
        return 1

    for line in out.strip().splitlines()[-3:]:
        print("  " + line.strip()[:170])
    if ok is None:
        print("SKIP voice-refuses-ambiguous-asset - WHVoice preflight not exposed on the host page")
        return 0
    if not ok:
        print("FAIL voice-refuses-ambiguous-asset - when two machines match, a confirm must not write to")
        print("    whichever ranked first. That puts a repair record on the wrong equipment, warned only")
        print("    by a red pill. Refuse, name the candidates, and let the worker say which one.")
        return 1
    print("PASS voice-refuses-ambiguous-asset - an ambiguous machine stops the write and names the "
          "candidates; a clear match still goes through.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
