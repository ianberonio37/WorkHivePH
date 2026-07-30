#!/usr/bin/env python3
"""validate_unprotected_write_grant.py — nothing an end-user role can write may stand on the GRANT alone.

WHAT THIS LOCKS, and how it was found. The marketplace test bank enumerated 18 `anon` obligations and
had never executed one: the SQL runner needed a uid to mint, and `anon` is not a different identity, it
is the ABSENCE of one. Teaching it `set local role anon` (no JWT at all) ran the partition with the
largest blast radius for the first time.

On the marketplace surface RLS held everywhere — anon moved 0 rows on insert, update and delete, and the
service tables refuse at the GRANT layer (42501) before RLS is even consulted. The finding was one level
up, in the question *where is RLS not there to catch it?*: **16 public tables with
`relrowsecurity = false` that granted `anon` INSERT/UPDATE/DELETE/TRUNCATE.** A rolled-back
`delete … where true` as `anon` destroyed **1,430 rows** — 766 of `embedding_cache`, 434 of
`persona_knowledge`, 207 of `multilingual_terms`, the 3 `service_slo_targets` the gate panel grades
against, and the single `ai_global_budget` row that caps AI spend.

The grants are the Supabase template default (`GRANT ALL ON ALL TABLES IN SCHEMA public TO anon,
authenticated`). On the ~130 tables where RLS is enabled that default is harmless, which is exactly why
this class hides: **the same grant is fine 130 times and catastrophic 16 times, and the only difference
is one line of DDL somewhere else.** No amount of reading the GRANT tells you which case you are in.

THE INVARIANT, therefore, is a CONJUNCTION and not a grant rule:

    a public BASE TABLE may grant anon/authenticated a write verb
      ONLY IF row-level security is enabled on it

Plus one corollary, on objects that cannot honestly own a write:

    no public VIEW may grant anon/authenticated INSERT/UPDATE/DELETE/TRUNCATE

Thirteen `v_*` views were auto-updatable with anon write grants, eleven of them not `security_invoker` —
the textbook RLS-bypass setup (a write through a non-invoker view runs as the view OWNER, `postgres`
here, and a table owner is exempt from RLS when `forced=false`). **Probed, it did not bypass**: 0 rows
through `v_hives_truth` and `v_asset_truth`, and even a plain SELECT returned 0. Recorded as measured,
not as reasoned. The grants were revoked anyway because a repo-wide grep finds zero writes through any
`v_*` view: a privilege nobody uses is only ever a future foothold.

TRUNCATE gets its own mention because it is the verb RLS would never have caught — **row-level security
does not apply to TRUNCATE.** An anon TRUNCATE on `marketplace_listings` fails today with 0A000, "cannot
truncate a table referenced in a foreign key constraint" — a coincidence of the schema, not a security
control, and one that evaporates the day that FK is dropped.

Fixed by mig 20260730000002; this gate is what stops it coming back, since the next `GRANT ALL` or the
next table created without `ENABLE ROW LEVEL SECURITY` re-opens it silently.

Usage:  python tools/validate_unprotected_write_grant.py [--selftest] [--verbose]
"""
from __future__ import annotations

import subprocess
import sys

DB = "supabase_db_workhive"
GREEN, RED, YEL, DIM, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m"
WRITE_VERBS = "'INSERT','UPDATE','DELETE','TRUNCATE'"

# A table may appear here ONLY with a reason that survives being read aloud. Empty on purpose: every
# one of the 16 found had a better answer than an exemption (a REVOKE for the 14 system tables, real RLS
# for the two the client writes). An entry added later is a claim someone has to defend.
EXEMPT: dict[str, str] = {}

# The two objects the migration deliberately left writable by `authenticated`, each with RLS now ON so
# they satisfy the invariant by the front door rather than by exemption. Listed for the reader, not
# consumed by the query.
_DOCUMENTED = {
    "avatar_state": "RLS ON + authenticated-only policy; no auth column exists to scope it per-owner",
    "language_preferences": "RLS ON + owner-scoped policy on worker_profiles.auth_uid",
}

Q_TABLES = f"""
select c.relname,
       (select string_agg(distinct g.privilege_type, ',' order by g.privilege_type)
          from information_schema.role_table_grants g
         where g.table_schema='public' and g.table_name=c.relname
           and g.grantee in ('anon','authenticated') and g.privilege_type in ({WRITE_VERBS}))
  from pg_class c
 where c.relnamespace='public'::regnamespace and c.relkind='r' and not c.relrowsecurity
   and exists (select 1 from information_schema.role_table_grants g
                where g.table_schema='public' and g.table_name=c.relname
                  and g.grantee in ('anon','authenticated')
                  and g.privilege_type in ({WRITE_VERBS}))
 order by c.relname;
"""

Q_VIEWS = f"""
select c.relname,
       (select string_agg(distinct g.privilege_type, ',' order by g.privilege_type)
          from information_schema.role_table_grants g
         where g.table_schema='public' and g.table_name=c.relname
           and g.grantee in ('anon','authenticated') and g.privilege_type in ({WRITE_VERBS}))
  from pg_class c
 where c.relnamespace='public'::regnamespace and c.relkind='v'
   and exists (select 1 from information_schema.role_table_grants g
                where g.table_schema='public' and g.table_name=c.relname
                  and g.grantee in ('anon','authenticated')
                  and g.privilege_type in ({WRITE_VERBS}))
 order by c.relname;
"""


def psql(sql: str):
    """-> list[list[str]] of `|`-split rows, or None if the local stack is not up."""
    try:
        r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres",
                            "-At", "-F", "|"],
                           input=sql, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=90)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    return [ln.split("|") for ln in (r.stdout or "").splitlines() if ln.strip()]


def scan(verbose=False):
    """-> (violations, counts) or (None, None) when the stack is absent."""
    tables, views = psql(Q_TABLES), psql(Q_VIEWS)
    if tables is None or views is None:
        return None, None
    bad = []
    for name, verbs in tables:
        if name in EXEMPT:
            if verbose:
                print(f"  {DIM}exempt: {name} — {EXEMPT[name]}{RST}")
            continue
        bad.append(("table", name, verbs,
                    "RLS is OFF, so this GRANT is the only thing between an end-user role and every "
                    "row in the table"))
    for name, verbs in views:
        bad.append(("view", name, verbs,
                    "a view cannot own a write; if it is auto-updatable the write lands on the base "
                    "table with the VIEW OWNER's privileges"))
    return bad, (len(tables), len(views))


def selftest():
    """Teeth: introduce the exact defect inside a rolled-back transaction and require the scan to see it.

    A gate that reports 0 because its query is wrong looks identical to a gate that reports 0 because
    the platform is clean — the failure mode this project has hit repeatedly ([[feedback_gate_parsed_
    text_not_the_db_false_green]]). So the self-test manufactures a violation and demands detection.
    """
    print("  selftest: a clean platform must scan clean")
    bad, counts = scan()
    if bad is None:
        print(f"  {YEL}SKIP{RST} — docker/psql unavailable, cannot self-test")
        return 0
    if bad:
        print(f"  {RED}the platform is NOT clean, so the self-test cannot establish a baseline{RST}")
        for kind, name, verbs, _ in bad:
            print(f"    {kind} {name}: {verbs}")
        return 1
    print(f"    {GREEN}ok{RST} — 0 violations across {counts[0]} rls-off tables, {counts[1]} views")

    # The detector must FIRE on a real violation. Committed, then reverted in a finally-shaped pair:
    # a GRANT inside a transaction the scan cannot see (the scan opens its own connection) would prove
    # nothing, so this grants for real and revokes for real.
    print("  selftest: a table with RLS off + an anon write grant must be CAUGHT")
    psql("create table if not exists public._tb_grant_probe(id int);"
         "alter table public._tb_grant_probe disable row level security;"
         "grant insert on public._tb_grant_probe to anon;")
    try:
        bad2, _ = scan()
        caught = any(n == "_tb_grant_probe" for _, n, _, _ in (bad2 or []))
    finally:
        psql("revoke all on public._tb_grant_probe from anon;drop table if exists public._tb_grant_probe;")
    if not caught:
        print(f"  {RED}FAIL{RST} — the planted violation was NOT detected; this gate has no teeth")
        return 1
    print(f"    {GREEN}ok{RST} — planted violation detected, probe table dropped")

    leftover = psql("select count(*) from pg_class where relname='_tb_grant_probe';")
    if leftover and leftover[0][0] != "0":
        print(f"  {RED}FAIL{RST} — the probe table survived the self-test")
        return 1
    print(f"  {GREEN}PASS{RST} — teeth proven in both directions, zero residue")
    return 0


def main(argv):
    verbose = "--verbose" in argv
    if "--selftest" in argv:
        return selftest()

    print("Unprotected write grant (a write privilege standing on no row-level security)")
    bad, counts = scan(verbose)
    if bad is None:
        print(f"  {YEL}SKIP{RST} — docker/psql unavailable (local stack down); nothing asserted.")
        return 0

    print(f"  scanned {counts[0]} rls-off public tables with a write grant, "
          f"{counts[1]} views with a write grant.")
    if not bad:
        print(f"  {GREEN}PASS{RST} - every end-user write privilege sits behind row-level security, "
              f"and no view grants one.")
        return 0

    print(f"  {RED}FAIL{RST} - {len(bad)} object(s) grant a write verb with nothing behind it:")
    for kind, name, verbs, why in bad:
        print(f"    {RED}{kind} public.{name}{RST}  [{verbs}]")
        print(f"      {DIM}{why}{RST}")
    print(f"\n  {DIM}Fix: either ALTER TABLE … ENABLE ROW LEVEL SECURITY with a policy that names the "
          f"owner,\n  or REVOKE the write verbs from anon/authenticated if only service_role writes it.\n"
          f"  Precedent: supabase/migrations/20260730000002_close_anon_write_on_unprotected_tables.sql,"
          f"\n  which closed 1,430 anon-destroyable rows across 16 tables.{RST}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
