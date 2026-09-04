#!/usr/bin/env python3
"""scroll-gate-at-open - T18: a read-gate must not depend on an event that may never fire.

skillmatrix gates its exam behind "read the lesson first": the Take-exam button starts
disabled, and a scroll handler enables it once the reader reaches the bottom. Correct
intent, and it had a hole - the button was enabled ONLY from inside that handler.

★A LESSON WHOSE CONTENT FITS THE BOX NEVER SCROLLS, so the scroll event never fires, so
checkScroll never runs, and the reader is left staring at a permanently disabled "Take
exam" beside a hint telling them to scroll something that does not scroll. There is no
way out of that screen except closing it. It was latent only because every lesson
written so far happens to overflow - and lesson bodies are AUTHORED CONTENT, so the
first short one ships the trap to whoever writes it.

FIXED by evaluating the gate once at open, after the scroll reset. It costs nothing and
it is self-correcting: for a non-scrolling box scrollTop + clientHeight already exceeds
scrollHeight - 80, so the check passes immediately; for a long lesson at scrollTop 0 it
does not, and the gate holds.

VERIFIED LIVE ON BOTH BRANCHES, because the risk of this fix is that it opens the gate
for everyone: long content (scrollHeight 822 vs clientHeight 502) still reports
disabled=true with the hint shown, while short content (54 vs 54) reports disabled=false
with the hint cleared.

THE ASSERTION: the lesson gate's checker is invoked outside its own listener. Narrow by
design - this is one known control, and a gate that tried to infer "enabled only by an
event" across the platform would be guessing at intent.

Usage: python tools/validate_scroll_gate_evaluates_at_open.py
"""
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "skillmatrix.html"


def main() -> int:
    if not PAGE.exists():
        print("SKIP scroll-gate-at-open - skillmatrix.html not found")
        return 0
    src = io.open(PAGE, encoding="utf-8", errors="replace").read()

    if "function checkScroll" not in src:
        print("SKIP scroll-gate-at-open - the lesson scroll gate is no longer shaped this way; "
              "re-derive the assertion before trusting this gate again.")
        return 0

    listener = "addEventListener('scroll', checkScroll)"
    if listener not in src:
        print("FAIL scroll-gate-at-open - checkScroll exists but is not wired to the scroll event.")
        return 1

    # A bare CALL, not the declaration. ★The first version counted `function checkScroll()` as an
    # invocation, so deleting the real call still left a count of 1 and the gate reported PASS on
    # the very defect it exists for - caught only because the teeth test refused to go red.
    invocations = [m.start() for m in re.finditer(r"(?<![.\w])(?<!function )checkScroll\(\s*\)", src)]
    at_open = len(invocations)

    print(f"  lesson scroll gate: listener wired | direct invocations: {at_open}")
    if at_open == 0:
        print("FAIL scroll-gate-at-open - the exam button is enabled ONLY from inside the scroll")
        print("    handler. A lesson whose content fits the box never scrolls, so the event never")
        print("    fires and the reader is trapped in front of a disabled 'Take exam' beside a hint")
        print("    telling them to scroll something that does not scroll. Call checkScroll() once")
        print("    after the scroll reset: it passes immediately for short content and still holds")
        print("    the gate for long content.")
        return 1
    print("PASS scroll-gate-at-open - the lesson read-gate is evaluated at open, so a lesson that "
          "fits the box cannot strand its reader.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
