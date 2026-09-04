#!/usr/bin/env python3
"""validate_provider_availability_driven.py — T102's lock: service-provider availability is DRIVEN
end-to-end, never write-once.

The failure T102 guards (the real bug behind feedback_availability_was_write_once_so_supply_vanished):
if availability were a field someone had to remember to reset, a provider who took one job would be
stuck 'on a job' forever and silently leave the supply pool — 43% of supply once vanished this way.
The fix makes availability FUNCTION-DRIVEN: accept_service_request sets it when a job is taken, and
sync_provider_availability keeps it in step as the job's state changes, so a provider returns to the
pool automatically.

This gate holds that both drivers exist AND both actually touch the availability field (a driver
that stopped writing availability would silently re-introduce the write-once bug):
  1. accept_service_request exists and references availability;
  2. sync_provider_availability exists and references availability.

DB-backed (psql), read-only, browser-free. SKIPs if the DB is unreachable. Registered in
run_platform_checks (Platform)."""
from __future__ import annotations

import io
import subprocess
import sys

CHECK_NAMES = ["provider-availability-driven"]
DRIVERS = ["accept_service_request", "sync_provider_availability"]


def _fn_refs_availability(fn: str) -> bool | None:
    # A real driver must touch service_providers AND the availability column in its BODY — not merely
    # match '%availab%' (which the function's own NAME, sync_provider_availability, contains: that early
    # false-positive is exactly why this checks the TABLE + column, per feedback_grep_matched_the_comment).
    try:
        r = subprocess.run(
            ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres", "-t", "-A",
             "-c", f"select case when not exists(select 1 from pg_proc where proname='{fn}') then 'MISSING' "
                   f"else (select bool_or(pg_get_functiondef(oid) ilike '%service_providers%' and pg_get_functiondef(oid) ~* 'availability')::text "
                   f"from pg_proc where proname='{fn}') end;"],
            capture_output=True, text=True, timeout=45)
        if r.returncode != 0:
            return None
        out = (r.stdout or "").strip()
        if out == "MISSING":
            return "MISSING"  # function truly absent (distinct from DB-down None)
        return out == "true"  # boolean::text is 'true'/'false' in psql, NOT 't'/'f'
    except Exception:
        return None


def check(refs: dict) -> list[str]:
    problems: list[str] = []
    for fn in DRIVERS:
        v = refs.get(fn)
        if v == "MISSING":
            problems.append(f"{fn} does not exist — availability has no {('setter' if 'accept' in fn else 'keeper')}, so it risks going write-once")
        elif v is False:
            problems.append(f"{fn} exists but does not touch service_providers.availability — it stopped driving supply (the write-once bug returns)")
    return problems


def main() -> int:
    # DB-down => every probe returns None => SKIP. A truly-absent function returns "MISSING" (not None),
    # so it is a real FAIL, not a silent skip.
    refs = {}
    any_ok = False
    for fn in DRIVERS:
        v = _fn_refs_availability(fn)
        refs[fn] = v
        if v is not None:
            any_ok = True
    if not any_ok:
        print("SKIP provider-availability-driven — DB unreachable (no unearned pass)."); return 0
    problems = check(refs)
    if problems:
        print("FAIL provider-availability-driven — availability is not driven end-to-end:")
        for p in problems:
            print(f"    {p}")
        return 1
    print("PASS provider-availability-driven — accept_service_request SETS availability on job-take and "
          "sync_provider_availability KEEPS it in step: a provider returns to the supply pool automatically, "
          "never stuck write-once.")
    return 0


def self_test() -> int:
    fails = []
    if check({"accept_service_request": True, "sync_provider_availability": True}):
        fails.append("both drivers referencing availability should PASS")
    if not any("does not exist" in p for p in check({"accept_service_request": "MISSING", "sync_provider_availability": True})):
        fails.append("a missing driver should FAIL")
    if not any("stopped driving" in p for p in check({"accept_service_request": True, "sync_provider_availability": False})):
        fails.append("a driver that stopped referencing availability should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_provider_availability_driven self-test (missing / stopped-referencing redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
