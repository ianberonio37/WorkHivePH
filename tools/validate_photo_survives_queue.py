#!/usr/bin/env python3
"""photo-survives-queue gate - T14's last probe (2026-08-27).

Runs tools/prove_photo_survives_queue.mjs. The dead-zone entry a worker most wants to keep is the
one with the picture on it - the cracked bearing, the leak, the burnt contactor. logbook puts that
photo in the row's `photo` column and, offline, the whole row goes into IndexedDB. This asks whether
the PICTURE comes back intact after the phone has been pocketed and the app closed.

SCOPE, STATED. It does not re-drive the save form; prove_offline_queued.mjs's logbook-entry case
already covers form -> queue (including that the save is a form SUBMIT, not a click on a zero-width
button). What was never covered is photo FIDELITY across storage and a restart. The photo half is
driven for real - a genuine PNG goes to the page's own #f-photo input and the page's own pipeline
(FileReader -> Image -> canvas -> toDataURL, plus its 700KB re-encode guard) makes the data URL.

Four assertions: PRODUCED (a real file becomes a compressed JPEG data URL), QUEUED (offline, into
wh_logbook_offline, zero server traffic), SURVIVES (byte-identical after a full document restart),
STILL AN IMAGE (the survivor decodes to a real bitmap).

Writes NOTHING to the database: the row never leaves the queue, so no PM mirror, XP ledger or
embedding is disturbed and there is nothing to clean up server-side. The queue entry is removed and
the removal verified.

Teeth: `--teeth` stores a photo of exactly the SAME LENGTH with one character changed. SURVIVES goes
false while both lengths still read 36783 - the only way to show the comparison is byte-wise rather
than the "roughly the right size" check that lets a corrupted image through. Worth noting what that
run also shows: STILL AN IMAGE stays TRUE for the corrupted photo, because a one-character JPEG
corruption still decodes. Either assertion alone would have passed it.

Discipline (carried from validate_queue_drain.py):
  - retry-once before failing (full-suite live gates flake under load).
  - node invoked DIRECTLY, never npx (the repo path contains an ampersand).
  - utf-8 pinned on the subprocess decode; PASS matched line-anchored.
  - SKIPs cleanly when node / the local stack is absent.

Re-drive: node tools/prove_photo_survives_queue.mjs
"""
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _run(node: str) -> tuple[bool, str]:
    r = subprocess.run(
        [node, str(ROOT / "tools" / "prove_photo_survives_queue.mjs")],
        cwd=str(ROOT), capture_output=True, text=True, timeout=300,
        encoding="utf-8", errors="replace",
    )
    out = (r.stdout or "") + (r.stderr or "")
    passed = bool(re.search(r"^\s*PASS", out, re.M))
    tail = out.strip().splitlines()[-3:] if out.strip() else ["<no output>"]
    return passed, " | ".join(line.strip() for line in tail)


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("SKIP photo-survives-queue — node not on PATH (live browser gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP photo-survives-queue — local stack down (Flask :5000 / Supabase :54321)")
        return 0

    try:
        ok, tail = _run(node)
        if not ok:
            ok, tail = _run(node)
    except subprocess.TimeoutExpired:
        print("FAIL photo-survives-queue — timed out at 300s")
        return 1

    print(f"  {'PASS' if ok else 'FAIL'}  {tail[:240]}")
    if not ok:
        print("FAIL photo-survives-queue — the attached photo did not survive the queue and restart "
              "intact, or it no longer decodes as an image.")
        return 1
    print("PASS photo-survives-queue — the page compressed a real photo, held it offline, and it came "
          "back byte-identical and still an image after a restart.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
