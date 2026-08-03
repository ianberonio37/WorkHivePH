#!/usr/bin/env python3
"""validate_no_client_truncate.py -- RLS does not apply to TRUNCATE, so the grant is the only control.

FOUND 2026-08-03 by the live-MCP flywheel, three steps from where it started. Walking G-trust as an
anonymous visitor showed every seller as an unverified Bronze; the read policy turned out to be
signed-in-only; widening the READ meant auditing the WRITES; and the write privileges included TRUNCATE.
Proven as `anon`, in a rolled-back transaction:

    truncate table public.marketplace_sellers cascade;   -- SUCCEEDED
    select count(*) from public.marketplace_sellers;     -- 0

Every seller on the platform, by someone who never signed in. Blast radius at the time: **140 tables
anon-truncatable, 142 for authenticated, ~104,000 rows.**

WHY THE EXISTING GATE COULD NOT SEE IT. `validate_unprotected_write_grant` holds the invariant "a base
table may grant an end-user write verb ONLY IF row-level security is enabled on it". That is right for
INSERT/UPDATE/DELETE and inert for TRUNCATE, because **RLS is never consulted for TRUNCATE**.
marketplace_sellers has RLS enabled with a proper policy set, so it passed that gate cleanly while an
anonymous TRUNCATE emptied it. The July sweep's own notes had even flagged the shape -- an anon TRUNCATE
on marketplace_listings failed only with `0A000 cannot truncate a table referenced in a foreign key
constraint`, which is a coincidence of the schema, not a control. marketplace_sellers had no such FK.

So this gate holds the invariant RLS cannot: **no client role may hold TRUNCATE on anything.**

    public schema      ENFORCED  -- revoked by 20260803000028, and by default privileges going forward
    storage/* schemas  TRACKED   -- owned by supabase_storage_admin; postgres is not superuser here and
                                    cannot `set role` to it, so no migration this project writes can
                                    revoke them. Reported every run so it stays a decision rather than
                                    a thing everyone forgot.

Usage:  python tools/validate_no_client_truncate.py [--selftest]
"""
import subprocess
import sys

GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"
CONTAINER = "supabase_db_workhive"
CLIENT_ROLES = ("anon", "authenticated")

# Owned by a role no project migration can assume. Not forgiven — reported, every run.
VENDOR_TRACKED = {"storage.objects", "storage.buckets", "storage.buckets_analytics"}

QUERY = """
select g.grantee, g.table_schema || '.' || g.table_name
  from information_schema.role_table_grants g
 where g.grantee in ('anon','authenticated') and g.privilege_type = 'TRUNCATE'
 order by 1, 2;
"""


def psql(sql):
    try:
        r = subprocess.run(["docker", "exec", CONTAINER, "psql", "-U", "postgres", "-d", "postgres",
                            "-t", "-A", "-F", "|", "-c", sql],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    except Exception as e:
        return None, str(e)
    if r.returncode != 0:
        return None, (r.stderr or "")[:200]
    return [ln.split("|") for ln in (r.stdout or "").splitlines() if ln.strip()], ""


def judge(grants):
    """-> (enforced_violations, tracked). Pure, so the split is testable without a database."""
    enforced, tracked = [], []
    for role, obj in grants:
        (tracked if obj in VENDOR_TRACKED else enforced).append((role, obj))
    return enforced, tracked


def selftest():
    print("  selftest: a public-schema TRUNCATE grant must FAIL; a vendor one must be tracked, not hidden")
    ok = True
    e, t = judge([("anon", "public.marketplace_sellers")])
    if len(e) != 1 or t:
        print(f"  {RED}FAIL{RST} — a public-schema grant was not treated as a violation"); ok = False
    e, t = judge([("anon", "storage.objects")])
    if e or len(t) != 1:
        print(f"  {RED}FAIL{RST} — the vendor grant was not tracked (or was wrongly enforced)"); ok = False
    e, t = judge([])
    if e or t:
        print(f"  {RED}FAIL{RST} — a clean grant list produced findings"); ok = False
    if ok:
        print(f"  {GREEN}PASS{RST} — enforces the public schema, tracks the vendor residual, quiet when clean")
    return 0 if ok else 1


def main(argv):
    if "--selftest" in argv:
        return selftest()
    print(f"{BOLD}No client TRUNCATE{RST} — RLS is never consulted for TRUNCATE, so the grant is the control")
    if selftest() != 0:
        return 1

    rows, err = psql(QUERY)
    if rows is None:
        print(f"  {YEL}SKIP{RST} database unavailable ({err})")
        return 0

    enforced, tracked = judge([(r[0], r[1]) for r in rows])

    for role, obj in tracked:
        print(f"  {YEL}TRACKED{RST} {role} holds TRUNCATE on {obj} {DIM}(owned by supabase_storage_admin; "
              f"postgres is not superuser here, so no migration can revoke it){RST}")

    if enforced:
        print(f"\n  {RED}FAIL{RST} — {len(enforced)} client TRUNCATE grant(s) in a schema we control:")
        for role, obj in enforced[:12]:
            print(f"    . {role} -> {obj}")
        print(f"  {DIM}Fix: revoke truncate on all tables in schema public from anon, authenticated; and "
              f"alter default privileges so new tables do not inherit it.{RST}")
        return 1

    print(f"\n  {GREEN}PASS{RST} — no client role holds TRUNCATE in any schema we own"
          + (f"; {len(tracked)} vendor grant(s) tracked above" if tracked else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
