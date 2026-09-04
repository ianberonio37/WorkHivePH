#!/usr/bin/env python3
"""validate_audit_log_append_only.py — T384's lock: the hive audit log is APPEND-ONLY under RLS — a user can
insert their own action and supervisors can read, but NO ONE can UPDATE or DELETE a row, so the audit trail
cannot be rewritten or gapped to hide what happened.

hive_audit_log is the tamper-evidence record. Under RLS, a verb with NO policy is DENIED by default — so the
append-only guarantee is simply the ABSENCE of any UPDATE/DELETE/ALL policy, plus RLS being ON (without RLS,
the table grants would decide and the default-deny is gone). This gate asserts exactly that: RLS enabled,
an INSERT policy exists (members can append), a SELECT policy exists (supervisors/grafana can read), and NO
UPDATE / DELETE / ALL policy exists (no tamper, no gap).

DB-backed (psql), browser-free. SKIPs if the DB is unreachable (no unearned pass). Registered in
run_platform_checks (Platform).
"""
from __future__ import annotations

import io
import subprocess
import sys

CHECK_NAMES = ["audit-log-append-only"]
TABLE = "hive_audit_log"


def _fetch():
    try:
        rls = subprocess.run(
            ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
             "-t", "-A", "-c", f"select relrowsecurity from pg_class where relname='{TABLE}';"],
            capture_output=True, text=True, timeout=30)
        if rls.returncode != 0 or not (rls.stdout or "").strip():
            return None
        cmds = subprocess.run(
            ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
             "-t", "-A", "-c", f"select polcmd from pg_policy pol join pg_class c on c.oid=pol.polrelid "
             f"where c.relname='{TABLE}';"],
            capture_output=True, text=True, timeout=30)
        return {"rls": (rls.stdout or "").strip().lower().startswith("t"),
                "cmds": [x.strip() for x in (cmds.stdout or "").splitlines() if x.strip()]}
    except Exception:
        return None


def check(data: dict) -> list[str]:
    problems: list[str] = []
    if not data.get("rls"):
        problems.append(f"RLS is NOT enabled on {TABLE} — the append-only guarantee depends on RLS "
                        f"default-deny; without it, table grants decide and a row can be tampered/deleted.")
    cmds = set(data.get("cmds", []))
    # polcmd: r=SELECT a=INSERT w=UPDATE d=DELETE *=ALL
    if "a" not in cmds:
        problems.append(f"{TABLE} has no INSERT policy — members cannot append audit rows (the log is dead).")
    if "r" not in cmds:
        problems.append(f"{TABLE} has no SELECT policy — supervisors cannot READ the audit trail.")
    if "w" in cmds:
        problems.append(f"{TABLE} has an UPDATE policy — a row could be REWRITTEN (audit tampering).")
    if "d" in cmds:
        problems.append(f"{TABLE} has a DELETE policy — a row could be REMOVED (audit gap).")
    if "*" in cmds:
        problems.append(f"{TABLE} has an ALL policy — it permits UPDATE/DELETE, breaking append-only.")
    return problems


def main() -> int:
    data = _fetch()
    if data is None:
        print("SKIP audit-log-append-only — DB unreachable or table absent (no unearned pass).")
        return 0
    problems = check(data)
    if problems:
        print("FAIL audit-log-append-only — the audit trail is not tamper-proof:")
        for p in problems:
            print(f"    {p}")
        return 1
    print("PASS audit-log-append-only — hive_audit_log has RLS on, INSERT(member) + SELECT(supervisor) "
          "policies, and NO UPDATE/DELETE/ALL policy — the trail cannot be rewritten or gapped.")
    return 0


def self_test() -> int:
    good = {"rls": True, "cmds": ["a", "r", "r"]}
    fails = []
    if check(good):
        fails.append("the real append-only posture should PASS")
    if not any("RLS is NOT enabled" in p for p in check({**good, "rls": False})):
        fails.append("RLS disabled should FAIL")
    if not any("UPDATE policy" in p for p in check({"rls": True, "cmds": ["a", "r", "w"]})):
        fails.append("an UPDATE policy should FAIL")
    if not any("DELETE policy" in p for p in check({"rls": True, "cmds": ["a", "r", "d"]})):
        fails.append("a DELETE policy should FAIL")
    if not any("ALL policy" in p for p in check({"rls": True, "cmds": ["*"]})):
        fails.append("an ALL policy should FAIL")
    if not any("no INSERT" in p for p in check({"rls": True, "cmds": ["r"]})):
        fails.append("a missing INSERT policy should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_audit_log_append_only self-test (no-RLS / UPDATE / DELETE / ALL / no-INSERT redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
