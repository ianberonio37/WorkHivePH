#!/usr/bin/env python3
"""export-reads-its-own-set - T129/T49: the file that leaves the building must be complete.

A logbook export is the artifact an auditor reads, and it is the one place where "looked complete
and was not" cannot be caught by the reader: a person can see that a LIST is short, because the
screen shows a Load more button, but a CSV carries no total, no window and no hint of omission.

★THE RECORDED INCIDENT: the team-branch export handed over `_teamEntries` - only what the feed had
already fetched, one TEAM_PAGE batch of 30 plus whatever Load more had added - while the page said
"517 entries". A supervisor exporting a filtered team view for a DOLE/ISO trail got a file that
looked whole. The mine-branch had been fixed in an earlier arc; the team branch was the one nobody
had walked.

★WHAT IS ASSERTED, and why each half is here:
  1. every export reads its OWN set by PAGING (a loop with .range), not by reusing the feed's array
     - the second an export sources from a render buffer it inherits that buffer's cap;
  2. the paging carries a TOTAL order (a sort key plus a tiebreak), because a non-total order over a
     paged read can repeat one row and drop another entirely - a file that is the right LENGTH and
     the wrong CONTENTS, which is worse than a short one;
  3. the property is NON-VACUOUS: the database must actually hold more rows for one hive than a
     single page, or this gate would pass on an empty table and prove nothing.

★IT NAMES THE FEED ARRAY IT FORBIDS rather than pattern-matching "looks like an export", because
the failure was specific and mechanical: `_teamEntries` is the render buffer, and handing it to a
writer is the whole bug in one identifier.

Re-drive: python tools/validate_export_reads_its_own_set.py
"""
import io
import os
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
CONTAINER = os.environ.get("WH_DB_CONTAINER", "supabase_db_workhive")
FEED_BUFFERS = ("_teamEntries", "_mineEntries", "entriesCache")


def _body_of(src: str, name: str):
    """The function's OWN body, delimited by matching braces.

    ★A FIXED CHARACTER WINDOW GOT THIS WRONG FIRST, and wrongly: reading 4000 characters from
    `const _exportTeamAll` ran past its end, through the next function, and into the click handler -
    so the gate reported BOTH exporters as sourcing from the feed's render buffer when neither does.
    One hit was a COMMENT describing the old bug; the other was the handler's announced fallback.
    Two false accusations from one lazy delimiter. A window sized to today's code is wrong the day
    someone documents something. [[feedback_fixed_char_window_validator_is_brittle]]
    """
    i = src.find(f"const {name}")
    if i == -1:
        return None
    open_brace = src.find("{", i)
    if open_brace == -1:
        return None
    depth, j = 0, open_brace
    while j < len(src):
        c = src[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return src[i:j + 1]
        j += 1
    return None


def main() -> int:
    failures = []
    page = io.open(ROOT / "logbook.html", encoding="utf-8", errors="replace").read()

    exporters = re.findall(r"const (_export\w+)\s*=\s*async\s*\([^)]*\)\s*=>\s*\{", page)
    if not exporters:
        print("FAIL export-reads-its-own-set - no _export* function found in logbook.html; the export "
              "moved and this gate no longer knows what it guards")
        return 1

    for name in exporters:
        body = _body_of(page, name)
        if body is None:
            failures.append(f"could not delimit {name}'s body; refusing to judge it on a guess")
            continue
        if not re.search(r"\.range\(", body):
            failures.append(f"{name} does not page with .range() - it reads one bounded batch and "
                            f"writes it as the whole record")
        if not re.search(r"for\s*\(", body):
            failures.append(f"{name} has no paging loop, so it stops at the first page")
        for buf in FEED_BUFFERS:
            if re.search(rf"\b{buf}\b", body):
                failures.append(f"{name} sources from {buf}, the FEED's render buffer - an export "
                                f"built from what the screen happened to load inherits that cap, "
                                f"which is exactly the incident this guards")
        orders = re.findall(r"\.order\(\s*['\"](\w+)['\"]", body)
        if len(orders) < 2:
            failures.append(f"{name} orders by {orders or 'nothing'} - a paged read needs a TOTAL "
                            f"order (a sort key AND a tiebreak), or pages can repeat one row and drop "
                            f"another: a file of the right length and the wrong contents")

    # non-vacuity: the data must actually exceed a page, or none of the above means anything
    try:
        r = subprocess.run(
            ["docker", "exec", "-i", CONTAINER, "psql", "-U", "postgres", "-d", "postgres", "-tA"],
            input="SELECT max(c) FROM (SELECT count(*) c FROM public.logbook GROUP BY hive_id) q;",
            capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace")
        biggest = int(re.search(r"(\d+)", r.stdout or "0").group(1)) if r.returncode == 0 else -1
    except Exception:
        biggest = -1

    page_size = re.search(r"const TEAM_PAGE\s*=\s*(\d+)", page)
    ps = int(page_size.group(1)) if page_size else 30
    if biggest == -1:
        print(f"  (database unreachable - non-vacuity unchecked; {len(exporters)} exporters examined)")
    elif biggest <= ps:
        failures.append(f"the largest hive holds {biggest} logbook rows and a page is {ps}, so nothing "
                        f"here exercises paging - this gate would pass on a table too small to fail. "
                        f"Seed more history before trusting it")
    else:
        print(f"  exporters: {', '.join(exporters)} · largest hive: {biggest} rows vs a {ps}-row page")

    if failures:
        print("FAIL export-reads-its-own-set - an export would leave the building incomplete:")
        for f in failures:
            print("    - " + f)
        return 1

    print(f"PASS export-reads-its-own-set - all {len(exporters)} exporters page their own set in a "
          f"total order and none reuses the feed's buffer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
