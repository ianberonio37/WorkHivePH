#!/usr/bin/env python3
"""validate_team_deeplink_survives.py — T29's lock: a deep-linked team search must SURVIVE init.

The chain alert-hub → asset-hub → "Fault history" hands off to logbook.html?q=<tag>&view=team.
Walked live 2026-09-02 (as Pablo, PV-002): the URL handler started searchTeam(), then the
supervisor-default init re-ran setViewMode('team'), which clears the list, resets _teamSearched
and shows the browse prompt — the seeded search was WIPED and 36 real team entries rendered as
"Search team entries above". Only supervisors hit it (workers skip the default branch), which is
exactly who walks the diagnostic chain. A second, quieter half: loadTeamMembers() lands a 7-day
date default ASYNCHRONOUSLY, so even a surviving hand-off search got silently narrowed to a week
on any later re-search — "has this failed before" is an ALL-history question.

Locks both shapes in logbook.html:
  1. the supervisor team-default is GUARDED: it must not call setViewMode('team') when _viewMode
     is already 'team' (the deep-link handler runs first and owns the view);
  2. the browse-window default is CONDITIONAL on !_teamSearched (a browse-load discipline must
     never re-scope an in-flight or completed search).
Static, fast, no DB. Self-test proves both mutations redden (resurrection: the pre-fix shapes).
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "logbook.html"

CHECK_NAMES = ["team-deeplink-survives"]

GUARD_RE = re.compile(
    r"HIVE_ROLE\s*===\s*'supervisor'\s*&&\s*_viewMode\s*!==\s*'team'\s*\)\s*setViewMode\('team'\)")
UNGUARDED_RE = re.compile(
    r"if\s*\(\s*HIVE_ROLE\s*===\s*'supervisor'\s*\)\s*setViewMode\('team'\)")
# T15 S2: multi-word team search must term-AND (each term .or()'d across fields, chained = AND),
# never ride the whole phrase into one ilike ('bearing temperature' -> 0 while 'bearing' -> 5).
TERM_AND_RE = re.compile(r"for \(const _term of safeSV\.split\(/\\s\+/\)")
DATE_COND_RE = re.compile(
    r"if\s*\(\s*!_teamSearched\s*&&.{0,100}filter-date-from.{0,30}\.value\s*\)\s*\{[\s\S]{0,400}?weekAgo")


def check(src: str) -> list[str]:
    problems: list[str] = []
    if UNGUARDED_RE.search(src):
        problems.append("the supervisor team-default calls setViewMode('team') UNGUARDED - it will "
                        "wipe a deep-linked team search that is already in flight (the T29 chain-break)")
    elif not GUARD_RE.search(src):
        problems.append("the guarded supervisor team-default (`HIVE_ROLE === 'supervisor' && "
                        "_viewMode !== 'team'`) is missing - the deep-link handler no longer owns the view")
    if not DATE_COND_RE.search(src):
        problems.append("the 7-day browse default is not conditional on !_teamSearched - an async "
                        "roster load will silently re-scope a hand-off search to one week")
    if not TERM_AND_RE.search(src):
        problems.append("the team search no longer term-ANDs multi-word queries - 'bearing "
                        "temperature' returns 0 while 'bearing' returns 5 again (T15 S2)")
    return problems


def main() -> int:
    src = io.open(PAGE, encoding="utf-8", errors="replace").read()
    problems = check(src)
    if problems:
        print("FAIL team-deeplink-survives - the fault-history hand-off can be wiped or narrowed:")
        for p in problems:
            print(f"    {p}")
        return 1
    print("PASS team-deeplink-survives - a ?q=&view=team hand-off keeps its search (supervisor "
          "default is view-guarded) and its ALL-history scope (browse window only applies pre-search).")
    return 0


def self_test() -> int:
    src = io.open(PAGE, encoding="utf-8", errors="replace").read()
    fails = []
    if check(src):
        fails.append("HEAD should PASS")
    pre_fix = src.replace("HIVE_ROLE === 'supervisor' && _viewMode !== 'team') setViewMode('team')",
                          "HIVE_ROLE === 'supervisor') setViewMode('team')")
    if not any("UNGUARDED" in p for p in check(pre_fix)):
        fails.append("the pre-fix unguarded default must redden (resurrection)")
    no_cond = src.replace("if (!_teamSearched && !document.getElementById('filter-date-from').value) {", "{")
    if not any("not conditional" in p for p in check(no_cond)):
        fails.append("an unconditional 7-day default must redden")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_team_deeplink_survives self-test (unguarded default + unconditional window both redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
