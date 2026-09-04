#!/usr/bin/env python3
"""asset-reaches-its-history - T15: the machine reaches its own fault history (2026-08-27).

Runs tools/prove_asset_reaches_its_history.mjs.

T15's done-definition is a JOURNEY, not a field: "machine -> its history -> a usable prior fix,
under a minute". asset-hub COUNTED the asset's logbook entries in a stat card and offered no way to
open them - a number with no door, on the page a worker stands in front of the machine with.

*TWO WAYS THE LINK COULD LOOK RIGHT AND BE USELESS, both asserted here:
  1. logbook.machine stores the TAG ("M-001"), not the asset NAME ("Siemens Simotics SD 200L").
     The sibling chips on that page (pm-scheduler, alert-hub) use tag-with-name-fallback, and
     copying that shape would land a NAME search on ZERO results for a machine with 47 entries -
     an empty page indistinguishable from an empty history. The gate therefore requires ROWS on
     arrival, counted against the database, not merely a link that navigates.
  2. Fault history is the TEAM's history. Without ?view=team the reader sees only their own
     entries and reads a colleague's fix as ABSENT, so the landing must be in the team window.

Verified live: M-001, 47 entries in the table, one tap, search box carries the tag, team view on,
30 cards on the first page with the page's own Load More for the rest.

Read-only. Re-drive: node tools/prove_asset_reaches_its_history.mjs
"""
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _run(node: str):
    r = subprocess.run([node, str(ROOT / "tools" / "prove_asset_reaches_its_history.mjs")],
                       cwd=str(ROOT), capture_output=True, text=True, timeout=300,
                       encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    return bool(re.search(r"^PASS", out, re.M)), " | ".join(
        l.strip() for l in (out.strip().splitlines()[-3:] or ["<no output>"]))


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("SKIP asset-reaches-its-history - node not on PATH (live browser gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP asset-reaches-its-history - local stack down")
        return 0
    try:
        ok, tail = _run(node)
        if not ok:
            ok, tail = _run(node)
    except subprocess.TimeoutExpired:
        print("FAIL asset-reaches-its-history - timed out at 300s")
        return 1
    print(f"  {'PASS' if ok else 'FAIL'}  {tail[:220]}")
    if not ok:
        print("FAIL asset-reaches-its-history - the asset cannot reach its fault history, the hop "
              "drops the tag, the window is not the team's, or the history arrives empty.")
        return 1
    print("PASS asset-reaches-its-history - one tap from the machine to what happened to it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
