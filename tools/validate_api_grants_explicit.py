#!/usr/bin/env python3
"""validate_api_grants_explicit.py - BRH-X (2026-10-21): every Data API grant this schema relies on is WRITTEN in a
migration, so a replay of the schema reaches what production reaches after Supabase stops granting new tables
automatically on 2026-10-30.

Supabase's "Final notice" of 2026-10-20: from 2026-10-30 a new public table gets no automatic grant to anon,
authenticated or service_role - for new tables in production and for every replay (a local `supabase db reset`, a
preview branch, a new project). Measured 2026-10-21: 238 of 247 public tables and views held API access no migration
granted. 20261015800000_brh_x_explicit_api_grants wrote production's grants down (tools/generate_api_grant_backfill.py).

STATIC  A1 every migration after the backfill that creates a public table, view, materialized view or sequence grants
           it explicitly in the same file (`grant ... on <it> to <role>`), or revokes it from anon and authenticated
           outright and grants service_role (a server-only object) - a create with neither fails
LIVE    A2 every API privilege (SELECT/INSERT/UPDATE/DELETE/TRUNCATE) anon, authenticated or service_role holds on a
           public table or view in the local database is granted explicitly by some migration
        A3 REPLAY SIMULATION, in a transaction that is rolled back: every API grant on every public table, view and
           sequence is revoked and Supabase's new default imposed (no automatic grant), then the backfill's DO block is
           run - each object production serves must come back with its grants for each role
SELF-TEST (--self-test): a migration creating a table with no grant (A1); an undeclared anon SELECT granted inside a
           rolled-back transaction (A2); the replay with one backfill tuple removed (A3). Each must fail.

    python tools/validate_api_grants_explicit.py [--self-test] [--json]
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DB = "supabase_db_workhive"
MIG = ROOT / "supabase" / "migrations"
BACKFILL = "20261015800000_brh_x_explicit_api_grants.sql"
API = ("anon", "authenticated", "service_role")
NAME = r"(?:public\.)?\"?([a-z_][a-z0-9_]*)\"?"
# ★ANY SCHEMA, AND ONLY public IS THE API (2026-10-27): with only `public.` optional, `create table private.scheduled_calls`
# read as a table named "private" in public. Group 2 is a schema other than public (None for public or none named);
# group 3 is the object. An object outside public is not reachable through the API and needs no API grant.
CREATE = re.compile(r"\bcreate\s+(?:or\s+replace\s+)?(?:unlogged\s+)?(table|view|materialized\s+view|sequence)\s+"
                    r"(?:if\s+not\s+exists\s+)?(?:(?!public\.)([a-z_][a-z0-9_]*)\.(?=\"?[a-z_]))?" + NAME, re.I)
GRANT = re.compile(r"\bgrant\s+[a-z ,()_]+?\s+on\s+(?:table\s+|sequence\s+)?((?:(?:public\.)?\"?[a-z_][a-z0-9_]*\"?\s*,\s*)*"
                   r"(?:public\.)?\"?[a-z_][a-z0-9_]*\"?)\s+to\s+([a-z_, ]+)", re.I)
REVOKE_ALL = re.compile(r"\brevoke\s+all\s+(?:privileges\s+)?on\s+(?:table\s+)?" + NAME + r"\s+from\s+([a-z_, ]+)", re.I)
TUPLE = re.compile(r"\(\s*'([a-z_][a-z0-9_]*)'\s*,\s*'([rpvmS])'\s*,\s*'(anon|authenticated|service_role)'\s*,\s*'([A-Z, ]+)'\s*\)")


def strip_sql(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    return re.sub(r"--[^\n]*", " ", sql)


def psql(sql: str) -> tuple[int, str, str]:
    r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-At", "-v",
                        "ON_ERROR_STOP=1"], input=sql, capture_output=True, text=True, encoding="utf-8", timeout=600)
    return r.returncode, r.stdout, r.stderr


def migrations(override: dict | None = None) -> list[tuple[str, str]]:
    files = {f.name: f.read_text(encoding="utf-8", errors="replace") for f in sorted(MIG.glob("*.sql"))}
    files.update(override or {})
    return sorted(files.items())


def explicit_grants(migs) -> dict[str, set]:
    out: dict[str, set] = {}
    for name, text in migs:
        t = strip_sql(text)
        for m in GRANT.finditer(t):
            roles = {r.strip().lower() for r in m.group(2).split(",")} & set(API)
            for o in re.split(r"\s*,\s*", m.group(1)):
                out.setdefault(o.split(".")[-1].strip('"').lower(), set()).update(roles)
        if "execute format('grant %s on %s public.%I to %I'" in t:
            for m in TUPLE.finditer(t):
                out.setdefault(m.group(1), set()).add(m.group(3))
    return out


DROP = re.compile(r"\bdrop\s+(?:table|view|materialized\s+view|sequence)\s+(?:if\s+exists\s+)?" + NAME, re.I)


def check_static(migs) -> list[str]:
    """A create resets an object's privileges only when the object is NEW, or was DROPPED before it in the same file;
    `create or replace view` of a view that already exists keeps its grants (in production, and in a replay, where the
    backfill granted it first)."""
    issues = []
    existed: set[str] = set()
    for name, text in migs:
        t = strip_sql(text)
        if name <= BACKFILL:
            existed |= {m.group(3).lower() for m in CREATE.finditer(t) if not m.group(2)}
            if name == BACKFILL:
                existed |= {m.group(1) for m in TUPLE.finditer(t)}
            continue
        granted = {o.split(".")[-1].strip('"').lower() for m in GRANT.finditer(t) for o in re.split(r"\s*,\s*", m.group(1))}
        closed = {m.group(1).lower() for m in REVOKE_ALL.finditer(t)
                  if {"anon", "authenticated"} <= {r.strip().lower() for r in m.group(2).split(",")}}
        dropped = {m.group(1).lower(): m.start() for m in DROP.finditer(t)}
        for m in CREATE.finditer(t):
            if m.group(2):
                continue   # another schema: not reachable through the API
            obj = m.group(3).lower()
            replace = bool(re.match(r"create\s+or\s+replace\s+view", m.group(0), re.I))
            keeps = replace and obj in existed and not (obj in dropped and dropped[obj] < m.start())
            existed.add(obj)
            if keeps:
                continue
            if obj not in granted and obj not in closed:
                issues.append(f"A1 {name}: creates {m.group(1).lower()} public.{obj} and never grants it - from "
                              f"2026-10-30 nothing grants it automatically: grant the roles that read it, or revoke it "
                              f"from anon and authenticated outright and grant service_role")
    return issues


ACCESS_SQL = """select c.relname || '|' || coalesce((select string_agg(distinct a.grantee::regrole::text, ',')
  from aclexplode(c.relacl) a where a.grantee in ('anon'::regrole, 'authenticated'::regrole, 'service_role'::regrole)
  and a.privilege_type in ('SELECT','INSERT','UPDATE','DELETE','TRUNCATE')), '')
from pg_class c join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relkind in ('r','p','v','m') order by 1;"""


def check_live(migs, prefix_sql: str = "") -> list[str]:
    code, out, err = psql(("begin;\n" + prefix_sql + "\n" if prefix_sql else "") + ACCESS_SQL + ("\nrollback;" if prefix_sql else ""))
    if code:
        return [f"A2 LIVE could not read the grants: {(err or out).strip()[-200:]}"]
    exp = explicit_grants(migs)
    issues = []
    for ln in out.splitlines():
        if "|" not in ln:
            continue
        obj, roles = ln.split("|", 1)
        for role in sorted({r for r in roles.split(",") if r} - exp.get(obj, set())):
            issues.append(f"A2 {role} reaches public.{obj} through a grant no migration writes - a replay from 2026-10-30 "
                          f"would refuse it")
    return issues


def replay_sql(backfill_text: str) -> str:
    """A rolled-back transaction: strip every API grant, impose the no-automatic-grant default, run the backfill's DO
    block, and list (object, role) pairs the backfill was expected to restore and did not."""
    m = re.search(r"\ndo \$\$.*?\n\$\$;", backfill_text, re.S)
    if not m:
        return ""
    expected = [(t[0], t[2]) for t in TUPLE.findall(backfill_text)]
    exp_sql = ", ".join(f"('{o}', '{r}')" for o, r in expected)
    return f"""begin;
do $strip$
declare r record;
begin
  for r in select c.oid, c.relname, c.relkind from pg_class c join pg_namespace n on n.oid = c.relnamespace
           where n.nspname = 'public' and c.relkind in ('r','p','v','m','S') loop
    execute format('revoke all on %s public.%I from anon, authenticated, service_role',
                   case when r.relkind = 'S' then 'sequence' else 'table' end, r.relname);
  end loop;
end
$strip$;
alter default privileges in schema public revoke all on tables from anon, authenticated, service_role;
alter default privileges in schema public revoke all on sequences from anon, authenticated, service_role;
{m.group(0).strip()}
select e.obj || '|' || e.role from (values {exp_sql}) as e(obj, role)
where to_regclass('public.' || quote_ident(e.obj)) is not null
  and not exists (select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace
                  cross join lateral aclexplode(c.relacl) a
                  where n.nspname = 'public' and c.relname = e.obj and a.grantee::regrole::text = e.role);
rollback;
"""


def check_replay(backfill_text: str | None = None, expected_text: str | None = None) -> list[str]:
    bf = backfill_text if backfill_text is not None else (MIG / BACKFILL).read_text(encoding="utf-8")
    sql = replay_sql(bf)
    if not sql:
        return [f"A3 {BACKFILL} has no DO block to replay"]
    if expected_text is not None:
        # the self-test's mutant: the SAME expectations, a backfill missing one tuple
        sql = sql.replace(re.search(r"\ndo \$\$.*?\n\$\$;", bf, re.S).group(0).strip(),
                          re.search(r"\ndo \$\$.*?\n\$\$;", expected_text, re.S).group(0).strip())
    code, out, err = psql(sql)
    if code:
        return [f"A3 the replay simulation failed to run: {(err or out).strip()[-300:]}"]
    missing = [ln for ln in out.splitlines() if "|" in ln]
    return [f"A3 a replay under the new default leaves {len(missing)} grant(s) unrestored: {missing[:5]}"] if missing else []


def run() -> tuple[list[str], dict]:
    migs = migrations()
    issues = check_static(migs) + check_live(migs) + check_replay()
    return issues, {"migrations": len(migs)}


def self_test() -> list[str]:
    fails = []
    clean, _ = run()
    if clean:
        fails.append(f"the clean run is not green: {clean[:2]}")
    bad = migrations({"29991231000000_selftest.sql": "create table public.wh_selftest_ungranted (id int primary key);"})
    if not any(i.startswith("A1") for i in check_static(bad)):
        fails.append("mutant 'a migration creates a table and grants nothing' was not caught (A1)")
    if not any(i.startswith("A2") and "ops_artifact_metrics" in i
               for i in check_live(migrations(), "grant select on public.ops_artifact_metrics to anon;")):
        fails.append("mutant 'anon granted SELECT no migration writes' was not caught (A2)")
    bf = (MIG / BACKFILL).read_text(encoding="utf-8")
    first = TUPLE.search(bf)
    cut = bf[:first.start()] + bf[first.end():].lstrip(",\n ") if first else bf
    if first and not check_replay(bf, cut):
        fails.append("mutant 'the backfill loses a tuple' was not caught by the replay (A3)")
    return fails


def main() -> int:
    as_json = "--json" in sys.argv
    if "--self-test" in sys.argv:
        fails = self_test()
        print(json.dumps({"self_test": "FAIL" if fails else "PASS", "fails": fails}, indent=1) if as_json else
              ("SELF-TEST PASS (A1 static, A2 live and A3 replay mutants caught; the clean run is green)"
               if not fails else "SELF-TEST FAIL\n  " + "\n  ".join(fails)))
        return 1 if fails else 0
    issues, info = run()
    if as_json:
        print(json.dumps({"validator": "api_grants_explicit", "status": "FAIL" if issues else "PASS", "issues": issues}, indent=1))
    else:
        print("API grants explicit (BRH-X): every Data API grant is written in a migration, so a replay after 2026-10-30 "
              "reaches what production reaches")
        for i in issues[:40]:
            print("  [FAIL] " + i)
        print(f"  PASS - {info['migrations']} migrations; every API grant is explicit; the replay under the new default "
              f"restores every object production serves" if not issues else f"  FAIL - {len(issues)} problem(s)")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
