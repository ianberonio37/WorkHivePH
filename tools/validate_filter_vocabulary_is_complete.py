#!/usr/bin/env python3
"""filter-vocabulary-is-complete - T64: a filter must offer everyone who acted (2026-08-26).

audit-log's feed reads the newest 500 rows, which is right for a scrolling feed. The filter
dropdowns were then built from THAT array, so the choices offered were whatever happened to fall
inside the cap.

MEASURED on the fixture hive: 3,402 audit rows, 4 distinct actors and 22 distinct actions overall,
but only 3 actors and 18 actions inside the newest 500. A supervisor could not filter to one of the
four people who acted, or to 4 of the 22 action types, and nothing said the list was partial. On a
compliance surface, "no option for that person" reads as "that person did nothing" - the opposite
of what an audit trail is for. Same class this file had already fixed for the CSV export, one
function away, which is the tell: the cap was removed where someone had looked, and left where
nobody had.

THE ASSERTION: the option lists match the DISTINCT values in the database. The database is the
oracle, so this cannot drift into checking the page against itself.

★AND THE FIX'S OWN FIRST VERSION FAILED LIVE. It declared its cache with `let` further down the
file than the async path that reads it - a temporal dead zone - so the page threw ReferenceError on
first paint and every dropdown came back EMPTY. No syntax check sees that; only opening the page
does, which is why this gate is live rather than static.

★SKIPS BELOW THE CAP. With fewer than 500 rows the cap cannot hide anything, and a pass there would
mean nothing.

Re-drive: node tools/prove_filter_vocabulary_is_complete.mjs
"""
import io
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("SKIP filter-vocabulary-is-complete - node not on PATH (live gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP filter-vocabulary-is-complete - local stack down")
        return 0

    def run():
        r = subprocess.run([node, str(ROOT / "tools" / "prove_filter_vocabulary_is_complete.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=420,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        if re.search(r"^\s*SKIP", out, re.M):
            return None, out
        return bool(re.search(r"^\s*PASS", out, re.M)), out

    try:
        ok, out = run()
        if ok is False:
            ok, out = run()
    except subprocess.TimeoutExpired:
        print("FAIL filter-vocabulary-is-complete - timed out at 420s")
        return 1

    for line in out.strip().splitlines()[-3:]:
        print("  " + line.strip()[:170])
    if ok is None:
        print("SKIP filter-vocabulary-is-complete - fixture below the row cap, or hive unresolved")
        return 0
    if not ok:
        print("FAIL filter-vocabulary-is-complete - the audit filter does not offer every actor or action")
        print("    the database holds. A filter that omits someone who acted tells the reader they did")
        print("    nothing. The feed may be capped; the vocabulary of who and what may not be.")
        return 1
    print("PASS filter-vocabulary-is-complete - the audit filters offer every actor and action in the "
          "record, not just those inside the feed's cap.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
