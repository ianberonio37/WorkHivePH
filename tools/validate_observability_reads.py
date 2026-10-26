#!/usr/bin/env python3
"""validate_observability_reads.py - SL AU4 (2026-10-14): the observability tables are read only by the people the pages
that show them admit.

Asked of the server directly as Bryan Garcia (a worker of Baguio Textile Mills, not an admin), every active member could
read gateway_audit_log (32 rows: each person's ip_hash and ua_fingerprint), ai_cost_log (1,467 rows: each person's model
use, cost and feedback) and agentic_rag_traces (44 rows: each person's QUESTION and the AI's ANSWER) - behind
plant-connections (supervisors only), ai-quality (supervisor or admin), llm-observability and agentic-rag-observability
(platform admin). Migration 20261014000004 made each read follow its page. This gate asks the LIVE local database, as
each person (role authenticated + their JWT claims, so RLS and auth.uid() apply exactly as through PostgREST), inside
transactions that are always rolled back:

  worker      0 gateway rows, 0 traces, and no ai_cost_log row that is not their own
  supervisor  more than 0 of each for their hive  (the positive control: a read that returns nothing proves nothing)

    python tools/validate_observability_reads.py
"""
from __future__ import annotations

import subprocess
import sys

BAGUIO = "084c113b-99c0-45c6-a8e8-b4b8349da46d"     # pinned by the seeder (hives_workers.PINNED_HIVE_IDS)


def _one(sql: str) -> str | None:
    try:
        out = subprocess.run(["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
                              "-At", "-c", sql], capture_output=True, text=True, timeout=60).stdout.strip()
    except Exception:
        return None
    return out.splitlines()[0] if out else None


def people() -> tuple[str | None, str | None]:
    """A worker and the supervisor of Baguio, resolved LIVE (2026-10-27): the literal uids this gate named were recreated
    with new ids on 2026-10-26, and a uid that names nobody reads 0 rows - the gate then 'proved' the supervisor sees
    nothing. A worker is a worker-only member of Baguio; the supervisor is its supervisor."""
    worker = _one(f"select auth_uid from hive_members m where hive_id = '{BAGUIO}' and role = 'worker' and status = 'active'"
                  " and auth_uid is not null and not exists (select 1 from hive_members s where s.auth_uid = m.auth_uid"
                  " and s.role = 'supervisor' and s.status = 'active') order by joined_at, id limit 1")
    sup = _one(f"select auth_uid from hive_members where hive_id = '{BAGUIO}' and role = 'supervisor' and status = 'active'"
               " and auth_uid is not null order by joined_at, id limit 1")
    return worker, sup


def as_user(uid: str) -> tuple[int, int, int, int] | None:
    sql = (
        "begin;"
        f"select set_config('request.jwt.claims', '{{\"sub\":\"{uid}\",\"role\":\"authenticated\"}}', true);"
        "set local role authenticated;"
        "select (select count(*) from gateway_audit_log), (select count(*) from agentic_rag_traces),"
        " (select count(*) from ai_cost_log), (select count(*) from ai_cost_log where auth_uid is distinct from auth.uid());"
        "rollback;")
    try:
        out = subprocess.run(["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
                              "-At", "-c", sql], capture_output=True, text=True, timeout=60).stdout
    except Exception:
        return None
    rows = [ln for ln in out.splitlines() if ln.count("|") == 3]
    if not rows:
        return None
    return tuple(int(x) for x in rows[-1].split("|"))  # type: ignore[return-value]


def main() -> int:
    worker, sup = people()
    w, s = (as_user(worker) if worker else None), (as_user(sup) if sup else None)
    if w is None or s is None:
        print("FAIL observability-reads - the local database could not be asked (is supabase_db_workhive up?)")
        return 1
    problems = []
    if w[0]:
        problems.append(f"a worker reads {w[0]} gateway_audit_log row(s) (ip_hash, ua_fingerprint of teammates)")
    if w[1]:
        problems.append(f"a worker reads {w[1]} agentic_rag_traces row(s) (teammates' questions and the AI's answers)")
    if w[3]:
        problems.append(f"a worker reads {w[3]} ai_cost_log row(s) that are not their own")
    if not (s[0] and s[1] and s[2]):
        problems.append(f"the supervisor read gateway {s[0]}, traces {s[1]}, cost {s[2]} - a gate whose admitted reader "
                        "sees nothing proves nothing (seed the local data)")
    if problems:
        for p in problems:
            print("  FAIL " + p)
        print(f"FAIL observability-reads - {len(problems)} problem(s)")
        return 1
    print(f"PASS observability-reads - a worker reads 0 gateway rows, 0 traces and only their own {w[2]} cost row(s); "
          f"the supervisor reads {s[0]} / {s[1]} / {s[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
