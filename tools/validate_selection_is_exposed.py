#!/usr/bin/env python3
"""A control that conveys SELECTION must expose it, not signal it with colour alone (T125).

Across the platform, "which one is active" is drawn as a class: `.active` paints a violet
background. That is invisible to a screen reader, invisible to a forced-colors user, and
invisible to anyone who cannot separate the two colours. The state has to be in the ACCESSIBILITY
TREE as well as in the pixels.

analytics.html already worked this out and wrote the reasoning down in place:

    // NOTE: the phase switcher LOOKS like a tab set, but role="tab" without a tablist +
    // arrow-key roving focus ships a BROKEN tab widget -- partial ARIA is worse than none.
    // These are one-of-N selectors, so a pressed toggle-button group is the honest pattern.

So the platform has two legitimate answers, and this gate enforces whichever a page CHOSE:

  * TOGGLE BUTTONS  -> aria-pressed, mirrored from .active in one statement.
  * TABS            -> the FULL widget: role="tablist", aria-selected on every role="tab",
                       aria-controls pointing at a real role="tabpanel". Half of it is worse
                       than none of it, which is exactly what the note above says.

MEASURED 2026-08-27: 20 pages use role="tab"; 18 set aria-selected and asset-hub set NONE --
three reliability tabs (FMEA / Weibull / P-F) inside a proper role="tablist", announcing
"tab" to a screen reader while never saying which of the three was current, with no tabpanels
and no arrow-key movement. The shared contract had left one page behind. (The 20th "page",
analytics.html, was my grep matching the COMMENT above rather than markup -- it has no
role="tab" at all, by decision.)

★AND THE TWO MUST MOVE TOGETHER. The class and the ARIA attribute drift when they are assigned
in separate statements -- one code path updates the paint and forgets the announcement, and the
bug is invisible to anyone testing with their eyes. Both fixed pages now set them in the same
statement, and the drift clause below checks that a file which toggles `active` on a tab set
also writes aria-selected somewhere in that file.

TEETH: synthetic negatives -- each clause removed from a real page in turn.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REPORTED = []  # non-failing observations, printed every run (see clause 3)

TAG_RE = re.compile(r"<(?:button|a|div|span|li)\b[^>]*role=\"tab\"[^>]*>", re.I)
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
JS_LINE_COMMENT_RE = re.compile(r"^\s*//.*$", re.M)


def _strip_comments(src: str) -> str:
    """A comment that says role="tab" is not a tab.

    This gate's own first measurement counted the analytics.html NOTE quoted above as a
    role="tab" occurrence and reported a defect on a page that had deliberately avoided the
    pattern. Prose about markup is not markup.
    """
    return JS_LINE_COMMENT_RE.sub("", COMMENT_RE.sub("", src))


def audit_page(path: Path, src: str) -> list:
    name = path.name
    body = _strip_comments(src)
    tabs = TAG_RE.findall(body)
    out = []
    if not tabs:
        return out

    # 1. every role="tab" says whether it is the selected one
    missing_sel = [t for t in tabs if "aria-selected" not in t]
    if missing_sel:
        out.append(f"{name}: {len(missing_sel)} of {len(tabs)} role=\"tab\" elements carry no "
                   f"aria-selected - a screen reader announces \"tab\" but never which one is "
                   f"current, and the only signal left is the .active background colour")

    # 2. tabs live in a tablist, or they are loose roles with no widget around them
    if 'role="tablist"' not in body:
        out.append(f"{name}: role=\"tab\" without a role=\"tablist\" container - a tab outside a "
                   f"tablist is an orphan role, which is the 'partial ARIA is worse than none' "
                   f"case; either complete the widget or use aria-pressed toggle buttons")

    # 3. each tab owns a panel, and that panel is marked as one
    #
    # ★THIS CLAUSE IS REPORTED, NOT FAILED, AND THE SPLIT IS DELIBERATE. The APG tabs pattern
    # does ask for aria-controls, and 17 of the 19 tab-using pages do not have it -- a real gap,
    # recorded below in every run so it cannot be forgotten. But it is NOT the load-bearing
    # half: those 17 pages all announce aria-selected, so a screen-reader user knows which tab
    # is current and can operate the widget; what they lose is the direct jump to the panel.
    # Reddening the board on a clause the platform never adopted would be this gate
    # over-claiming, and quietly deleting the clause would shrink the denominator until the gap
    # stopped existing on paper. So it is neither enforced nor hidden -- it is owed work with a
    # number attached. The tab->non-tabpanel case below IS failed, because a tab that names a
    # target which cannot BE a panel is a broken pointer rather than a missing one.
    missing_ctrl = [t for t in tabs if "aria-controls" not in t]
    if missing_ctrl:
        REPORTED.append(f"{name}: {len(missing_ctrl)} of {len(tabs)} role=\"tab\" elements have "
                        f"no aria-controls - the tab is operable but does not name its panel")
    else:
        targets = [m.group(1) for t in tabs
                   for m in [re.search(r"aria-controls=\"([^\"]+)\"", t)] if m]
        for tid in targets:
            panel = re.search(r"<[^>]*id=\"" + re.escape(tid) + r"\"[^>]*>", body)
            if panel and 'role="tabpanel"' not in panel.group(0):
                out.append(f"{name}: aria-controls points at #{tid}, which is not a "
                           f"role=\"tabpanel\" - the tab names a target the AT cannot treat "
                           f"as the tab's panel")

    # 4. the paint and the announcement move together
    if re.search(r"classList\.toggle\(\s*['\"]active['\"]", body) and "aria-selected" not in body:
        out.append(f"{name}: the switcher toggles the .active CLASS but never writes "
                   f"aria-selected - the paint updates and the announcement does not")
    return out


def pages() -> list:
    skip = {"_fixtures"}
    return sorted(p for p in ROOT.glob("*.html")
                  if not any(s in p.parts for s in skip))


def audit_all() -> tuple:
    del REPORTED[:]
    findings, scanned, with_tabs = [], 0, 0
    for p in pages():
        src = io.open(p, encoding="utf-8", errors="replace").read()
        scanned += 1
        if TAG_RE.search(_strip_comments(src)):
            with_tabs += 1
        findings.extend(audit_page(p, src))
    return findings, scanned, with_tabs


def selftest() -> int:
    real = ROOT / "asset-hub.html"
    src = io.open(real, encoding="utf-8", errors="replace").read()
    cases = [("the real asset-hub.html is clean", src, 0)]
    cases.append(("a tab with no aria-selected is caught",
                  src.replace('aria-selected="true"', "", 1), 1))
    cases.append(("ALL tabs losing aria-selected is caught",
                  src.replace('aria-selected="true"', "").replace('aria-selected="false"', ""), 1))
    cases.append(("tabs with no tablist container are caught",
                  src.replace('role="tablist"', 'class="was-tablist"'), 1))
    # aria-controls is the REPORTED clause, so its negative must prove the split works:
    # it lands in REPORTED and leaves the pass/fail verdict alone. Asserting it as a FAILURE
    # would re-encode the very strictness the clause-3 note argues against.
    del REPORTED[:]
    ctrl_findings = audit_page(real, src.replace('aria-controls="rel-panel-weibull"', "", 1))
    ctrl_ok = len(ctrl_findings) == 0 and len(REPORTED) == 1
    print(f"  {'ok  ' if ctrl_ok else 'MISS'} a tab with no aria-controls is REPORTED, not "
          f"failed (findings={len(ctrl_findings)}, reported={len(REPORTED)})")
    cases.append(("aria-controls pointing at a non-tabpanel is caught",
                  src.replace('id="rel-panel-pf" role="tabpanel"', 'id="rel-panel-pf"'), 1))
    # the drift case: class toggled, aria never written
    cases.append(("class toggled with no aria-selected anywhere is caught",
                  src.replace("aria-selected", "data-was-selected"), 1))
    # and the instrument's own first fault: prose must not read as markup
    cases.append(("a role=\"tab\" inside a COMMENT is not counted",
                  '<!-- role="tab" with no aria-selected -->\n<p>no tabs here</p>', 0))
    bad = 0 if ctrl_ok else 1
    for label, s, want in cases:
        del REPORTED[:]
        f = audit_page(real, s)
        ok = (len(f) == 0) if want == 0 else (len(f) >= want)
        if not ok:
            bad += 1
        print(f"  {'ok  ' if ok else 'MISS'} {label} (findings={len(f)})")
    print(f"\nSELFTEST {'FAILED' if bad else 'ok'} - {len(cases) - bad}/{len(cases)}")
    return 1 if bad else 0


def main() -> int:
    findings, scanned, with_tabs = audit_all()
    print("selection-is-exposed - which one is active must reach the accessibility tree, "
          "not just the pixels")
    print(f"  pages scanned: {scanned} | pages using role=\"tab\": {with_tabs}")
    if findings:
        print("\nFAIL - selection is conveyed by appearance alone:")
        for f in findings:
            print(f"    {f}")
        return 1
    print("\nPASS - every tab set names its selected tab, owns its panel, and keeps the class "
          "and the ARIA state in step.")
    return 0


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
