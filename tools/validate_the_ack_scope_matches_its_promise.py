#!/usr/bin/env python3
"""Acking a plant alert hides it for the WHOLE CREW, and the page must say so (T144).

alert-hub's dismissal is HIVE state. The upsert is keyed `onConflict: 'hive_id,alert_key'` - not on
the actor - so one person marking an alert handled removes it from every teammate's feed. That is a
deliberate design: a plant alert is about a machine, not about a person's inbox, and it should stop
nagging the crew once somebody has dealt with it.

★IT IS ALSO THE ONE FAILURE MODE THIS PAGE CANNOT AFFORD, if it happens silently. A worker tidying
what they believe is their own view can blind the entire crew to a live plant condition. So the
scope and the SENTENCE have to be checked together, and this gate holds them as one property:

  1. the write is keyed hive_id + alert_key, NOT the actor - crew-wide by construction;
  2. the row still records `actor`, so the action is attributable. Crew-wide AND anonymous would be
     a far worse combination than either alone;
  3. the toast says it is hidden for the whole hive, and says it is recorded under their name.

★CLAUSE 3 IS NOT DECORATION - IT IS THE HALF THAT MAKES THE OTHER TWO SAFE. The old copy said only
"Alert marked handled", which is true and tells the person nothing about who else just stopped
seeing it. A scope this wide is defensible when stated and indefensible when discovered.

AND THE BADGE MUST CONVERGE: an untouched second tab reads the old count until the next poll, so
the poll has to exist and be bounded (setInterval(loadAll, 60000)), and it has to PAUSE when the
tab is hidden - a phone in a pocket polling a plant database every minute is a battery cost with no
reader. The practical lag for a background tab becomes "until you look at it", which is the moment
a person could act anyway.

TEETH: synthetic negatives - each clause reverted, including scoping the ack to the actor.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "alert-hub.html"

BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT = re.compile(r"(?m)^\s*//.*$")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)


def _strip_comments(src: str) -> str:
    """This page's comment explains the crew-wide scope in six lines; the code must carry it."""
    return LINE_COMMENT.sub("", BLOCK_COMMENT.sub(" ", HTML_COMMENT.sub(" ", src)))


def audit(src: str) -> list:
    s = _strip_comments(src)
    out = []

    # 1. the conflict key is hive-wide, not per-actor
    conflicts = re.findall(r"onConflict:\s*['\"]([^'\"]+)['\"]", s)
    alert_conflicts = [c for c in conflicts if "alert_key" in c]
    if not alert_conflicts:
        out.append("alert-hub.html: the alert dismissal upsert no longer declares an onConflict key on "
                   "alert_key - without it the ack either duplicates rows or fails, and an alert the "
                   "crew handled keeps nagging them")
    for c in alert_conflicts:
        if "actor" in c or "worker" in c:
            out.append(f"alert-hub.html: the dismissal is keyed on '{c}' - it now includes the ACTOR, so "
                       f"acking hides the alert only for the person who acked. Every teammate must ack "
                       f"the same plant condition separately, and the toast promising it is hidden for "
                       f"the whole hive becomes false")
        elif "hive_id" not in c:
            out.append(f"alert-hub.html: the dismissal is keyed on '{c}' with no hive_id - the ack is "
                       f"not scoped to a plant, which crosses the tenant boundary")

    # 2. attribution survives ON THE DISMISSAL ITSELF
    # ★A WHOLE-FILE SEARCH WAS TOO LOOSE AND MADE THIS CLAUSE VACUOUS: `actor: WORKER_NAME` also
    # appears in an UNRELATED upsert at line 987 (with different spacing) and twice inside the
    # explanatory comment. Removing it from every dismissal write still left the file matching, so
    # the negative passed while detecting nothing. The check now reads the dismissal statement.
    dismissals = re.findall(r"from\(\s*['\"]alert_dismissals['\"]\s*\)\s*\.\s*upsert\(\s*\{([^}]*)\}", s)
    if not dismissals:
        out.append("alert-hub.html: no alert_dismissals upsert found - the ack no longer persists, so "
                   "a handled alert returns on the next load")
    for d in dismissals:
        if not re.search(r"actor\s*:", d):
            out.append("alert-hub.html: a dismissal write no longer records actor - a crew-wide "
                       "silencing of a plant alert with nobody's name on it is worse than either "
                       "property alone")
            break

    # 3. ★the sentence must match the scope
    if not re.search(r"hidden for your whole hive", s, re.I):
        out.append("alert-hub.html: the ack toast no longer says the alert is hidden for the WHOLE HIVE - "
                   "a worker tidying what they think is their own view can blind the entire crew to a "
                   "live plant condition. This scope is defensible when stated and indefensible when "
                   "discovered")
    if not re.search(r"under your name|recorded under your name", s, re.I):
        out.append("alert-hub.html: the ack toast no longer says the action is recorded under their "
                   "name - which is what makes a crew-wide scope read as deliberate rather than as "
                   "something that happened to them")

    # 4. the badge converges, and not while nobody is looking
    if not re.search(r"setInterval\(\s*loadAll\s*,\s*\d+\s*\)", s):
        out.append("alert-hub.html: the periodic refresh is gone - a second tab's badge is now stale "
                   "until the person reloads, with nothing telling them so")
    if not re.search(r"visibilitychange", s) or not re.search(r"stopRefresh", s):
        out.append("alert-hub.html: the poll no longer pauses on visibilitychange - a phone in a pocket "
                   "polls a plant database every minute with no reader")
    return out


def _drop_actor(src: str) -> str:
    """Remove ONLY the actor field from each dismissal upsert, leaving the statement intact.

    ★A NEGATIVE THAT DELETES TOO MUCH TESTS THE WRONG CLAUSE. Substituting the whole match with ''
    also removed the `from('alert_dismissals').upsert({` prefix, so the mutant tripped "no upsert
    found" while the case was labelled "losing attribution". It detected something real and proved
    nothing about the clause it named - a vacuity trap wearing a passing grade. Written as a helper
    so the backreference cannot be lost to escaping.
    """
    pat = re.compile(r"(from\(\s*['\"]alert_dismissals['\"]\s*\)\s*\.\s*upsert\(\s*\{[^}]*?)actor\s*:\s*WORKER_NAME\s*,\s*")
    return pat.sub(lambda m: m.group(1), src)

def selftest() -> int:
    src = io.open(SRC, encoding="utf-8", errors="replace").read()
    cases = [("the real alert-hub.html is clean", src, 0)]
    cases.append(("scoping the ack to the actor is caught",
                  src.replace("{ onConflict: 'hive_id,alert_key' }", "{ onConflict: 'hive_id,alert_key,actor' }"), 1))
    cases.append(("losing attribution on the dismissal is caught",
                  _drop_actor(src), 1))
    cases.append(("the toast no longer naming the crew scope is caught",
                  src.replace("hidden for your whole hive", "done"), 1))
    cases.append(("dropping the periodic refresh is caught",
                  src.replace("setInterval(loadAll, 60000)", "null"), 1))
    cases.append(("a poll that never pauses is caught",
                  src.replace("visibilitychange", "_neverfires"), 1))
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
        print("FAIL - alert-hub.html is gone; re-point this gate")
        return 1
    findings = audit(io.open(SRC, encoding="utf-8", errors="replace").read())
    print("the-ack-scope-matches-its-promise - one person's ack silences the alert for the crew, and says so")
    if findings:
        print("\nFAIL - the ack's reach and the sentence describing it have come apart:")
        for f in findings:
            print(f"    {f}")
        return 1
    print("\nPASS - the ack is hive-keyed and attributed, the toast names both, and the badge converges "
          "on a bounded poll that sleeps with the tab.")
    return 0


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
