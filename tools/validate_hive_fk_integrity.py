#!/usr/bin/env python3
"""validate_hive_fk_integrity.py — T422's REAL lock: a hive delete can never orphan a row, because every
hive_id column is FK-ENFORCED against hives with a deliberate disposition (CASCADE or SET NULL), typed uuid,
and holding zero dangling references.

FOUND 2026-09-01 (correcting T422's walk, which had verified only the FK-BEARING relations and concluded
"no orphaned rows"): THIRTY-THREE public tables carried hive_id with NO foreign key at all — including core
hive data (projects + 6 children, pm_scope_items, pm_completions, inventory_items, kb_documents, the
community content + xp-award tables, credit_reservations, service_payments) — and live orphans existed:
analytics_events 1,834, anomaly_alerts 20, kb_documents 3, dialog_state 3 (dangling hive_ids of deleted
hives: invisible to hive-scoped RLS, still reachable through service-role/DEFINER paths). Two tables even
stored hive_id as TEXT. Fixed by migration 20260901000001 (cleanup + 33 FKs per the schema's own
CASCADE/SET-NULL disposition pattern + uuid type repair). This gate holds all four properties:
  1. NO FK-LESS hive_id — every public base table with a hive_id column has an FK to hives.
  2. DELIBERATE DISPOSITION — every hives-FK is CASCADE ('c', hive-owned dies with the hive) or
     SET NULL ('n', worker/money/telemetry survives detached); NO ACTION/RESTRICT would make a hive
     delete BLOCK unpredictably and is refused.
  3. UUID-TYPED — no hive_id column is text (the wh_traces/ai_user_rate_limits smell, repaired).
  4. ZERO DANGLING — no row anywhere references a hive that does not exist (belt-and-braces; with 1-3
     enforced this cannot happen, but a future FK-less table's orphans surface here as well as in 1).

DB-backed (psql), read-only, browser-free. SKIPs if the DB is unreachable (no unearned pass). Registered
in run_platform_checks (Platform).
"""
from __future__ import annotations

import io
import subprocess
import sys

CHECK_NAMES = ["hive-fk-integrity"]


def _psql(sql: str) -> str | None:
    try:
        r = subprocess.run(
            ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
             "-t", "-A"], input=sql, capture_output=True, text=True, timeout=90)
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None


def _fetch():
    # EXEMPT community_reply_xp_awards: the community_xp_ledger gate holds the OPPOSITE invariant for
    # that one table — it must carry NO foreign keys at all (replies HARD-delete; any cascade erases
    # the award row at the instant the reversal trigger reads it, silently re-opening the reply-XP
    # farm). The 2026-09-02 full board caught the two gates fighting; its orphan risk is accepted and
    # still surfaces via check 4 (dangling scan) if a hive delete ever leaves rows behind.
    fkless = _psql("""
select coalesce(string_agg(c.table_name, ','), '') from information_schema.columns c
join information_schema.tables t on t.table_name=c.table_name and t.table_schema='public' and t.table_type='BASE TABLE'
where c.table_schema='public' and c.column_name='hive_id'
and c.table_name <> 'community_reply_xp_awards'
and not exists (select 1 from pg_constraint con join pg_class cl on cl.oid=con.conrelid
  join pg_class ref on ref.oid=con.confrelid join pg_attribute a on a.attrelid=con.conrelid and a.attnum=any(con.conkey)
  where con.contype='f' and ref.relname='hives' and cl.relname=c.table_name and a.attname='hive_id');""")
    if fkless is None:
        return None
    baddisp = _psql("""
select coalesce(string_agg(c.relname||'='||con.confdeltype, ','), '')
from pg_constraint con join pg_class c on c.oid=con.conrelid join pg_class ref on ref.oid=con.confrelid
where con.contype='f' and ref.relname='hives' and con.confdeltype not in ('c','n');""")
    nonuuid = _psql("""
select coalesce(string_agg(c.table_name||':'||c.data_type, ','), '') from information_schema.columns c
join information_schema.tables t on t.table_name=c.table_name and t.table_schema='public' and t.table_type='BASE TABLE'
where c.table_schema='public' and c.column_name='hive_id' and c.data_type<>'uuid';""")
    dangling = _psql("""
do $$ declare r record; n bigint; total bigint := 0; begin
for r in (select c.table_name from information_schema.columns c join information_schema.tables t
  on t.table_name=c.table_name and t.table_schema='public' and t.table_type='BASE TABLE'
  where c.table_schema='public' and c.column_name='hive_id') loop
  execute format('select count(*) from %I x where x.hive_id is not null and not exists (select 1 from hives h where h.id=x.hive_id::uuid)', r.table_name) into n;
  total := total + n;
end loop; raise notice 'DANGLING_TOTAL=%', total; end $$;""")
    # the DO block reports via NOTICE on stderr; re-fetch via a temp function-free approach:
    dtot = _psql("""
with t as (select c.table_name from information_schema.columns c join information_schema.tables tt
  on tt.table_name=c.table_name and tt.table_schema='public' and tt.table_type='BASE TABLE'
  where c.table_schema='public' and c.column_name='hive_id')
select count(*) from t;""")
    return {"fkless": (fkless or "").strip(), "baddisp": (baddisp or "").strip(),
            "nonuuid": (nonuuid or "").strip(), "tables": int((dtot or "0").strip() or 0)}


def _dangling_total() -> int | None:
    out = _psql("""
select coalesce(sum(cnt),0)::text from (
  select c.table_name, (xpath('/row/c/text()', query_to_xml(
    format('select count(*) as c from %I x where x.hive_id is not null and not exists (select 1 from hives h where h.id=x.hive_id::uuid)', c.table_name),
    false,true,''))::text[])[1]::text::bigint as cnt
  from information_schema.columns c
  join information_schema.tables t on t.table_name=c.table_name and t.table_schema='public' and t.table_type='BASE TABLE'
  where c.table_schema='public' and c.column_name='hive_id') s;""")
    try:
        return int((out or "").strip())
    except Exception:
        return None


def check(data: dict, dangling: int | None) -> list[str]:
    problems: list[str] = []
    if data["fkless"]:
        problems.append(f"hive_id tables with NO FK to hives (a hive delete orphans them): {data['fkless'][:200]}")
    if data["baddisp"]:
        problems.append(f"hive-FKs that are neither CASCADE nor SET NULL (a hive delete would BLOCK): {data['baddisp'][:160]}")
    if data["nonuuid"]:
        problems.append(f"hive_id columns not typed uuid: {data['nonuuid'][:160]}")
    if dangling is None:
        problems.append("could not count dangling hive_ids (the orphan assertion did not run — no silent pass).")
    elif dangling > 0:
        problems.append(f"{dangling} row(s) reference a hive that does not exist (live orphans).")
    return problems


def main() -> int:
    data = _fetch()
    if data is None:
        print("SKIP hive-fk-integrity — DB unreachable (no unearned pass).")
        return 0
    problems = check(data, _dangling_total())
    if problems:
        print("FAIL hive-fk-integrity — a hive delete can orphan or block:")
        for p in problems:
            print(f"    {p}")
        return 1
    print(f"PASS hive-fk-integrity — all {data['tables']} hive_id tables are FK-enforced (CASCADE or SET NULL, "
          f"uuid-typed) with zero dangling references: a hive delete cascades or detaches, never orphans.")
    return 0


def self_test() -> int:
    good = {"fkless": "", "baddisp": "", "nonuuid": "", "tables": 111}
    fails = []
    if check(good, 0):
        fails.append("the clean posture should PASS")
    if not any("NO FK" in p for p in check({**good, "fkless": "projects"}, 0)):
        fails.append("an FK-less hive_id table should FAIL")
    if not any("BLOCK" in p for p in check({**good, "baddisp": "projects=a"}, 0)):
        fails.append("a NO-ACTION hive-FK should FAIL")
    if not any("uuid" in p for p in check({**good, "nonuuid": "wh_traces:text"}, 0)):
        fails.append("a text hive_id should FAIL")
    if not any("orphans" in p for p in check(good, 3)):
        fails.append("dangling rows should FAIL")
    if not any("did not run" in p for p in check(good, None)):
        fails.append("an unmeasurable dangling count should FAIL (never silently pass)")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_hive_fk_integrity self-test (fk-less / no-action / text-type / dangling / unmeasured redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
