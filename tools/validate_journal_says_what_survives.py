#!/usr/bin/env python3
"""journal-says-what-survives - T77/T164: the most private surface must say what you can take back.

A worker speaks or types something personal into the voice journal. Two facts govern whether they
should, and neither is guessable:

  1. THE NOTE IS PERMANENT. ai-gateway persists the row inside the same call that generates the
     reply, so it exists before the worker has seen anything, and renderHistory's only per-entry
     action is "Speak again" - there is no edit and no per-note delete.
  2. THERE IS SOMEWHERE TO GO. The privacy policy's Data Rights Request route is the documented way
     to have personal data erased, and validate_erasure_path_intact proves the database honours it.

★THE IN-APP ERASURE IS VOICE-ONLY AND IS DELIBERATELY NOT ADVERTISED AS THE REMEDY. voice-handler's
_isErasureRequest does detect "delete my voice history", but it is reached from _onStopRecording
alone - only after a voice recording. This page's own typed fallback exists, in its words, for "a
loud plant floor, a denied mic, or a worker who cannot speak", and those are exactly the people it
would not serve. Pointing them at a spoken phrase would be offering a remedy that excludes the
person most likely to need it.

★THE FIRST ATTEMPT AT THIS FIX WAS DUPLICATION, which is why the gate checks ONE disclosure rather
than the presence of some text: the permanence was ALREADY stated on the primary surface, and a new
paragraph restating it inside a collapsed <details> would have been a second home for information
that already had one. The fix was a single clause completing the existing sentence.

Re-drive: python tools/validate_journal_says_what_survives.py
"""
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    failures = []
    src = io.open(ROOT / "voice-journal.html", encoding="utf-8", errors="replace").read()

    # 1. the permanence is stated
    if not re.search(r"cannot be edited or removed here afterwards", src):
        failures.append("the write surface no longer says a note cannot be edited or removed - the "
                        "row is persisted by ai-gateway inside the same call that writes the reply, "
                        "so a worker who assumes they can take it back is wrong at the moment it "
                        "matters most")
    if not re.search(r"saved as soon as the assistant replies", src):
        failures.append("the write surface no longer says WHEN the note is saved - there is no "
                        "separate save step, and a worker who expects one has already committed")

    # 2. and there is somewhere to go
    if not re.search(r"Data Rights Request", src, re.I):
        failures.append("the surface states the permanence but names no route to erasure - telling "
                        "someone their note is permanent and nothing else leaves them with a dead end "
                        "on the page most likely to hold something personal")
    if not re.search(r"admin@workhiveph\.com", src):
        failures.append("the erasure route names no address, so it is not walkable")

    # 3. ONE disclosure, not two. The permanence sentence must not be duplicated elsewhere.
    hits = len(re.findall(r"cannot be edited or removed", src))
    if hits > 1:
        failures.append(f"the permanence is stated {hits} times - a second copy is duplication, not "
                        f"disclosure, and the redundant one lands in a collapsed panel nobody opens")

    # 4. the voice phrase must NOT be offered as the general remedy: it is unreachable by typing
    if re.search(r"delete my voice history", src, re.I):
        failures.append("the page advertises the spoken erasure phrase. It is reached only from "
                        "_onStopRecording, so it excludes the worker with a denied mic or no voice - "
                        "precisely who the typed fallback exists for")

    if failures:
        print("FAIL journal-says-what-survives:")
        for f in failures:
            print("    - " + f)
        return 1

    print("  permanence stated once, on the primary surface, with the documented erasure route")
    print("PASS journal-says-what-survives - a worker is told the note is permanent and where to go "
          "to have their data erased.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
