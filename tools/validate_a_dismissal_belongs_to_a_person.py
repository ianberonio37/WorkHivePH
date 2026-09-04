#!/usr/bin/env python3
"""A dismissal is a person's decision, not the browser's (T121).

MEASURED 2026-08-28. The shared station tablet is this platform's normal deployment - one device,
a crew signing in and out through a shift - and three dismissal flags were stored as the literal
string '1', which belongs to the BROWSER:

  wh_onboarding_dismissed        index.html, the first-run "Getting Started" ladder
  wh_cmms_guide_dismissed        integrations.html, the CMMS setup guide
  wh_guide_link_dismissed_<page> learn-link.js, the "New to this page?" chip on EVERY page

Worker A taps Dismiss; worker B signs in on the same tablet and is never introduced to anything.

★THIS LEAK RUNS THE OPPOSITE DIRECTION FROM ITS SIBLINGS, WHICH IS WHY IT SURVIVED THEM. The draft,
filter and companion-history fixes all stopped A's CONTENT reaching B, so they read as privacy work
and this did not: nothing of A's is exposed here. What crosses the boundary is A's DECISION, and the
cost lands on B as an ABSENCE - no card, no chip, no explanation, nothing on screen to notice. An
absence is the hardest defect class for a person to report and for a gate to see, so it needs the
gate more than the visible ones did, not less.

The onboarding ladder made it sharper still: its three step-checks were ALREADY person-aware
(workerName, jobs, pmDoneToday), so the card knew perfectly well that B had done nothing. It just
never got to run - the flag returned before the check. Correct logic behind a device-wide gate.

THE PROPERTY: a dismissal store must record WHOSE dismissal it is. Reads go through whIsDismissed(),
writes through whSetDismissed(), and a legacy '1' is treated as nobody's - the guide returns once,
which for HELP is the safe direction (re-showing a card costs a tap; hiding it costs the
introduction). sessionStorage flags are exempt: they die with the tab, so they cannot outlive the
person who set them.

TEETH: synthetic negatives - the raw-write, the raw-read, and the helper removed.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The shared helpers must exist for any of this to hold.
UTILS = ROOT / "utils.js"

BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT = re.compile(r"(?m)^\s*//.*$")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)


def _strip_comments(src: str) -> str:
    """Prose ABOUT a raw write is not a raw write.

    Every gate in this family that skipped this step convicted its own subject's explanation -
    the clearest fixes quote what they removed.
    """
    return LINE_COMMENT.sub("", BLOCK_COMMENT.sub(" ", HTML_COMMENT.sub(" ", src)))


# a localStorage write of a dismissal-shaped key that does NOT go through the helper
RAW_WRITE = re.compile(
    r"localStorage\.setItem\(\s*([^,)]*dismiss[^,)]*?)\s*,", re.I)
# a localStorage read of a dismissal-shaped key
RAW_READ = re.compile(
    r"localStorage\.getItem\(\s*([^,)]*dismiss[^,)]*?)\s*\)", re.I)

# files that legitimately define the helpers / registry prose
EXEMPT_NAMES = {"utils.js"}


def _product_files() -> list:
    out = []
    for p in sorted(ROOT.glob("*.html")) + sorted(ROOT.glob("*.js")):
        if p.name in EXEMPT_NAMES:
            continue
        if p.name.startswith(".") or "backup" in p.name or "-test" in p.name:
            continue
        out.append(p)
    return out


def audit_helpers(src: str) -> list:
    out = []
    if "function whIsDismissed" not in src:
        out.append("utils.js: whIsDismissed() is gone - every dismissal flag falls back to the raw "
                   "device-wide read this gate exists to prevent")
    if "function whSetDismissed" not in src:
        out.append("utils.js: whSetDismissed() is gone - dismissals lose their owner stamp")
    if "function whStateOwner" not in src:
        out.append("utils.js: whStateOwner() is gone - the one accessor the owner-stamped stores "
                   "share (drafts, filters, analytics, companion history, dismissals)")
    # the legacy value must NOT count as a dismissal
    body = src[src.find("function whIsDismissed"):][:800] if "function whIsDismissed" in src else ""
    if body and not re.search(r"===\s*['\"]1['\"]\s*\)\s*return\s+false", body):
        out.append("utils.js: whIsDismissed() no longer treats a legacy '1' as nobody's dismissal - "
                   "an unowned flag would again hide help from everyone on a shared device")
    return out


def audit_file(path: Path, src: str) -> list:
    out = []
    clean = _strip_comments(src)
    for m in RAW_WRITE.finditer(clean):
        key = m.group(1).strip()
        # Allowed ONLY as the fallback arm of a helper guard, the same exemption the read rule
        # already carried. The guarded arm writes an unowned value, and whIsDismissed refuses an
        # unowned value - so if utils.js were ever missing, the guide RE-SHOWS rather than hiding
        # from everyone. That is the safe direction, and it is why this arm is not the defect.
        span = clean[max(0, m.start() - 190):m.start()]
        if "whSetDismissed" in span:
            continue
        out.append(f"{path.name}: localStorage.setItem({key[:44]}, ...) writes a dismissal without "
                   f"an owner - use whSetDismissed() so it belongs to the person who dismissed it")
    for m in RAW_READ.finditer(clean):
        key = m.group(1).strip()
        # a raw read is allowed ONLY as the fallback arm of a helper-guarded expression
        span = clean[max(0, m.start() - 190):m.start()]
        if "whIsDismissed" in span:
            continue
        out.append(f"{path.name}: localStorage.getItem({key[:44]}) reads a dismissal without "
                   f"checking WHOSE it is - one worker's dismissal hides the guide from the next")
    return out


def selftest() -> int:
    utils = io.open(UTILS, encoding="utf-8", errors="replace").read()
    cases = [("the real utils.js defines all three helpers", audit_helpers(utils), 0)]
    cases.append(("removing whIsDismissed is caught",
                  audit_helpers(utils.replace("function whIsDismissed", "function _gone")), 1))
    cases.append(("removing whSetDismissed is caught",
                  audit_helpers(utils.replace("function whSetDismissed", "function _gone2")), 1))
    cases.append(("dropping the legacy-'1' rule is caught",
                  audit_helpers(utils.replace("if (v === '1') return false;", "")), 1))

    real = [(p, io.open(p, encoding="utf-8", errors="replace").read()) for p in _product_files()]
    live = []
    for p, s in real:
        live += audit_file(p, s)
    cases.append(("no product file writes or reads a bare dismissal", live, 0))

    # synthetic negatives against a real subject
    ll = ROOT / "learn-link.js"
    lls = io.open(ll, encoding="utf-8", errors="replace").read()
    # ★THE GUARD MUST BE REMOVED, NOT JUST ITS BODY. A first version of these negatives swapped
    # only the helper CALL for a raw one, leaving `typeof whSetDismissed === 'function'` sitting in
    # the same 190-char window - so the fallback exemption swallowed the mutant and both tests
    # passed while detecting nothing. A negative that the exemption absorbs is not a negative.
    raw_write = re.sub(r"if \(typeof whSetDismissed[^\n]*\n\s*else ", "", lls)
    raw_write = raw_write.replace("whSetDismissed(DISMISS_KEY);", "localStorage.setItem(DISMISS_KEY, '1');")
    cases.append(("a raw dismissal WRITE, guard and all, is caught", audit_file(ll, raw_write), 1))
    cases.append(("...and that negative is not vacuous (the guard is really gone)",
                  [] if "typeof whSetDismissed" not in _strip_comments(raw_write) else ["guard survived the mutation"], 0))

    raw_read = re.sub(r"if \(typeof whIsDismissed[^\n]*\n\s*else if ", "if ", lls)
    cases.append(("a raw dismissal READ, guard and all, is caught", audit_file(ll, raw_read), 1))
    cases.append(("...and that negative is not vacuous (the guard is really gone)",
                  [] if "typeof whIsDismissed" not in _strip_comments(raw_read) else ["guard survived the mutation"], 0))
    bad = 0
    for label, findings, want in cases:
        ok = (len(findings) == 0) if want == 0 else (len(findings) >= want)
        if not ok:
            bad += 1
        print(f"  {'ok  ' if ok else 'MISS'} {label} (findings={len(findings)})")
    print(f"\nSELFTEST {'FAILED' if bad else 'ok'} - {len(cases) - bad}/{len(cases)}")
    return 1 if bad else 0


def main() -> int:
    if not UTILS.exists():
        print("FAIL - utils.js is gone; re-point this gate")
        return 1
    findings = audit_helpers(io.open(UTILS, encoding="utf-8", errors="replace").read())
    files = _product_files()
    for p in files:
        findings += audit_file(p, io.open(p, encoding="utf-8", errors="replace").read())
    print("a-dismissal-belongs-to-a-person - one worker's Dismiss does not silence the next one's guide")
    print(f"  scanned: {len(files)} product files + the shared helpers")
    if findings:
        print("\nFAIL - a dismissal belongs to the browser, so it outlives the person who made it:")
        for f in findings:
            print(f"    {f}")
        return 1
    print("\nPASS - every dismissal records whose it is; a new person on a shared device is still introduced.")
    return 0


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
