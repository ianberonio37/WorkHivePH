#!/usr/bin/env python3
"""validate_stale_membership_no_access.py — T374's lock: a REMOVED or SUSPENDED membership grants NO access.
The tenancy is derived by three DEFINER helpers that every RLS policy on the platform leans on, and each
must filter hive_members to status='active' — so a stale (non-active) row cannot escalate a user who was
removed from a hive back into it.

The helpers and the invariant (verified live 2026-09-01 against the real function bodies):
  · user_hive_ids()            -> hive_members WHERE auth_uid = auth.uid() AND status = 'active'
  · user_supervisor_hive_ids() -> ... AND role = 'supervisor' AND status = 'active'
  · user_can_access_hive(h)     -> service_role OR h IN user_hive_ids()  (inherits the active filter)

If any helper drops `status = 'active'`, a suspended or ex-member silently regains access to every table
those helpers gate — the whole platform's tenancy leaks at once. This gate reads the LIVE function
definitions (pg_get_functiondef) and refuses if the active-status filter is gone.

DB-backed (psql), browser-free. SKIPs if the DB is unreachable (no unearned pass). Registered in
run_platform_checks (Platform).
"""
from __future__ import annotations

import io
import subprocess
import sys

CHECK_NAMES = ["stale-membership-no-access"]

# each helper -> the tokens its body MUST contain (the active-membership filter on hive_members)
HELPERS = {
    "user_hive_ids":            ["hive_members", "auth.uid()", "status", "active"],
    "user_supervisor_hive_ids": ["hive_members", "auth.uid()", "status", "active", "supervisor"],
}
DELEGATOR = "user_can_access_hive"


def _fndef(name: str) -> str | None:
    try:
        r = subprocess.run(
            ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
             "-t", "-A", "-c", f"select pg_get_functiondef(oid) from pg_proc where proname='{name}' limit 1;"],
            capture_output=True, text=True, timeout=30)
        return (r.stdout or "").strip() or None
    except Exception:
        return None


def check(defs: dict) -> list[str]:
    problems: list[str] = []
    for name, tokens in HELPERS.items():
        body = defs.get(name)
        if body is None:
            problems.append(f"{name}() not found — the tenancy helper is missing (RLS would have no active filter).")
            continue
        low = body.lower()
        # the active-status filter: status ... 'active' must both be present in the hive_members query
        if "hive_members" not in low or "status" not in low or "active" not in low:
            problems.append(f"{name}() no longer filters hive_members to status='active' — a removed/suspended "
                            f"member would regain access (stale-membership privilege escalation).")
        if "auth.uid()" not in low:
            problems.append(f"{name}() no longer scopes to auth.uid() — it would not be caller-specific.")
        if name == "user_supervisor_hive_ids" and "supervisor" not in low:
            problems.append(f"{name}() no longer requires role='supervisor'.")
    # the delegator must route through user_hive_ids (so it inherits the active filter), not re-query loosely
    dele = defs.get(DELEGATOR)
    if dele is not None and "user_hive_ids" not in dele.lower() and "service_role" not in dele.lower():
        problems.append(f"{DELEGATOR}() does not delegate to user_hive_ids() — it may not inherit the "
                        f"active-membership filter.")
    return problems


def main() -> int:
    defs = {n: _fndef(n) for n in list(HELPERS) + [DELEGATOR]}
    if all(v is None for v in defs.values()):
        print("SKIP stale-membership-no-access — DB unreachable (no unearned pass).")
        return 0
    problems = check(defs)
    if problems:
        print("FAIL stale-membership-no-access — a stale (non-active) membership can escalate:")
        for p in problems:
            print(f"    {p}")
        return 1
    print("PASS stale-membership-no-access — user_hive_ids / user_supervisor_hive_ids filter hive_members to "
          "status='active' (scoped to auth.uid()), and user_can_access_hive delegates through them — a "
          "removed/suspended member gets no access.")
    return 0


def self_test() -> int:
    good = {
        "user_hive_ids": "select hive_id from hive_members where auth_uid = auth.uid() and status = 'active'",
        "user_supervisor_hive_ids": "select hive_id from hive_members where auth_uid = auth.uid() and role = 'supervisor' and status = 'active'",
        "user_can_access_hive": "select ... or (p_hive_id in (select public.user_hive_ids()))",
    }
    fails = []
    if check(good):
        fails.append("the real active-filtered helpers should PASS")
    bad = dict(good); bad["user_hive_ids"] = "select hive_id from hive_members where auth_uid = auth.uid()"
    if not any("status='active'" in p for p in check(bad)):
        fails.append("dropping the status='active' filter should FAIL")
    bad2 = dict(good); bad2["user_supervisor_hive_ids"] = "select hive_id from hive_members where auth_uid = auth.uid() and status = 'active'"
    if not any("supervisor" in p for p in check(bad2)):
        fails.append("dropping role='supervisor' should FAIL")
    bad3 = dict(good); bad3["user_hive_ids"] = None
    if not any("missing" in p for p in check(bad3)):
        fails.append("a missing helper should FAIL")
    bad4 = dict(good); bad4["user_can_access_hive"] = "select p_hive_id in (select hive_id from hive_members)"
    if not any("delegate" in p for p in check(bad4)):
        fails.append("a delegator that re-queries loosely should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_stale_membership_no_access self-test (no-active / no-supervisor / missing / loose-delegator redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
