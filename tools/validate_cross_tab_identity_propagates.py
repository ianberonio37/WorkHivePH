#!/usr/bin/env python3
"""An identity change in ONE tab must reach the others (T148).

Two events change what EVERY open tab is allowed to show, and both happen in a single tab:

  1. SIGN-OUT  — the other tabs sit painted and stale, looking signed in while identity is gone.
  2. HIVE SWITCH — the other tabs keep rendering the PREVIOUS hive's figures. Worse than an
     ordinary stale number, because the person just switched and believes they are looking at the
     new plant. This is the cross-tenant confusion T51 exists to prevent.

MEASURED with two real tabs (2026-08-27): sign-out already propagated and did it well, sending the
other tab to index.html?signin=1&reason=othertab&return=<page> — it noticed, named the reason, and
kept the destination. The hive switch propagated NOT AT ALL: storage said Manila Electronics
Assembly while the other tab still rendered Baguio Textile Mills.

★THE HIVE HANDLER TELLS RATHER THAN RELOADS, and the gate enforces that distinction. Auto-reloading
somebody's other tab would discard a half-typed entry to fix a DISPLAY problem, against a platform
whose whole posture on interruption is that typed work survives. So the rule is: react to the
switch, and do it WITHOUT calling reload() unprompted — a reload the person CHOOSES (a button) is
correct; a reload done to them is not.

★AND THE NOTICE MUST READ THE NAME LATE. A switch writes several keys and storage events arrive one
per key in write order, so reading wh_hive_name the instant the ID event lands reads the name the
switch has not replaced yet — the first cut said "You switched to Baguio... still showing Baguio",
naming one hive twice, which reads like a bug in the switch rather than a stale tab.

TEETH: synthetic negatives — each clause removed in turn.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "session-timeout.js"

CLAUSES = [
    ("storage-listener", r"addEventListener\(\s*['\"]storage['\"]",
     "no cross-tab storage listener at all - nothing in this tab can learn what another tab did"),
    ("signout-propagates", r"e\.key\s*===\s*['\"]wh_last_worker['\"][\s\S]{0,200}?_signInUrlWithReturn",
     "a sign-out in another tab does not redirect this one - it sits painted and stale, looking signed in"),
    ("signout-names-reason", r"_signInUrlWithReturn\(\s*['\"]othertab['\"]\s*\)",
     "the sign-out redirect does not name its REASON - arriving at a sign-in screen with no "
     "explanation is indistinguishable from being logged out at random"),
    ("hive-switch-propagates", r"e\.key\s*===\s*['\"]wh_active_hive_id['\"]",
     "a hive switch in another tab is ignored - this tab keeps rendering the previous hive's figures"),
    ("compares-mounted-hive", r"_mountedHiveId",
     "the handler does not compare against the hive this tab MOUNTED with - by the time the event "
     "fires localStorage already holds the new value, so reading it then compares it to itself"),
    ("name-read-is-deferred", r"setTimeout\(\s*function\s*\(\)\s*\{\s*_showHiveSwitchNotice",
     "the notice is built synchronously on the ID event, so wh_hive_name is read before the switch "
     "has written it and the notice names the same hive twice"),
]

FORBIDDEN = [
    (r"e\.key\s*===\s*['\"]wh_active_hive_id['\"][\s\S]{0,400}?location\.reload\(\)",
     "the hive-switch handler calls reload() itself - that discards a half-typed entry in someone's "
     "other tab to fix a display problem. Offer a Reload the person CHOOSES."),
]


def audit(src: str) -> list:
    out = [f"session-timeout.js: {why}" for _, pat, why in CLAUSES if not re.search(pat, src)]
    for pat, why in FORBIDDEN:
        if re.search(pat, src):
            out.append(f"session-timeout.js: {why}")
    return out


def selftest() -> int:
    src = io.open(SRC, encoding="utf-8", errors="replace").read()
    cases = [("the real session-timeout.js is clean", src, 0)]
    for name, pat, _ in CLAUSES:
        # count=0 (ALL occurrences): _mountedHiveId appears both at its declaration and at the
        # comparison, so removing only the first left the pattern still matchable and the negative
        # passed vacuously - a control that does not fully remove the thing controls nothing.
        cases.append((f"missing {name} is caught", re.sub(pat, "__REMOVED__", src, count=0), 1))
    # and the forbidden shape: a handler that reloads the other tab on its own
    cases.append(("an unprompted reload in the hive handler is caught",
                  src.replace("setTimeout(function () { _showHiveSwitchNotice(); }, 250);",
                              "window.location.reload();"), 1))
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
        print("FAIL - session-timeout.js is gone; re-point this gate")
        return 1
    findings = audit(io.open(SRC, encoding="utf-8", errors="replace").read())
    print("cross-tab-identity-propagates - a sign-out or hive switch in one tab must reach the others")
    print(f"  clauses checked: {len(CLAUSES)} required + {len(FORBIDDEN)} forbidden")
    if findings:
        print("\nFAIL - another tab can be left showing something it should not:")
        for f in findings:
            print(f"    {f}")
        return 1
    print("\nPASS - sign-out redirects with its reason, and a hive switch tells the other tabs without "
          "reloading them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
