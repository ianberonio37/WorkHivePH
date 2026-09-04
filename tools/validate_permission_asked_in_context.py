#!/usr/bin/env python3
"""permission-in-context - T46/T105: ask for push when the worker wants it (2026-08-26).

A notification prompt at first paint is the fastest way to lose the permission
permanently: the person has no reason to say yes yet, they say no, and the browser
remembers that answer forever. There is no second chance and no in-app way to undo it.
So WHEN the prompt fires matters more than how the feature is built.

MEASURED 2026-08-26 - two call sites, both exemplary:
  marketplace-seller  svcEnablePush() runs from an onclick ("Turning on…"), behind
                      online / support / signed-in checks, and refuses honestly when the
                      answer is no: "Alerts stay off until you allow notifications."
  voice-handler       _requestPushPerm() fires only when the worker has VERBALLY opted
                      in (_isPushOptInReply) and only when the state is still 'default',
                      inside the open user-gesture window. A prior 'denied' is never
                      re-prompted.

TWO ASSERTIONS:
  guarded   every Notification.requestPermission() call sits behind a permission-state
            check or an explicit user action - never bare
  not-at-load  no call site is reachable from a load-time path (DOMContentLoaded, an
            init IIFE), which is the first-paint beg this gate exists to prevent

★IT CHECKS THE ASK, NOT THE FEATURE. Whether push is wired, which VAPID key is used and
whether the message is good all belong elsewhere. This is only about the one moment that
cannot be taken back.

Usage: python tools/validate_permission_asked_in_context.py
"""
import glob
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SKIP = re.compile(r"backup|test|^index-", re.I)

ASK = re.compile(r"Notification\s*\.\s*requestPermission\s*\(")
GUARD = re.compile(r"Notification\s*\.\s*permission|_pushNotifyState|permission\s*===\s*['\"]|"
                   r"pushState\s*===\s*['\"]|onclick|addEventListener\(\s*['\"]click", re.I)
AT_LOAD = re.compile(r"DOMContentLoaded|window\.onload|document\.readyState", re.I)


def strip_comments(src: str) -> str:
    def blank(m):
        return "".join(c if c == "\n" else " " for c in m.group(0))
    s = re.sub(r"<!--.*?-->", blank, src, flags=re.S)
    # (?!quote): accept="image/*" is NOT a comment opener
    s = re.sub(r"/\*(?![\"']).*?\*/", blank, s, flags=re.S)
    return re.sub(r"(?m)^[ \t]*//[^\n]*$", blank, s)


def main() -> int:
    files = [f for f in (sorted(glob.glob(str(ROOT / "*.html"))) + sorted(glob.glob(str(ROOT / "*.js"))))
             if not SKIP.search(Path(f).name)]
    if not files:
        print("SKIP permission-in-context - no surfaces found")
        return 0

    asks, bare, at_load = 0, [], []
    for f in files:
        name = Path(f).name
        src = strip_comments(io.open(f, encoding="utf-8", errors="replace").read())
        for m in ASK.finditer(src):
            asks += 1
            line = src[:m.start()].count("\n") + 1
            before = src[max(0, m.start() - 1200):m.start()]
            # ★A LOOKBACK WINDOW CANNOT SEE A GESTURE BINDING, and the first version proved it:
            # marketplace-seller's svcEnablePush() IS bound to an onclick - 350 lines earlier, far
            # outside any sane window - so the gate called a correctly-gated prompt "bare". The
            # binding is a property of the enclosing FUNCTION, not of nearby text, so resolve the
            # function name and ask whether the file wires it to a click anywhere.
            fn = None
            for d in re.finditer(r"(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", src[:m.start()]):
                fn = d.group(1)
            gesture_bound = bool(fn and re.search(
                r"onclick\s*=\s*[\"'][^\"']*\b" + re.escape(fn) + r"\b"
                r"|addEventListener\(\s*[\"']click[\"']\s*,\s*" + re.escape(fn) + r"\b"
                r"|\b" + re.escape(fn) + r"\s*\(\s*\)\s*;?\s*\}\s*\)", src))
            if not GUARD.search(before) and not gesture_bound:
                bare.append(f"{name}:{line} asks for notification permission with no state check and "
                            f"no user action in front of it")
            if AT_LOAD.search(src[max(0, m.start() - 400):m.start()]):
                at_load.append(f"{name}:{line} asks from a load-time path - the first-paint beg")

    print(f"  notification permission prompts: {asks} | bare: {len(bare)} | at load: {len(at_load)}")
    fails = bare + at_load
    if fails:
        print(f"FAIL permission-in-context - {len(fails)} prompt(s) fire at the wrong moment:")
        for x in fails[:8]:
            print("    - " + x)
        print("    A prompt before the worker wants the feature gets a no, and the browser remembers")
        print("    that answer forever with no in-app way to undo it. Ask when they ask - the platform")
        print("    already does this twice: a 'turn on job alerts' button, and a verbal opt-in.")
        return 1
    if asks == 0:
        print("PASS permission-in-context - no notification prompt exists to mistime.")
        return 0
    print(f"PASS permission-in-context - all {asks} notification prompts fire behind a user action or a "
          f"permission-state check, never at first paint.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
