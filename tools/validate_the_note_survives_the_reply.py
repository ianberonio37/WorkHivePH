#!/usr/bin/env python3
"""A spoken or typed note must outlive the AI that was going to answer it (T12).

voice-journal is where a worker captures a thought mid-shift. The companion's reply is the nice
part; the NOTE is the part that matters, because it is the worker's own words about a machine.

★THE ORIGINAL DESIGN LOST THE NOTE TO A QUOTA ERROR. The write happened server-side inside the
voice-journal-agent call, so a `429` from the AI gateway meant the row was never written at all -
the page was honest about it ("your note was not saved") and the note was still gone. On a shared
free tier, Friday afternoon is exactly when that happens, and it is exactly when a worker is most
likely to be capturing something they will not remember later.

TWO CLAUSES, and they are separate failures:

  1. THE PAGE HAS ITS OWN EYES. noteLanded() re-reads for the note rather than inferring its fate
     from the call's outcome. An error on the reply says nothing about whether the row exists, and
     a page that guesses will guess wrong in one direction or the other - either telling a worker
     their words are gone when they are safe, or the reverse, which is worse.
  2. IT SAYS THE TRUE SENTENCE ON BOTH PATHS. Typed and spoken are two different catch blocks, and
     a fix landing in one is a page that tells the truth depending on how you happened to enter
     the note. Both must say the note IS saved and only the reply failed.

★AND THE MIC FAILURE MUST NAME ITS OWN CAUSE. One catch blamed "permission denied" for EVERY
getUserMedia failure, so a mic-less desktop told the worker to check permissions they had never
refused - sending them to a settings page that could not help. Branching on err.name (NotAllowed /
Security -> permission; NotFound / Overconstrained -> no microphone) is the difference between a
remedy and a wild goose chase, and every branch must still name the typed fallback, because the
point is to get the note captured either way.

TEETH: synthetic negatives - each clause reverted, and the two reply paths mutated independently.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "voice-journal.html"

BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT = re.compile(r"(?m)^\s*//.*$")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)


def _strip_comments(src: str) -> str:
    return LINE_COMMENT.sub("", BLOCK_COMMENT.sub(" ", HTML_COMMENT.sub(" ", src)))


def audit(src: str) -> list:
    s = _strip_comments(src)
    out = []

    # 1. the page verifies for itself
    if not re.search(r"async function noteLanded\s*\(", s):
        out.append("voice-journal.html: noteLanded() is gone - the page can no longer check whether "
                   "the note actually landed, so it must INFER the row's fate from the reply call's "
                   "outcome. An AI error says nothing about whether the write succeeded, and a page "
                   "that guesses tells a worker their words are lost when they are safe, or the "
                   "reverse")

    # 2. both reply paths tell the truth - and they are separate catch blocks
    landed_calls = len(re.findall(r"noteLanded\s*\(", s))
    # one definition + at least two call sites (mic + typed)
    if landed_calls < 3:
        out.append(f"voice-journal.html: noteLanded is referenced {landed_calls} time(s) - the mic path "
                   f"and the typed path are separate catch blocks, and a check on only one means the "
                   f"page tells the truth depending on how the worker happened to enter the note")
    saved_sentences = len(re.findall(r"Your note IS saved", s))
    if saved_sentences < 2:
        out.append(f"voice-journal.html: the 'Your note IS saved' sentence appears {saved_sentences} "
                   f"time(s) - both the spoken and typed failure paths must say it, or one of them "
                   f"leaves the worker believing a quota error ate their words")

    # 3. the mic failure names its real cause
    if not re.search(r"NotAllowedError", s) or not re.search(r"NotFoundError|OverconstrainedError", s):
        out.append("voice-journal.html: the microphone failure no longer branches on err.name - one "
                   "catch blaming 'permission denied' for every getUserMedia failure sends a worker "
                   "with no microphone to check a permission they never refused")
    return out


def selftest() -> int:
    src = io.open(SRC, encoding="utf-8", errors="replace").read()
    cases = [("the real voice-journal.html is clean", src, 0)]
    cases.append(("removing noteLanded is caught",
                  src.replace("async function noteLanded(", "async function _retired_noteLanded("), 1))
    cases.append(("checking only ONE reply path is caught",
                  src.replace("if (await noteLanded(text)) {", "if (false) {", 1), 1))
    cases.append(("the truth sentence on only one path is caught",
                  src.replace("Your note IS saved - it is in the list below. Only the companion reply failed; you can ask again later.",
                              "Something went wrong."), 1))
    cases.append(("collapsing the mic causes back to one is caught",
                  src.replace("NotAllowedError", "_x").replace("NotFoundError", "_y"), 1))
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
        print("FAIL - voice-journal.html is gone; re-point this gate")
        return 1
    findings = audit(io.open(SRC, encoding="utf-8", errors="replace").read())
    print("the-note-survives-the-reply - a worker's words outlive the AI that was going to answer them")
    if findings:
        print("\nFAIL - a quota error can take the note with it, or the page misreports what happened:")
        for f in findings:
            print(f"    {f}")
        return 1
    print("\nPASS - the page verifies the note landed, says so on both paths, and names the real "
          "microphone cause.")
    return 0


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
