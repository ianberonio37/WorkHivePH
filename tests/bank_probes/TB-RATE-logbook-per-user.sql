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

-- Setup as postgres: read the caller's live same-day count, then pin the caps around it.
do $setup$
declare v_now int;
  day_start timestamptz := (date_trunc('day', now() AT TIME ZONE 'Asia/Manila')) AT TIME ZONE 'Asia/Manila';
begin
  select count(*) into v_now from public.logbook
   where auth_uid='91e0d1eb-cd96-43ee-af5f-0ff2714b3923' and created_at >= day_start;
  insert into public.hive_quotas(hive_id, max_rows_logbook, max_rows_logbook_per_user)
    values ('084c113b-99c0-45c6-a8e8-b4b8349da46d', 1000000, v_now + 1)
    on conflict (hive_id) do update set max_rows_logbook = 1000000, max_rows_logbook_per_user = v_now + 1;
end $setup$;

-- Act as Bryan (a Baguio worker). RLS bypassed (superuser) so the trigger, not a grant, is what refuses.
select set_config('request.jwt.claims','{"sub":"91e0d1eb-cd96-43ee-af5f-0ff2714b3923","role":"authenticated"}', true);
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
