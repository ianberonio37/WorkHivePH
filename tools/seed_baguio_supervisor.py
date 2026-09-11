#!/usr/bin/env python3
"""seed_baguio_supervisor.py — give Baguio Textile Mills a supervisor who is not a platform admin.

WHY (found walking W3530 through the MCPs, 2026-09-10). J19 — "locked out and back to work" — declares a
worker × supervisor PAIR, and its last step is the audit log, which the product correctly shows only to
supervisors. Walked as Wilfredo Malabanan the worker half is sound; the supervisor half could not be
walked at all, because **Baguio Textile Mills is the only one of the six hives whose single supervisor,
Leandro Marquez, sits in `marketplace_platform_admins`** — and an admin cast may answer ROUTE questions
but never ENTITLEMENT ones. An admin sees doors an ordinary supervisor does not, which is the whole
lesson of [[feedback_the_probes_persona_was_an_admin]]: seven "cross-hive leaks" were an admin
legitimately reading.

Measured, so the size of the gap is on the record rather than asserted: **154 trajectory rows are cast in
Baguio, 129 of them declare a role pair, and 109 name a supervisor.** Every one of those supervisor
halves is currently uncastable. Missing data is a reseed, never a ceiling.

WHO, AND WHY IT IS NOT AN INVENTION — the same reasoning `seed_multi_hive_worker.py` used for Ben Ocampo
earlier the same day. Christine Dizon already supervises TWO hives (Lucena Pharmaceutical and Manila
Electronics); `prove_full_journeys.mjs` names her in its own comments as the person who proves multi-hive
membership works. Using her means **no new identity, profile or password enters the corpus**, and a
supervisor covering three plants for one manufacturing group is the ordinary case in that industry, not a
contrivance.

WHAT THIS DELIBERATELY DOES NOT DO, because both alternatives change meanings that 154 banked rows rest
on: it does not promote Bryan Garcia or Wilfredo Malabanan from worker to supervisor (that would rewrite
what their rows are about), and it does not remove Leandro Marquez from `marketplace_platform_admins`
(that is a security-relevant table and the marketplace rows depend on who is in it). This is purely
ADDITIVE: nothing existing is altered, and `--revert` removes exactly what it added.

    python tools/seed_baguio_supervisor.py            # report only
    python tools/seed_baguio_supervisor.py --apply    # add the membership
    python tools/seed_baguio_supervisor.py --revert   # remove exactly what this added
"""
from __future__ import annotations

import subprocess
import sys

PSQL = ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres", "-tA", "-c"]
SUPERVISOR = "Christine Dizon"
TARGET = "Baguio Textile Mills"


def psql(sql: str) -> str:
    r = subprocess.run(PSQL + [sql], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        print("  ! " + (r.stderr or "").strip()[:200])
        return ""
    return (r.stdout or "").strip()


def hives_held() -> list[str]:
    out = psql("select h.name from hive_members m join hives h on h.id = m.hive_id "
               f"where m.worker_name = '{SUPERVISOR}' and m.status = 'active' order by h.name")
    return [x for x in out.splitlines() if x.strip()]


def clean_supervisors(hive: str) -> list[str]:
    """Supervisors of `hive` who are NOT marketplace platform admins - the castable ones."""
    out = psql(
        "select m.worker_name from hive_members m join hives h on h.id = m.hive_id "
        "left join auth.users u on u.id = m.auth_uid "
        f"where h.name = '{hive}' and m.status = 'active' and m.role = 'supervisor' "
        "and u.email is not null "
        "and m.worker_name not in (select worker_name from marketplace_platform_admins) "
        "order by m.worker_name")
    return [x for x in out.splitlines() if x.strip()]


def main() -> int:
    apply_ = "--apply" in sys.argv
    revert = "--revert" in sys.argv

    before = clean_supervisors(TARGET)
    print(f"{TARGET} non-admin supervisors: {before or '(none - the gap this fixes)'}")
    print(f"{SUPERVISOR} currently supervises: {hives_held() or '(nothing)'}")

    if revert:
        # exact: the only membership this script ever creates is SUPERVISOR in TARGET
        psql(f"delete from hive_members where worker_name = '{SUPERVISOR}' "
             f"and hive_id = (select id from hives where name = '{TARGET}')")
        print(f"reverted -> {TARGET} non-admin supervisors: {clean_supervisors(TARGET) or '(none)'}")
        return 0

    if SUPERVISOR in before:
        print("already applied - nothing to do (idempotent)")
        return 0
    if before:
        print(f"REFUSING: {TARGET} already has a castable supervisor ({', '.join(before)}); "
              "this script exists only for the hive that has none.")
        return 1

    held = hives_held()
    if not held:
        print(f"REFUSING: {SUPERVISOR} holds no active membership, so this is not the person described here.")
        return 1
    uid = psql(f"select auth_uid from hive_members where worker_name = '{SUPERVISOR}' "
               "and status = 'active' and auth_uid is not null limit 1")
    if not uid:
        print(f"REFUSING: {SUPERVISOR} has no auth_uid, so no walk could sign in as them anyway.")
        return 1
    if psql(f"select count(*) from marketplace_platform_admins where worker_name = '{SUPERVISOR}'") != "0":
        print(f"REFUSING: {SUPERVISOR} is a marketplace platform admin, which is the very problem "
              "this script exists to solve.")
        return 1

    if not apply_:
        print(f"would add: {SUPERVISOR} as an active SUPERVISOR of {TARGET}, reusing their existing "
              f"auth account (re-run with --apply)")
        return 0

    psql("insert into hive_members (hive_id, worker_name, role, status, auth_uid) values "
         f"((select id from hives where name = '{TARGET}'), '{SUPERVISOR}', 'supervisor', 'active', '{uid}')")
    after = clean_supervisors(TARGET)
    print(f"applied  -> {TARGET} non-admin supervisors: {after or '(none)'}")
    print(f"           {SUPERVISOR} now supervises: {hives_held()}")
    return 0 if SUPERVISOR in after else 1


if __name__ == "__main__":
    sys.exit(main())
