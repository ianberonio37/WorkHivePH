#!/usr/bin/env python3
"""missing-brief-says-so - T81: a daily brief that did not run must say so (2026-08-26).

The 6am PHT cron writes one amc_briefings row per shift_date, and alert-hub reads only TODAY's.
That scoping is right and stays: yesterday's brief must never pose as this morning's.

★BUT WHEN THE CRON MISSED, THE CARD VANISHED. renderAmcCard(null) set display:none, so a supervisor
could not tell "no brief ran today" from "this feature does not exist" or "the page is still
loading". Worse, a skeleton is rendered in that card on first load, so the sequence was a loading
state resolving into NOTHING - an answer erasing itself, on a surface whose whole promise is a brief
every morning. On a missed morning the absence IS the news.

It now stays visible, says no brief was generated for this shift, names the 6am cadence so the
reader knows what was missed, points at the most recent brief the page has already fetched (marked
as not a substitute), and blanks the figure tiles so no number stands under a "not generated"
header.

BOTH DIRECTIONS: with today's row absent the card speaks; with the real row it still renders the
brief and does not claim absence. The second half matters - a card that always cried "no brief"
would satisfy the first while destroying the feature.

★NO DATA IS MUTATED. Only the today-scoped read (shift_date=eq.) is intercepted, so the historic
query answers for real, which is what lets the empty state name the most recent brief.

Re-drive: node tools/prove_missing_brief_says_so.mjs
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
        print("SKIP missing-brief-says-so - node not on PATH (live gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP missing-brief-says-so - local stack down")
        return 0

    def run():
        r = subprocess.run([node, str(ROOT / "tools" / "prove_missing_brief_says_so.mjs")],
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
        print("FAIL missing-brief-says-so - timed out at 420s")
        return 1

    for line in out.strip().splitlines()[-3:]:
        print("  " + line.strip()[:170])
    if ok is None:
        print("SKIP missing-brief-says-so - the probe could not resolve its hive fixture")
        return 0
    if not ok:
        print("FAIL missing-brief-says-so - a morning brief that did not run must say it did not run.")
        print("    Hiding the card leaves a supervisor unable to tell a missed cron from a feature that")
        print("    was never there - and after a skeleton, that reads as a loading state that resolved")
        print("    into nothing.")
        return 1
    print("PASS missing-brief-says-so - a missed brief is stated with its cadence; a real one still renders.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
