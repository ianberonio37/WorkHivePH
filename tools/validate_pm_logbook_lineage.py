#!/usr/bin/env python3
"""validate_pm_logbook_lineage.py — T32's lock instrument: the PM↔Logbook lineage is ON GLASS in BOTH
directions, so a mirrored entry is never mistaken for a hand-typed one, and a logbook-driven PM completion
names its source.

T32 proved the two DB chains (pm→logbook mirror row; logbook→pm completion) and fixed the missing THIRD
surface: a PM-mirrored logbook entry used to be indistinguishable from a hand-typed one. The fix renders a
'via PM Scheduler' chip in the entry modal, keyed on the mirror's own `pm-` id prefix (minted for
traceability, never otherwise surfaced). This gate LOCKS both lineage markers so a future edit cannot
silently drop either half — the 'a fix shipped into a dead path' / 'declared but never wired' class.

TWO assertions (each refutable — see the self-test), both in logbook.html:
  1. PM → LOGBOOK chip: a render branch keyed on the `pm-` id prefix that surfaces a 'via PM Scheduler'
     (or 'PM Scheduler') label — so a mirrored entry announces its origin.
  2. LOGBOOK → PM note: a 'Logged via Logbook' provenance string written into the PM completion — so a
     logbook-driven compliance movement names its source.

Read-only; no browser; no DB. Registered in run_platform_checks (Platform).
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGBOOK = ROOT / "logbook.html"

CHECK_NAMES = ["pm-logbook-lineage"]

# 1. the PM→logbook chip: a branch keyed on the `pm-` id prefix that renders a PM-Scheduler origin label.
_PM_PREFIX_BRANCH = re.compile(r"""startsWith\(\s*['"]pm-['"]\s*\)""")
_VIA_PM_LABEL = re.compile(r"via PM Scheduler|PM Scheduler", re.I)
# 2. the logbook→PM provenance note written into the completion.
_LOGGED_VIA = re.compile(r"Logged via Logbook", re.I)


def check(src: str) -> list[str]:
    problems: list[str] = []
    if not (_PM_PREFIX_BRANCH.search(src) and _VIA_PM_LABEL.search(src)):
        problems.append("PM→logbook lineage MISSING: no `startsWith('pm-')`-keyed branch rendering a "
                        "'via PM Scheduler' origin chip — a mirrored entry would read as hand-typed.")
    if not _LOGGED_VIA.search(src):
        problems.append("logbook→PM lineage MISSING: no 'Logged via Logbook' provenance note on the PM "
                        "completion — a logbook-driven compliance movement would not name its source.")
    return problems


def main() -> int:
    if not LOGBOOK.exists():
        print("FAIL pm-logbook-lineage: logbook.html not found"); return 1
    problems = check(LOGBOOK.read_text(encoding="utf-8", errors="replace"))
    if problems:
        print(f"FAIL pm-logbook-lineage — the PM↔Logbook lineage is not fully on glass:")
        for p in problems:
            print(f"    {p}")
        return 1
    print("PASS pm-logbook-lineage — both directions are on glass: the 'via PM Scheduler' chip keyed on the "
          "pm- prefix, and the 'Logged via Logbook' provenance note.")
    return 0


def self_test() -> int:
    fails = []
    good = ("x ${String(entry.id||'').startsWith('pm-') ? `<span>via PM Scheduler</span>` : ''} "
            "notes: `Logged via Logbook: ${machine}`")
    if check(good):
        fails.append("the real both-directions markup should PASS")
    # drop the chip -> PM→logbook half fails
    if not any("PM→logbook" in p for p in check("notes: `Logged via Logbook: ${m}`")):
        fails.append("missing the via-PM-Scheduler chip should FAIL")
    # drop the note -> logbook→PM half fails
    if not any("logbook→PM" in p for p in check("${entry.id.startsWith('pm-') ? '<span>via PM Scheduler</span>' : ''}")):
        fails.append("missing the Logged-via-Logbook note should FAIL")
    # the chip label WITHOUT the pm- prefix branch must still FAIL (a label with no keying is not lineage)
    if not any("PM→logbook" in p for p in check("<span>via PM Scheduler</span> Logged via Logbook:")):
        fails.append("a 'via PM Scheduler' label not keyed on the pm- prefix should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_pm_logbook_lineage self-test (both halves redden when dropped; unkeyed label rejected)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
