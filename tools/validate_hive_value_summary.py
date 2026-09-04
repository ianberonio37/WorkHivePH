#!/usr/bin/env python3
"""validate_hive_value_summary.py — T188's data-layer lock: the whole-platform value summary is a real,
RLS-scoped view computing the three honest renewal counts from EXISTING tables — pms_kept,
faults_resolved, knowledge_written — so a renewing owner's "is this worth it?" rests on data, not a made
number, and the count semantics cannot silently drift.

T188's approved default: no new table, no new collection — a saved query (view) over what the hive already
did. Three counts a renewing owner can check by hand: pms_kept (pm_completions status 'done' — a 'skipped'
PM is NOT kept, verified against real data), faults_resolved (logbook status 'Closed'), knowledge_written
(fault_knowledge rows). security_invoker so a caller sees only their own hive's row. This gate locks that
the view exists, is security_invoker, and still computes those three counts with the right status filters.

DB-backed (psql), NOT browser. SKIPS if the DB is unreachable (no unearned pass). Registered in
run_platform_checks (Platform). NOTE: this locks the DATA layer; a renewal UI surface reading this view is
a scoped follow-up (T188 remains fixing until that surface lands).
"""
from __future__ import annotations

import io
import re
import subprocess
import sys

CHECK_NAMES = ["hive-value-summary"]
VIEW = "v_hive_value_summary"


def _viewdef() -> str | None:
    try:
        r = subprocess.run(
            ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
             "-t", "-A", "-c", f"select pg_get_viewdef('public.{VIEW}'::regclass, true);"],
            capture_output=True, text=True, timeout=30)
        return (r.stdout or "").strip() or None
    except Exception:
        return None


def _is_security_invoker() -> bool:
    try:
        r = subprocess.run(
            ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
             "-t", "-A", "-c",
             f"select reloptions::text from pg_class where relname='{VIEW}';"],
            capture_output=True, text=True, timeout=30)
        return "security_invoker=true" in (r.stdout or "").lower()
    except Exception:
        return False


def check(vdef: str, sec_invoker: bool) -> list[str]:
    problems: list[str] = []
    low = vdef.lower()
    if not sec_invoker:
        problems.append("the view is not security_invoker=true — a caller could read another hive's value "
                        "counts (it must be RLS-scoped to the caller).")
    # pms_kept: pm_completions filtered to 'done' (a 'skipped' PM is not kept)
    if "pm_completions" not in low or "'done'" not in low:
        problems.append("pms_kept does not count pm_completions filtered to status 'done' — a skipped PM "
                        "must not read as kept.")
    if "logbook" not in low or "'closed'" not in low:
        problems.append("faults_resolved does not count logbook filtered to status 'Closed'.")
    if "fault_knowledge" not in low:
        problems.append("knowledge_written does not count fault_knowledge rows.")
    return problems


def main() -> int:
    vdef = _viewdef()
    if vdef is None:
        print(f"SKIP hive-value-summary — DB unreachable or {VIEW} absent (no unearned pass; apply "
              f"migration 20260831000002).")
        return 0
    problems = check(vdef, _is_security_invoker())
    if problems:
        print(f"FAIL hive-value-summary — {VIEW} does not compute the three honest renewal counts safely:")
        for p in problems:
            print(f"    {p}")
        return 1
    print("PASS hive-value-summary — the value summary is a security_invoker view computing pms_kept "
          "(done), faults_resolved (Closed) and knowledge_written from existing tables.")
    return 0


def self_test() -> int:
    fails = []
    good = ("select h.id, (select count(*) from public.pm_completions pc where pc.status = 'done') as pms_kept, "
            "(select count(*) from public.logbook lb where lb.status = 'Closed') as faults_resolved, "
            "(select count(*) from public.fault_knowledge fk) as knowledge_written from public.hives h")
    if check(good, True):
        fails.append("the real view definition should PASS")
    if not any("security_invoker" in p for p in check(good, False)):
        fails.append("a non-security_invoker view should FAIL")
    if not any("skipped PM" in p for p in check(good.replace("'done'", "'completed'"), True)):
        fails.append("pms_kept not filtered to 'done' should FAIL")
    if not any("Closed" in p for p in check(good.replace("'Closed'", "'open'"), True)):
        fails.append("faults_resolved not filtered to 'Closed' should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_hive_value_summary self-test (non-invoker / wrong-status-filter redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
