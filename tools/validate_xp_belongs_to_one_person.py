#!/usr/bin/env python3
"""xp-belongs-to-one-person - T17/T51: an XP ledger keyed by NAME merges two people who share one.

achievement_xp_log carries id, worker_name, achievement_id, xp_earned, source_action, source_id,
earned_at, reversed_at - and NO auth_uid and NO hive_id. Its RLS reads
`worker_name IN (SELECT auth_worker_names())`, so a row belongs to whoever answers to that name.

★WHY THAT IS A HAZARD RATHER THAN A CHOICE: worker_name is unique PER HIVE, not globally. Two
different people in two different hives may both be Juan Dela Cruz - which in a Philippine plant is
ordinary - and this table cannot tell them apart. Their XP totals merge, their levels are computed
from each other's work, and because the RLS predicate is the NAME, each can READ the other's ledger:
achievement_id, source_action, source_id and timestamps, describing work done in a hive they have
never belonged to.

★MEASURED 2026-08-26: it is NOT happening. 982 XP rows across 20 distinct names, and ZERO names held
by more than one auth_uid. That is exactly why this gate exists now - while the data is still
unambiguous, a backfill could resolve every row to a person; once two namesakes accumulate history
the ledgers cannot be untangled afterwards, because nothing recorded which of them earned what.

★SO THIS DETECTS THE TRIGGER, IT DOES NOT PRETEND TO FIX IT. The real remedy is an auth_uid column,
backfilled while it is still unambiguous, with the four read sites (achievements.html x2,
logbook.html, pm-scheduler.html) and the RLS predicate moved onto it - a schema change to a ledger
that carries reversal semantics, which is Ian's call rather than something to smuggle in. What this
does is fail the moment the condition that makes the merge possible appears, so the window to fix it
cleanly cannot close unnoticed.

Re-drive: python tools/validate_xp_belongs_to_one_person.py
"""
import io
import os
import re
import subprocess
import sys

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

CONTAINER = os.environ.get("WH_DB_CONTAINER", "supabase_db_workhive")


def psql(sql: str):
    return subprocess.run(
        ["docker", "exec", "-i", CONTAINER, "psql", "-U", "postgres", "-d", "postgres", "-tA"],
        input=sql, capture_output=True, text=True, timeout=90, encoding="utf-8", errors="replace")


def main() -> int:
    probe = psql("SELECT 1;")
    if probe.returncode != 0:
        print("SKIP xp-belongs-to-one-person - local database not reachable (live gate)")
        return 0

    # If the column ever arrives, the hazard is structurally gone and this gate should say so rather
    # than keep policing a condition that no longer matters.
    has_uid = psql("SELECT count(*) FROM information_schema.columns "
                   "WHERE table_name='achievement_xp_log' AND column_name='auth_uid';")
    if re.search(r"\b[1-9]\b", has_uid.stdout or ""):
        print("PASS xp-belongs-to-one-person - achievement_xp_log now carries auth_uid, so the ledger "
              "is keyed to a person rather than to a name. The name-collision hazard is structurally "
              "gone; this gate can be retired once the readers and the RLS predicate use it.")
        return 0

    dupes = psql("""
SELECT coalesce(string_agg(worker_name || ' (' || people || ' people, ' || hives || ' hives)', '; '), '')
FROM (SELECT worker_name, count(DISTINCT auth_uid) AS people, count(DISTINCT hive_id) AS hives
      FROM public.hive_members GROUP BY worker_name HAVING count(DISTINCT auth_uid) > 1) q;""")
    collisions = (dupes.stdout or "").strip()

    stats = psql("SELECT count(*) || '|' || count(DISTINCT worker_name) FROM public.achievement_xp_log;")
    rows, names = (stats.stdout or "0|0").strip().split("|")[:2]

    if collisions:
        print(f"FAIL xp-belongs-to-one-person - two different people now share one worker_name: "
              f"{collisions}")
        print("    achievement_xp_log has no auth_uid and its RLS reads by NAME, so from this moment "
              "their XP totals merge, their levels are computed from each other's work, and each can "
              "read the other's ledger - source_action and source_id describing work done in a hive "
              "they never belonged to.")
        print("    THE WINDOW TO FIX THIS CLEANLY IS CLOSING: a backfill can only resolve rows to a "
              "person while every name still maps to exactly one. Add auth_uid, backfill now, and "
              "move the four readers and the RLS predicate onto it.")
        return 1

    print(f"  achievement_xp_log: {rows} rows across {names} names · no name held by two people")
    print("PASS xp-belongs-to-one-person - every worker_name in the XP ledger still resolves to "
          "exactly one person, so a backfill onto auth_uid remains unambiguous.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
