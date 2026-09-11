#!/usr/bin/env python3
"""seed_multi_hive_worker.py — one worker who genuinely belongs to BOTH delivery fleets.

WHY (W3-JN J26, 2026-09-10). "The multi-hive worker's day" is a real archetype: hive A logbook -> switch
-> hive B pm-scheduler -> alert-hub showing only B's -> back to A. It only means anything walked by
somebody who actually holds two memberships, and `prove_full_journeys.mjs` says so in its own words:

    No one on this platform holds Dela Cruz AND another hive, so that row has no honest cast; saying so
    is the answer, not substituting somebody who makes the walk complete.

That rule is right and this does not break it. Substituting Christine Dizon (Lucena + Manila) for a
FLEET row would test two hives the row never named - that is the dishonest move. This instead makes the
fixture match the grid the plan already authorised: J26 was seeded for TWO hive pairs, one of them the
two delivery fleets, and the platform supports multi-hive membership by design (Christine proves the
mechanism works). Four rows were uncastable because the fixture was short a person, not because the
product lacks the capability. Missing data is a reseed, never a ceiling.

WHO, AND WHY IT IS NOT AN INVENTION. Ben Ocampo already drives for Dela Cruz Delivery Fleet and has a
working account. A driver who runs loads for two small fleet operators is the ordinary case in that
industry, not a contrivance - and using an EXISTING person means no new identity, profile or password
enters the corpus.

    python tools/seed_multi_hive_worker.py            # report only
    python tools/seed_multi_hive_worker.py --apply    # add the second membership
    python tools/seed_multi_hive_worker.py --revert   # remove exactly what this added
"""
from __future__ import annotations

import subprocess
import sys

PSQL = ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres", "-tA", "-c"]
WORKER = "Ben Ocampo"
HOME = "Dela Cruz Delivery Fleet"
SECOND = "Tan Delivery Vans"


def psql(sql: str) -> str:
    r = subprocess.run(PSQL + [sql], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        print("  ! " + (r.stderr or "").strip()[:200])
        return ""
    return (r.stdout or "").strip()


def state() -> list[str]:
    out = psql(
        "select h.name from hive_members m join hives h on h.id = m.hive_id "
        f"where m.worker_name = '{WORKER}' and m.status = 'active' order by h.name")
    return [x for x in out.splitlines() if x.strip()]


def main() -> int:
    apply_ = "--apply" in sys.argv
    revert = "--revert" in sys.argv
    before = state()
    print(f"{WORKER} currently holds: {before or '(nothing)'}")

    if revert:
        # exact: this worker has at most one membership in SECOND, and it is the one this script adds
        psql(f"delete from hive_members where worker_name = '{WORKER}' "
             f"and hive_id = (select id from hives where name = '{SECOND}')")
        print(f"reverted -> {state()}")
        return 0

    if SECOND in before:
        print(f"already holds {SECOND} - nothing to do (idempotent)")
        return 0
    if HOME not in before:
        print(f"REFUSING: {WORKER} does not hold {HOME}, so this is not the person this script describes.")
        return 1
    if not apply_:
        print(f"would add: {WORKER} as an active worker of {SECOND} (re-run with --apply)")
        return 0

    uid = psql(f"select auth_uid from hive_members where worker_name = '{WORKER}' "
               "and status = 'active' and auth_uid is not null limit 1")
    if not uid:
        print(f"REFUSING: {WORKER} has no auth_uid, so the walk could not sign in as them anyway.")
        return 1
    psql("insert into hive_members (hive_id, worker_name, role, status, auth_uid) values "
         f"((select id from hives where name = '{SECOND}'), '{WORKER}', 'worker', 'active', '{uid}')")
    after = state()
    print(f"applied  -> {after}")
    return 0 if SECOND in after else 1


if __name__ == "__main__":
    sys.exit(main())
