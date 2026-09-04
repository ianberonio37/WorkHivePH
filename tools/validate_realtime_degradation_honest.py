#!/usr/bin/env python3
"""validate_realtime_degradation_honest.py — T143's lock instrument: when realtime degrades, the hive
board is HONEST — it paints an 'offline' connection state and falls back to a DB read for the roster,
rather than silently showing a stale or empty presence list as if it were live.

T143 walked the flagship realtime surface (hive.html) with all realtime sockets refused at connect and
verified the honest-degraded path: the conn pill paints 'Offline' (surfaced only when degraded, per its
silence-is-golden design) and renderPresenceFallback paints the roster from the DB read. This gate locks
that path so a future edit cannot drop it and let a dead socket read as a live-but-quiet hive (the
'silence a reader misreads as fact' class).

Assertions on hive.html (each refutable — see the self-test):
  1. OFFLINE IS PAINTED — a `setConn('offline')` call on the disconnect/degrade path.
  2. THE ROSTER FALLS BACK — `renderPresenceFallback(` is called (the DB read that replaces the dead
     presence channel), and the two sit together on the degrade path.

Read-only; no browser; no DB. Registered in run_platform_checks (Platform).
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "hive.html"

CHECK_NAMES = ["realtime-degradation-honest"]

_SET_OFFLINE = re.compile(r"""setConn\(\s*['"]offline['"]\s*\)""")
_FALLBACK = re.compile(r"""renderPresenceFallback\s*\(""")
# the two together on the same degrade path (offline set then the roster fallback, within a small window)
_TOGETHER = re.compile(r"""setConn\(\s*['"]offline['"]\s*\)\s*;?\s*renderPresenceFallback\s*\(""")


def check(src: str) -> list[str]:
    problems: list[str] = []
    if not _SET_OFFLINE.search(src):
        problems.append("no setConn('offline') — a degraded realtime connection is not painted as offline, "
                        "so a dead socket reads as live.")
    if not _FALLBACK.search(src):
        problems.append("no renderPresenceFallback() — on a dead presence channel the roster is not "
                        "re-read from the DB, so it shows stale/empty as if live.")
    if _SET_OFFLINE.search(src) and _FALLBACK.search(src) and not _TOGETHER.search(src):
        problems.append("setConn('offline') and renderPresenceFallback() both exist but are not wired on "
                        "the SAME degrade path (offline-then-fallback) — the honest-degrade handler is split.")
    return problems


def main() -> int:
    if not PAGE.exists():
        print("FAIL realtime-degradation-honest: hive.html not found"); return 1
    problems = check(PAGE.read_text(encoding="utf-8", errors="replace"))
    if problems:
        print("FAIL realtime-degradation-honest — the hive board is not honest when realtime degrades:")
        for p in problems:
            print(f"    {p}")
        return 1
    print("PASS realtime-degradation-honest — a degraded realtime connection paints 'offline' and the "
          "roster falls back to a DB read on the same path (a dead socket cannot read as a live quiet hive).")
    return 0


def self_test() -> int:
    fails = []
    good = "    setConn('offline');\n    renderPresenceFallback();"
    if check(good):
        fails.append("the real offline-then-fallback wiring should PASS")
    if not any("setConn('offline')" in p for p in check("renderPresenceFallback();")):
        fails.append("missing setConn('offline') should FAIL")
    if not any("renderPresenceFallback" in p for p in check("setConn('offline');")):
        fails.append("missing renderPresenceFallback should FAIL")
    # both present but far apart (not on the same path) should FAIL the together-check
    split = "setConn('offline'); doOtherStuff(); moreLines(); " + "x;"*40 + " renderPresenceFallback();"
    if not any("SAME degrade path" in p for p in check(split)):
        fails.append("offline and fallback not wired together should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_realtime_degradation_honest self-test (missing offline / missing fallback / split path all redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
