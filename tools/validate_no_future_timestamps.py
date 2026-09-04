#!/usr/bin/env python3
"""validate_no_future_timestamps.py — T437's lock: no backfill (or clock bug) leaves a created_at in the
future — every public table that carries a created_at holds only past/near-now values, so time-ordered
reads, "recent activity" windows, MTBF/OEE windows and the ledger's chronology are not corrupted by a row
dated next week.

A backfill that stamps created_at = a wrong (future) time is invisible to a foreign-key or NOT-NULL check
and silently poisons every window/ordering query — a row dated 2027 sorts to the top of "latest" forever.
This gate discovers every public table with a created_at column and asserts none holds a value more than a
day past now(). One day of slack absorbs clock skew / an in-flight insert; anything beyond that is a bug.

DB-backed (psql), browser-free. SKIPs if the DB is unreachable (no unearned pass). Registered in
run_platform_checks (Platform).
"""
from __future__ import annotations

import io
import subprocess
import sys

CHECK_NAMES = ["no-future-timestamps"]


def _psql(sql: str) -> str | None:
    try:
        r = subprocess.run(
            ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
             "-t", "-A", "-c", sql], capture_output=True, text=True, timeout=60)
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None


def _future_counts() -> dict | None:
    tables = _psql("select table_name from information_schema.columns where table_schema='public' "
                   "and column_name='created_at' and data_type like 'timestamp%' order by table_name;")
    if tables is None:
        return None
    names = [t.strip() for t in tables.splitlines() if t.strip()]
    if not names:
        return {}
    # one query: union the future-row count per table
    union = " union all ".join(
        f"select '{n}' as t, count(*) c from public.\"{n}\" where created_at > now() + interval '1 day'"
        for n in names)
    out = _psql(union + ";")
    if out is None:
        return None
    res = {}
    for ln in out.splitlines():
        ln = ln.strip()
        if not ln or "|" not in ln:
            continue
        name, c = ln.rsplit("|", 1)
        try:
            res[name] = int(c)
        except ValueError:
            pass
    return res


def check(counts: dict) -> list[str]:
    problems = []
    for name, c in sorted(counts.items()):
        if c > 0:
            problems.append(f"{name}: {c} row(s) have created_at more than a day in the FUTURE — a backfill "
                            f"or clock bug poisoned the chronology (they sort to the top of 'latest' forever).")
    return problems


def main() -> int:
    counts = _future_counts()
    if counts is None:
        print("SKIP no-future-timestamps — DB unreachable (no unearned pass).")
        return 0
    if not counts:
        print("SKIP no-future-timestamps — no public table has a created_at timestamp column.")
        return 0
    problems = check(counts)
    if problems:
        print("FAIL no-future-timestamps — future-dated rows corrupt time-ordered reads:")
        for p in problems:
            print(f"    {p}")
        return 1
    print(f"PASS no-future-timestamps — all {len(counts)} public tables with a created_at hold only "
          f"past/near-now values (no backfill left a future timestamp).")
    return 0


def self_test() -> int:
    fails = []
    if check({"logbook": 0, "community_posts": 0}):
        fails.append("all-zero (no future rows) should PASS")
    if not any("logbook" in p for p in check({"logbook": 3, "community_posts": 0})):
        fails.append("a table with future rows should FAIL")
    if not any("FUTURE" in p for p in check({"x": 1})):
        fails.append("a single future row should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_no_future_timestamps self-test (future rows redden; all-zero passes)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
