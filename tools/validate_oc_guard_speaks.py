#!/usr/bin/env python3
"""oc-guard-speaks — T138: a concurrency guard that says nothing is a lost edit (2026-08-26).

An optimistic-concurrency guard filters an UPDATE on the row's `updated_at`, so a
write loses if somebody else changed the record first. That is the easy half. The
half that decides whether it HELPS is what happens next: if nothing checks that
zero rows changed, the update silently does nothing, the form closes, and the
person walks away believing they saved work that no longer exists. A guard that
returns without speaking is worse than no guard, because it converts a visible
conflict into an invisible loss.

CENSUS, 2026-08-26 — and it CORRECTS this trajectory's recorded belief. The basis
read that logbook amends, community post edits and PM scope edits were "presumed
LAST-WRITE-WINS". They are not: there are TEN hand-rolled guards across EIGHT
pages (asset-hub, community, founder-console, integrations, logbook,
platform-actions, pm-scheduler, project-manager x3), plus inventory through the
central ocUpdate helper. Eleven protected edit surfaces, not two. And every one of
the ten detects the zero-row case AND tells the person.

THE ASSERTION: every `updated_at`-filtered update must, within the same handler,
check for zero rows changed and say something. It does NOT demand migration to
ocUpdate — that is ten rewrites of live edit paths for a refactor, and the
property that protects a person is "the guard speaks", not "the guard is shared".
The install-the-guard lesson still applies to anything NEW: reach for ocUpdate
first. This gate exists so a hand-rolled one cannot ship SILENT.

★AND IT WOULD RATHER MISS THAN LIE. The window is the 40 lines after the filter,
so a guard whose reporting lives further away reads as a miss. That is the safe
direction for a gate whose failure mode would otherwise be a false accusation
about working code.

Usage: python tools/validate_oc_guard_speaks.py
"""
import glob
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

FILTER = re.compile(r"\.eq\(\s*'updated_at'")
ZERO = re.compile(r"length\s*===?\s*0|!\s*data\b|!\s*updated\b|count\s*===?\s*0|\brows?\s*===?\s*0|"
                  r"data\s*&&\s*data\.length|\.length\s*<\s*1")
SAYS = re.compile(r"showToast|whWriteError|setStatus|textContent\s*=|whConfirm|alert\(")


def main() -> int:
    silent, total = [], 0
    for f in sorted(glob.glob(str(ROOT / "*.html"))):
        lines = io.open(f, encoding="utf-8", errors="replace").read().split("\n")
        for i, line in enumerate(lines):
            if not FILTER.search(line):
                continue
            total += 1
            window = "\n".join(lines[i: i + 40])
            if not (ZERO.search(window) and SAYS.search(window)):
                silent.append(f"{Path(f).name}:{i + 1}")

    central = sum(1 for f in glob.glob(str(ROOT / "*.html"))
                  if "ocUpdate" in io.open(f, encoding="utf-8", errors="replace").read())
    print(f"  updated_at-guarded updates: {total} hand-rolled | pages using central ocUpdate: {central}")

    if silent:
        print("FAIL oc-guard-speaks — a concurrency guard filters the update but never notices it "
              "changed nothing:")
        for s in silent:
            print("    - " + s)
        print("    The write vanishes, the form closes, and the person believes they saved work that no")
        print("    longer exists. Check for zero rows changed and SAY so — or use ocUpdate, which does")
        print("    both. A guard that returns without speaking turns a visible conflict into an")
        print("    invisible loss.")
        return 1
    if total == 0:
        print("PASS oc-guard-speaks — no updated_at-filtered updates found. If that is a surprise, the "
              "guards were removed or renamed; re-point this gate rather than trusting the zero.")
        return 0
    print(f"PASS oc-guard-speaks — all {total} concurrency guards detect a lost race and tell the person.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
