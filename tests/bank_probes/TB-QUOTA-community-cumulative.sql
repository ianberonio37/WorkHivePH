-- TB-QUOTA-community-cumulative.sql
--
-- `check_hive_quota_community` is the CUMULATIVE per-hive community-posts quota — the same two-branch shape as
-- check_hive_quota_ai_reports / check_hive_quota_logbook (enforce -> 54000 / warn-only -> automation_log,
-- 'hive_quota_community_over'). Scored by the four existing §12 quota operators; no new operators.
--
-- THREE-WAY ISOLATION (roadmap S14.4). community_posts also carries community_post_rate_limit (per-AUTHOR, a
-- 30-second window, >=3) and check_daily_row_cap (200/hive, 100/user per day). So:
--   * yesterday-rows separate the CUMULATIVE quota (all-time) from any daily/recent window;
--   * a DIFFERENT author_name per test insert keeps the per-author 30s rate limit at zero (the per-hive quota
--     still counts them all);
--   * the daily cap (200/100) is far above the handful of test rows.
-- so the only guard that can refuse the test writes is the quota under test.
begin;

insert into public.hives(id, name, invite_code, created_by)
values ('a1000000-0000-4000-8000-00000000c001'::uuid, 'TB Quota Community Hive', 'TBQC01', 'tb-probe');

-- 3 posts dated YESTERDAY -> cumulative = 3, today's/recent count = 0.
insert into public.community_posts(id, hive_id, author_name, content, category, created_at)
select gen_random_uuid(), 'a1000000-0000-4000-8000-00000000c001'::uuid, 'TB Q0', 'seed', 'general',
       now() - interval '1 day'
from generate_series(1,3);

-- ── MODE 1: enforcing — cumulative(3) >= cap(3) refuses ──
insert into public.hive_quotas(hive_id, max_rows_community, enforce_blocking)
values ('a1000000-0000-4000-8000-00000000c001'::uuid, 3, true)
on conflict (hive_id) do update set max_rows_community = 3, enforce_blocking = true;

do $enforcing$
declare n int;
begin
  begin
    insert into public.community_posts(hive_id, author_name, content, category)
      values ('a1000000-0000-4000-8000-00000000c001'::uuid, 'TB QA', 'over cap', 'general');
    get diagnostics n = row_count;
    raise notice 'RESULT at_cap_blocking=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT at_cap_blocking=blocked sqlstate=%', sqlstate; end;
end $enforcing$;

-- ── MODE 2: warn-only — allowed, overrun recorded ──
update public.hive_quotas set enforce_blocking = false
 where hive_id = 'a1000000-0000-4000-8000-00000000c001'::uuid;

do $warnonly$
declare n int; logged int;
begin
  begin
    insert into public.community_posts(hive_id, author_name, content, category)
      values ('a1000000-0000-4000-8000-00000000c001'::uuid, 'TB QB', 'warn', 'general');
    get diagnostics n = row_count;
    raise notice 'RESULT at_cap_warnonly_write=%', case when n>0 then 'allowed' else 'BLOCKED' end;
  exception when others then raise notice 'RESULT at_cap_warnonly_write=BLOCKED sqlstate=%', sqlstate; end;
  select count(*) into logged from public.automation_log
   where job_name = 'hive_quota_community_over'
     and detail like '%' || 'a1000000-0000-4000-8000-00000000c001' || '%';
  raise notice 'RESULT at_cap_warnonly_logged=%', logged;
end $warnonly$;

-- ── NON-VACUITY: below the cap nothing refuses and nothing is logged ──
update public.hive_quotas set max_rows_community = 1000, enforce_blocking = true
 where hive_id = 'a1000000-0000-4000-8000-00000000c001'::uuid;

do $under$
declare n int; logged_before int; logged_after int;
begin
  select count(*) into logged_before from public.automation_log where job_name = 'hive_quota_community_over';
  begin
    insert into public.community_posts(hive_id, author_name, content, category)
      values ('a1000000-0000-4000-8000-00000000c001'::uuid, 'TB QC', 'under', 'general');
    get diagnostics n = row_count;
    raise notice 'RESULT under_cap_write=%', case when n>0 then 'works' else 'BROKEN' end;
  exception when others then raise notice 'RESULT under_cap_write=BROKEN sqlstate=%', sqlstate; end;
  select count(*) into logged_after from public.automation_log where job_name = 'hive_quota_community_over';
  raise notice 'RESULT under_cap_logged_nothing=%',
    case when logged_after = logged_before then 'yes' else 'NO-FALSE-ALARM' end;
end $under$;

rollback;
