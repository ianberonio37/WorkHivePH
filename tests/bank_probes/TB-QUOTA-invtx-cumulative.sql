-- TB-QUOTA-invtx-cumulative.sql
--
-- `check_hive_quota_inv_tx` is the CUMULATIVE per-hive inventory-transactions quota — same two-branch shape as
-- the other hive quotas (enforce -> 54000 / warn-only -> automation_log 'hive_quota_inv_tx_over'). Scored by
-- the four existing §12 quota operators; no new operators.
--
-- ISOLATION (roadmap S14.4). inventory_transactions carries only check_daily_row_cap besides this quota (no
-- per-author recent-window rate limit), so yesterday-rows alone isolate the cumulative quota from the daily
-- cap; the daily cap has ample headroom for a handful of test rows. The fixture plants one inventory_item to
-- satisfy the item_id FK; inventory_sync_balance_from_ledger recomputes the item balance on each insert, which
-- does not block.
begin;

insert into public.hives(id, name, invite_code, created_by)
values ('a1000000-0000-4000-8000-00000000d001'::uuid, 'TB Quota InvTx Hive', 'TBQI01', 'tb-probe');

insert into public.inventory_items(id, hive_id, worker_name, part_name)
values ('a3000000-0000-4000-8000-00000000d001'::uuid, 'a1000000-0000-4000-8000-00000000d001'::uuid,
        'TB Q', 'TB Widget');

-- 3 transactions dated YESTERDAY -> cumulative = 3, today's count = 0.
insert into public.inventory_transactions(id, hive_id, item_id, worker_name, type, qty_change, qty_after, created_at)
select gen_random_uuid(), 'a1000000-0000-4000-8000-00000000d001'::uuid,
       'a3000000-0000-4000-8000-00000000d001'::uuid, 'TB Q', 'adjust', 1, g, now() - interval '1 day'
from generate_series(1,3) g;

-- ── MODE 1: enforcing — cumulative(3) >= cap(3) refuses ──
insert into public.hive_quotas(hive_id, max_rows_inv_tx, enforce_blocking)
values ('a1000000-0000-4000-8000-00000000d001'::uuid, 3, true)
on conflict (hive_id) do update set max_rows_inv_tx = 3, enforce_blocking = true;

do $enforcing$
declare n int;
begin
  begin
    insert into public.inventory_transactions(hive_id, item_id, worker_name, type, qty_change, qty_after)
      values ('a1000000-0000-4000-8000-00000000d001'::uuid,'a3000000-0000-4000-8000-00000000d001'::uuid,
              'TB Q','adjust',1,4);
    get diagnostics n = row_count;
    raise notice 'RESULT at_cap_blocking=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT at_cap_blocking=blocked sqlstate=%', sqlstate; end;
end $enforcing$;

-- ── MODE 2: warn-only — allowed, overrun recorded ──
update public.hive_quotas set enforce_blocking = false
 where hive_id = 'a1000000-0000-4000-8000-00000000d001'::uuid;

do $warnonly$
declare n int; logged int;
begin
  begin
    insert into public.inventory_transactions(hive_id, item_id, worker_name, type, qty_change, qty_after)
      values ('a1000000-0000-4000-8000-00000000d001'::uuid,'a3000000-0000-4000-8000-00000000d001'::uuid,
              'TB Q','adjust',1,5);
    get diagnostics n = row_count;
    raise notice 'RESULT at_cap_warnonly_write=%', case when n>0 then 'allowed' else 'BLOCKED' end;
  exception when others then raise notice 'RESULT at_cap_warnonly_write=BLOCKED sqlstate=%', sqlstate; end;
  select count(*) into logged from public.automation_log
   where job_name = 'hive_quota_inv_tx_over'
     and detail like '%' || 'a1000000-0000-4000-8000-00000000d001' || '%';
  raise notice 'RESULT at_cap_warnonly_logged=%', logged;
end $warnonly$;

-- ── NON-VACUITY: below the cap nothing refuses and nothing is logged ──
update public.hive_quotas set max_rows_inv_tx = 1000, enforce_blocking = true
 where hive_id = 'a1000000-0000-4000-8000-00000000d001'::uuid;

do $under$
declare n int; logged_before int; logged_after int;
begin
  select count(*) into logged_before from public.automation_log where job_name = 'hive_quota_inv_tx_over';
  begin
    insert into public.inventory_transactions(hive_id, item_id, worker_name, type, qty_change, qty_after)
      values ('a1000000-0000-4000-8000-00000000d001'::uuid,'a3000000-0000-4000-8000-00000000d001'::uuid,
              'TB Q','adjust',1,6);
    get diagnostics n = row_count;
    raise notice 'RESULT under_cap_write=%', case when n>0 then 'works' else 'BROKEN' end;
  exception when others then raise notice 'RESULT under_cap_write=BROKEN sqlstate=%', sqlstate; end;
  select count(*) into logged_after from public.automation_log where job_name = 'hive_quota_inv_tx_over';
  raise notice 'RESULT under_cap_logged_nothing=%',
    case when logged_after = logged_before then 'yes' else 'NO-FALSE-ALARM' end;
end $under$;

rollback;
