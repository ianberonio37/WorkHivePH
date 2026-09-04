#!/usr/bin/env python3
"""A printed artifact that shortens free text must SAY it shortened it.

★THE GAP THIS EXISTS FOR (T49). export-reads-its-own-set holds the row axis: a CSV must not
inherit the render buffer's cap, so no ROW goes missing. This holds the other axis on the same
artifact — the CELL. project-report.html renders each daily-progress log with
`.slice(0, 200)` and nothing appended, and that page exists to be PRINTED and handed to a
stakeholder. On paper there is no hover, no expand, no scroll: a 350-character blocker arrived
as a complete-looking 200-character sentence, cut mid-word, and the reader had no way to know
anything had been removed. Blockers is the field carrying WHY a project is late.

A cap on a printed column is legitimate — the column is real and text has to fit. What is not
legitimate is a SILENT one. So the rule is not "never truncate", it is "truncate out loud".

THE ORACLE, per printed surface: every free-text slice that feeds printed markup must be
accompanied by a disclosure marker in the same helper, and the marker must be conditional
(a complete value must carry NO false alarm), and it must survive @media print.

TEETH: synthetic negatives — a bare slice, an unconditional marker, and a marker that a print
rule would hide are each detected. This is a proactive guard (the surface is fixed), so its
teeth are manufactured rather than resurrected, the same discipline
validate_bounded_list_offers_the_rest.py records.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Surfaces whose whole purpose is to be printed / PDF'd and handed to someone outside the app.
PRINTED_SURFACES = ["project-report.html"]

# A free-text cell cap: .slice(0, N) with N large enough to be prose rather than a code/label.
SLICE_RE = re.compile(r"\.slice\(\s*0\s*,\s*(\d{2,})\s*\)")
PROSE_MIN = 40           # below this it is an id, a code or a badge, not prose
MARKER_RE = re.compile(r"shortened|truncat|…|\.\.\.", re.I)


def audit(src: str, fname: str):
    """Return (findings, facts) for one printed surface."""
    findings, facts = [], {}

    # 1) Does a disclosure helper exist, and is it CONDITIONAL?
    helper = re.search(r"function\s+clip\s*\(([^)]*)\)\s*\{(.*?)\n\}", src, re.S)
    facts["has_helper"] = bool(helper)
    if not helper:
        findings.append(f"{fname}: no clip() disclosure helper — a printed cap would be silent")
        return findings, facts
    body = helper.group(2)
    facts["helper_conditional"] = bool(re.search(r"if\s*\(.*?length\s*<=?\s*", body, re.S))
    facts["helper_marks"] = bool(MARKER_RE.search(body))
    if not facts["helper_conditional"]:
        findings.append(f"{fname}: clip() is unconditional — a complete value would carry a false alarm")
    if not facts["helper_marks"]:
        findings.append(f"{fname}: clip() shortens without appending any marker")

    # 2) No BARE prose slice may reach printed markup — every one must go through the helper.
    #    Only slices inside a `${...}` interpolation count: `.slice(0,10)` on an ISO date string
    #    is a date format, not a truncated sentence.
    bare = []
    for m in re.finditer(r"\$\{[^}]*" + SLICE_RE.pattern + r"[^}]*\}", src):
        n = int(re.search(r"\.slice\(\s*0\s*,\s*(\d{2,})\s*\)", m.group(0)).group(1))
        frag = m.group(0)
        if n < PROSE_MIN:
            continue
        if "toISOString" in frag or "clip(" in frag:
            continue
        bare.append(frag.strip()[:70])
    facts["bare_prose_slices"] = len(bare)
    for b in bare:
        findings.append(f"{fname}: prose shortened with no disclosure -> {b}")

    # 3) The marker must PRINT. A disclosure that only survives on screen discloses nothing to
    #    the person holding the printout.
    printed_ok = True
    for cls in ("clip-mark", "clip-note"):
        hidden = re.search(r"@media print\s*\{[^}]*\." + cls + r"[^}]*display:\s*none", src, re.S)
        if hidden:
            printed_ok = False
            findings.append(f"{fname}: .{cls} is hidden in @media print — the disclosure never reaches paper")
    facts["marker_prints"] = printed_ok
    return findings, facts


def selftest() -> int:
    """Synthetic negatives — one per way the disclosure can fail."""
    good = io.open(ROOT / "project-report.html", encoding="utf-8").read()
    cases = [
        ("the real surface is clean", good, 0),
        ("bare prose slice detected",
         good.replace("<td>${clip(l.notes)}</td>", "<td>${e((l.notes || '').slice(0, 200))}</td>"), 1),
        ("unconditional helper detected",
         good.replace("if (v.length <= LOG_TEXT_CAP) return e(v);", "/* removed */"), 1),
        ("marker hidden in print detected",
         good.replace("@media print {", "@media print { .clip-note { display: none; }", 1), 1),
        # NOTE: this negative must strip EVERY marker token the helper carries — the visible
        # "… (shortened)" AND the title attribute that also says "shortened". A first cut replaced
        # a string that did not appear in the source at all, so it silently tested the UNCHANGED
        # file and reported no findings: a negative control that never negated anything.
        ("helper with no marker detected",
         good.replace(
             '''return e(v.slice(0, LOG_TEXT_CAP).trimEnd()) + '<span class="clip-mark" title="shortened to fit this column">… (shortened)</span>';''',
             "return e(v.slice(0, LOG_TEXT_CAP).trimEnd());"), 1),
    ]
    bad = 0
    for name, src, want_min in cases:
        f, _ = audit(src, "project-report.html")
        ok = (len(f) == 0) if want_min == 0 else (len(f) >= want_min)
        if not ok:
            bad += 1
        print(f"  {'ok  ' if ok else 'MISS'} {name} (findings={len(f)})")
    print(f"\nSELFTEST {'FAILED' if bad else 'ok'} — {len(cases) - bad}/{len(cases)}")
    return 1 if bad else 0


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    all_findings = []
    for fname in PRINTED_SURFACES:
        p = ROOT / fname
        if not p.exists():
            all_findings.append(f"{fname}: printed surface missing from the repo")
            continue
        f, facts = audit(io.open(p, encoding="utf-8").read(), fname)
        all_findings += f
        print(f"  {fname}: helper={facts.get('has_helper')} conditional={facts.get('helper_conditional')} "
              f"marks={facts.get('helper_marks')} bare_prose_slices={facts.get('bare_prose_slices')} "
              f"prints={facts.get('marker_prints')}")
    if all_findings:
        print("\nFAIL — a printed artifact shortens text without telling its reader:")
        for f in all_findings:
            print(f"  - {f}")
        return 1
    print("\nPASS — every printed cap discloses itself, and only when it actually bites.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
