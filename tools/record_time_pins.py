#!/usr/bin/env python3
"""record_time_pins.py - which record times can a signed-in member rewrite? (BRH class AQ, 2026-11-11)

Found by the M13 claim audit of the guide "start a digital logbook in a Philippine factory". The guide tells a plant
that an auditor's first question is "can the entry be backdated?" and that the answer must be no, and its table says
WorkHive keeps a server-side timestamp. Measured on the local stack: a worker, signed in, ran
    update logbook set created_at = '2020-01-01' where id = <their own open entry>
through the API and it held. Nothing recorded it: the post-close audit fires only for closed entries.

The cause is not one table. Supabase grants `authenticated` UPDATE on every column, so on every table a member may
update, every timestamp column is writable unless a BEFORE UPDATE trigger puts the old value back. This tool measures
that population from the database itself: one cell per (table, time column) where
  - the table has row-level security on and an UPDATE policy that a signed-in member can pass,
  - `authenticated` holds UPDATE on the column, and
  - no BEFORE UPDATE trigger on the table sets NEW.<column> := OLD.<column>.

Two kinds of cell, fixed differently:
  created_at   - a record's creation time. It never changes once the row exists, so it is pinned on every table
                 (migration 20261111000001: wh_pin_created_at). The gate allows no open created_at cell.
  domain times - completed_at, closed_at, approved_at, resolved_at, recorded_at. These change on purpose, on a state
                 transition (a PM completed, an entry closed, a strategy approved), so each table needs its own rule.
                 The gate holds them forward-only against the committed evidence until each is fixed.

Usage:
  python tools/record_time_pins.py              # print the cells
  python tools/record_time_pins.py --write      # write record_time_pin_evidence.json (the class-AQ population)
  python tools/record_time_pins.py --check      # gate: no open created_at; domain cells no more than the evidence
  python tools/record_time_pins.py --probe      # teeth: a member's backdate of their own logbook entry, rolled back
  python tools/record_time_pins.py --self-test
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "record_time_pin_evidence.json"
DB_CONTAINER = "supabase_db_workhive"
TIME_COLUMNS = ("created_at", "completed_at", "closed_at", "approved_at", "signed_at", "recorded_at", "logged_at",
                "performed_at", "occurred_at", "submitted_at", "resolved_at")

MEASURE_SQL = """
with upd_tables as (
  select distinct c.oid, c.relname from pg_policy p join pg_class c on c.oid = p.polrelid
  join pg_namespace n on n.oid = c.relnamespace
  where n.nspname = 'public' and c.relkind = 'r' and c.relrowsecurity and p.polcmd in ('w', '*')
    and (p.polroles = '{0}' or exists (select 1 from pg_roles r where r.oid = any(p.polroles)
                                       and r.rolname = 'authenticated'))
), cols as (
  select t.oid, t.relname, cp.column_name from upd_tables t
  join information_schema.column_privileges cp on cp.table_schema = 'public' and cp.table_name = t.relname
       and cp.grantee = 'authenticated' and cp.privilege_type = 'UPDATE'
  join information_schema.columns ic on ic.table_schema = 'public' and ic.table_name = t.relname
       and ic.column_name = cp.column_name
  where ic.data_type like 'timestamp%%' and cp.column_name in (%(cols)s)
), trig as (
  -- each BEFORE UPDATE trigger's body, plus "fn:<name>:<first argument>" so a generic pin that takes the column as its
  -- argument (wh_server_time_on_change('completed_at')) is recognised as well as a literal NEW.col := OLD.col
  select tg.tgrelid,
         string_agg(pg_get_functiondef(tg.tgfoid) || ' fn:' || p.proname || ':' ||
                    split_part(encode(tg.tgargs, 'escape'), '\\000', 1), ' ') body
  from pg_trigger tg join pg_proc p on p.oid = tg.tgfoid
  where not tg.tgisinternal and (tg.tgtype & 2) = 2 and (tg.tgtype & 16) = 16 group by tg.tgrelid
)
select c.relname || '|' || c.column_name || '|' ||
       case when lower(regexp_replace(coalesce(t.body, ''), '\\s+', '', 'g'))
                 like '%%new.' || c.column_name || ':=old.' || c.column_name || '%%'
                 or coalesce(t.body, '') like '%%fn:wh_server_time_on_change:' || c.column_name || '%%'
            then 'pinned' else 'open' end
from cols c left join trig t on t.tgrelid = c.oid order by 1;
"""

PROBE_SQL = """
begin;
select set_config('request.jwt.claims', json_build_object('sub', '%(uid)s', 'role', 'authenticated')::text, true);
set local role authenticated;
update public.logbook set created_at = '2020-01-01T00:00:00Z' where id = '%(lid)s' returning 'AFTER|' || created_at;
rollback;
"""


def _psql(sql: str) -> list[str]:
    r = subprocess.run(["docker", "exec", "-i", DB_CONTAINER, "psql", "-U", "postgres", "-v", "ON_ERROR_STOP=1",
                        "-tAq"], input=sql, capture_output=True, text=True, encoding="utf-8", timeout=120)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip()[:400])
    return [ln for ln in r.stdout.splitlines() if ln.strip()]


def classify(lines: list[str]) -> list[dict]:
    """Turn 'table|column|state' lines into cells."""
    out = []
    for ln in lines:
        parts = ln.split("|")
        if len(parts) != 3:
            continue
        t, c, s = parts
        out.append({"table": t, "column": c, "state": s,
                    "kind": "created_at" if c == "created_at" else "domain"})
    return out


def measure() -> list[dict]:
    cols = ", ".join(f"'{c}'" for c in TIME_COLUMNS)
    return classify(_psql(MEASURE_SQL % {"cols": cols}))


def verdict(cells: list[dict], evidence: dict | None) -> tuple[bool, list[str]]:
    """The gate's rule, pure so the self-test can hold it."""
    msgs = []
    open_created = [c for c in cells if c["kind"] == "created_at" and c["state"] == "open"]
    open_domain = sorted(f"{c['table']}.{c['column']}" for c in cells if c["kind"] == "domain" and c["state"] == "open")
    ok = True
    if open_created:
        ok = False
        msgs.append(f"{len(open_created)} created_at column(s) a signed-in member can rewrite: "
                    + ", ".join(c["table"] for c in open_created[:12]) + (" ..." if len(open_created) > 12 else "")
                    + " - attach trg_pin_created_at (wh_pin_created_at) to each")
    if evidence is not None:
        allowed = set(evidence.get("open_domain_allowed", []))
        new = [x for x in open_domain if x not in allowed]
        if new:
            ok = False
            msgs.append(f"{len(new)} domain time(s) newly writable by a member, not in the evidence: {', '.join(new)}")
    msgs.append(f"{len(open_domain)} domain time(s) still open (forward-only): {', '.join(open_domain) or 'none'}")
    return ok, msgs


def probe() -> tuple[bool, str]:
    """A signed-in member tries to backdate their own open logbook entry; the transaction always rolls back."""
    row = _psql("select l.auth_uid || '|' || l.id from logbook l join hive_members m on m.auth_uid = l.auth_uid "
                "and m.hive_id = l.hive_id and m.status = 'active' where l.deleted_at is null "
                "and l.auth_uid is not null and l.status <> 'Closed' limit 1;")
    if not row:
        return False, "no open logbook entry owned by an active member to probe - reseed the local stack"
    uid, lid = row[0].split("|", 1)
    out = _psql(PROBE_SQL % {"uid": uid, "lid": lid})
    after = next((ln.split("|", 1)[1] for ln in out if ln.startswith("AFTER|")), "")
    if not after:
        return False, f"the probe's update returned no row for entry {lid} (RLS refused the owner?)"
    if after.startswith("2020-01-01"):
        return False, f"a member moved their own entry's created_at to {after} - backdating holds"
    first = f"a member's attempt to move created_at to 2020-01-01 left it at {after}"
    # the domain slice (20261111000002): a member who moves their own PM completion's completed_at gets the server's
    # clock, not the moment they chose - a backdated completion would move PM compliance
    row = _psql("select c.auth_uid || '|' || c.id from pm_completions c join hive_members m on m.auth_uid = c.auth_uid "
                "and m.hive_id = c.hive_id and m.status = 'active' where c.auth_uid is not null limit 1;")
    if not row:
        return False, first + "; no PM completion owned by an active member to probe - reseed the local stack"
    uid, cid = row[0].split("|", 1)
    out = _psql(PROBE_SQL.replace("public.logbook", "public.pm_completions").replace("set created_at", "set completed_at")
                .replace("|| created_at", "|| completed_at") % {"uid": uid, "lid": cid})
    moved = next((ln.split("|", 1)[1] for ln in out if ln.startswith("AFTER|")), "")
    if not moved:
        return False, first + f"; the PM-completion probe returned no row for {cid} (RLS refused the owner?)"
    if moved.startswith("2020-01-01"):
        return False, first + f"; but a member moved their own PM completion's completed_at to {moved} - compliance can be backdated"
    return True, first + f"; a member's move of their PM completion to 2020-01-01 was recorded at the server's {moved}"


def self_test() -> int:
    cells = classify(["logbook|created_at|open", "logbook|closed_at|open", "pm_completions|completed_at|open",
                      "hives|created_at|pinned", "bad line"])
    assert len(cells) == 4, cells
    ok, _ = verdict(cells, {"open_domain_allowed": ["logbook.closed_at", "pm_completions.completed_at"]})
    assert not ok, "an open created_at must fail"
    fixed = [dict(c, state="pinned") if c["kind"] == "created_at" else c for c in cells]
    ok, _ = verdict(fixed, {"open_domain_allowed": ["logbook.closed_at", "pm_completions.completed_at"]})
    assert ok, "pinned created_at + allowed domain cells must pass"
    ok, msgs = verdict(fixed, {"open_domain_allowed": ["logbook.closed_at"]})
    assert not ok and "pm_completions.completed_at" in msgs[0], "a domain cell not in the evidence must fail"
    print("PASS self-test (4 cases)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    try:
        cells = measure()
    except Exception as e:  # the stack is down: say so, never pass silently
        print(f"FAIL record-time-pins: cannot read the local database ({e})")
        return 1
    if a.write:
        prev = json.loads(EVIDENCE.read_text(encoding="utf-8")) if EVIDENCE.exists() else {}
        open_domain = sorted(f"{c['table']}.{c['column']}" for c in cells if c["kind"] == "domain" and c["state"] == "open")
        ev = {"read": date.today().isoformat(), "source": "local stack (docker psql), tools/record_time_pins.py",
              "seeded": prev.get("seeded") or [c for c in cells if c["state"] == "open"],
              "open_domain_allowed": open_domain,
              "cells": cells}
        EVIDENCE.write_text(json.dumps(ev, indent=1) + "\n", encoding="utf-8")
        print(f"wrote {EVIDENCE.name}: {len(cells)} cell(s), {sum(c['state'] == 'open' for c in cells)} open")
        return 0
    if a.check:
        ev = json.loads(EVIDENCE.read_text(encoding="utf-8")) if EVIDENCE.exists() else None
        ok, msgs = verdict(cells, ev)
        good, why = probe()
        print(("PASS" if ok and good else "FAIL") + " record-time-pins")
        for m in msgs + [("teeth: " if good else "FAIL teeth: ") + why]:
            print("  " + m)
        return 0 if ok and good else 1
    if a.probe:
        good, why = probe()
        print(("PASS " if good else "FAIL ") + why)
        return 0 if good else 1
    for c in cells:
        print(f"{c['state']:<7} {c['table']}.{c['column']}")
    print(f"{len(cells)} cell(s), {sum(c['state'] == 'open' for c in cells)} open")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
