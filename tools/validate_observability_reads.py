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

BRYAN = "91e0d1eb-cd96-43ee-af5f-0ff2714b3923"      # worker, Baguio Textile Mills
LEANDRO = "bcb5a6e3-fb12-4238-bc1e-ffeb48f60d53"    # supervisor of Baguio Textile Mills


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
    w, s = as_user(BRYAN), as_user(LEANDRO)
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
