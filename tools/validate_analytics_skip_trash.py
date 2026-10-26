#!/usr/bin/env python3
"""validate_analytics_skip_trash.py - an entry in the trash never counts in the analytics (2026-10-26).

The logbook's own reads go through v_logbook_truth, which leaves a trashed entry out. The five analytics RPCs read
logbook directly with no such filter, so a breakdown a worker moved to the trash kept counting as a failure, a repeat
and downtime (found on the BRH.10 AI walk of analytics.html; fixed by 20261026000004).

The rule this holds is wider than the five: every function in public that reads logbook and is named get_* (the
analytics readers) must filter deleted_at. It reads the INSTALLED definitions, so a later CREATE OR REPLACE that drops
the filter reddens it the day it lands. A stopped stack prints SKIP; nothing is read from a file.

    python tools/validate_analytics_skip_trash.py
    python tools/validate_analytics_skip_trash.py --self-test
"""
from __future__ import annotations

import re
import subprocess
import sys

QUERY = """
select p.proname, pg_get_functiondef(p.oid)
  from pg_proc p join pg_namespace n on n.oid = p.pronamespace
 where n.nspname = 'public' and p.proname like 'get\\_%' and p.prokind = 'f'
   and pg_get_functiondef(p.oid) ~* 'from\\s+(public\\.)?logbook\\M'
"""


def findings(defs: dict[str, str]) -> list[str]:
    out = []
    for name, body in sorted(defs.items()):
        reads = len(re.findall(r"from\s+(?:public\.)?logbook\b", body, re.I))
        filters = len(re.findall(r"\bdeleted_at\s+is\s+null\b", body, re.I))
        if filters < reads:
            out.append(f"{name}() reads logbook {reads} time(s) and leaves trashed entries out {filters} time(s)")
    return out


def self_test() -> int:
    good = {"get_x": "select * from logbook where deleted_at is null and a"}
    bad = {"get_y": "select * from logbook where a", "get_z": "from logbook where deleted_at IS NULL union from public.logbook where b"}
    ok = not findings(good) and len(findings(bad)) == 2
    print(("PASS" if ok else "FAIL") + " analytics-skip-trash self-test")
    return 0 if ok else 1


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    r = subprocess.run(["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-At", "-F", "\x1f", "-R", "\x1e",
                        "-c", QUERY], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    print("analytics-skip-trash: an entry in the trash never counts in the analytics")
    if r.returncode != 0:
        print(f"  SKIP: the local database could not be read ({(r.stderr or '').strip()[:160]})")
        return 0
    defs = {}
    for rec in (r.stdout or "").split("\x1e"):
        if "\x1f" in rec:
            name, body = rec.split("\x1f", 1)
            defs[name.strip()] = body
    bad = findings(defs)
    print(f"  {len(defs)} analytics function(s) read logbook")
    for b in bad:
        print(f"  - {b}")
    print("PASS" if not bad else "FAIL")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
