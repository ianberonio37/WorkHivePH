#!/usr/bin/env python3
"""validate_profile_no_self_privilege.py — T365's lock: a client cannot MASS-ASSIGN a privileged column it
is not allowed to raise on its own record — self-granting a marketplace verification badge, or self-promoting
to supervisor. Both are privilege/trust escalations that RLS-with-no-WITH-CHECK on a self-updatable row would
let through unless a guard bites; this gate proves the guards bite, LIVE.

The real mechanism (T365's basis cited tg_guard_approval, which is actually the work-table supervisor-approval
guard — a DIFFERENT property; corrected 2026-09-01):
  1. service_providers.verified — the row is self-updatable (RLS: auth_uid = auth.uid(), NO WITH CHECK) and
     `authenticated` even holds a column-UPDATE grant on `verified`. What stops a seller stamping their own
     badge is the BEFORE trigger guard_service_provider_writes: "verification is granted by the platform, not
     self-declared". This is the 'a trust claim no query enforces' class — so we make the query enforce it and
     PROVE it by trying the self-stamp and requiring the raise.
  2. hive_members.role — the UPDATE policy is supervisor-only (hive_id IN user_supervisor_hive_ids()), so a
     worker's self-promotion updates ZERO rows (RLS filters it), never 1.

LIVE psql probe, each in a ROLLED-BACK transaction (no data changes), simulating the caller via SET ROLE
authenticated + request.jwt.claims.sub. DB-backed, browser-free. SKIPs if the DB/fixtures are unreachable
(no unearned pass). Registered in run_platform_checks (Platform).
"""
from __future__ import annotations

import io
import subprocess
import sys

CHECK_NAMES = ["profile-no-self-privilege"]


def _psql(sql: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
         "-v", "ON_ERROR_STOP=1", "-t", "-A"],
        input=sql, capture_output=True, text=True, timeout=40)


def _scalar(sql: str) -> str | None:
    r = subprocess.run(
        ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
         "-t", "-A", "-c", sql], capture_output=True, text=True, timeout=30)
    out = (r.stdout or "").strip()
    return out.splitlines()[0] if out else None


def probe():
    """Returns (available, verify_refused, role_rows) — available=False when fixtures are missing (SKIP)."""
    seller = _scalar("select auth_uid from public.service_providers where auth_uid is not null "
                     "and coalesce(verified,false)=false limit 1;")
    worker = _scalar("select auth_uid from public.hive_members where auth_uid is not null "
                     "and role <> 'supervisor' and status='active' limit 1;")
    if not seller or not worker:
        return (False, None, None)
    # 1. seller self-stamps verified -> the trigger must RAISE
    verify_sql = (
        "begin;\n"
        "set local role authenticated;\n"
        f"select set_config('request.jwt.claims', '{{\"sub\":\"{seller}\",\"role\":\"authenticated\"}}', true);\n"
        f"update public.service_providers set verified = true where auth_uid = '{seller}';\n"
        "rollback;\n")
    vr = _psql(verify_sql)
    verify_refused = ("not self-declared" in (vr.stderr or "").lower()
                      or "check_violation" in (vr.stderr or "").lower()
                      or vr.returncode != 0)
    # 2. worker self-promotes to supervisor -> RLS must filter it to ZERO rows
    role_sql = (
        "begin;\n"
        "set local role authenticated;\n"
        f"select set_config('request.jwt.claims', '{{\"sub\":\"{worker}\",\"role\":\"authenticated\"}}', true);\n"
        f"update public.hive_members set role = 'supervisor' where auth_uid = '{worker}' and role <> 'supervisor';\n"
        "rollback;\n")
    rr = _psql(role_sql)
    # psql prints "UPDATE N"; RLS refusal => UPDATE 0. An error also counts as refused.
    role_rows = None
    if rr.returncode != 0:
        role_rows = 0  # errored out = not silently promoted
    else:
        for line in (rr.stdout or "").splitlines():
            if line.strip().upper().startswith("UPDATE "):
                try:
                    role_rows = int(line.strip().split()[1])
                except Exception:
                    role_rows = None
    return (True, verify_refused, role_rows)


def check(verify_refused: bool, role_rows: int) -> list[str]:
    problems: list[str] = []
    if not verify_refused:
        problems.append("a seller SELF-STAMPED service_providers.verified = true and it was NOT refused — the "
                        "platform's trust badge is self-declarable (guard_service_provider_writes is not "
                        "biting). This is a trust-fraud / mass-assignment escalation.")
    if role_rows is None or role_rows > 0:
        problems.append(f"a worker's self-promotion to supervisor changed {role_rows} hive_members row(s) "
                        f"(expected 0 — RLS UPDATE must be supervisor-only). Self-privilege escalation.")
    return problems


def main() -> int:
    try:
        available, verify_refused, role_rows = probe()
    except Exception as e:
        print(f"SKIP profile-no-self-privilege — DB unreachable ({e}); no unearned pass.")
        return 0
    if not available:
        print("SKIP profile-no-self-privilege — no non-verified seller / non-supervisor worker fixture to "
              "probe with (no unearned pass; seed the marketplace + a hive).")
        return 0
    problems = check(verify_refused, role_rows)
    if problems:
        print("FAIL profile-no-self-privilege — a client can mass-assign a privileged field on its own record:")
        for p in problems:
            print(f"    {p}")
        return 1
    print("PASS profile-no-self-privilege — a seller CANNOT self-stamp verified (guard trigger raises) and a "
          "worker CANNOT self-promote to supervisor (RLS UPDATE is supervisor-only; 0 rows).")
    return 0


def self_test() -> int:
    fails = []
    if check(True, 0):
        fails.append("the real holding case (verify refused, 0 role rows) should PASS")
    if not any("trust-fraud" in p for p in check(False, 0)):
        fails.append("a seller self-stamping verified should FAIL")
    if not any("self-promotion" in p for p in check(True, 1)):
        fails.append("a worker self-promoting (1 row) should FAIL")
    if not any("self-promotion" in p for p in check(True, None)):
        fails.append("an unparseable role-update result should FAIL (never a silent pass)")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_profile_no_self_privilege self-test (self-verify / self-promote / unparseable redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
