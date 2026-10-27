-- TB-RATE-logbook-per-user.sql
--
-- `check_logbook_rate_limit` caps logbook writes per hive/day AND per user/day. This cell scores the PER-USER
-- rule — the real abuse stop — in isolation from the sibling quota guard (`check_hive_quota_logbook`), which
-- reads the SAME `max_rows_logbook`. Both raise 54000, so a naive fixture cannot tell which refused.
--
-- ISOLATION (roadmap S14.4): set the hive cap high so neither hive-cap path (quota OR rate-limit) can trip, and
-- the per-user cap to exactly (the caller's current same-day count) + 1. Then the caller's FIRST insert reaches
-- the cap and is allowed, and the SECOND trips the per-user rate limit alone. The cap is computed from the live
-- count so the cell controls its own state rather than assuming an empty day
-- ([[feedback_a_test_asserting_a_state_it_does_not_control]]).
begin;

-- ★WHO ACTS IS RESOLVED BY WHAT THEY ARE, NOT BY A LITERAL ID (2026-10-28). This probe named its worker, supervisor,
-- outsider and project by literal uuids; the clean reseed (2026-10-27) recreated every account and project, so each id
-- named nobody - the supervisor's legitimate writes read BLOCKED, the change orders broke their foreign key, and the
-- same literal was flagged on push as a leaked "secret". A missing one stops the probe loudly: a null sub would read
-- as the backend's allow-branch and the probe would test nothing.
create temp table _tb as select
  (select id from auth.users where email = 'bryangarcia@auth.workhiveph.com') as worker,
  (select m.auth_uid from public.hive_members m where m.hive_id = '084c113b-99c0-45c6-a8e8-b4b8349da46d' and m.role = 'supervisor'
      and m.status = 'active' and m.auth_uid is not null
      and m.auth_uid not in (select auth_uid from public.marketplace_platform_admins where auth_uid is not null)
    order by m.worker_name limit 1) as supervisor,
  (select m.auth_uid from public.hive_members m where m.hive_id = 'b4f7fe63-92e1-4f8d-b96e-625c3f85ba61' and m.role = 'worker'
      and m.status = 'active' and m.auth_uid is not null
      and m.auth_uid not in (select auth_uid from public.hive_members where hive_id = '084c113b-99c0-45c6-a8e8-b4b8349da46d' and auth_uid is not null)
    order by m.worker_name limit 1) as outsider,
  (select p.id from public.projects p where p.hive_id = '084c113b-99c0-45c6-a8e8-b4b8349da46d' and p.deleted_at is null
    order by p.created_at, p.id limit 1) as project;
do $tb$ begin
  if exists (select 1 from _tb where worker is null) then
    raise exception 'probe fixture missing: %', (select row_to_json(_tb)::text from _tb);
  end if;
end $tb$;


-- Setup as postgres: read the caller's live same-day count, then pin the caps around it.
do $setup$
declare v_now int;
  day_start timestamptz := (date_trunc('day', now() AT TIME ZONE 'Asia/Manila')) AT TIME ZONE 'Asia/Manila';
begin
  select count(*) into v_now from public.logbook
   where auth_uid=(select worker from _tb) and created_at >= day_start;
  insert into public.hive_quotas(hive_id, max_rows_logbook, max_rows_logbook_per_user)
    values ('084c113b-99c0-45c6-a8e8-b4b8349da46d', 1000000, v_now + 1)
    on conflict (hive_id) do update set max_rows_logbook = 1000000, max_rows_logbook_per_user = v_now + 1;
end $setup$;

-- Act as Bryan (a Baguio worker). RLS bypassed (superuser) so the trigger, not a grant, is what refuses.
select set_config('request.jwt.claims',json_build_object('sub', (select worker from _tb), 'role', 'authenticated')::text, true);
do $probe$
declare n int;
begin
  -- FIRST write reaches the per-user cap and is allowed.
  begin
    insert into public.logbook(worker_name, date, hive_id)
      values ('Bryan Garcia', current_date, '084c113b-99c0-45c6-a8e8-b4b8349da46d');
    get diagnostics n=row_count; raise notice 'RESULT rate_first=%', case when n>0 then 'allowed' else 'BLOCKED' end;
  exception when others then raise notice 'RESULT rate_first=BLOCKED sqlstate=%', sqlstate; end;

  -- SECOND write trips the per-user rate limit (54000). The hive cap (1,000,000) cannot be what refused.
  begin
    insert into public.logbook(worker_name, date, hive_id)
      values ('Bryan Garcia', current_date, '084c113b-99c0-45c6-a8e8-b4b8349da46d');
    get diagnostics n=row_count; raise notice 'RESULT rate_second=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT rate_second=blocked sqlstate=%', sqlstate; end;
end $probe$;

rollback;
