""" -*- coding: utf-8 -*-
Is every status value the code WRITES understood by the view that READS it? (T112/T63, 2026-08-28)

`automation-log-status` already asserts that every literal written to automation_log.status is
permitted by its CHECK constraint. That is necessary and it is not sufficient, because a constraint
answers "may this value be stored" and never "does anything downstream know what it means".

★THE BUG THAT PROVED THE GAP. cmms-push-completion wrote external_sync.sync_status = 'failed' as a
durable marker for a completion that never reached the CMMS. The CHECK permits five values —
'active', 'deleted', 'error', 'failed', 'success' — so a constraint-shaped gate passes it happily.
But v_external_sync_truth, the view whose entire job is classifying sync state, buckets exactly
three: is_active, is_deleted, is_error. A row left at 'failed' is none of them. The marker built
specifically to stop a lost completion being invisible landed in the one value that made it
invisible to the truth view as well, and no surface on the platform ever showed it.

So the assertion here is the other half: EVERY status literal a writer can produce must be a value
the consuming view classifies. A value nothing classifies is a value that means nothing.

★THE COLUMN NAME NEEDS A WORD BOUNDARY, and this cost a wrong reading once already today: without
one, `sync_status` matches the tail of `last_sync_status`, which is a DIFFERENT column on a
different table with its own vocabulary ('failed'/'success') and its own reader. Two columns whose
names overlap are not one column.

USAGE:  python tools/validate_status_literals_are_classified.py
Exit 1 when a written literal is classified by nothing.
"""
from __future__ import annotations

import io
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# (column, the view that classifies it, where writers live). Add a pair as each is understood —
# a wrong pair is worse than a missing one, because it invents findings.
PAIRS = [
    {"column": "sync_status", "view": "v_external_sync_truth",
     "globs": ["supabase/functions/**/*.ts", "*.html", "*.js"]},
]

SKIP_DIRS = {"node_modules", ".emoji_bak", "_fixtures", "__pycache__", ".git"}


def live_view_values(view: str) -> set[str] | None:
    """The values the view actually classifies, read from the deployed definition."""
    try:
        out = subprocess.run(
            ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
             "-t", "-c", f"select pg_get_viewdef('{view}'::regclass, true);"],
            capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace")
        if out.returncode != 0:
            return None
        return set(re.findall(r"=\s*'([^']+)'::text", out.stdout))
    except Exception:
        return None


def written_literals(column: str, globs: list[str]) -> dict[str, list[str]]:
    """Every literal assigned to `column` in code, with where it was written."""
    # ★the (?<![\w_]) is load-bearing: `sync_status` otherwise matches `last_sync_status`.
    pat = re.compile(r"(?<![\w_])" + re.escape(column) + r"\s*:\s*[\"']([a-z_]+)[\"']", re.I)
    found: dict[str, list[str]] = {}
    for g in globs:
        for f in ROOT.glob(g):
            if any(part in SKIP_DIRS for part in f.parts):
                continue
            try:
                src = io.open(f, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            for m in pat.finditer(src):
                line = src[:m.start()].count("\n") + 1
                found.setdefault(m.group(1), []).append(f"{f.relative_to(ROOT).as_posix()}:{line}")
    return found


def main() -> int:
    print("status-literals-are-classified - does anything downstream know what this value means?\n")
    problems = 0
    checked = 0
    for pair in PAIRS:
        col, view = pair["column"], pair["view"]
        classified = live_view_values(view)
        if classified is None:
            print(f"  SKIP  {view} - database not reachable; this gate needs the live view definition")
            continue
        checked += 1
        writes = written_literals(col, pair["globs"])
        print(f"  {col} -> {view}")
        print(f"    classified by the view : {sorted(classified) or '(none)'}")
        print(f"    written by the code    : {sorted(writes) or '(none)'}")
        for value, sites in sorted(writes.items()):
            if value not in classified:
                problems += 1
                print(f"    ORPHAN  '{value}' is written but classified by nothing:")
                for s in sites[:4]:
                    print(f"              {s}")
    print()
    if problems:
        print(f"FAIL status-literals-are-classified - {problems} status value(s) that no consumer understands.")
        print("  A CHECK constraint says a value MAY be stored. It never says anything can read it.")
        return 1
    # ★A ZERO THAT MEANS "NOTHING WRONG" AND A ZERO THAT MEANS "I COULD NOT LOOK" MUST NOT RENDER
    # THE SAME. This gate reads the LIVE view definition, so with the database unreachable every
    # pair skips and `problems` stays 0 — which the first version of this file happily reported as a
    # PASS. A skipped partition reading as a covered one is the exact false-green shape the rest of
    # this board exists to prevent, and the convention here (fb1_webhook_idempotency_live) is to
    # fail loudly on an unreachable psql rather than to shrug.
    if checked == 0:
        print("FAIL status-literals-are-classified - NOTHING was checked: the database was not reachable,")
        print("  so this run has no opinion about the code. That is not the same as finding it clean.")
        return 1
    print(f"PASS status-literals-are-classified - every written status value is one its view classifies "
          f"({checked} column/view pair(s) checked).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
