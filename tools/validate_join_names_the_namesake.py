#!/usr/bin/env python3
"""join-names-the-namesake - T185: two people who share a name both get into the hive (2026-08-26).

THE DAY-ONE SCENARIO: a plant pilots WorkHive and five workers are handed one invite code at the
morning briefing. Two of them are named Juan Dela Cruz - which in a Philippine plant is not a
contrived edge case, it is Tuesday. The first joins. The second, a different human being with a
different auth identity and the correct code, used to hit:

    duplicate key value violates unique constraint "hive_members_hive_id_worker_name_key"

and hive.html rendered it verbatim. He could not join his team, he was shown database internals,
and he was handed no way forward - on the pilot's first morning.

★THE CONSTRAINT IS RIGHT AND STAYS. worker_name is the attribution key across many tables; two
members sharing one name inside a hive would make every by-name rollup ambiguous. The defect was
never the constraint - it was that the function let the constraint speak to the user.

★TWO CASES RAISE THE IDENTICAL 23505 AND MUST NOT GET THE SAME ANSWER, which is the whole reason
this gate runs a real race instead of reading the source:
  - a genuine NAMESAKE (a different auth identity) must be refused BY NAME so the page can offer a
    distinguishing one;
  - the SAME user double-tapping Join must be told "you are in". Two concurrent calls both read no
    membership (READ COMMITTED - neither sees the other's uncommitted insert) and both insert, so
    the function's idempotent path is bypassed by the race and only the exception handler can tell
    these apart, by re-reading who actually won.

★HOW THE RACE IS MADE DETERMINISTIC: session A opens a transaction and inserts the row WITHOUT
committing. Session B then calls the RPC - B's pre-check cannot see A's uncommitted row, so it
passes and proceeds to INSERT, where it BLOCKS on the unique index until A commits and it receives
the violation for real. That is the genuine concurrent path, not a simulation of it, and it is why
a source-text check would not do: it would pass just as happily against a handler that returns the
wrong answer.

Re-drive: python tools/validate_join_names_the_namesake.py
"""
import io
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
CONTAINER = os.environ.get("WH_DB_CONTAINER", "supabase_db_workhive")

HIVE = "e1851850-0000-4000-8000-000000000185"
SUP = "e1851850-0000-4000-8000-00000000a000"
UID_A = "e1851850-0000-4000-8000-00000000a001"
UID_B = "e1851850-0000-4000-8000-00000000a002"
CODE = "T185PB"
NAME = "WH-T185-PROBE Juan Dela Cruz"


def psql(sql: str, timeout: int = 60):
    return subprocess.run(
        ["docker", "exec", "-i", CONTAINER, "psql", "-U", "postgres", "-d", "postgres", "-v", "ON_ERROR_STOP=0"],
        input=sql, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")


def stack_up() -> bool:
    try:
        r = psql("SELECT 1;", timeout=25)
        return r.returncode == 0 and "1" in (r.stdout or "")
    except Exception:
        return False


SEED = f"""
INSERT INTO auth.users (id, instance_id, aud, role, email, encrypted_password,
                        email_confirmed_at, created_at, updated_at)
VALUES ('{SUP}','00000000-0000-0000-0000-000000000000','authenticated','authenticated',
        'wh-t185-probe-sup@example.com','x', now(), now(), now()),
       ('{UID_A}','00000000-0000-0000-0000-000000000000','authenticated','authenticated',
        'wh-t185-probe-a@example.com','x', now(), now(), now()),
       ('{UID_B}','00000000-0000-0000-0000-000000000000','authenticated','authenticated',
        'wh-t185-probe-b@example.com','x', now(), now(), now())
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.hives (id, name, invite_code, created_by)
VALUES ('{HIVE}', 'WH-T185-PROBE Plant', '{CODE}', '{SUP}')
ON CONFLICT (id) DO NOTHING;
DELETE FROM public.hive_members WHERE hive_id = '{HIVE}';
"""

CLEAN = f"""
DELETE FROM public.hive_members WHERE hive_id = '{HIVE}';
DELETE FROM public.hives WHERE id = '{HIVE}';
DELETE FROM auth.users WHERE id IN ('{SUP}','{UID_A}','{UID_B}');
"""


def call_join(uid: str, name: str) -> str:
    """Call the RPC as `uid`; return combined output."""
    r = psql(f"""
SET ROLE authenticated;
SET request.jwt.claims = '{{"sub":"{uid}","role":"authenticated"}}';
SELECT member_status FROM public.join_hive_by_code('{CODE}', '{name}');
""")
    return (r.stdout or "") + (r.stderr or "")


def race(holder_uid: str, caller_uid: str) -> str:
    """Session A holds an UNCOMMITTED insert of NAME; session B calls the RPC and blocks on the
    unique index until A commits, so B takes the exception handler for real."""
    out = {}

    def hold():
        # insert, linger, then commit - B's INSERT waits on this row's index entry
        psql(f"""
BEGIN;
INSERT INTO public.hive_members (hive_id, worker_name, role, status, auth_uid)
VALUES ('{HIVE}', '{NAME}', 'worker', 'active', '{holder_uid}');
SELECT pg_sleep(3);
COMMIT;
""", timeout=40)

    t = threading.Thread(target=hold, daemon=True)
    t.start()
    time.sleep(1.2)                      # let A's insert land (uncommitted) before B looks
    out["b"] = call_join(caller_uid, NAME)
    t.join(timeout=40)
    return out["b"]


def main() -> int:
    if not stack_up():
        print("SKIP join-names-the-namesake - local Supabase DB not reachable (live gate)")
        return 0

    failures = []
    try:
        psql(SEED)

        # 1. THE DAY-ONE CASE: a namesake is refused BY NAME, never by the unique index.
        call_join(UID_A, NAME)                       # first Juan is in
        second = call_join(UID_B, NAME)              # a different Juan, same name
        if "duplicate key value violates unique constraint" in second:
            failures.append("a namesake was refused by the raw unique index - the second worker is "
                            "shown 'duplicate key value violates unique constraint "
                            "hive_members_hive_id_worker_name_key' and cannot join their team")
        elif "HIVE_NAME_TAKEN" not in second:
            failures.append(f"a namesake join did not raise HIVE_NAME_TAKEN; got: {second.strip()[:160]}")

        # 2. THE RACE, SAME PERSON: a double-tap must resolve to "you are in", not to a name clash.
        psql(f"DELETE FROM public.hive_members WHERE hive_id = '{HIVE}';")
        same = race(holder_uid=UID_A, caller_uid=UID_A)
        if "HIVE_NAME_TAKEN" in same:
            failures.append("double-tapping Join told the worker their own name was taken - the "
                            "concurrent path must recognise its own row and return the membership")
        elif "duplicate key value violates" in same:
            failures.append("double-tapping Join surfaced the raw unique violation")
        elif "active" not in same:
            failures.append(f"double-tapping Join did not return the membership; got: {same.strip()[:160]}")

        # 3. THE RACE, DIFFERENT PEOPLE: the loser is still refused by name.
        psql(f"DELETE FROM public.hive_members WHERE hive_id = '{HIVE}';")
        other = race(holder_uid=UID_A, caller_uid=UID_B)
        if "duplicate key value violates" in other:
            failures.append("losing the insert race to a namesake surfaced the raw unique violation")
        elif "HIVE_NAME_TAKEN" not in other:
            failures.append(f"losing the race to a namesake did not raise HIVE_NAME_TAKEN; got: {other.strip()[:160]}")

        # 4. THE RENAME MOVES THE PERSON, NOT ONE MEMBERSHIP. A hive-only rename is reverted by
        #    utils.js restoreIdentityFromSession(), which reconciles the cached name from
        #    worker_profiles.display_name - after which this worker's writes carry a name that, in
        #    this hive, belongs to someone else. So the disambiguating name must land on the
        #    profile AND every membership, in one transaction.
        psql(f"DELETE FROM public.hive_members WHERE hive_id = '{HIVE}';")
        # The rename runs BEFORE the join, which is both the page's order and the only safe one:
        # set_worker_display_name refuses a worker who already belongs to a hive, because their
        # records live under the current name across 47 tables and 19 of those carry no identity
        # column to follow them by (mig ...008). A member-less identity has nothing to orphan.
        r = psql(f"""
BEGIN;
INSERT INTO public.worker_profiles (auth_uid, username, display_name, email)
VALUES ('{UID_B}','wht185probeb','{NAME}','wh-t185-probe-b@example.com')
ON CONFLICT (auth_uid) DO UPDATE SET display_name = EXCLUDED.display_name;
SET LOCAL ROLE authenticated;
SET LOCAL request.jwt.claims = '{{"sub":"{UID_B}","role":"authenticated"}}';
SELECT public.set_worker_display_name('{NAME} (Mechanical)');
SELECT public.join_hive_by_code('{CODE}', '{NAME} (Mechanical)');
RESET ROLE;
SELECT 'PROFILE=' || display_name FROM public.worker_profiles WHERE auth_uid = '{UID_B}';
SELECT 'MEMBER=' || worker_name FROM public.hive_members
  WHERE auth_uid = '{UID_B}' AND hive_id = '{HIVE}';
ROLLBACK;
""")
        rt = (r.stdout or "") + (r.stderr or "")
        prof = re.search(r"PROFILE=(.+)", rt)
        memb = re.search(r"MEMBER=(.+)", rt)
        if not prof or not memb:
            failures.append(f"the rename probe produced no readback (set_worker_display_name "
                            f"missing?): {rt.strip()[:200]}")
        else:
            p_name, m_name = prof.group(1).strip(), memb.group(1).strip()
            if p_name != m_name:
                failures.append(f"a rename left the profile and the membership disagreeing "
                                f"(profile '{p_name}' vs membership '{m_name}') - identity restore "
                                f"will revert the cached name and this worker's writes will carry a "
                                f"name that belongs to someone else in this hive")
            elif "(Mechanical)" not in p_name:
                failures.append(f"the rename did not take: both still read '{p_name}'")

        # 5. A WORKER WITH HISTORY MUST BE REFUSED, NOT SILENTLY DISCONNECTED FROM IT. worker_name is
        #    a denormalised label across 47 tables, and 19 of them carry NO identity column to follow
        #    it by - achievement_xp_log has neither auth_uid nor hive_id, so one person's 267 XP rows
        #    cannot be located at all. Measured for a single real worker: 648 identity-linked rows
        #    plus 933 name-only rows. Renaming anyway would leave ~1,581 rows under a name their
        #    owner no longer has, and since the reads filter by worker_name their own logbook, XP and
        #    standings would vanish. So the rename is allowed only before there is anything to orphan.
        r = psql(f"""
BEGIN;
INSERT INTO public.hive_members (hive_id, worker_name, role, status, auth_uid)
VALUES ('{HIVE}', '{NAME} Veteran', 'worker', 'active', '{UID_A}') ON CONFLICT DO NOTHING;
SET LOCAL ROLE authenticated;
SET LOCAL request.jwt.claims = '{{"sub":"{UID_A}","role":"authenticated"}}';
SELECT public.set_worker_display_name('{NAME} Veteran Renamed');
ROLLBACK;
""")
        rt = (r.stdout or "") + (r.stderr or "")
        if "HIVE_NAME_HAS_HISTORY" not in rt:
            failures.append("an existing member was allowed to rename themselves. Their records live "
                            "under the old name across tables this function cannot reach (19 carry no "
                            "identity column), so the rename disconnects them from their own logbook, "
                            "XP and standings instead of refusing by name")
    finally:
        psql(CLEAN)

    # 4. The refusal has to be WALKABLE on the page that raised it: the join form carries only a
    #    code field, so naming the cause without offering a name input is a dead end.
    page = io.open(ROOT / "hive.html", encoding="utf-8", errors="replace").read()
    if not re.search(r"HIVE_NAME_TAKEN", page):
        failures.append("hive.html has no HIVE_NAME_TAKEN branch - the named refusal falls through "
                        "to 'Could not join: ' + joinErr.message, which prints Postgres internals")
    if not re.search(r'id="join-name-input"', page):
        failures.append("hive.html offers no name field on the namesake refusal - the join form has "
                        "only a code input, so the worker is told the name is taken with no way to "
                        "change it")
    if not re.search(r"wh_last_worker", page):
        failures.append("hive.html does not persist the disambiguated name to wh_last_worker - the "
                        "roster would show the new name while later writes attribute to the old one")

    if failures:
        print("FAIL join-names-the-namesake - two people who share a name cannot both work here:")
        for f in failures:
            print("    - " + f)
        return 1

    print("PASS join-names-the-namesake - a second worker with the same name is refused by name and "
          "handed a way to disambiguate; a double-tap resolves to the membership it already made.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
