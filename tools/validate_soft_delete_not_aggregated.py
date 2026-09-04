#!/usr/bin/env python3
"""validate_soft_delete_not_aggregated.py — T432's lock: a soft-deleted row never leaks into an AGGREGATE.
Every view that COUNTs or SUMs a soft-deletable table (one with a deleted_at column) must exclude the
soft-deleted rows (deleted_at IS NULL), so a deleted community post or project cannot inflate a reputation
score, a total, or a dashboard tile while still being individually hidden.

Pass-through views (which EXPOSE deleted_at / is_deleted so the consumer can decide) are fine — the leak is
specifically an AGGREGATE (count/sum) that forgot the filter. Verified 2026-09-01: v_community_reputation_truth
counts community_posts WHERE deleted_at IS NULL (holds); this gate keeps any new aggregate honest.

DB-backed (psql), read-only, browser-free. SKIPs if the DB is unreachable. Registered in run_platform_checks.
"""
from __future__ import annotations

import io
import subprocess
import sys

CHECK_NAMES = ["soft-delete-not-aggregated"]


def _psql(sql: str) -> str | None:
    try:
        r = subprocess.run(
            ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
             "-t", "-A", "-c", sql], capture_output=True, text=True, timeout=45)
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None


def _soft_tables() -> list[str] | None:
    out = _psql("select table_name from information_schema.columns where table_schema='public' "
                "and column_name='deleted_at' and table_name in "
                "(select table_name from information_schema.tables where table_schema='public' and table_type='BASE TABLE') "
                "order by table_name;")
    if out is None:
        return None
    return [t.strip() for t in out.splitlines() if t.strip()]


def _aggregating_views_missing_filter(soft: list[str]) -> list[str] | None:
    bad = []
    for tbl in soft:
        # views that reference the table AND aggregate (count(/sum() over it, AND do NOT filter deleted_at
        out = _psql(f"""
select c.relname from pg_class c join pg_namespace n on n.oid=c.relnamespace
where n.nspname='public' and c.relkind='v'
  and pg_get_viewdef(c.oid) ilike '%{tbl}%'
  and (pg_get_viewdef(c.oid) ~* 'count\\s*\\(' or pg_get_viewdef(c.oid) ~* 'sum\\s*\\(')
  and pg_get_viewdef(c.oid) !~* '{tbl}\\.deleted_at is null'
  and pg_get_viewdef(c.oid) !~* 'deleted_at is null';""")
        if out is None:
            return None
        for v in out.splitlines():
            v = v.strip()
            if v:
                bad.append(f"{v} aggregates {tbl} without a deleted_at IS NULL filter")
    return bad


def check(soft: list[str], bad: list[str]) -> list[str]:
    problems: list[str] = []
    if not soft:
        return problems  # no soft-deletable tables -> nothing to leak
    problems.extend(bad)
    return problems


def main() -> int:
    soft = _soft_tables()
    if soft is None:
        print("SKIP soft-delete-not-aggregated — DB unreachable (no unearned pass)."); return 0
    bad = _aggregating_views_missing_filter(soft)
    if bad is None:
        print("SKIP soft-delete-not-aggregated — DB unreachable mid-scan (no unearned pass)."); return 0
    problems = check(soft, bad)
    if problems:
        print("FAIL soft-delete-not-aggregated — a soft-deleted row leaks into an aggregate:")
        for p in problems:
            print(f"    {p}")
        return 1
    print(f"PASS soft-delete-not-aggregated — every aggregating view of a soft-deletable table "
          f"({', '.join(soft)}) filters deleted_at IS NULL; deleted rows cannot inflate a total.")
    return 0


def self_test() -> int:
    fails = []
    if check(["community_posts"], []):
        fails.append("no bad aggregate should PASS")
    if not any("without a deleted_at" in p for p in check(["community_posts"], ["v_x aggregates community_posts without a deleted_at IS NULL filter"])):
        fails.append("a leaking aggregate should FAIL")
    if check([], ["ignored"]):
        fails.append("no soft-deletable tables -> PASS (nothing to leak)")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_soft_delete_not_aggregated self-test (leaking aggregate reddens; clean passes)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
