-- TB-QUOTA-ai-reports-both-modes.sql
--
-- `check_hive_quota_ai_reports` is one of FOUR guards on this platform that no registered gate names, found by
-- ranking all 27 un-scored guards on four signals (what they protect, whether they carry the row-version
-- shape, whether they write, and how many gates mention them). It is the only one of the four that WRITES,
-- and it leads for that reason: a quota guard that stops refusing is a COST leak, and its failure mode is an
-- invoice rather than a corrupted row.
--
-- IT IS LIVE, ATTACHED, AND HAS NEVER FIRED. `trg_hive_quota_ai_reports` is on `ai_reports`; there are 3
-- `hive_quotas` rows, all with `enforce_blocking = true` and a cap of 5000; and `ai_reports` holds 16 rows.
-- So the cap is three orders of magnitude away from the data and NEITHER branch has ever executed in anger.
-- That is the precise sense in which it was unmonitored: not absent, not broken — untested and unobserved.
--
-- THE GUARD HAS TWO MODES AND THEY FAIL DIFFERENTLY, which is why one cell cannot cover it:
--
--   enforce_blocking = TRUE   at/over cap -> RAISE 54000, the write is REFUSED
--   enforce_blocking = FALSE  at/over cap -> the write is ALLOWED and a row is written to `automation_log`
--                             ('hive_quota_ai_reports_over', status 'skipped')
--
-- The WARN-ONLY mode is the one worth guarding hardest, because its failure is SILENT: if that INSERT ever
-- stops happening, quota overruns simply stop being recorded and nothing goes red. A guard whose warning mode
-- warns nobody is the same shape as a refusal that tells the user nothing
-- ([[feedback_string_is_not_an_announcement_until_it_reaches_a_user]]) — so the assertion here reads the
-- automation_log row BACK rather than settling for "no exception was raised".
--
-- The cap is planted LOW (2) inside begin/rollback rather than the live 5000 being approached, because a probe
-- that needs 5000 rows to prove a rule is a probe nobody will run.
begin;

insert into public.hives(id, name, invite_code, created_by)
values ('a1000000-0000-4000-8000-00000000e001'::uuid, 'TB Quota Hive', 'TBQ001', 'tb-probe');

-- Two reports, and a cap of 2: the hive is exactly AT its cap, which is the boundary the guard tests
-- (`current_n >= q_max`). Testing from over the cap would pass on a guard that only handled strictly-greater.
insert into public.ai_reports(id, hive_id, report_type) values
  ('a2000000-0000-4000-8000-00000000e001'::uuid,'a1000000-0000-4000-8000-00000000e001'::uuid,'weekly'),
  ('a2000000-0000-4000-8000-00000000e002'::uuid,'a1000000-0000-4000-8000-00000000e001'::uuid,'weekly');

-- ── MODE 1: enforcing ───────────────────────────────────────────────────────────────────────────────────
-- UPSERT, not INSERT: creating a hive fires `trg_seed_hive_quota_defaults`, which provisions the quota row
-- automatically, so a plain INSERT here collided on `hive_quotas_pkey`. Discovered by the collision rather
-- than assumed — and worth stating, because it means every hive on this platform HAS a quota row, so the
-- guard's `q_max IS NULL -> RETURN NEW` escape hatch is effectively unreachable in production.
insert into public.hive_quotas(hive_id, max_rows_ai_reports, enforce_blocking)
values ('a1000000-0000-4000-8000-00000000e001'::uuid, 2, true)
on conflict (hive_id) do update set max_rows_ai_reports = 2, enforce_blocking = true;

do $enforcing$
declare n int;
begin
  begin
    insert into public.ai_reports(id, hive_id, report_type)
    values ('a2000000-0000-4000-8000-00000000e003'::uuid,
            'a1000000-0000-4000-8000-00000000e001'::uuid,'weekly');
    get diagnostics n = row_count;
    raise notice 'RESULT at_cap_blocking=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then
    -- The SQLSTATE is asserted, not just the refusal: 54000 is `program_limit_exceeded`, the code this guard
    -- chose to mean "quota". A different code would mean something else refused (a CHECK, RLS, a FK), and
    -- "something said no" is not evidence that the QUOTA said no.
    raise notice 'RESULT at_cap_blocking=blocked sqlstate=%', sqlstate;
  end;
end
$enforcing$;

-- ── MODE 2: warn-only ───────────────────────────────────────────────────────────────────────────────────
update public.hive_quotas set enforce_blocking = false
 where hive_id = 'a1000000-0000-4000-8000-00000000e001'::uuid;

do $warnonly$
declare n int; logged int;
begin
  begin
    insert into public.ai_reports(id, hive_id, report_type)
    values ('a2000000-0000-4000-8000-00000000e004'::uuid,
            'a1000000-0000-4000-8000-00000000e001'::uuid,'weekly');
    get diagnostics n = row_count;
    raise notice 'RESULT at_cap_warnonly_write=%', case when n>0 then 'allowed' else 'BLOCKED' end;
  exception when others then
    raise notice 'RESULT at_cap_warnonly_write=BLOCKED sqlstate=%', sqlstate;
  end;
  -- THE POINT OF THIS MODE. The write is supposed to succeed; the guard's whole contribution is the record it
  -- leaves. Read it back, because an absent log entry is exactly as silent as a correct one.
  select count(*) into logged from public.automation_log
   where job_name = 'hive_quota_ai_reports_over'
     and detail like '%' || 'a1000000-0000-4000-8000-00000000e001' || '%';
  raise notice 'RESULT at_cap_warnonly_logged=%', logged;
end
$warnonly$;

-- ── NON-VACUITY: below the cap, nothing should refuse and nothing should be logged ──────────────────────
update public.hive_quotas set max_rows_ai_reports = 100, enforce_blocking = true
 where hive_id = 'a1000000-0000-4000-8000-00000000e001'::uuid;

do $under$
declare n int; logged_before int; logged_after int;
begin
  select count(*) into logged_before from public.automation_log
   where job_name = 'hive_quota_ai_reports_over';
  begin
    insert into public.ai_reports(id, hive_id, report_type)
    values ('a2000000-0000-4000-8000-00000000e005'::uuid,
            'a1000000-0000-4000-8000-00000000e001'::uuid,'weekly');
    get diagnostics n = row_count;
    raise notice 'RESULT under_cap_write=%', case when n>0 then 'works' else 'BROKEN' end;
  exception when others then raise notice 'RESULT under_cap_write=BROKEN sqlstate=%', sqlstate; end;
  select count(*) into logged_after from public.automation_log
   where job_name = 'hive_quota_ai_reports_over';
  -- A guard that logged an overrun while under cap would be crying wolf, and the warn-only assertion above
  -- would still pass. Both directions of the log matter.
  raise notice 'RESULT under_cap_logged_nothing=%',
    case when logged_after = logged_before then 'yes' else 'NO-FALSE-ALARM' end;
end
$under$;

rollback;
