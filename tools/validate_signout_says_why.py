#!/usr/bin/env python3
"""signout-says-why - T8: the sign-in screen explains why the worker is looking at it (2026-08-26).

A worker mid-task looks up and finds a sign-in modal. Nothing tells them what happened, so an
automatic idle sign-out is indistinguishable from being logged out at random, and the question in
their head goes unanswered: did I lose what I was doing?

★ONE FUNCTION, THREE EVENTS, THREE DIFFERENT TRUTHS. session-timeout.js's clearIdentityHard() runs
for an automatic idle timeout, for the worker deliberately pressing Sign out, and (via the storage
listener) for a sign-out in another tab. Telling someone who just pressed Sign out that their
session "timed out" is false, so the reason is a PARAMETER and the deliberate path passes none -
this gate asserts that separation, because collapsing it is the easy mistake.

★THE REAL ASSERTION IS THE CLAIM'S PRECONDITION, not the wording. The notice tells an idle-timed-out
worker "your drafts are still here", and that is only true because clearIdentityHard wipes IDENTITY
keys alone - wh_last_worker and the hive keys - and never touches whAutoSaveDraft's storage. Add a
draft key to that wipe list and the copy silently becomes a lie that no test would catch. So the
gate reads the wipe list and fails if anything draft-shaped appears in it. A claim has to rest on
something, and this is the something. [[feedback_a_claim_must_name_what_it_rests_on]]

★AND THE COPY MUST BE A WHITELIST, not interpolation: ?reason= comes from the URL, so the page looks
it up in a fixed table and writes it with textContent. An unknown value must render NOTHING.

Re-drive: python tools/validate_signout_says_why.py
"""
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DRAFTY = re.compile(r"draft|autosave|_wip|compose", re.I)


def main() -> int:
    failures = []
    st = io.open(ROOT / "session-timeout.js", encoding="utf-8", errors="replace").read()
    ix = io.open(ROOT / "index.html", encoding="utf-8", errors="replace").read()

    # ── the three events must not collapse into one message ────────────────────────────────
    if not re.search(r"function clearIdentityHard\(\s*reason\s*\)", st):
        failures.append("clearIdentityHard() takes no reason, so an automatic idle sign-out, a "
                        "deliberate Sign out and another tab's sign-out all arrive identically - and "
                        "any message shown will be wrong for two of the three")
    if not re.search(r"clearIdentityHard\(\s*['\"]idle['\"]\s*\)", st):
        failures.append("the automatic idle path does not pass a reason, so the timeout stays "
                        "unexplained - the case this exists for")
    if re.search(r"wh-idle-signout'\)\.addEventListener\('click',\s*clearIdentityHard\s*\)", st):
        failures.append("the deliberate Sign out button passes clearIdentityHard directly, so the "
                        "click EVENT object becomes the reason - a worker who chose to sign out "
                        "would be told something about it, and the browser event decides what")

    # ── the claim's precondition: identity keys only, never drafts ─────────────────────────
    m = re.search(r"function clearIdentityHard\([^)]*\)\s*\{(.*?)\n  \}", st, re.S)
    if not m:
        failures.append("could not read clearIdentityHard()'s body to check what it wipes")
    else:
        wiped = re.findall(r"'([A-Za-z0-9_]+)'", m.group(1))
        drafty = [k for k in wiped if DRAFTY.search(k)]
        if drafty:
            failures.append(f"clearIdentityHard now wipes {drafty}, which look like DRAFT storage - "
                            f"the sign-in notice promises an idle-timed-out worker that their drafts "
                            f"are still here, and that promise is now false")

    # ── the notice itself ──────────────────────────────────────────────────────────────────
    if not re.search(r'id="si-reason"', ix):
        failures.append("index.html has no #si-reason element, so the sign-in screen cannot say why "
                        "the worker is looking at it")
    if 'role="status"' not in (re.search(r'<p id="si-reason"[^>]*>', ix) or type("", (), {"group": lambda s: ""})()).group(0):
        failures.append('#si-reason is not role="status", so a screen-reader user is never told why '
                        "they were signed out")
    body = re.search(r"function _siReason\(\)\s*\{(.*?)\n    \}\)\(\);", ix, re.S)
    if not body:
        failures.append("the reason resolver (_siReason) is gone from index.html")
    else:
        b = body.group(1)
        if ".textContent" not in b:
            failures.append("the reason copy is not written with textContent - ?reason= comes from "
                            "the URL and must never reach innerHTML")
        if not re.search(r"\bidle:\s*'", b) or not re.search(r"\bothertab:\s*'", b):
            failures.append("the copy is not a fixed lookup keyed by reason; an unknown ?reason= "
                            "must render nothing rather than whatever the URL said")
        if not re.search(r"if\s*\(\s*!_copy\s*\)\s*return", b):
            failures.append("an unrecognised ?reason= does not fall through to silence")

    if failures:
        print("FAIL signout-says-why:")
        for f in failures:
            print("    - " + f)
        return 1

    print("PASS signout-says-why - the idle timeout explains itself, a deliberate sign-out stays "
          "silent, an unknown reason renders nothing, and the 'your drafts are still here' promise "
          "still holds: clearIdentityHard wipes identity keys only.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
