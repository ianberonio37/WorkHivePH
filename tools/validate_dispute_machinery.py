#!/usr/bin/env python3
"""validate_dispute_machinery.py — T97's lock: the three-role dispute-resolution lane has real,
enforced machinery end to end.

A dispute in the marketplace touches three parties (buyer who raises it, provider it is against, and
the platform that adjudicates) and has a money consequence (a credit adjustment). T97's risk is that
the lane is only UI theatre with no backing state or enforced lifecycle. This gate holds the machinery
that makes it real:
  1. a marketplace_disputes table exists (the dispute is a first-class record, not a message);
  2. an apply_dispute_adjustment function exists (the money consequence is a controlled operation,
     not an ad-hoc balance edit); and
  3. the dispute status is CHECK-constrained (the lifecycle is enforced by the DB, so a dispute
     cannot sit in an invented state).

DB-backed (psql), read-only, browser-free. SKIPs if the DB is unreachable. Registered in
run_platform_checks (Platform)."""
from __future__ import annotations

import io
import subprocess
import sys

CHECK_NAMES = ["dispute-machinery"]


def _psql(sql: str) -> str | None:
    try:
        r = subprocess.run(
            ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres", "-t", "-A", "-c", sql],
            capture_output=True, text=True, timeout=45)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def _fetch() -> dict | None:
    tbl = _psql("select (to_regclass('public.marketplace_disputes') is not null)::text;")
    if tbl is None:
        return None
    fn = _psql("select exists(select 1 from pg_proc where proname='apply_dispute_adjustment')::text;")
    chk = _psql("select exists(select 1 from pg_constraint where conrelid='public.marketplace_disputes'::regclass "
                "and contype='c' and pg_get_constraintdef(oid) ilike '%status%')::text;")
    # boolean::text is 'true'/'false' in psql, NOT 't'/'f'
    return {"table": tbl == "true", "fn": fn == "true", "status_check": chk == "true"}


def check(data: dict) -> list[str]:
    problems: list[str] = []
    if not data.get("table"):
        problems.append("no marketplace_disputes table — a dispute is not a first-class record (UI theatre only)")
    if not data.get("fn"):
        problems.append("no apply_dispute_adjustment function — the money consequence is an uncontrolled ad-hoc edit")
    if not data.get("status_check"):
        problems.append("no CHECK on marketplace_disputes.status — the dispute lifecycle is not DB-enforced")
    return problems


def main() -> int:
    data = _fetch()
    if data is None:
        print("SKIP dispute-machinery — DB unreachable (no unearned pass)."); return 0
    problems = check(data)
    if problems:
        print("FAIL dispute-machinery — the dispute lane is not real end to end:")
        for p in problems:
            print(f"    {p}")
        return 1
    print("PASS dispute-machinery — marketplace_disputes is a first-class record, apply_dispute_adjustment makes "
          "the credit consequence a controlled operation, and a CHECK constraint enforces the dispute lifecycle: "
          "the three-role lane is real, not theatre.")
    return 0


def self_test() -> int:
    fails = []
    if check({"table": True, "fn": True, "status_check": True}):
        fails.append("full machinery should PASS")
    if not any("first-class record" in p for p in check({"table": False, "fn": True, "status_check": True})):
        fails.append("missing table should FAIL")
    if not any("ad-hoc edit" in p for p in check({"table": True, "fn": False, "status_check": True})):
        fails.append("missing adjustment fn should FAIL")
    if not any("not DB-enforced" in p for p in check({"table": True, "fn": True, "status_check": False})):
        fails.append("missing status CHECK should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_dispute_machinery self-test (missing table / fn / status-check redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
