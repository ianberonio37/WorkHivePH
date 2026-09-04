#!/usr/bin/env python3
"""A locked button must say WORKING, not merely UNAVAILABLE - and say it in both pairs (T41).

button-lock.js is this platform's single-flight guard: `withButtonLock(btn, asyncFn)` disables a
committing control while its work runs, so a rage-tap on a slow plant connection produces one
effect instead of five. It set `disabled` and an `is-loading` class and nothing else.

★DISABLED AND BUSY ARE DIFFERENT SENTENCES. `disabled` alone announces "unavailable" - the same
thing a control says when it is not applicable, when a form is invalid, when you may not use it at
all. A sighted user never hears that sentence; they see the spinner and know the press landed.
A screen-reader user hears only "unavailable" and reasonably concludes the tap did NOT register -
so they press again, on exactly the controls where a second press costs the most. `aria-busy` is
the state that means in progress.

THE PAIRING IS THE OTHER HALF: aria-busy must be REMOVED in the release, beside `disabled`. A
button left announcing itself busy forever after an exception is worse than one that never
announced it, because now the control is permanently lying about its state.

★AND IT MUST HOLD IN BOTH PAIRS. This file has TWO lock/release paths - withButtonLock (which
awaits an async fn) and lockButtonDuring (which returns a release closure for callers that manage
their own timing). Fixing only the first would produce a shared helper that is right half the time,
which is harder to trust than one that is consistently wrong: three pages adopt it today
(dayplanner, inventory, marketplace-seller) and every future adopter inherits whichever path it
happens to call.

TEETH: synthetic negatives - each attribute removed, from each pair independently, so a fix that
lands in only one path is caught.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "button-lock.js"

BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT = re.compile(r"(?m)^\s*//.*$")

PAIRS = ["withButtonLock", "lockButtonDuring"]


def _strip_comments(src: str) -> str:
    """The T41 comment explains aria-busy at length; prose about the contract is not the contract."""
    return LINE_COMMENT.sub("", BLOCK_COMMENT.sub(" ", src))


def _pair_body(src: str, name: str) -> str:
    s = _strip_comments(src)
    i = s.find(name + " = ")
    if i < 0:
        i = s.find("function " + name + "(")
    if i < 0:
        return ""
    nxt = min([p for p in (s.find(o + " = ", i + 1) for o in PAIRS) if p > i] or [len(s)])
    return s[i:nxt]


def audit(src: str) -> list:
    out = []
    for name in PAIRS:
        body = _pair_body(src, name)
        if not body:
            out.append(f"button-lock.js: {name} is gone - a lock path the adopting pages call has "
                       f"disappeared, taking its single-flight guard with it")
            continue
        sets = re.search(r"setAttribute\(\s*['\"]aria-busy['\"]\s*,\s*['\"]true['\"]\s*\)", body)
        clears = re.search(r"removeAttribute\(\s*['\"]aria-busy['\"]\s*\)", body)
        if not sets:
            out.append(f"button-lock.js: {name} locks the button without setting aria-busy - it "
                       f"announces 'unavailable' where it means 'working', so a screen-reader user "
                       f"concludes the tap did not land and presses again, on exactly the control "
                       f"where a second press costs the most")
        if not clears:
            out.append(f"button-lock.js: {name} never removes aria-busy - a button that survives an "
                       f"exception is left permanently announcing itself busy, which is worse than "
                       f"never announcing it at all")
        if not re.search(r"\.disabled\s*=\s*true", body):
            out.append(f"button-lock.js: {name} no longer sets disabled - the single-flight guard is "
                       f"gone and a rage-tap produces N effects")
        if not re.search(r"\.disabled\s*=\s*false", body):
            out.append(f"button-lock.js: {name} never re-enables the button - one slow action strands "
                       f"the control forever")
    return out


def selftest() -> int:
    src = io.open(SRC, encoding="utf-8", errors="replace").read()
    cases = [("the real button-lock.js is clean", src, 0)]
    # ★each pair mutated INDEPENDENTLY - a fix that lands in only one path must be caught
    first = src.index("window.withButtonLock")
    second = src.index("window.lockButtonDuring")
    def mut(seg_start, seg_end, old, new):
        return src[:seg_start] + src[seg_start:seg_end].replace(old, new, 1) + src[seg_end:]
    cases.append(("aria-busy missing from withButtonLock ONLY is caught",
                  mut(first, second, "btn.setAttribute('aria-busy', 'true');", ""), 1))
    cases.append(("aria-busy missing from lockButtonDuring ONLY is caught",
                  mut(second, len(src), "btn.setAttribute('aria-busy', 'true');", ""), 1))
    cases.append(("a stranded busy state in withButtonLock is caught",
                  mut(first, second, "btn.removeAttribute('aria-busy');", ""), 1))
    cases.append(("a stranded busy state in lockButtonDuring is caught",
                  mut(second, len(src), "btn.removeAttribute('aria-busy');", ""), 1))
    cases.append(("losing the single-flight disable is caught",
                  src.replace("btn.disabled = true;", "", 1), 1))
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
        print("FAIL - button-lock.js is gone; re-point this gate")
        return 1
    findings = audit(io.open(SRC, encoding="utf-8", errors="replace").read())
    print("a-busy-button-says-working - a locked control announces work, not unavailability")
    print(f"  lock paths held: {', '.join(PAIRS)}")
    if findings:
        print("\nFAIL - the shared lock helper misreports its state to the people who cannot see it:")
        for f in findings:
            print(f"    {f}")
        return 1
    print("\nPASS - both lock paths set aria-busy on lock and clear it on release, beside disabled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
