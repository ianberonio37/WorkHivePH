#!/usr/bin/env python3
"""admin-is-an-account - a platform admin is an ACCOUNT, never a name a person can choose (S layer, 2026-10-08).

FOUND by the LXC-S reading as the solo owner (Jun Salvador, no hive, no admin rights), at the database's own role
level - `authenticated` with his jwt claims, inside a transaction that is always ROLLED BACK:

  1. is_platform_admin() joined worker_profiles.display_name to marketplace_platform_admins.worker_name, and the
     policy "profiles update own" lets a person change their own display_name. ONE update of his display_name to an
     admin's name made is_platform_admin() true, and analytics_events went from 0 visible rows to 238,232.
  2. is_marketplace_admin() asked whether an admin NAME is among auth_worker_names(), which reads hive_members. Any
     signed-in person may create a hive (hives_insert) and join it as its sole supervisor (hive_members_insert)
     under any name. Two inserts named after an admin made is_marketplace_admin() true and every marketplace order
     readable - and every policy with an `OR is_marketplace_admin()` arm (29 of them) opened with it.

Both are the same mistake: an allowlist of NAMES checked against names the person controls. The fix keys the
allowlist on auth_uid (migration 20261008000031). This gate re-runs the attacks as a non-admin, rolled back, and
requires both checks to stay FALSE - beside a CONTROL that requires a real admin's account to stay TRUE, so a fix that
simply revoked everyone cannot pass. It also holds the solo owner's half: a person with no hive must read his OWN
name-keyed rows (achievement_xp_log), which auth_worker_names() denied him entirely before the same migration.

  python tools/validate_admin_is_an_account.py
"""
from __future__ import annotations

import io
import os
import subprocess
import sys

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

CONTAINER = os.environ.get("WH_DB_CONTAINER", "supabase_db_workhive")
SOLO_EMAIL = "junvanowner@auth.workhiveph.com"     # tools/seed_solo_personas.py: a one-person shop, no hive, no admin


def psql(sql: str) -> tuple[int, str]:
    r = subprocess.run(["docker", "exec", "-i", CONTAINER, "psql", "-U", "postgres", "-d", "postgres", "-tA",
                        "-v", "ON_ERROR_STOP=1"],
                       input=sql, capture_output=True, text=True, timeout=120, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def one(sql: str) -> str:
    rc, out = psql(sql)
    return out.strip().splitlines()[0].strip() if rc == 0 and out.strip() else ""


def as_person(uid: str, body: str) -> dict:
    """Run `body` as the signed-in person `uid` (role authenticated + jwt claims) inside a transaction that is ALWAYS
    rolled back, and return every `marker|value` line it printed. Nothing a probe writes survives it."""
    sql = ("BEGIN;\nSET LOCAL ROLE authenticated;\n"
           f"SELECT set_config('request.jwt.claims', '{{\"sub\":\"{uid}\",\"role\":\"authenticated\"}}', true);\n"
           + body + "\nROLLBACK;\n")
    rc, out = psql(sql)
    got = {}
    for ln in out.splitlines():
        if "|" in ln:
            k, v = ln.split("|", 1)
            got[k.strip()] = v.strip()
    got["_rc"] = rc
    got["_err"] = "" if rc == 0 else out.strip()[-300:]
    return got


def main() -> int:
    if psql("SELECT 1;")[0] != 0:
        print("SKIP admin-is-an-account - local database not reachable (live gate)")
        return 0
    admin_name = one("select worker_name from marketplace_platform_admins order by worker_name limit 1")
    solo = one(f"select id::text from auth.users where email = '{SOLO_EMAIL}'")
    if not admin_name or not solo:
        print(f"FAIL admin-is-an-account - fixture missing (admin name {admin_name!r}, solo owner uid {solo!r}); "
              "reseed with tools/seed_solo_personas.py")
        return 1
    has_uid_col = one("select count(*) from information_schema.columns where table_name = "
                      "'marketplace_platform_admins' and column_name = 'auth_uid'") == "1"
    # the CONTROL: the real admin's account, read the way the fixed allowlist reads it when it can
    admin_uid = (one(f"select auth_uid::text from marketplace_platform_admins where worker_name = '{admin_name}'")
                 if has_uid_col else "") or \
        one(f"select auth_uid::text from hive_members where worker_name = '{admin_name}' and auth_uid is not null limit 1")
    fails, notes = [], []
    q = admin_name.replace("'", "''")

    # A1 - rename my own profile to an admin's name ("profiles update own" permits it)
    a1 = as_person(solo, f"""
SELECT 'before_platform', is_platform_admin();
SELECT 'before_market', is_marketplace_admin();
UPDATE worker_profiles SET display_name = '{q}' WHERE auth_uid = auth.uid();
SELECT 'after_platform', is_platform_admin();
SELECT 'after_market', is_marketplace_admin();""")
    if a1["_rc"]:
        fails.append(f"A1 rename probe did not run: {a1['_err']}")
    elif a1.get("before_platform") == "t" or a1.get("before_market") == "t":
        fails.append("A1 the solo owner already reads as an admin BEFORE the attack - the fixture is wrong")
    elif a1.get("after_platform") == "t" or a1.get("after_market") == "t":
        fails.append(f"A1 renaming his own display_name to '{admin_name}' made the solo owner an admin "
                     f"(is_platform_admin={a1.get('after_platform')}, is_marketplace_admin={a1.get('after_market')})")
    else:
        notes.append("A1 rename-to-an-admin's-name: both checks stayed false")

    # A2 - found a hive and join it as its sole supervisor under the admin's name (hives_insert + hive_members_insert)
    a2 = as_person(solo, f"""
SELECT gen_random_uuid() AS probe_hive \\gset
INSERT INTO hives (id, name, invite_code, created_by) VALUES (:'probe_hive', 'Gate Name Claim Hive', 'GATENC', '{q}');
INSERT INTO hive_members (hive_id, worker_name, auth_uid, role, status) VALUES (:'probe_hive', '{q}', auth.uid(), 'supervisor', 'active');
SELECT 'after_platform', is_platform_admin();
SELECT 'after_market', is_marketplace_admin();""")
    if a2["_rc"]:
        # a refusal of the hive or the membership is ALSO a pass for this gate's question - say which
        notes.append(f"A2 hive-name-claim was refused before it could be asked ({a2['_err'][-120:]})")
    elif a2.get("after_platform") == "t" or a2.get("after_market") == "t":
        fails.append(f"A2 founding a hive and joining it as '{admin_name}' made the solo owner an admin "
                     f"(is_platform_admin={a2.get('after_platform')}, is_marketplace_admin={a2.get('after_market')})")
    else:
        notes.append("A2 found-a-hive-under-an-admin's-name: both checks stayed false")

    # CONTROL - the real admin's own account must still be an admin, or the fix revoked the people it protects
    if not admin_uid:
        fails.append(f"CONTROL no account resolves for admin '{admin_name}' - the allowlist would admit nobody")
    else:
        c = as_person(admin_uid, "SELECT 'platform', is_platform_admin();\nSELECT 'market', is_marketplace_admin();")
        if c.get("platform") != "t" or c.get("market") != "t":
            fails.append(f"CONTROL the real admin '{admin_name}' reads is_platform_admin={c.get('platform')}, "
                         f"is_marketplace_admin={c.get('market')} - a fix that revokes the admin is not a fix")
        else:
            notes.append(f"CONTROL '{admin_name}' (the account on the allowlist) is still an admin on both checks")

    # SOLO - a person with no hive reads his OWN name-keyed rows (achievement_xp_log has no auth_uid column)
    own_name = one(f"select display_name from worker_profiles where auth_uid = '{solo}'")
    own_n = one(f"select count(*) from achievement_xp_log where worker_name = '{own_name.replace(chr(39), chr(39) * 2)}'")
    s = as_person(solo, f"SELECT 'sees_own_xp', count(*) FROM achievement_xp_log WHERE worker_name = "
                        f"'{own_name.replace(chr(39), chr(39) * 2)}';")
    if own_n and own_n != "0":
        if s.get("sees_own_xp") != own_n:
            fails.append(f"SOLO '{own_name}' holds {own_n} XP row(s) under his own name and reads "
                         f"{s.get('sees_own_xp')} - a person with no hive is refused his own record")
        else:
            notes.append(f"SOLO '{own_name}' reads all {own_n} of his own XP rows")
    else:
        notes.append(f"SOLO '{own_name}' holds no XP rows - the over-refusal half is unasked (reseed to ask it)")

    if fails:
        print("FAIL admin-is-an-account - " + "; ".join(fails))
        for n in notes:
            print("   " + n)
        return 1
    print("PASS admin-is-an-account - " + "; ".join(notes) + " (every probe ran as the person and was rolled back)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
