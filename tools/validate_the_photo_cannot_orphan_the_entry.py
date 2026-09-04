#!/usr/bin/env python3
"""A repair entry and its photo must land together or not at all (T9).

The logbook is the platform's core write: a worker on a plant floor, one-handed, recording what
they just fixed. Attaching a photo is where that write usually goes wrong on other systems, because
a photo normally means a SECOND write - upload the file, then insert the row referencing it - and
two writes have two ways to half-succeed:

  * the photo uploads and the entry fails  -> an orphaned file nobody can find
  * the entry saves and the photo fails    -> a record that claims evidence it does not have

★NEITHER IS REACHABLE HERE, AND THAT IS A DESIGN PROPERTY WORTH PINNING DOWN. logbook.html contains
NO storage.from(...).upload() at all. The photo is compressed client-side and carried INLINE as a
data URL in logbook.photo (a text column), inside the SAME insert as the entry. There is no second
write, so there is no split to fail - the decoupling that T12 had to ARGUE for on voice-journal is
satisfied here by construction.

That is exactly why it needs a gate rather than a comment. Adding an upload to this page would look
like an improvement in review - "move photos to storage, keep rows small" - and would silently
reintroduce a failure class the page currently cannot have.

★THE COUPLING RUNS THE OTHER WAY, AND THAT IS THE REAL RISK: one row now carries the typed work AND
the image, so a big photo makes a big row, and a failed insert takes the worker's typed words with
it. Both halves of that are guarded and both are gated here - an oversize file is refused BY NAME
before compression ("Photo too large (max 20 MB).") so the worker learns the limit rather than
watching a save fail, and the image is compressed rather than sent raw.

Fourth clause: when the AI vision path fails, it must say the entry is UNCHANGED. An analysis
failure is not a save failure, and a worker who cannot tell the difference will retype work that
was never lost.

TEETH: synthetic negatives - each clause reverted, including adding an upload call.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "logbook.html"

BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT = re.compile(r"(?m)^\s*//.*$")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)


def _strip_comments(src: str) -> str:
    """This page's comments DESCRIBE the single-write design in detail.

    A detector reading them would find every property satisfied in prose while the code had lost
    them - and on this page the prose is unusually thorough, which makes the trap worse.
    """
    return LINE_COMMENT.sub("", BLOCK_COMMENT.sub(" ", HTML_COMMENT.sub(" ", src)))


def audit(src: str) -> list:
    s = _strip_comments(src)
    out = []

    # 1. ★the single-write property: no storage upload on this page
    if re.search(r"storage\s*\.\s*from\s*\([^)]*\)\s*\.\s*upload\s*\(", s):
        out.append("logbook.html: a storage upload has appeared - the photo is no longer carried "
                   "inline in the entry's own insert, so the write can now half-succeed. Either an "
                   "orphaned file with no entry, or an entry claiming evidence it does not have. "
                   "This page was free of that class BY CONSTRUCTION; an upload reintroduces it")

    # 2. the image is compressed, not sent raw
    if not re.search(r"whCompressImage|vdcCompress", s):
        out.append("logbook.html: the client-side compression step is gone - a full-resolution photo "
                   "now rides inside the entry row, making a failed insert take the worker's typed "
                   "words with it")

    # 3. oversize is refused BY NAME, before the work
    if not re.search(r"Photo too large \(max \d+ ?MB\)", s):
        out.append("logbook.html: the oversize refusal no longer names the limit - a worker learns "
                   "their photo is too big by watching a save fail, instead of being told the number")

    # 4. an analysis failure must say the entry survived
    if not re.search(r"unchanged|untouched", s, re.I):
        out.append("logbook.html: the AI-analysis failure path no longer says the entry is unchanged - "
                   "a worker who cannot tell an analysis failure from a save failure retypes work that "
                   "was never lost")
    return out


def selftest() -> int:
    src = io.open(SRC, encoding="utf-8", errors="replace").read()
    cases = [("the real logbook.html is clean", src, 0)]
    cases.append(("adding a storage upload is caught",
                  src.replace("const { data, error } = await db",
                              "await db.storage.from('photos').upload(k, f);\n    const { data, error } = await db", 1), 1))
    cases.append(("losing compression is caught",
                  src.replace("whCompressImage", "_noCompress").replace("vdcCompress", "_noCompress2"), 1))
    cases.append(("dropping the named size limit is caught",
                  src.replace("Photo too large (max 20 MB).", "Upload failed."), 1))
    cases.append(("losing the entry-survived wording is caught",
                  re.sub(r"unchanged|untouched", "REMOVED", src, flags=re.I), 1))
    bad = 0
    for label, s, want in cases:
        f = audit(s)
        ok = (len(f) == 0) if want == 0 else (len(f) >= want)
        if not ok:
            bad += 1
        print(f"  {'ok  ' if ok else 'MISS'} {label} (findings={len(f)})")
    print(f"\nSELFTEST {'FAILED' if bad else 'ok'} - {len(cases) - bad}/{len(cases)}")
    return 1 if bad else 0


def main() -> int:
    if not SRC.exists():
        print("FAIL - logbook.html is gone; re-point this gate")
        return 1
    findings = audit(io.open(SRC, encoding="utf-8", errors="replace").read())
    print("the-photo-cannot-orphan-the-entry - one write, so there is no half to lose")
    if findings:
        print("\nFAIL - the core repair write can now half-succeed, or fails without saying so:")
        for f in findings:
            print(f"    {f}")
        return 1
    print("\nPASS - the photo rides inside the entry's own insert, compressed, with the size limit "
          "named and analysis failures declared harmless.")
    return 0


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
