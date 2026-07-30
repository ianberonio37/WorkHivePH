-- TB-QUOTA-logbook-cumulative.sql
--
-- `check_hive_quota_logbook` is the CUMULATIVE per-hive logbook quota — the same two-branch shape as
-- `check_hive_quota_ai_reports` (§12 / TB-QUOTA): enforce_blocking=TRUE refuses at/over cap with 54000;
-- enforce_blocking=FALSE allows the write and records the overrun to automation_log. The warn-only mode is the
-- one worth guarding hardest, because its failure is SILENT, so the assertion reads the log row BACK.
--
-- ISOLATION FROM THE SIBLING RATE LIMIT (roadmap S14.4). check_logbook_rate_limit's HIVE cap reads the SAME
-- `max_rows_logbook`, but over TODAY's rows; this guard counts CUMULATIVE. For a fresh hive whose rows are all
-- today the two are equal and setting the cap to trip the quota ALSO trips the rate limit — which would refuse
-- the warn-only write and turn the baseline red. So the fixture rows are dated YESTERDAY: cumulative(3) > today(0),
-- the quota trips while the daily rate-limit cap stays clear, and the per-user cap is pinned high for good
-- measure. Scored by the four EXISTING §12 quota operators; no new operators.
begin;

insert into public.hives(id, name, invite_code, created_by)
values ('a1000000-0000-4000-8000-00000000f001'::uuid, 'TB Quota Logbook Hive', 'TBQL01', 'tb-probe');

-- 3 logbook rows dated YESTERDAY, so cumulative = 3 while today's count = 0.
insert into public.logbook(id, hive_id, worker_name, date, created_at)
select gen_random_uuid(), 'a1000000-0000-4000-8000-00000000f001'::uuid, 'TB Q', current_date - 1,
       now() - interval '1 day'
from generate_series(1,3);

-- ── MODE 1: enforcing — cumulative(3) >= cap(3) refuses; the rate limit (today=0) cannot be what refused ──
insert into public.hive_quotas(hive_id, max_rows_logbook, max_rows_logbook_per_user, enforce_blocking)
values ('a1000000-0000-4000-8000-00000000f001'::uuid, 3, 1000000, true)
on conflict (hive_id) do update set max_rows_logbook = 3, max_rows_logbook_per_user = 1000000, enforce_blocking = true;

do $enforcing$
declare n int;
begin
  begin
    insert into public.logbook(hive_id, worker_name, date)
      values ('a1000000-0000-4000-8000-00000000f001'::uuid, 'TB Q', current_date);
    get diagnostics n = row_count;
    raise notice 'RESULT at_cap_blocking=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then
    raise notice 'RESULT at_cap_blocking=blocked sqlstate=%', sqlstate;   -- 54000 = program_limit_exceeded
  end;
end $enforcing$;

-- ── MODE 2: warn-only — the write is ALLOWED and the overrun is recorded ──
update public.hive_quotas set enforce_blocking = false
 where hive_id = 'a1000000-0000-4000-8000-00000000f001'::uuid;

do $warnonly$
declare n int; logged int;
begin
  begin
    insert into public.logbook(hive_id, worker_name, date)
      values ('a1000000-0000-4000-8000-00000000f001'::uuid, 'TB Q', current_date);
    get diagnostics n = row_count;
    raise notice 'RESULT at_cap_warnonly_write=%', case when n>0 then 'allowed' else 'BLOCKED' end;
  exception when others then raise notice 'RESULT at_cap_warnonly_write=BLOCKED sqlstate=%', sqlstate; end;
  select count(*) into logged from public.automation_log
   where job_name = 'hive_quota_logbook_over'
     and detail like '%' || 'a1000000-0000-4000-8000-00000000f001' || '%';
  raise notice 'RESULT at_cap_warnonly_logged=%', logged;
end $warnonly$;

-- ── NON-VACUITY: below the cap, nothing refuses and nothing is logged ──
update public.hive_quotas set max_rows_logbook = 1000, enforce_blocking = true
 where hive_id = 'a1000000-0000-4000-8000-00000000f001'::uuid;

do $under$
declare n int; logged_before int; logged_after int;
begin
  select count(*) into logged_before from public.automation_log where job_name = 'hive_quota_logbook_over';
  begin
    insert into public.logbook(hive_id, worker_name, date)
      values ('a1000000-0000-4000-8000-00000000f001'::uuid, 'TB Q', current_date);
    get diagnostics n = row_count;
    raise notice 'RESULT under_cap_write=%', case when n>0 then 'works' else 'BROKEN' end;
  exception when others then raise notice 'RESULT under_cap_write=BROKEN sqlstate=%', sqlstate; end;
  select count(*) into logged_after from public.automation_log where job_name = 'hive_quota_logbook_over';
  raise notice 'RESULT under_cap_logged_nothing=%',
    case when logged_after = logged_before then 'yes' else 'NO-FALSE-ALARM' end;
end $under$;

rollback;
