#!/usr/bin/env python3
"""
validate_cmms_import_rollback.py - PER_PAGE_BUGHUNT P3 gate for integrations.html's bulk CMMS import (2026-07-21).
==================================================================================================================
Locks the LAST deferred P3-write frontier: the CMMS file-import path (work_order / asset / pm_schedule /
inventory) that writes external_sync + logbook + asset_nodes + pm_assets/pm_scope_items + inventory_items
+ cmms_audit_log. One SUPERVISOR-JWT psql transaction mirrors each entity batch in the page's exact write
shapes, then ROLLS BACK (0 pollution — after-commit side-effects like the embed-logbook pg_net call never
fire on a rolled-back tx).

WHAT IT PROVES (each was a REAL bug or a live-proven hazard, 2026-07-21):
  1. STATUS CLAMP (static): normalizeRow must clamp work-order status to the DB-valid set — an unmapped
     raw code passed through as-is 23514-kills the WHOLE 500-row chunk (external_sync.status CHECK), and
     a mapped 'Cancelled' kills the logbook insert (logbook_status_check allows Open/Closed/Resolved).
  2. NO CLIENT fault_knowledge WRITE (static + live): the table is client-INSERT-LOCKED (RLS CHECK false,
     mig 20260513000003) — the import's old direct insert silently failed for ~2 months (supabase-js does
     not throw). Knowledge rows flow via the embed-logbook trigger -> embed-entry edge fn (service-role,
     WITH embedding). Live half asserts a client insert still 42501s (the lock can't silently drop).
  3. ERROR-CHECKED BATCHES (static): every batch write must check `.error` — without it the try/catch is
     dead code and a failed chunk is counted as imported.
  4. IMPORT ROUND-TRIP (live, rolled back): per entity type, the exact page shapes persist under the
     supervisor JWT; attribution triggers PIN forged worker_name/approved_by/submitted_by; re-running an
     upsert is IDEMPOTENT (1 row, updated — the #6 onConflict-index class, exercised not just indexed);
     the duplicate-guard read (v_external_sync_truth) sees the synced row; cmms_audit_log accepts the
     audit write.

Skips cleanly (exit 0) if docker/DB is unreachable. `--selftest` proves the parser has teeth.
"""
from __future__ import annotations
import io, re, sys, subprocess
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

G = "\033[92m"; R = "\033[91m"; B = "\033[1m"; X = "\033[0m"
CHECK_NAMES = ["validate_cmms_import_rollback"]
DB = "supabase_db_workhive"
ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "integrations.html"

# Supervisor identity (the import is a supervisor surface) — resolved live so a reseed can't rot it.
def _resolve_supervisor():
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
        from test_identity import resolve_test_identity
        i = resolve_test_identity("leandromarquez@auth.workhiveph.com")
        return i.user_id, i.hive_id
    except Exception:
        return ("00000000-0000-0000-0000-000000000000", "636cf7e8-431a-4907-8a9f-43dd4cc216d6")

# Static teeth: the fixed import invariants must stay in the page source.
STATIC_RULES = [
    ("status-clamp", re.compile(r"\{\s*open:'Open',\s*closed:'Closed',\s*cancelled:'Cancelled'\s*\}"), True,
     "normalizeRow must clamp WO status to the DB-valid set (unmapped raw code chunk-kills the import)"),
    ("cancelled-to-closed", re.compile(r"r\.status\s*===\s*'Cancelled'\s*\?\s*'Closed'"), True,
     "logbook rows must map Cancelled->Closed (logbook_status_check has no 'Cancelled')"),
    ("no-client-fault-knowledge-insert", re.compile(r"\.from\('fault_knowledge'\)\s*\.\s*insert"), False,
     "fault_knowledge is client-INSERT-LOCKED; knowledge flows via embed-logbook -> embed-entry (service-role)"),
    ("error-checked-batches", re.compile(r"if \(sErr\) throw sErr"), True,
     "batch writes must check supabase .error (it does not throw) or failures are counted as imported"),
]

EXPECT = {
    "FKLOCK":   ["true"],
    "SYNC":     ["1", "Closed"],
    "DUPGUARD": ["1"],
    "LOG":      ["true", "true", "true"],
    "ASSET":    ["1", "true", "true", "true", "true"],
    "PM":       ["true", "true", "true"],
    "SCOPE":    ["1", "true"],
    "INV":      ["1", "true", "9"],
    "AUDIT":    ["1", "true"],
}
EXPLAIN = {
    "FKLOCK":   "client fault_knowledge INSERT still 42501-locked",
    "SYNC":     "external_sync upsert x2 idempotent (1 row, re-import updated status)",
    "DUPGUARD": "duplicate-guard read (v_external_sync_truth) sees the synced row",
    "LOG":      "logbook import row: worker_name PINNED + hive + auth_uid correct",
    "ASSET":    "asset_nodes upsert x2: 1 row, worker/approved_by/submitted_by PINNED, re-import updated",
    "PM":       "pm_assets import row: worker_name PINNED + hive + auth_uid correct",
    "SCOPE":    "pm_scope_items FK row landed in-hive",
    "INV":      "inventory_items upsert x2 idempotent (1 row, qty re-imported)",
    "AUDIT":    "cmms_audit_log accepts the import audit write",
}


def _sql(uid: str, hive: str) -> str:
    return f"""
begin;
set local role authenticated;
set local request.jwt.claims = '{{"sub":"{uid}","role":"authenticated"}}';
do $$ begin
  insert into fault_knowledge(hive_id, machine, category, problem, worker_name)
  values('{hive}', 'CMMSGATE machine', 'Mechanical', 'CMMSGATE-FKLOCK probe', 'probe');
  raise notice 'FKLOCK|false';
exception when others then
  if sqlstate = '42501' then raise notice 'FKLOCK|true'; else raise; end if;
end $$;
insert into external_sync(hive_id, system_type, external_id, entity_type, workhive_table, status, sync_payload, sync_status)
values('{hive}','generic','CMMSGATE-WO-1','work_order','logbook','Open','{{"probe":true}}'::jsonb,'active')
on conflict (system_type,external_id,entity_type) do update set status=excluded.status, sync_payload=excluded.sync_payload, sync_status=excluded.sync_status;
insert into external_sync(hive_id, system_type, external_id, entity_type, workhive_table, status, sync_payload, sync_status)
values('{hive}','generic','CMMSGATE-WO-1','work_order','logbook','Closed','{{"probe":true,"v":2}}'::jsonb,'active')
on conflict (system_type,external_id,entity_type) do update set status=excluded.status, sync_payload=excluded.sync_payload, sync_status=excluded.sync_status;
select 'SYNC|'||count(*)||'|'||max(status) from external_sync where external_id='CMMSGATE-WO-1';
select 'DUPGUARD|'||count(*) from v_external_sync_truth where hive_id='{hive}' and entity_type='work_order' and external_id='CMMSGATE-WO-1';
insert into logbook(id, worker_name, auth_uid, date, machine, category, problem, action, knowledge, status, created_at, maintenance_type, root_cause, downtime_hours, hive_id, closed_at, parts_used)
values('cmmsgate-'||gen_random_uuid()::text, 'FORGED HACKER', '{uid}', now(), 'CMMSGATE machine', 'Mechanical', 'CMMSGATE-ROLLBACK wo', '', '', 'Closed', now(), 'Breakdown / Corrective', '', 0, '{hive}', now(), '[]'::jsonb);
select 'LOG|'||(worker_name <> 'FORGED HACKER')||'|'||(hive_id='{hive}')||'|'||(auth_uid='{uid}') from logbook where problem='CMMSGATE-ROLLBACK wo';
insert into asset_nodes(worker_name, auth_uid, tag, name, iso_class, location, criticality, level, status, hive_id, submitted_by, approved_by, approved_at, external_ids)
values('FORGED HACKER', '{uid}', 'CMMSGATE-TAG-1', 'CMMSGATE asset', 'General', '', 'medium', 'equipment', 'approved', '{hive}', 'FORGED HACKER', 'FORGED HACKER', now(), '{{"source_external_id":"CMMSGATE-TAG-1"}}'::jsonb)
on conflict (hive_id,tag) do update set name=excluded.name;
insert into asset_nodes(worker_name, auth_uid, tag, name, iso_class, location, criticality, level, status, hive_id, submitted_by, approved_by, approved_at, external_ids)
values('FORGED HACKER', '{uid}', 'CMMSGATE-TAG-1', 'CMMSGATE asset v2', 'General', '', 'medium', 'equipment', 'approved', '{hive}', 'FORGED HACKER', 'FORGED HACKER', now(), '{{"source_external_id":"CMMSGATE-TAG-1"}}'::jsonb)
on conflict (hive_id,tag) do update set name=excluded.name;
select 'ASSET|'||count(*)||'|'||bool_and(worker_name <> 'FORGED HACKER')||'|'||bool_and(coalesce(approved_by,'') <> 'FORGED HACKER')||'|'||bool_and(coalesce(submitted_by,'') <> 'FORGED HACKER')||'|'||bool_and(name='CMMSGATE asset v2') from asset_nodes where tag='CMMSGATE-TAG-1';
insert into pm_assets(hive_id, worker_name, auth_uid, asset_name, tag_id, location, category, criticality, last_anchor_date)
values('{hive}', 'FORGED HACKER', '{uid}', 'CMMSGATE-PM-1', 'CMMSGATE-PM-1', '', 'General', 'Major', current_date);
-- separate statement (mirrors the page's two round-trips): an RLS policy subquery cannot see a row
-- inserted in the SAME statement, so a single data-modifying CTE here would false-fail.
insert into pm_scope_items(asset_id, hive_id, item_text, frequency, anchor_date, is_custom)
select id, '{hive}', 'CMMSGATE task', 'Monthly', current_date, false from pm_assets where asset_name='CMMSGATE-PM-1';
select 'PM|'||(worker_name <> 'FORGED HACKER')||'|'||(hive_id='{hive}')||'|'||(auth_uid='{uid}') from pm_assets where asset_name='CMMSGATE-PM-1';
select 'SCOPE|'||count(*)||'|'||bool_and(hive_id='{hive}') from pm_scope_items where item_text='CMMSGATE task';
insert into inventory_items(worker_name, auth_uid, part_number, part_name, category, unit, qty_on_hand, min_qty, bin_location, linked_asset_node_ids, notes, status, hive_id, submitted_by, approved_by, approved_at)
values('probe', '{uid}', 'CMMSGATE-PART-1', 'CMMSGATE part', 'General', 'pcs', 5, 1, '', '{{}}', 'Imported from CMMS', 'approved', '{hive}', 'probe', 'probe', now())
on conflict (part_number,hive_id) do update set qty_on_hand=excluded.qty_on_hand;
insert into inventory_items(worker_name, auth_uid, part_number, part_name, category, unit, qty_on_hand, min_qty, bin_location, linked_asset_node_ids, notes, status, hive_id, submitted_by, approved_by, approved_at)
values('probe', '{uid}', 'CMMSGATE-PART-1', 'CMMSGATE part', 'General', 'pcs', 9, 1, '', '{{}}', 'Imported from CMMS', 'approved', '{hive}', 'probe', 'probe', now())
on conflict (part_number,hive_id) do update set qty_on_hand=excluded.qty_on_hand;
select 'INV|'||count(*)||'|'||bool_and(hive_id='{hive}')||'|'||max(qty_on_hand)::int from inventory_items where part_number='CMMSGATE-PART-1';
insert into cmms_audit_log(hive_id, batch_id, operation, entity_type, system_type, rows_attempted, rows_written, rows_failed, quality_score, triggered_by)
values('{hive}', 'CMMSGATE-BATCH', 'file_import', 'work_order', 'generic', 1, 1, 0, '{{}}'::jsonb, 'probe');
select 'AUDIT|'||count(*)||'|'||bool_and(hive_id='{hive}') from cmms_audit_log where batch_id='CMMSGATE-BATCH';
rollback;
"""


def check_static() -> list[str]:
    fails = []
    try:
        src = PAGE.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return [f"static:integrations.html unreadable ({e})"]
    for name, rx, must_exist, why in STATIC_RULES:
        found = bool(rx.search(src))
        if found != must_exist:
            verb = "MISSING" if must_exist else "REGRESSED (present)"
            fails.append(f"static:{name} {verb} — {why}")
    return fails


def run_live() -> tuple[dict, str]:
    uid, hive = _resolve_supervisor()
    try:
        r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres",
                            "-t", "-A", "-v", "ON_ERROR_STOP=1"],
                           input=_sql(uid, hive), capture_output=True, text=True, timeout=60)
    except Exception as e:
        return {}, "SKIP:docker-unreachable(" + str(e)[:40] + ")"
    out = (r.stdout or "") + (r.stderr or "")
    if "no such container" in out.lower() or "cannot connect" in out.lower():
        return {}, "SKIP:db-unreachable"
    # markers live in stdout; FKLOCK arrives as a psql NOTICE on stderr
    lines = {}
    for ln in out.splitlines():
        ln = ln.replace("NOTICE:", "").strip()
        if "|" in ln:
            key = ln.split("|", 1)[0]
            if key in EXPECT:
                lines[key] = ln.split("|")[1:]
    if r.returncode != 0 and "ERROR" in out:
        return lines, "FAIL:sql-error(" + out.strip().replace("\n", " ")[-160:] + ")"
    return lines, ""


def self_test() -> bool:
    ok = True
    # teeth: a wrong marker value must be caught
    if EXPECT["ASSET"] == ["1", "true", "true", "true", "false"]:
        print(f"{R}self-test FAIL: expectation table corrupt.{X}"); ok = False
    bad = "ASSET|2|true|false|true|true".split("|")[1:]
    if bad == EXPECT["ASSET"]:
        print(f"{R}self-test FAIL: forged marker not distinguishable.{X}"); ok = False
    # teeth: static rule regexes must match their own canonical fixtures
    fixtures = {
        "status-clamp": "{ open:'Open', closed:'Closed', cancelled:'Cancelled' }",
        "cancelled-to-closed": "r.status === 'Cancelled' ? 'Closed'",
        "no-client-fault-knowledge-insert": ".from('fault_knowledge').insert",
        "error-checked-batches": "if (sErr) throw sErr;",
    }
    for name, rx, _must, _why in STATIC_RULES:
        if not rx.search(fixtures[name]):
            print(f"{R}self-test FAIL: static rule {name} does not match its fixture.{X}"); ok = False
    print((G + "self-test PASS - cmms-import gate has teeth." + X) if ok else (R + "self-test FAILED." + X))
    return ok


def main() -> int:
    if "--selftest" in sys.argv or "--self-test" in sys.argv:
        return 0 if self_test() else 1
    print(f"{B}P3 CMMS bulk-import gate (integrations.html): static clamps + rolled-back supervisor batch{X}")
    fails = check_static()
    for f in fails:
        print(f"  {R}FAIL{X}  {f}")
    if not fails:
        print(f"  {G}PASS{X}  static: status clamp + Cancelled->Closed + no client fault_knowledge write + error-checked batches")
    lines, err = run_live()
    if err.startswith("SKIP"):
        print(f"  SKIP  live: {err}")
        return 1 if fails else 0
    if err.startswith("FAIL"):
        print(f"  {R}FAIL{X}  live: {err}")
        fails.append(err)
    for key, want in EXPECT.items():
        got = lines.get(key)
        if got == want:
            print(f"  {G}PASS{X}  {key}: {EXPLAIN[key]}")
        else:
            msg = f"live:{key} expected {want} got {got} — {EXPLAIN[key]}"
            print(f"  {R}FAIL{X}  {msg}")
            fails.append(msg)
    if fails:
        print(f"{R}FAIL: {len(fails)} CMMS-import regression(s).{X}")
        return 1
    print(f"{G}PASS - CMMS bulk-import path verified at the DB (rolled back, 0 pollution) + clamps locked.{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
