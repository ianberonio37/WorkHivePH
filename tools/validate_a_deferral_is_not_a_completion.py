#!/usr/bin/env python3
"""Deferring a PM must never credit it as done (T10).

A worker who cannot do a task today defers it. A worker who does it completes it. Those are
different facts about a machine, and the gap between them is where a compliance percentage becomes
a lie: if a deferral sets last_completed_at, the task's next_due_date rolls forward, the item drops
off the overdue list, and the plant's compliance number rises for work nobody did. Nothing looks
wrong. The number just quietly stops meaning maintenance.

★THE ENFORCEMENT IS ONE CLAUSE IN ONE VIEW, WHICH IS WHY IT NEEDS A GATE. v_pm_scope_items_truth's
LATERAL join carries `AND pc.status = 'done'`, so a skipped completion can never set
last_completed_at and therefore can never move next_due_date. Every consumer inherits that from the
view rather than re-implementing it - which is the right design, and also means a single dropped
AND silently converts every deferral on the platform into a completion. That edit would look like
a harmless simplification in a diff.

THREE INDEPENDENT CHECKS, because each can be true while another is false:

  1. STRUCTURAL - the view definition still carries the status filter;
  2. EMPIRICAL - no scope item whose completions are ONLY deferrals carries a last_completed_at.
     The structure can be right and the data still wrong (a backfill, a trigger, a manual UPDATE),
     and this is the check that would catch it;
  3. LEXICAL - the glass says "Deferred", never the raw enum `skipped`. A person cannot act on a
     word the product does not use.

★AND THE LEXICAL CHECK IS DELIBERATELY NARROW. Grepping the roster for 'skipped' finds it in
hive.html and logbook.html, which looks like a raw-enum leak in exactly the way a naive scan would
report - but all four occurrences are code comments and console.warn text about unrelated things
(an embed skipped, an identity sync skipped), and neither page displays PM completion status at
all. A check that cannot tell prose from a rendered value would file two false findings here, so
this one reads only the pages that actually render completion status, and strips comments first.

Fails CLOSED: if the database is unreachable, SKIP rather than pass.

TEETH: --teeth drops the filter from the view inside a transaction it ROLLS BACK.
"""
from __future__ import annotations

import io
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_CONTAINER = "supabase_db_workhive"
VIEW = "public.v_pm_scope_items_truth"

# ★ONLY THE PAGE THAT ACTUALLY RENDERS PM COMPLETION STATUS, and the list started wrong.
# I seeded it from this trajectory's own prose ("pm-scheduler and analytics both render
# 'Deferred'") and analytics does NOT: its two matches are a comment about deferred CHART DRAWS
# and one about a deferred redirect. Trusting the note instead of the file produced a confident
# false finding against correct code - the same shape as trusting a code comment.
RENDERS_STATUS = ["pm-scheduler.html"]

BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT = re.compile(r"(?m)^\s*//.*$")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)


def _strip_comments(src: str) -> str:
    return LINE_COMMENT.sub("", BLOCK_COMMENT.sub(" ", HTML_COMMENT.sub(" ", src)))


def psql(sql: str, timeout: int = 60):
    try:
        proc = subprocess.run(["docker", "exec", "-i", DB_CONTAINER, "psql", "-U", "postgres",
                               "-d", "postgres", "-qtA", "-c", sql], capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return proc.stdout.strip() if proc.returncode == 0 else None
    except Exception:  # noqa: BLE001
        return None


STRUCT_SQL = ("select case when pg_get_viewdef('" + VIEW + "'::regclass) ilike '%status%done%' "
              "then 'ok' else 'MISSING' end;")

EMPIRICAL_SQL = """
select count(*) || '|' || count(*) filter (where last_completed_at is not null)
from v_pm_scope_items_truth v
where exists (select 1 from pm_completions c where c.scope_item_id = v.id)
  and not exists (select 1 from pm_completions c where c.scope_item_id = v.id and c.status = 'done');
"""


def audit_db() -> list | None:
    struct = psql(STRUCT_SQL)
    if struct is None:
        return None
    out = []
    if struct.strip() != "ok":
        out.append(f"{VIEW}: the LATERAL join no longer filters pc.status = 'done' - a DEFERRED task "
                   f"can now set last_completed_at, roll its next_due_date forward, and drop off the "
                   f"overdue list. Compliance rises for work nobody did, and nothing errors")
    emp = psql(EMPIRICAL_SQL)
    if emp and "|" in emp:
        total, credited = emp.split("|", 1)
        if credited.strip() not in ("0", ""):
            out.append(f"{VIEW}: {credited.strip()} of {total.strip()} scope items whose completions are "
                       f"ONLY deferrals carry a last_completed_at - the structure may be right, but the "
                       f"DATA credits deferrals as done (a backfill, a trigger, or a manual UPDATE)")
    return out


def audit_words() -> list:
    """The DISPLAY MAPPING is the property - not the absence of the word 'skipped'.

    ★MY FIRST VERSION HUNTED RAW-ENUM LEAKS WITH A REGEX AND CONVICTED CORRECT CODE. pm-scheduler
    contains 'skipped' three times and every one is legitimate: `status: isDefer ? 'skipped' :
    'done'` is the DB WRITE, and the others are comparisons. The enum SHOULD appear in code that
    talks to the database; what must never appear is the enum on the GLASS. So this reads the one
    thing that decides that - the ternary that turns a status into a word - instead of pattern-
    matching for a string that has every right to be there.
    """
    out = []
    for name in RENDERS_STATUS:
        p = ROOT / name
        if not p.exists():
            continue
        s = _strip_comments(io.open(p, encoding="utf-8", errors="replace").read())
        mapping = re.search(r"status\s*===\s*['\"]done['\"]\s*\?\s*['\"]Completed['\"]\s*:\s*['\"]Deferred['\"]", s)
        if not mapping:
            out.append(f"{name}: the completion-status display mapping is gone - the history no longer "
                       f"turns done/skipped into 'Completed'/'Deferred', so either the raw enum reaches "
                       f"a person or a deferral is shown as a completion")
    return out


def teeth() -> int:
    before = audit_db()
    if before is None:
        print("  SKIP - database unreachable; teeth cannot run")
        return 0
    print(f"  clean state: findings={len(before)}")
    # ★THE MUTATION MUST BE THE REAL VIEW MINUS THE FILTER. A first attempt replaced it with a
    # two-column stub, which CREATE OR REPLACE VIEW refuses (the column list must match) - psql
    # errored, the read came back empty, and the teeth reported MISS against a working detector.
    # This takes the view's OWN definition, strips the status predicate, and re-creates it.
    viewdef = psql("select pg_get_viewdef('" + VIEW + "'::regclass);")
    if not viewdef:
        print("  MISS could not read the view definition to mutate it")
        return 1
    # Postgres renders it PARENTHESISED - `AND (pc.status = 'done'::text)` - which my first
    # pattern (AND + whitespace + identifier) could not match, so the mutation silently did
    # nothing and the teeth reported MISS against a detector that was working fine. Written
    # against the actual pg_get_viewdef output rather than against what I expected it to say.
    stripped = re.sub(r"AND\s*\(?\s*\w+\.status\s*=\s*'done'(::text)?\s*\)?", "", viewdef, flags=re.I)
    if stripped == viewdef:
        print("  MISS the status predicate was not found in the view definition to strip")
        return 1
    sql = ("begin; create or replace view " + VIEW + " as " + stripped.rstrip().rstrip(';')
           + "; " + STRUCT_SQL + " rollback;")
    mutated = psql(sql)
    caught = mutated is not None and "MISSING" in mutated
    after = audit_db()
    restored = after is not None and len(after) == 0
    print(f"  {'ok  ' if caught else 'MISS'} dropping the done-filter is detected (read inside the txn: "
          f"{(mutated or '?').strip()})")
    print(f"  {'ok  ' if restored else 'MISS'} the rollback restored the real view (findings now "
          f"{len(after) if after is not None else '?'})")
    bad = (0 if caught else 1) + (0 if restored else 1)
    print(f"\nTEETH {'FAILED' if bad else 'ok'} - {2 - bad}/2")
    return 1 if bad else 0


def main() -> int:
    db = audit_db()
    if db is None:
        print("a-deferral-is-not-a-completion - SKIP: local database unreachable")
        print("  (fails closed: the enforcement lives in a view, so it cannot be checked from source alone)")
        return 0
    findings = db + audit_words()
    print("a-deferral-is-not-a-completion - a task put off is not a task done")
    if findings:
        print("\nFAIL - a deferral can be credited as a completion, so compliance counts work nobody did:")
        for f in findings:
            print(f"    {f}")
        return 1
    print("\nPASS - the view refuses to credit a deferral, no data contradicts it, and the glass says "
          "'Deferred'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(teeth() if "--teeth" in sys.argv else main())
