-- TB-QUOTA-pm-cumulative.sql
--
-- `check_hive_quota_pm_completions` is the last of the FIVE cumulative per-hive quotas — same two-branch shape
-- (enforce -> 54000 / warn-only -> automation_log 'hive_quota_pm_completions_over'). Scored by the four §12
-- quota operators; no new operators. Isolated from check_daily_row_cap by yesterday-rows; pm_completions has no
-- per-author recent-window rate limit, so no author trick is needed.
begin;

insert into public.hives(id, name, invite_code, created_by)
values ('a1000000-0000-4000-8000-00000000e001'::uuid, 'TB Quota PM Hive', 'TBQP01', 'tb-probe');

-- completed_at dated yesterday so the daily-cap sibling (which counts by completed_at) sees 0 today; the quota
-- is cumulative and counts all three regardless.
insert into public.pm_completions(id, hive_id, worker_name, completed_at)
select gen_random_uuid(), 'a1000000-0000-4000-8000-00000000e001'::uuid, 'TB Q', now() - interval '1 day'
from generate_series(1,3);

insert into public.hive_quotas(hive_id, max_rows_pm_comp, enforce_blocking)
values ('a1000000-0000-4000-8000-00000000e001'::uuid, 3, true)
on conflict (hive_id) do update set max_rows_pm_comp = 3, enforce_blocking = true;

do $enforcing$
declare n int;
begin
  begin
    insert into public.pm_completions(hive_id, worker_name) values ('a1000000-0000-4000-8000-00000000e001'::uuid,'TB Q');
    get diagnostics n = row_count;
    raise notice 'RESULT at_cap_blocking=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT at_cap_blocking=blocked sqlstate=%', sqlstate; end;
end $enforcing$;

update public.hive_quotas set enforce_blocking = false where hive_id = 'a1000000-0000-4000-8000-00000000e001'::uuid;

do $warnonly$
declare n int; logged int;
begin
  begin
    insert into public.pm_completions(hive_id, worker_name) values ('a1000000-0000-4000-8000-00000000e001'::uuid,'TB Q');
    get diagnostics n = row_count;
    raise notice 'RESULT at_cap_warnonly_write=%', case when n>0 then 'allowed' else 'BLOCKED' end;
  exception when others then raise notice 'RESULT at_cap_warnonly_write=BLOCKED sqlstate=%', sqlstate; end;
  select count(*) into logged from public.automation_log
   where job_name = 'hive_quota_pm_completions_over'
     and detail like '%' || 'a1000000-0000-4000-8000-00000000e001' || '%';
  raise notice 'RESULT at_cap_warnonly_logged=%', logged;
end $warnonly$;

update public.hive_quotas set max_rows_pm_comp = 1000, enforce_blocking = true where hive_id = 'a1000000-0000-4000-8000-00000000e001'::uuid;

do $under$
declare n int; logged_before int; logged_after int;
begin
  select count(*) into logged_before from public.automation_log where job_name = 'hive_quota_pm_completions_over';
  begin
    insert into public.pm_completions(hive_id, worker_name) values ('a1000000-0000-4000-8000-00000000e001'::uuid,'TB Q');
    get diagnostics n = row_count;
    raise notice 'RESULT under_cap_write=%', case when n>0 then 'works' else 'BROKEN' end;
  exception when others then raise notice 'RESULT under_cap_write=BROKEN sqlstate=%', sqlstate; end;
  select count(*) into logged_after from public.automation_log where job_name = 'hive_quota_pm_completions_over';
  raise notice 'RESULT under_cap_logged_nothing=%',
    case when logged_after = logged_before then 'yes' else 'NO-FALSE-ALARM' end;
end $under$;

rollback;
