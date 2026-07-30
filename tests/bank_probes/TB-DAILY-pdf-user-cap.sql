-- TB-DAILY-pdf-user-cap.sql
--
-- `check_daily_row_cap` is the SHARED per-hive/per-user daily row cap, attached to ~20 tables via TG_ARGV
-- (cap, ts_col, ident_col, user_cap). Found unscored 2026-07-31 (ARC 13 / F). Scored here on pdf_jobs, whose
-- caps are the lowest (20/hive, 10/user, ident_col=uploaded_by) and whose only OTHER trigger is the size cap
-- cap_pdf_job_size (already scored) — not a count guard, so it cannot conflate.
--
-- The PER-USER branch is isolated cleanly: setting hive_id NULL skips the per-hive branch entirely, so the only
-- cap that can trip is the per-user one. Ten jobs by one uploader are planted today; the 11th trips (54000,
-- HINT daily_user_pdf_jobs). chunks_json is left null so the size cap sees zero chunks and stays out of the way.
begin;

insert into public.pdf_jobs(id, source_name, target_table, uploaded_by, status, created_at)
select gen_random_uuid(), 'TB '||g, 'pm_knowledge', 'TB U', 'pending', now()
from generate_series(1,10) g;

do $probe$
declare n int;
begin
  -- the 11th by the same uploader trips the per-user daily cap
  begin
    insert into public.pdf_jobs(source_name, target_table, uploaded_by, status)
      values ('TB 11','pm_knowledge','TB U','pending');
    get diagnostics n = row_count; raise notice 'RESULT over_user_cap=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT over_user_cap=blocked sqlstate=%', sqlstate; end;

  -- a DIFFERENT uploader is unaffected (per user, not a freeze)
  begin
    insert into public.pdf_jobs(source_name, target_table, uploaded_by, status)
      values ('TB other','pm_knowledge','TB U2','pending');
    get diagnostics n = row_count; raise notice 'RESULT other_uploader=%', case when n>0 then 'allowed' else 'BLOCKED' end;
  exception when others then raise notice 'RESULT other_uploader=BLOCKED'; end;
end $probe$;

rollback;
