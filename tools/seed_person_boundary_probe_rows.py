#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Seed a STRANGER's row into the five person-scoped tables that had nothing to hide, so the boundary becomes provable.

WHY THIS EXISTS. tools/prove_tenant_refusal.mjs grew a person-scoped loop: fifteen public tables carry no hive_id
at all - they are scoped to a PERSON by auth_uid or worker_name - so every tenant sweep had skipped them in
silence. Ten could be tested. Five reported UNPROVEN for one honest reason: nobody other than the subject had any
rows in them, and a refusal of nothing proves nothing.

  avatar_state - marketplace_saved_searches - mfa_enrollments - push_subscriptions - resume_versions

Missing data is never a ceiling, it is a reseed - and these five are the ones I least want silently unproven:
mfa_enrollments is somebody's second factor, push_subscriptions is a device endpoint, resume_versions is a
personal document. After this runs, the prover has a real stranger's row to be refused.

*WHAT A "STRANGER" IS HERE, and why it is not simply "another person". The policies on these tables are not all
"own rows only" - several admit a CO-MEMBER by design (worker_achievements is an achievement wall the hive can
see). So the subject of a refusal test must share NO active hive with the actor, or the probe measures a policy
doing its job and calls it a leak - which is exactly the false finding the prover made on its first run. This
script picks a seeded persona with no shared membership and seeds under THEIR auth_uid.

*IDEMPOTENT, AND IT NEVER TOUCHES A REAL RECORD. Every row is tagged in a column the table already has (a note,
a name, a user_agent) with WH_PROBE_TAG, so a re-run adds nothing and `--remove` takes exactly these rows back
out. Nothing belonging to anyone else is modified or deleted. Local personas only - this must never be pointed
at production data.

  python tools/seed_person_boundary_probe_rows.py            # show what it would do
  python tools/seed_person_boundary_probe_rows.py --apply
  python tools/seed_person_boundary_probe_rows.py --remove --apply
"""
import argparse
import io
import json
import subprocess
import sys

ACTOR = "Wilfredo Malabanan"          # the prover's default subject; the stranger must share no hive with him
TAG = "wh-boundary-probe"             # every seeded row carries this, so removal is exact


def psql(sql):
    try:
        out = subprocess.run(
            ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
             "-tA", "-c", sql],
            capture_output=True, text=True, timeout=120)
        if out.returncode != 0:
            return "", (out.stderr or "").strip()
        return out.stdout.strip(), ""
    except Exception as e:                                   # noqa: BLE001
        return "", str(e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--remove", action="store_true")
    a = ap.parse_args()

    me, err = psql("select auth_uid::text from hive_members where worker_name = '{0}' "
                   "and status = 'active' limit 1".format(ACTOR))
    if err or not me:
        print("REFUSED - could not resolve the actor {0}: {1}".format(ACTOR, err or "no active membership"))
        return 1

    # a persona sharing NO active hive with the actor, preferring one who already owns a resume document so
    # resume_versions can be seeded against a real parent row rather than a fabricated FK
    stranger, err = psql(
        "with me as (select '{0}'::uuid u) "
        "select m.worker_name || '|' || m.auth_uid::text "
        "from hive_members m where m.status = 'active' and m.auth_uid is not null "
        "and not exists (select 1 from hive_members x join hive_members y on y.hive_id = x.hive_id "
        "                and y.status = 'active' where x.auth_uid = (select u from me) "
        "                and x.status = 'active' and y.auth_uid = m.auth_uid) "
        "group by m.worker_name, m.auth_uid "
        "order by (select count(*) from resume_documents r where r.auth_uid = m.auth_uid) desc limit 1"
        .format(me))
    if err or not stranger or "|" not in stranger:
        print("REFUSED - no seeded persona shares no hive with {0}: {1}".format(ACTOR, err or "none found"))
        return 1
    sname, suid = stranger.split("|")
    print("actor    {0} ({1})".format(ACTOR, me[:8]))
    print("stranger {0} ({1}) - shares no active hive with the actor".format(sname, suid[:8]))

    resume, _ = psql("select id::text from resume_documents where auth_uid = '{0}'::uuid limit 1".format(suid))

    # one statement per table. Each is guarded by a NOT EXISTS on the tag, so applying twice seeds once.
    plan = [
        ("avatar_state",
         "insert into avatar_state (session_id, current_state, emotion, auth_uid) "
         "select '{tag}', 'idle', 'neutral', '{uid}'::uuid "
         "where not exists (select 1 from avatar_state where session_id = '{tag}')"),
        ("marketplace_saved_searches",
         "insert into marketplace_saved_searches (worker_name, search_name, section, query_text) "
         "select '{sname}', '{tag}', 'parts', 'bearing' "
         "where not exists (select 1 from marketplace_saved_searches where search_name = '{tag}')"),
        ("mfa_enrollments",
         "insert into mfa_enrollments (auth_uid, worker_name, notes) "
         "select '{uid}'::uuid, '{sname}', '{tag}' "
         "where not exists (select 1 from mfa_enrollments where notes = '{tag}')"),
        ("push_subscriptions",
         "insert into push_subscriptions (auth_uid, endpoint, p256dh, auth, user_agent) "
         "select '{uid}'::uuid, 'https://example.invalid/{tag}', '{tag}-p256dh', '{tag}-auth', '{tag}' "
         "where not exists (select 1 from push_subscriptions where user_agent = '{tag}')"),
    ]
    if resume:
        plan.append(("resume_versions",
                     "insert into resume_versions (resume_id, auth_uid, doc, note) "
                     "select '{rid}'::uuid, '{uid}'::uuid, '{{}}'::jsonb, '{tag}' "
                     "where not exists (select 1 from resume_versions where note = '{tag}')"))
    else:
        print("   note  resume_versions SKIPPED - the stranger owns no resume_documents row to parent a version, "
              "and inventing an FK would seed a row the app could never have written")

    removals = {
        "avatar_state": "delete from avatar_state where session_id = '{tag}'",
        "marketplace_saved_searches": "delete from marketplace_saved_searches where search_name = '{tag}'",
        "mfa_enrollments": "delete from mfa_enrollments where notes = '{tag}'",
        "push_subscriptions": "delete from push_subscriptions where user_agent = '{tag}'",
        "resume_versions": "delete from resume_versions where note = '{tag}'",
    }

    fmt = {"tag": TAG, "uid": suid, "sname": sname.replace("'", "''"), "rid": resume or ""}
    jobs = ([(t, removals[t]) for t, _ in plan] if a.remove else plan)
    verb = "remove" if a.remove else "seed"
    changed, failed = [], []
    for table, sql in jobs:
        stmt = sql.format(**fmt)
        if not a.apply:
            print("   would {0:6} {1}".format(verb, table))
            continue
        out, err = psql(stmt)
        if err:
            failed.append((table, err.splitlines()[0][:120]))
            print("   FAIL   {0:28} {1}".format(table, err.splitlines()[0][:110]))
            continue
        changed.append(table)
        print("   {0:6} {1:28} {2}".format(verb, table, out or "ok"))

    if not a.apply:
        print("\n(dry run - pass --apply to write)")
        return 0

    # *VERIFY, never assume. The point of this script is that a stranger HAS rows; say so by counting them.
    print("\nverification - the stranger's row counts the prover will now ask to be refused:")
    for table in removals:
        n, err = psql("select count(*) from public.\"{0}\" where {1} = '{2}'".format(
            table,
            "session_id" if table == "avatar_state" else
            "search_name" if table == "marketplace_saved_searches" else
            "notes" if table == "mfa_enrollments" else
            "user_agent" if table == "push_subscriptions" else "note", TAG))
        print("   {0:28} {1}".format(table, (n or "?") + " tagged row(s)"))
    if failed:
        print("\n{0} table(s) could not be {1}ed: {2}".format(len(failed), verb, ", ".join(t for t, _ in failed)))
        return 1
    print("\nNext: re-run `node tools/prove_tenant_refusal.mjs` - the five UNPROVEN person-scoped tables now "
          "have a stranger's rows to withhold, so a refusal there finally means something.")
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")
    sys.exit(main())
