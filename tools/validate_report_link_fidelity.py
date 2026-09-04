#!/usr/bin/env python3
"""report-link-fidelity — T106: an emailed report's link keeps its subject (2026-08-26).

THE DEFECT. Every "View in WorkHive" link in send-report-email pointed at a bare
page root. A PM Overdue report — a document whose entire subject IS the overdue
set — landed its reader on the unfiltered schedule, and both logbook reports
landed on that page's default MINE view while the report itself is hive-wide.
That is T19's two-windows-one-metric mismatch arriving by email, and it lands on
whoever the supervisor forwarded the report to.

WHAT THIS ASSERTS, and deliberately what it does not:

  1. EVERY link in REPORT_META targets a page that EXISTS on disk. A link into a
     renamed page is a dead end reached from someone's inbox, where nobody can
     press Retry.
  2. EVERY query parameter a link carries is one the TARGET PAGE ACTUALLY READS,
     checked against substrate/reference/param_route_registry.json — the
     generated enumeration of every URLSearchParams read on every served page.
     This is the assertion that matters: a link decorated with ?window=7d would
     look more specific while doing nothing, which is worse than a bare link
     because it reads as context that was never delivered.
  3. The two links whose target pages DO read params carry one. pm-scheduler
     reads filter/cat and logbook reads status/view/cat/q, so a report about the
     overdue set or about the hive's last 8 hours has somewhere to point.

★NOT ASSERTED: that every report type carries a param. Five of the eight target
analytics.html and project-manager.html, which read NO query params at all, so
their links are already as specific as those pages allow. Demanding a param
there would push someone to invent one that does nothing — exactly the failure
in assertion 2. A page limit is recorded as a page limit.

Static: reads two files and a registry. No stack, no network.

Usage: python tools/validate_report_link_fidelity.py
"""
import io
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
FN = ROOT / "supabase" / "functions" / "send-report-email" / "index.ts"
REG = ROOT / "substrate" / "reference" / "param_route_registry.json"

# the report types whose target page reads params — these must carry one
MUST_CARRY = {"pm_overdue", "failure_digest", "shift_handover"}


def main() -> int:
    if not FN.exists():
        print(f"SKIP report-link-fidelity — {FN.name} not found")
        return 0
    src = io.open(FN, encoding="utf-8", errors="replace").read()
    reg = json.loads(io.open(REG, encoding="utf-8").read())
    routes = reg.get("routes", reg)

    block = re.search(r"const REPORT_META[^{]*\{(.*?)\n\};", src, re.S)
    if not block:
        print("FAIL report-link-fidelity — REPORT_META not found; the link table moved or was renamed.")
        return 1

    entries = re.findall(r"(\w+):\s*\{[^}]*?link:\s*\"([^\"]+)\"", block.group(1))
    if not entries:
        print("FAIL report-link-fidelity — REPORT_META parsed to zero links; the capture is wrong, not the table.")
        return 1

    fails = []
    carried = set()
    for kind, url in entries:
        parsed = urlparse(url)
        page = parsed.path.lstrip("/") or "index.html"
        if not (ROOT / page).exists():
            fails.append(f"{kind}: links to {page}, which does not exist on disk — a dead end from an inbox")
            continue
        params = list(parse_qs(parsed.query).keys())
        known = routes.get(page) or []
        for p in params:
            if p not in known:
                fails.append(
                    f"{kind}: ?{p}= is not a parameter {page} reads (it reads: {', '.join(known) or 'none'}) "
                    f"— a link that looks specific and delivers nothing is worse than a bare one")
        if params:
            carried.add(kind)
        print(f"  {kind:<20} {page:<24} {('?' + '&'.join(params)) if params else '(no params — page reads: ' + (', '.join(known) or 'none') + ')'}")

    missing = MUST_CARRY - carried
    if missing:
        fails.append(
            "these report types target pages that DO read params but carry none: "
            + ", ".join(sorted(missing))
            + " — the report's own subject is available and is being dropped")

    if fails:
        print("FAIL report-link-fidelity:")
        for f in fails:
            print("    - " + f)
        return 1
    print(f"PASS report-link-fidelity — {len(entries)} report links, every target exists, every param is one "
          f"its page reads, and all {len(MUST_CARRY)} links that can carry their subject do.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
