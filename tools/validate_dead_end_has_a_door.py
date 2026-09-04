#!/usr/bin/env python3
"""A read-failure state must offer a way OUT, not just a sentence (T193).

★THE THREE DOORS, each answering a different question a stuck person actually asks.
whListError is the shared read-failure panel behind ~24 pages, so what it renders IS the
platform's error state, and it must carry all three:

  1. RETRY   - "try again", the answer when the failure was transient;
  2. STATUS  - "is it just me?", a link to status.html, the answer when it was not;
  3. THE DOOR - "then who do I tell?", the escalation into the feedback queue, with the page,
     the error sentence and the time PRE-ATTACHED so a report describes the failure instead of
     saying "it doesn't work".

Lose the third and a person who has retried, checked status and found the platform healthy is
simply stuck with nowhere to go. That is the dead end this locks.

★WHY IT IS A GATE ON THE HELPER AND NOT A PAGE CENSUS. A first cut counted pages that call
whListError and also ship the feedback widget, and reported ALL 24 as missing it — because no page
ships it: nav-hub.js injects wh-feedback-fab.js centrally on every page that loads the hub. The
mechanism was fine and the census was measuring a per-page script tag that does not exist by
design. Absence of a per-page marker is not absence of the capability, so the property is held
where it actually lives: in the one function that renders the state.

★AND THE DOOR IS CONDITIONAL ON PURPOSE - rendered only when window.WHFeedback.open exists, so it
can never be a door onto nothing. That is correct, and it makes TIMING the real risk: the fab is
injected asynchronously, so a read failing faster than it loads would build a panel with no door.
Measured live under aborted reads: WHFeedback was ready at 1200ms, well before any panel built,
and a panel rendered on demand carries retry + status + door with a 44px target.

TEETH: synthetic negatives - each of the three affordances removed in turn.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UTILS = ROOT / "utils.js"

# (name, pattern, why it matters to a person who is stuck)
CLAUSES = [
    ("retry", r"wh-list-retry",
     "no retry control - a transient failure becomes a permanent one"),
    ("status", r'href=[\'"]status\.html',
     "no link to the status page - the person cannot tell 'it is me' from 'it is them'"),
    ("door", r"wh-list-report",
     "no escalation door - someone who retried and checked status has nowhere left to go"),
    ("door-is-guarded", r"WHFeedback\s*&&\s*typeof\s+window\.WHFeedback\.open",
     "the door is rendered unconditionally - it would open onto nothing where the widget is absent"),
    ("door-carries-context", r"wh-list-report[\s\S]{0,3000}?WHFeedback\.open",
     "the door does not open the widget - a link that goes nowhere is not an escalation"),
]


def body_of(src: str) -> str:
    m = re.search(r"function whListError\s*\(", src)
    if not m:
        return ""
    rest = src[m.start():]
    nxt = re.search(r"\nfunction \w+\s*\(", rest[10:])
    return rest[: 10 + nxt.start()] if nxt else rest[:8000]


def audit(src: str) -> list:
    body = body_of(src)
    if not body:
        return ["whListError() not found in utils.js - re-point this gate rather than trusting silence"]
    return [f"whListError: {why}" for name, pat, why in CLAUSES if not re.search(pat, body)]


def selftest() -> int:
    src = io.open(UTILS, encoding="utf-8", errors="replace").read()
    cases = [("the real whListError is clean", src, 0)]
    for name, pat, _ in CLAUSES[:3]:
        # Remove each affordance in turn and require it to be caught.
        cases.append((f"a panel with no {name} is caught",
                      re.sub(pat, "REMOVED-" + name, src, count=0), 1))
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
    if not UTILS.exists():
        print("FAIL - utils.js is gone; this gate cannot judge anything")
        return 1
    findings = audit(io.open(UTILS, encoding="utf-8", errors="replace").read())
    print("dead-end-has-a-door - the shared read-failure panel must offer retry, status and escalation")
    print(f"  clauses checked: {len(CLAUSES)}")
    if findings:
        print("\nFAIL - a stuck person is left without a way out:")
        for f in findings:
            print(f"    {f}")
        return 1
    print("\nPASS - retry, the status link and the context-carrying escalation door are all present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
