#!/usr/bin/env python3
"""validate_assistant_no_orphan_fragment.py — T16's lock: a mid-generation stream death can never
render a token fragment as the assistant's answer.

Walked live (T16): ai-gateway's downstream died mid-generation (console 546) and the chat showed
'What did I log today?' answered by a bare 'I' — a 200 whose answer was the first token, rendered
as if complete, with the excellent error copy only in an unreachable path. Root: a truthy string
IS a reply to the render code; a fragment is indistinguishable from an answer without a
plausibility floor. Fixed 2026-09-02 (both acquisition paths in assistant.html):
  - Step 1 (orchestrator): a fragment (len<4, or no sentence-ending punctuation and len<12)
    falls through to Step 2 instead of rendering.
  - Step 2 (fallback): a fragment THROWS to the catch — the designed failure surface (inline
    error bubble + question restored to the input).
Predicate verified live: 'I' and 'I think the' trapped; 'Yes.' and real answers pass.

Also locked here (same walk, resolved earlier in code): the signed-in auto-start — with
wh_last_worker set the page skips the name prompt and startChat() runs with the platform identity
(the B1 identity-amnesia + AI1 dead-personalization root; verified live: Bryan auto-started,
'I can see your job records').
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK_NAMES = ["assistant-no-orphan-fragment"]

STEP1_GUARD_RE = re.compile(r"stream-orphan guard[\s\S]{0,900}?_fragment\s*=\s*_a\.length\s*<\s*4")
STEP2_GUARD_RE = re.compile(r"fallback half[\s\S]{0,600}?_fb\.length\s*<\s*4[\s\S]{0,300}?throw new Error")
AUTOSTART_RE = re.compile(r"savedName\s*=\s*localStorage\.getItem\(KEY_WORKER\)[\s\S]{0,500}?startChat\(\)")
QUOTA_PREASK_RE = re.compile(r"wh_ai_remaining[\s\S]{0,300}?12 \* 3600 \* 1000")


def problems_for(src: str) -> list[str]:
    out = []
    if not STEP1_GUARD_RE.search(src):
        out.append("assistant.html: Step-1's stream-orphan fragment floor is gone — a mid-stream "
                   "death renders its first token as the answer again")
    if not STEP2_GUARD_RE.search(src):
        out.append("assistant.html: Step-2's fragment floor no longer throws to the inline error "
                   "path — a fallback fragment lands on the glass")
    if not AUTOSTART_RE.search(src):
        out.append("assistant.html: the signed-in auto-start (wh_last_worker -> startChat) is gone — "
                   "identity amnesia returns and a typo'd name zeroes personalization (T16 AI1/B1)")
    if not QUOTA_PREASK_RE.search(src):
        out.append("assistant.html: the pre-ask quota floor (wh_ai_remaining persisted + 12h-bounded "
                   "restore) is gone — a worker types an expensive question with no idea they are "
                   "near the wall (T16 quota seam)")
    return out


def main() -> int:
    src = io.open(ROOT / "assistant.html", encoding="utf-8", errors="replace").read()
    bad = problems_for(src)
    if bad:
        print("FAIL assistant-no-orphan-fragment:")
        for p in bad:
            print("    " + p)
        return 1
    print("PASS assistant-no-orphan-fragment — both reply paths floor out token fragments (mid-stream "
          "death reaches the inline error, never the glass) and the signed-in auto-start holds.")
    return 0


def self_test() -> int:
    src = io.open(ROOT / "assistant.html", encoding="utf-8", errors="replace").read()
    fails = []
    if problems_for(src):
        fails.append("HEAD should PASS")
    no_floor = re.sub(r"_fragment\s*=\s*_a\.length\s*<\s*4", "_fragment = false && _a.length < 4", src, count=1)
    if not any("first token" in p for p in problems_for(no_floor)):
        fails.append("disabling the Step-1 floor must redden")
    no_auto = AUTOSTART_RE.sub("/*autostart removed*/", src)
    if not any("identity amnesia" in p for p in problems_for(no_auto)):
        fails.append("removing the auto-start must redden")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_assistant_no_orphan_fragment self-test (disabled floor + removed auto-start both redden; HEAD clean)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
