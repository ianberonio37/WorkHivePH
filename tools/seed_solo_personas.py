#!/usr/bin/env python3
"""seed_solo_personas.py — give the solo vertical somebody who can actually sign in.

FOUND BY J11 (2026-09-08): "the cast could not sign in (auth: Invalid login credentials)". Both solo
stories - the one-person technician and the solo rider - walked eight pages as nobody, bounced off
asset-hub, logbook and hive to the landing page, and could report nothing about the platform.

WHY, AND IT IS THE CAST, NOT THE PRODUCT. `loadSolo()` picks its people with a keyword sweep over every
auth user who is NOT an active hive member - anyone whose name or email mentions rider, jeep, tricycle,
owner, van, fleet or truck. That set is leftovers: removed members, accounts from other flows, whoever
happens to match. The walk then signs in with the platform's test password, which none of them has. So
the solo vertical had a NAME to cast and no PERSON, and every solo row was evidence about a sign-in door.

★IT CREATES, IT DOES NOT RESET. The other repair available was to overwrite the password of whichever
stranger the keyword sweep landed on - a write to somebody else's account, unreversible in the way that
matters (the old password is not knowable, so there is nothing to put back). Two new accounts touch no
existing row and revert by deleting exactly themselves.

★THE PERSONAS ARE SOLO BY CONSTRUCTION: no hive_members row is written for them, because that is the
whole point of the vertical - J11 is "solo owner, no hive, grows into one". They carry `seed` in their
user metadata so `loadSolo()` can prefer a castable persona over a leftover, and so --revert can find
exactly these two and nothing else.

Uses the local GoTrue admin API, which is how the platform itself creates a user; inserting into
auth.users by hand would mean hashing a password myself and getting the identity rows right, which is a
seeder inventing a shape the product does not write.

  python tools/seed_solo_personas.py --check     # who the solo vertical can cast today
  python tools/seed_solo_personas.py --apply     # create them
  python tools/seed_solo_personas.py --revert    # delete exactly these two
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request

AUTH = "http://127.0.0.1:54321/auth/v1"
DB = "supabase_db_workhive"
MARKER = "solo-persona-seed"

# how long a closed job stayed open, taken from the rows that already carry closed_at (median 0.5h,
# p90 5.4h) rather than a single invented number that would make every record identical
CLOSE_HOURS = ["0.5", "1.5", "0.75", "4", "2", "5.4", "1"]
PASSWORD = "test1234"          # the password every walk in this repo signs in with

# ★THE PERSONA THE PRODUCT'S OWN SIGN-IN CANNOT REACH (2026-09-11, found trying to cast Jun for W3114).
# This file exists to "give the solo vertical somebody who can actually sign in", and its accounts could
# not sign in THROUGH THE PRODUCT - only through a programmatic signInWithPassword with the full address.
# index.html builds the credential itself: `_AUTH_DOMAIN = '@auth.workhiveph.com'` (index.html:3015,
# "Synthetic email = username@auth.workhiveph.com: workers never see it"), so the form only ever asks
# GoTrue about `<username>@auth.workhiveph.com`. These personas were seeded on `@workhive.test`, and the
# username derived at line ~198 is the email's local part with dots stripped - so Jun Salvador exists,
# is confirmed, carries this exact password, answers to username `junvanowner`, and the door constructs
# `junvanowner@auth.workhiveph.com`, which is nobody. Three sign-in attempts read "Wrong username or
# password" against a perfectly good account.
# ★AND THIS IS THE ROOT OF A BUG THAT HAS COST THIS PROGRAM FOUR TIMES. Because the UI could not reach
# them, every walk of a solo persona had to bypass the door with a programmatic session - and a
# programmatic sign-in does NOT set the wh_* keys, so the PREVIOUS persona's hive survived and a member
# once rendered hive-less under another person's name ([[feedback_a_valid_session_is_not_a_cast_persona]]).
# The contamination discipline was treating the symptom; this line is the cause.
# The auth address is now derived from the username the same way the door derives it, so the product's
# own sign-in reaches these people. `email` stays on the persona for the worker_profiles row - that is
# the human-readable address a person would recognise, and it is not what GoTrue is asked about.
AUTH_DOMAIN = "@auth.workhiveph.com"   # index.html:3015 - the only domain the sign-in form constructs


def _local(addr: str) -> str:
    """The stable identity of one of THIS FILE's personas, independent of its e-mail domain.

    ★WHY NOT THE ADDRESS (2026-09-11). The auth domain moved to the one index.html actually constructs,
    and every lookup here keyed off the address - so --revert would have reported "not present, nothing
    to remove" for the two accounts it created three days earlier, and --apply would then have made a
    SECOND Jun whose worker_profiles insert collides on worker_profiles_username_key (UNIQUE (username),
    checked against pg_constraint). The result would be an auth user with no profile: exactly the
    half-created account this file's 2026-09-10 note says makes every walk report a false ceiling.
    existing() already selects by the seed MARKER, which is this file's own statement of what it owns
    ("so --revert can find exactly these two and nothing else"), so the lookup now uses the part of the
    address that does not move. A future domain change needs no third patch.
    """
    return addr.split("@")[0].replace(".", "").lower()


def auth_email(persona_email: str) -> str:
    """The address the PRODUCT will ask GoTrue about, from the same local part the username uses."""
    return persona_email.split("@")[0].replace(".", "") + AUTH_DOMAIN

# The emails carry the words loadSolo's keyword sweep looks for, so the personas are picked up by the
# cast loader without teaching it a second vocabulary.
PERSONAS = [
    {"email": "jun.vanowner@workhive.test", "worker_name": "Jun Salvador",
     "what": "a one-person technician who owns his van and no hive"},
    {"email": "boyet.jeepney.rider@workhive.test", "worker_name": "Boyet Ramirez",
     "what": "a solo jeepney rider, no hive, keeps his own records"},
]


# ★A SOLO OPERATOR WHO KEEPS NO RECORDS IS NOT THE STORY. J11 is "solo owner, no hive, grows into one" and
# its chain asks whether "the one-person operator's own records exist" - which for a brand-new account is
# honestly no. A one-person operator keeps a logbook precisely BECAUSE nobody else is keeping it for them,
# so the persona gets one. `logbook.hive_id` is nullable and the platform already holds six hive-less rows,
# so this is a shape the product has, not one invented for a walk.
OWN_WORK = [
    ("Oil and filter change, own unit", "Drained and refilled with 15W-40, replaced the filter, noted the odometer",
     "Preventive Maintenance", ""),
    ("Front brake pads replaced before the long haul", "Fitted new pads, checked disc thickness, bedded them in on the way out",
     "Breakdown / Corrective", "Wear"),
    ("Battery terminals corroded, slow crank in the morning", "Cleaned both terminals, greased them, tested charging at 14.1 V",
     "Breakdown / Corrective", "Electrical Fault"),
]

def psql(sql: str) -> str | None:
    try:
        r = subprocess.run(["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres", "-tA", "-c", sql],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def service_key() -> str | None:
    for c in ("supabase_edge_runtime_workhive", "supabase_kong_workhive"):
        try:
            r = subprocess.run(["docker", "exec", c, "sh", "-c", "echo $SUPABASE_SERVICE_ROLE_KEY"],
                               capture_output=True, text=True, timeout=20)
            k = (r.stdout or "").strip()
            if k:
                return k
        except Exception:
            continue
    return None


def call(method: str, path: str, key: str, body: dict | None = None):
    """Returns (status, parsed-or-text). A failure is reported, never swallowed into a False."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{AUTH}{path}", data=data, method=method, headers={
        "Content-Type": "application/json", "apikey": key, "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8", "replace")
            try:
                return r.status, json.loads(raw)
            except json.JSONDecodeError:
                return r.status, raw
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:300]
    except Exception as e:                                    # connection refused, DNS, timeout
        return 0, str(e)[:300]


def existing() -> dict[str, str]:
    """email -> id, for the personas this file owns."""
    rows = psql("select u.email||'|'||u.id::text from auth.users u where u.raw_user_meta_data->>'seed' = '%s'" % MARKER)
    out = {}
    for line in (rows or "").splitlines():
        if "|" in line:
            e, i = line.split("|", 1)
            out[e.strip()] = i.strip()
    return out


def report() -> int:
    have = existing()
    print("  the solo vertical's castable people")
    for p in PERSONAS:
        mark = "seeded" if _local(p["email"]) in {_local(k) for k in have} else "MISSING"
        print(f"    {p['worker_name']:<16} {p['email']:<34} {mark}")
    leftovers = psql(
        "select count(*) from auth.users u where not exists "
        "(select 1 from hive_members m where m.auth_uid = u.id and m.status = 'active') "
        "and coalesce(u.raw_user_meta_data->>'seed','') <> '%s'" % MARKER)
    print(f"    (the keyword sweep also sees {leftovers} hive-less account(s) whose password nobody knows)")
    return 0


def apply(revert: bool) -> int:
    key = service_key()
    if not key:
        print("  could not read the service key from the running containers - nothing done")
        return 1
    have = existing()
    # keyed by the domain-independent local part, so a persona created under an
    # older auth domain is still recognised as one of ours (see _local)
    have_by_local = {_local(k): v for k, v in have.items()}
    n = 0
    for p in PERSONAS:
        if revert:
            uid = have_by_local.get(_local(p["email"]))
            if not uid:
                print(f"  {p['worker_name']}: not present, nothing to remove")
                continue
            # their records go with them: an account deleted while its logbook survives leaves rows
            # attributed to somebody who no longer exists
            psql("delete from logbook where worker_name = '%s' and hive_id is null" % p["worker_name"].replace("'", "''"))
            # versions before the document they hang off, or the parent delete takes them and the count lies
            psql("delete from resume_versions v using resume_documents d where d.id = v.resume_id and d.worker_name = '%s'" % p["worker_name"].replace("'", "''"))
            psql("delete from resume_documents where worker_name = '%s'" % p["worker_name"].replace("'", "''"))
            status, body = call("DELETE", f"/admin/users/{uid}", key)
            if status in (200, 204):
                print(f"  {p['worker_name']}: deleted")
                n += 1
            else:
                print(f"  {p['worker_name']}: delete refused ({status}) {body}")
            continue

        if _local(p["email"]) in have_by_local:
            print(f"  {p['worker_name']}: already seeded - not creating again")
            continue
        status, body = call("POST", "/admin/users", key, {
            "email": auth_email(p["email"]), "password": PASSWORD, "email_confirm": True,
            "user_metadata": {"worker_name": p["worker_name"], "seed": MARKER, "what": p["what"]},
        })
        if status in (200, 201):
            print(f"  {p['worker_name']}: created - {p['what']}")
            n += 1
        else:
            print(f"  {p['worker_name']}: create refused ({status}) {body}")
    # ★AN AUTH USER WITHOUT A worker_profiles ROW IS NOT WHAT SIGN-UP MAKES (2026-09-10, found by
    # walking J30 as Jun). This file creates the personas through the GoTrue admin API, which writes
    # auth.users and nothing else - but index.html's own Create Account inserts a worker_profiles row
    # (auth_uid / username / display_name) immediately after signUp(). So the seeded solo owner was
    # missing the one row every real account has, and it showed the moment he reached a page that
    # calls an edge function: analytics-orchestrator refused all four phases with
    # 403 "No worker profile for caller", the OEE tile read "Unavailable", and the page rendered
    # 1,237 characters. Proven by a reversible probe: with the row present the SAME page computed real
    # KPIs - 5,935 characters, PM compliance 0%, OEE "No logbook data found" - and the row was then
    # deleted and audited back to zero. Without this the persona is not a stand-in for a solo owner;
    # it is a stand-in for a half-created account, and every walk cast on it reports a false ceiling.
    # username is derived from the e-mail's local part, the same shape the sign-up form produces.
    # --revert needs no new branch: worker_profiles_auth_uid_fkey is ON DELETE CASCADE, so deleting
    # the auth user takes its profile with it (checked against pg_constraint, not assumed).
    if not revert:
        for p in PERSONAS:
            uid = psql("select id from auth.users where email = '%s'" % auth_email(p["email"]))
            if not uid:
                continue
            wn = p["worker_name"].replace("'", "''")
            un = p["email"].split("@")[0].replace(".", "").replace("'", "''")
            has_profile = psql("select count(*) from worker_profiles where auth_uid = '%s'" % uid)
            if has_profile and has_profile.isdigit() and int(has_profile) > 0:
                print(f"  {p['worker_name']}: already has a worker profile - not writing another")
            else:
                got = psql("insert into worker_profiles (auth_uid, username, display_name, email) "
                           "values ('%s','%s','%s','%s') returning id"
                           % (uid, un, wn, p["email"]))
                print(f"  {p['worker_name']}: wrote the worker profile"
                      if got else f"  {p['worker_name']}: the profile insert did not answer")

    # ...and their own records, so the story they are cast for has something to be true about
    if not revert:
        for p in PERSONAS:
            uid = psql("select id from auth.users where email = '%s'" % p["email"])
            if not uid:
                continue
            have = psql("select count(*) from logbook where worker_name = '%s'" % p["worker_name"].replace("'", "''"))
            if have and have.isdigit() and int(have) > 0:
                print(f"  {p['worker_name']}: already keeps {have} record(s) - not writing them again")
                continue
            rows = []
            for i, (problem, action, mtype, cause) in enumerate(OWN_WORK):
                # ★A JOB MARKED CLOSED NEEDS THE TIME IT WAS CLOSED. This wrote 'Closed' and left
                # closed_at null, so a solo owner's own record - the one the resume and the portfolio
                # are built from - carried six jobs with no sign-off time, and the logbook's CSV has a
                # "Signed Off (Closed At)" column that would have exported them blank. Measured on the
                # rows that DO carry it: median half an hour open, p90 5.4 hours.
                rows.append("(null,'%s','%s','%s','%s','Closed', now() - interval '%d days', "
                            "(now() - interval '%d days')::date,'%s',%s,'%s', "
                            "now() - interval '%d days' + interval '%s hours')"
                            % (p["worker_name"].replace("'", "''"), "Own unit",
                               problem.replace("'", "''"), action.replace("'", "''"),
                               9 * (i + 1), 9 * (i + 1), mtype,
                               ("'" + cause + "'") if cause else "null", uid,
                               9 * (i + 1), CLOSE_HOURS[i % len(CLOSE_HOURS)]))
            got = psql("insert into logbook (hive_id, worker_name, machine, problem, action, status, "
                       "created_at, date, maintenance_type, root_cause, auth_uid, closed_at) values "
                       + ",".join(rows) + " returning id")
            if got is None:
                print(f"  {p['worker_name']}: the record insert did not answer - they keep nothing yet")
            else:
                made = len([x for x in got.splitlines() if x.strip() and not x.strip().startswith("INSERT")])
                print(f"  {p['worker_name']}: wrote {made} of their own record(s), kept under no hive")

    # ...and a portfolio, because J31 is the OFW story: a solo worker's resume, reviewed and versioned.
    # A resume belongs to a PERSON - it is the one document on this platform that outlives any hive - so
    # hive_id is left null, which is what a solo operator's is.
    if not revert:
        for p in PERSONAS:
            uid = psql("select id from auth.users where email = '%s'" % p["email"])
            if not uid:
                continue
            wn = p["worker_name"].replace("'", "''")
            have = psql("select count(*) from resume_documents where worker_name = '%s'" % wn)
            if have and have.isdigit() and int(have) > 0:
                print(f"  {p['worker_name']}: already keeps a resume - not writing another")
                continue
            # ★THE PAGE CLAIMS "JSON RESUME SCHEMA" AT THREE SITES, AND THIS WROTE A DIFFERENT SHAPE.
            # `summary` and `experience` are not keys in that vocabulary: the summary belongs inside
            # `basics`, and the work history is `work`. Two seeded portfolios therefore sat in the
            # store as the only non-conforming documents on the platform, against one real one written
            # by the page itself (basics / skills / work). A seeded fixture that contradicts the page's
            # own stated schema teaches every reader of that store the wrong shape.
            doc = ('{"basics": {"name": "%s", "label": "Maintenance technician", '
                   '"summary": "Maintenance technician, own unit, Philippines."}, '
                   '"skills": [{"name": "preventive maintenance"}, {"name": "brake systems"}, '
                   '{"name": "12V electrical"}], '
                   '"work": [{"name": "Own unit", "position": "Owner-operator", "startDate": "2020-01"}]}'
                   % wn.replace('"', ""))
            rid = psql("insert into resume_documents (auth_uid, worker_name, hive_id, title, doc, template) "
                       "values ('%s','%s',null,'%s','%s'::jsonb,'ats-plain') returning id"
                       % (uid, wn, wn + " - Maintenance CV", doc.replace("'", "''")))
            rid = (rid or "").splitlines()[0].strip() if rid else ""
            if not rid:
                print(f"  {p['worker_name']}: the resume insert did not answer - no portfolio written")
                continue
            # a version, because the story is review-and-polish rather than upload-and-forget
            v = psql("insert into resume_versions (resume_id, auth_uid, doc, note) values "
                     "('%s','%s','%s'::jsonb,'First pass, before the polish') returning id"
                     % (rid, uid, doc.replace("'", "''")))
            print(f"  {p['worker_name']}: wrote a resume and {1 if v else 0} earlier version of it")

    # a persona that cannot sign in is the bug this file exists to fix, so prove the password works
    if not revert and n:
        for p in PERSONAS:
            # the address GoTrue actually holds - and therefore the one the PRODUCT'S sign-in form
            # constructs from the username. Proving p["email"] would prove the wrong door.
            status, body = call("POST", "/token?grant_type=password", key,
                                {"email": auth_email(p["email"]), "password": PASSWORD})
            ok = status == 200 and isinstance(body, dict) and "access_token" in body
            print(f"  {p['worker_name']}: sign-in {'works' if ok else f'FAILED ({status})'}")
            if not ok:
                return 1
    return 0 if n or revert else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    if a.revert:
        return apply(revert=True)
    if a.apply:
        return apply(revert=False)
    return report()


if __name__ == "__main__":
    sys.exit(main())
