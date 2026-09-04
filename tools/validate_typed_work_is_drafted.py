#!/usr/bin/env python3
"""Every committing surface that holds TYPED work must be able to give it back (T38).

★THE PROPERTY. A session dies, a phone is backgrounded, a tab is killed. On a page where the
person only READ, that costs a reload. On a page where they TYPED, it costs their words — and the
platform's whole promise on a plant floor is that the work you did is the work that is recorded.
So: a page that both writes rows and offers a textarea must carry a draft mechanism.

★AND THE GATE'S OWN FIRST CENSUS WAS WRONG, WHICH IS WHY THE RULE IS SHAPED THIS WAY. Checking for
`whAutoSaveDraft` alone reported logbook.html as UNPROTECTED — the flagship committing surface of
the entire platform, which has carried its own DRAFT_KEY / saveDraft / restoreDraft trio for
months. Absence of the shared HELPER is not absence of the GUARD. A gate that recognises only one
implementation does not measure the property, it measures a naming convention, and it would have
sent someone to "fix" a page that was already correct. So both forms count, and a page is a
finding only when NEITHER is present.

MEASURED at the time of writing: 13 committing surfaces with typed work; 11 use the shared helper,
logbook uses its own mechanism, and resume.html had NOTHING — its #jd-input holds a job
description the person PASTED from elsewhere, which is precisely the work that is expensive to
reproduce. Fixed, and proven live: the paste survives a full reload byte-for-byte.

TEETH: synthetic negatives — a page with typed work and no mechanism at all, and (the important
one) a page whose protection is page-local rather than the shared helper, which must PASS.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

WRITES = re.compile(r"\.insert\(")
TYPED = re.compile(r"<textarea")
SHARED = "whAutoSaveDraft"
# A page-local draft mechanism, in any of the spellings this codebase actually uses.
LOCAL = re.compile(r"DRAFT_KEY|restoreDraft|saveDraft|wh_draft", re.I)

# Pages that write and offer a textarea but are NOT a person composing their own work.
# Exempted by REASON, and each reason is checkable against the page.
EXEMPT = {
    "assistant.html": "a chat turn is SENT immediately; there is no compose-then-commit gap to lose",
}


def surfaces() -> list:
    out = []
    for p in sorted(ROOT.glob("*.html")):
        if p.name.startswith("index-"):
            continue
        try:
            s = io.open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if not (WRITES.search(s) and TYPED.search(s)):
            continue
        out.append((p.name, SHARED in s, bool(LOCAL.search(s))))
    return out


def audit(rows) -> list:
    findings = []
    for name, shared, local in rows:
        if name in EXEMPT:
            continue
        if not shared and not local:
            findings.append(f"{name}: writes rows and takes typed input, but carries NO draft "
                            f"mechanism - an interruption costs the person their words")
    return findings


def selftest() -> int:
    cases = [
        ("a page with the shared helper passes", [("a.html", True, False)], 0),
        ("a page with its OWN mechanism passes (logbook's shape)", [("b.html", False, True)], 0),
        ("a page with neither is caught", [("c.html", False, False)], 1),
        ("the real roster is clean", surfaces(), 0),
    ]
    bad = 0
    for name, rows, want in cases:
        f = audit(rows)
        ok = (len(f) == 0) if want == 0 else (len(f) >= want)
        if not ok:
            bad += 1
        print(f"  {'ok  ' if ok else 'MISS'} {name} (findings={len(f)})")
    print(f"\nSELFTEST {'FAILED' if bad else 'ok'} - {len(cases) - bad}/{len(cases)}")
    return 1 if bad else 0


def main() -> int:
    rows = surfaces()
    if not rows:
        print("FAIL - no committing surface found at all; this gate would be vacuous")
        return 1
    findings = audit(rows)
    shared = sum(1 for _, s, _ in rows if s)
    local = sum(1 for _, s, l in rows if l and not s)
    print("typed-work-is-drafted - a page that writes rows and takes typed input must keep a draft")
    print(f"  committing surfaces with typed work: {len(rows)}  "
          f"(shared helper {shared}, own mechanism {local}, exempt {len(EXEMPT)})")
    if findings:
        print("\nFAIL - typed work with nothing to give it back:")
        for f in findings:
            print(f"    {f}")
        return 1
    print("\nPASS - every committing surface with typed work can return it after an interruption.")
    return 0


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
