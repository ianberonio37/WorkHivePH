#!/usr/bin/env python3
"""validate_kpi_evidence_links.py — two T-walk locks: a KPI must count what it claims, and the
headline reliability figure must carry its evidence.

1. CAP-AS-TOTAL (T9, walked 2026-09-02): logbook's "Jobs closed out" strip derived its denominator
   from the LOADED WINDOW (_allEntries.length, row-capped), so a worker with 317 entries read a
   total of 200 — a cap shown as a total ([[feedback_a_row_cap_is_not_pagination]] class). Fixed:
   the strip prefers _mineTrueTotal/_mineTrueOpen (count:exact, the same source as the pills);
   verified live: "JOBS CLOSED OUT 313 of 317" with the window at 0. Lock: the lb-progress block
   must reference _mineTrueTotal, and the count-fetch must set it from the exact-count query.

2. DRILL-TO-EVIDENCE (T47, walked 2026-09-02): analytics' worst-MTBF card was accurate (0.6d
   traced to 137 breakdowns/90d by independent psql recompute) but a DEAD END — a skeptical
   engineer could only trust it or hand-count. Fixed: #an-card-mtbf is wired as a role=link
   (click/Enter -> logbook.html?view=team&q=<asset>, the T43-proven deep-link machinery);
   verified live: click landed on ?view=team&q=CT-001 with 28 evidence cards rendered. Lock:
   the wiring block must exist (getElementById('an-card-mtbf') + logbook.html?view=team&q=).

Static, fast, resurrection teeth: each pre-fix shape reddens in --self-test.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK_NAMES = ["kpi-evidence-links"]

CAP_FIX_RE = re.compile(r"_haveTrue\s*\?\s*_mineTrueTotal\s*:\s*_allEntries\.length")
CAP_SET_RE = re.compile(r"_mineTrueTotal\s*=\s*tRes\.count")
DRILL_RE = re.compile(r"getElementById\(\s*'an-card-mtbf'\s*\)[\s\S]{0,900}?logbook\.html\?view=team&q=")
# T26 S2: the worst-MTBF figure must NAME its window beside itself (4.7d here vs 8d cal-time in
# the workbench = two methods under one name; qualifier-beside-figure).
WINDOW_RE = re.compile(r"between failures\$\{basis\} · 90d window")


def problems_for(logbook_src: str, analytics_src: str) -> list[str]:
    out = []
    if not CAP_FIX_RE.search(logbook_src):
        out.append("logbook.html: the lb-progress strip no longer prefers _mineTrueTotal over the "
                   "loaded window — the denominator is a row cap again (a cap shown as a total)")
    if not CAP_SET_RE.search(logbook_src):
        out.append("logbook.html: _mineTrueTotal is no longer set from the exact-count query — the "
                   "strip's 'true total' would be stale/null")
    if not DRILL_RE.search(analytics_src):
        out.append("analytics.html: the worst-MTBF card is no longer wired to its evidence "
                   "(an-card-mtbf -> logbook.html?view=team&q=) — the KPI is a dead end again")
    if not WINDOW_RE.search(analytics_src):
        out.append("analytics.html: the worst-MTBF card no longer names its 90d window beside the "
                   "figure — two methods share one metric name across pages again (T26 S2)")
    return out


def main() -> int:
    lb = io.open(ROOT / "logbook.html", encoding="utf-8", errors="replace").read()
    an = io.open(ROOT / "analytics.html", encoding="utf-8", errors="replace").read()
    bad = problems_for(lb, an)
    if bad:
        print("FAIL kpi-evidence-links:")
        for p in bad:
            print("    " + p)
        return 1
    print("PASS kpi-evidence-links — logbook's progress strip counts the TRUE worker totals "
          "(count:exact, not the loaded window) and analytics' worst-MTBF card drills to its "
          "logbook evidence (?view=team&q=<asset>).")
    return 0


def self_test() -> int:
    lb = io.open(ROOT / "logbook.html", encoding="utf-8", errors="replace").read()
    an = io.open(ROOT / "analytics.html", encoding="utf-8", errors="replace").read()
    fails = []
    if problems_for(lb, an):
        fails.append("HEAD should PASS")
    # resurrection: the pre-fix shapes must redden
    pre_cap = lb.replace("_haveTrue ? _mineTrueTotal : _allEntries.length", "_allEntries.length")
    if not any("row cap again" in p for p in problems_for(pre_cap, an)):
        fails.append("the window-denominator shape must redden")
    pre_drill = re.sub(r"getElementById\(\s*'an-card-mtbf'\s*\)", "getElementById('an-card-mtbf-GONE')", an)
    if not any("dead end again" in p for p in problems_for(lb, pre_drill)):
        fails.append("the unwired-card shape must redden")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_kpi_evidence_links self-test (cap-denominator + unwired-card both redden; HEAD clean)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
