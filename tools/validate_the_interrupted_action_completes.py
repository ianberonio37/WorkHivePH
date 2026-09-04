#!/usr/bin/env python3
"""The action a person tapped before the wall must finish after it (T5).

An anonymous visitor browsing the marketplace taps Save on a listing. That tap is a decision. The
platform answers with a sign-in door - correctly - and the question that decides whether the door
was worth walking through is what happens on the other side: does the listing get saved, or does
the person land back on a page that has forgotten what they wanted?

Returning them to the PAGE is the easy half and was already done. Returning them to the ACTION is
this one: toggleWatchlist's anon branch stashes `wh_pending_action` before the wall, and
loadWatchlist replays it once the person has a name. Walked and proven live 2026-08-25 - tap,
sign in through the toast's own door, saved:true - and then left with NO GATE, which is why this
exists: the replay is four lines inside a loader, invisible to every other oracle, and the failure
is silent. Nothing errors. The listing is simply not saved, and only the person who tapped knows.

FOUR CLAUSES, each of which is load-bearing and each of which a plausible edit would remove:

  1. the anon branch STASHES the intent - without it there is nothing to resume;
  2. the loader REPLAYS it - a stash nobody reads is a stash that does nothing;
  3. the replay is SINGLE-SHOT - the key is consumed BEFORE the call, so a failing replay cannot
     loop forever against the same listing;
  4. the replay is IDEMPOTENT - it skips a listing already saved, because toggleWatchlist is a
     TOGGLE: replaying it over an already-saved listing would UN-save the very thing the person
     asked for, turning the feature into its own opposite.

★CLAUSE 4 IS THE ONE WORTH THE GATE. The other three fail visibly the first time anyone tests the
flow. This one only fires when the state raced ahead - the person saved it another way, or a
second tab got there first - and its symptom is the action being silently undone, which reads as
"the platform lost my save" rather than as a bug in a replay.

sessionStorage is the right store here and the gate holds it: the intent must die with the tab.
A pending action that outlived the session would fire days later against a listing the person no
longer wants, which is worse than losing it.

TEETH: synthetic negatives - each clause removed in turn.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "marketplace.html"
KEY = "wh_pending_action"

BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT = re.compile(r"(?m)^\s*//.*$")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)


def _strip_comments(src: str) -> str:
    """The fix's own comment describes every clause it implements.

    A detector that reads comments would find all four in the prose and pass a file whose CODE had
    lost them - the exact inversion this family has already shipped once.
    """
    return LINE_COMMENT.sub("", BLOCK_COMMENT.sub(" ", HTML_COMMENT.sub(" ", src)))


def audit(src: str) -> list:
    s = _strip_comments(src)
    out = []

    # 1. the intent is stashed, in sessionStorage (it must die with the tab)
    stash = re.search(r"(\w+)Storage\.setItem\(\s*['\"]" + KEY + r"['\"]\s*,\s*['\"]watchlist:['\"]\s*\+", s)
    if not stash:
        out.append(f"marketplace.html: nothing stashes {KEY} as 'watchlist:<id>' - an anon tap on Save "
                   f"is forgotten at the wall, so the sign-in door leads back to a page that has lost "
                   f"the reason the person walked through it")
    elif stash.group(1) != "session":
        out.append(f"marketplace.html: {KEY} is stashed in {stash.group(1)}Storage, not sessionStorage - "
                   f"an intent that outlives the tab can fire days later against a listing the person "
                   f"no longer wants")

    # locate the replay block
    idx = s.find("getItem('" + KEY + "')")
    if idx < 0:
        idx = s.find('getItem("' + KEY + '")')
    if idx < 0:
        out.append(f"marketplace.html: nothing READS {KEY} - the intent is stashed and never resumed, "
                   f"which is the same as not stashing it")
        return out

    block = s[idx:idx + 700]

    # 3. single-shot: the key is consumed BEFORE the replay call
    rm = block.find("removeItem")
    call = block.find("toggleWatchlist(")
    if rm < 0:
        out.append(f"marketplace.html: the replay never removes {KEY} - a failing replay re-fires on "
                   f"every load, looping against the same listing")
    elif call >= 0 and rm > call:
        out.append(f"marketplace.html: {KEY} is consumed AFTER the replay call, not before - if the "
                   f"call throws, the key survives and the replay loops")

    # 2. the replay actually calls the action
    if call < 0:
        out.append("marketplace.html: the pending action is read and cleared but never REPLAYED - the "
                   "person's tap is silently discarded at the moment it was supposed to complete")

    # 4. idempotent: skip a listing already saved (toggle would UN-save it)
    if not re.search(r"!\s*_watchlist\.has\(", block):
        out.append("marketplace.html: the replay does not skip an already-saved listing - toggleWatchlist "
                   "is a TOGGLE, so replaying it over a saved listing UN-saves the very thing the person "
                   "asked for, and the symptom reads as the platform losing their save")
    return out


def selftest() -> int:
    src = io.open(SRC, encoding="utf-8", errors="replace").read()
    cases = [("the real marketplace.html is clean", src, 0)]
    cases.append(("losing the stash is caught",
                  src.replace("sessionStorage.setItem('wh_pending_action', 'watchlist:' + listingId)",
                              "void 0"), 1))
    cases.append(("moving the stash to localStorage is caught",
                  src.replace("sessionStorage.setItem('wh_pending_action', 'watchlist:'",
                              "localStorage.setItem('wh_pending_action', 'watchlist:'"), 1))
    cases.append(("losing the replay call is caught",
                  src.replace("await toggleWatchlist(_pid)", "void _pid"), 1))
    cases.append(("dropping the idempotency guard is caught",
                  src.replace("&& !_watchlist.has(_pid)", ""), 1))
    cases.append(("consuming the key AFTER the call is caught",
                  src.replace("        sessionStorage.removeItem('wh_pending_action');\n        const _pid = _pa.slice('watchlist:'.length);\n        if (/^[0-9a-f-]{36}$/i.test(_pid) && !_watchlist.has(_pid)) await toggleWatchlist(_pid);",
                              "        const _pid = _pa.slice('watchlist:'.length);\n        if (/^[0-9a-f-]{36}$/i.test(_pid) && !_watchlist.has(_pid)) await toggleWatchlist(_pid);\n        sessionStorage.removeItem('wh_pending_action');"), 1))
    cases.append(("removing the read entirely is caught",
                  src.replace("sessionStorage.getItem('wh_pending_action')", "''"), 1))
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
        print("FAIL - marketplace.html is gone; re-point this gate")
        return 1
    findings = audit(io.open(SRC, encoding="utf-8", errors="replace").read())
    print("the-interrupted-action-completes - the tap that met the wall finishes after it")
    if findings:
        print("\nFAIL - the person walks through the door and their action does not follow:")
        for f in findings:
            print(f"    {f}")
        return 1
    print("\nPASS - the anon tap is stashed, replayed once, and never un-saves what it meant to save.")
    return 0


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
