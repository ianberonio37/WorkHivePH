#!/usr/bin/env python3
"""maturity-says-yes-too - T187: a ladder that only ever refuses (2026-08-26).

maturity-gate told a hive what it could not have yet - "unlocks at Stair 2", "reach Stair 3" - on
every gated surface, and said NOTHING when the hive crossed one. A plant that spent three months
building logbook history earned Stair 2 in silence: the refusal simply stopped appearing, which
nobody notices, because noticing an absence is not how people work. The whole premise of the
maturity ladder is that patience is rewarded, and the reward was never announced.

It now says so once, on the first gated surface loaded after the crossing.

★DETECTED CENTRALLY, in checkMaturityGate, because every gated page already calls it and only the
FIRST one after a crossing should speak. Doing it per-page would have announced the same climb on
every surface the person visited.

★KEYED BY HIVE. A multi-hive contractor switching between them must not have one hive's progress
announced as the other's - the same class of bug as the persona and hive-scoping defects this
program keeps finding.

★RISE ONLY, DELIBERATELY. Readiness decays if logging stops, and telling someone unprompted that
they have been DEMOTED, on whatever page they happened to open, is a different feature and a
crueller one. The refusal messages already explain what is missing when they next hit a gate.

★AND FIRST SIGHT IS SILENT: with no previous reading there is no crossing to report, only a
baseline to record. Without that, every worker's first ever page load would congratulate them.

Exercised against the shipped helper: first sight silent, 1->2 announces, repeat silent, 2->3
announces, 3->1 silent.

Usage: python tools/validate_maturity_says_yes_too.py
"""
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
GATE = ROOT / "maturity-gate.js"


def main() -> int:
    if not GATE.exists():
        print("SKIP maturity-says-yes-too - maturity-gate.js not present")
        return 0

    src = GATE.read_text(encoding="utf-8", errors="replace")
    body = re.search(r"function _noteStairProgress[\s\S]*?\n  \}", src)
    fails = []

    if not body:
        fails.append("the ladder has no positive announcement at all: it tells a hive what it cannot "
                     "have and never that it has earned it, so three months of patience end in silence")
    else:
        b = body.group(0)
        if "wh_last_stair_seen_" not in b or "hiveId" not in b:
            fails.append("the last-seen stair is not keyed by hive, so a multi-hive contractor gets one "
                         "hive's progress announced as another's")
        if not re.search(r"cs\s*<=\s*prev", b):
            fails.append("the announcement is not rise-only - a decayed stair would tell someone "
                         "unprompted that they have been demoted, on whatever page they opened")
        if not re.search(r"prev === null", b):
            fails.append("first sight is not silent, so a worker's first ever page load congratulates "
                         "them on a crossing that never happened")
        if not re.search(r"showToast", b):
            fails.append("nothing is ever said to the person - the crossing is recorded and swallowed")

    # it must be wired where a REAL snapshot exists, not on the fallback-to-zero path
    if not re.search(r"typeof data\.current_stair === 'number'\)\s*_noteStairProgress", src):
        fails.append("it is not gated on a genuine snapshot, so a missing one reads as stair 0 and a "
                     "later real reading announces a climb that never occurred")

    if fails:
        print(f"FAIL maturity-says-yes-too - {len(fails)} problem(s):")
        for x in fails:
            print("    - " + x)
        print("    A ladder that only ever says no teaches people it is a wall.")
        return 1

    print("PASS maturity-says-yes-too - a crossing is announced once, per hive, only upward, and never "
          "on first sight.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
