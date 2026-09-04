#!/usr/bin/env python3
"""validate_skill_privacy_copy_consistent.py — T18's lock: the skill-matrix privacy promise and the
exam-pass result copy cannot contradict each other on one screen.

Walked live (T18): the page header promises 'Private to you: your skills, badges and exam attempts
are visible only to you, not to your supervisor or teammates', and 60 seconds later the pass result
said 'Your Level N badge is on your skill matrix now, and it shows on the hive board.' — which a
reader hears as 'others can see it', contradicting the promise. Ground truth (RLS confirmed):
skill_badges is auth_uid=auth.uid(); the hive-board worker-profile drawer that reads
v_skill_badges_truth returns rows ONLY to the worker viewing their OWN profile — a teammate gets
nothing. So the privacy promise is the truth and the result copy over-claimed. Fixed 2026-09-02:
the result names the private truth ('on your own hive-board profile - still private to you').

Lock: (1) the privacy-promise header must still be present (the contract must not silently vanish),
and (2) the result copy must NOT contain the bare 'shows on the hive board' over-claim — if it
mentions the hive board it must qualify it as private/own. Static, fast; teeth plant the pre-fix
string.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK_NAMES = ["skill-privacy-copy-consistent"]

PROMISE_RE = re.compile(r"Private to you[^<]{0,140}not to your\s+supervisor or teammates", re.I)
# the over-claim: "shows on the hive board" without a nearby privacy qualifier
OVERCLAIM_RE = re.compile(r"it shows on the hive board(?![^.]{0,60}(private|only to you|as promised))", re.I)


def problems_for(src: str) -> list[str]:
    out = []
    if not PROMISE_RE.search(src):
        out.append("skillmatrix.html: the 'Private to you ... not to your supervisor or teammates' "
                   "promise header is gone — the privacy contract must stay stated")
    if OVERCLAIM_RE.search(src):
        out.append("skillmatrix.html: the pass-result copy says 'it shows on the hive board' without "
                   "a privacy qualifier — it reads as public visibility, contradicting the promise")
    return out


def main() -> int:
    src = io.open(ROOT / "skillmatrix.html", encoding="utf-8", errors="replace").read()
    bad = problems_for(src)
    if bad:
        print("FAIL skill-privacy-copy-consistent:")
        for p in bad:
            print("    " + p)
        return 1
    print("PASS skill-privacy-copy-consistent — the privacy promise is stated and the pass-result "
          "copy does not over-claim public visibility (badge is named as private/own-board).")
    return 0


def self_test() -> int:
    src = io.open(ROOT / "skillmatrix.html", encoding="utf-8", errors="replace").read()
    fails = []
    if problems_for(src):
        fails.append("HEAD should PASS")
    pre_fix = src.replace(
        "on your own hive-board profile - still private to you, as promised.",
        "it shows on the hive board.")
    if not any("public visibility" in p for p in problems_for(pre_fix)):
        fails.append("the pre-fix over-claim must redden")
    no_promise = PROMISE_RE.sub("(promise removed)", src)
    if not any("privacy contract must stay" in p for p in problems_for(no_promise)):
        fails.append("removing the promise header must redden")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_skill_privacy_copy_consistent self-test (over-claim + missing-promise both redden; HEAD clean)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
