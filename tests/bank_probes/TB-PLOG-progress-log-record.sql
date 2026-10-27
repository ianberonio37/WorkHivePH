-- TB-PLOG-progress-log-record.sql
--
-- Two guards on project_progress_logs, both found unscored 2026-07-31 (ARC 13 / F):
--
--   bind_progress_log_submitter (INSERT)  binds identity SERVER-SIDE: NEW.auth_uid := auth.uid() and
--     NEW.reported_by := the caller's own worker_name (from hive_members), and refuses a non-member. The name
--     is the caller's, not the caller's CHOICE — [[feedback_free_text_identity_is_a_claim]] /
--     [[feedback_authuid_attribution_on_every_write]].
--   guard_progress_log_is_a_record (UPDATE)  a filed report is immutable (project/hive/log_date/reported_by/
--     pct_complete/hours_worked/notes/blockers), acknowledging is a SUPERVISOR act, and NOT of your OWN report
--     (segregation of duties — reviewing your own work is a signature, not a review).
--
-- Guard-isolated: fixtures planted as postgres (auth.uid() null -> the backend branch both guards share), then
-- each actor acts with its jwt claims set, RLS bypassed, so the trigger is what refuses. Real Baguio identities
-- (a worker, a supervisor, a non-member) so the membership/role lookups resolve against live data.
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
  if exists (select 1 from _tb where outsider is null or project is null or supervisor is null or worker is null) then
    raise exception 'probe fixture missing: %', (select row_to_json(_tb)::text from _tb);
  end if;
end $tb$;


-- two filed reports: L1 by the worker, L2 by the ACTING supervisor - by name, because the guard matches the
-- acknowledger's worker_name against reported_by (a literal 'Leandro Marquez' stopped being 'own' when the
-- acting supervisor became a resolved one)
insert into public.project_progress_logs(id, project_id, hive_id, reported_by, log_date, pct_complete,
       hours_worked, notes, blockers, acknowledged_at)
  values ('d0000000-0000-4000-8000-0000000000e1',(select project from _tb),
          '084c113b-99c0-45c6-a8e8-b4b8349da46d','Bryan Garcia','2026-07-20', 50, 8, 'original notes','none', null),
         ('d0000000-0000-4000-8000-0000000000e2',(select project from _tb),
          '084c113b-99c0-45c6-a8e8-b4b8349da46d',(select m.worker_name from public.hive_members m where m.auth_uid = (select supervisor from _tb)
             and m.hive_id = '084c113b-99c0-45c6-a8e8-b4b8349da46d' and m.status = 'active' limit 1),
          '2026-07-20', 60, 9, 'sup notes','none', null);

-- ── bind_progress_log_submitter: identity is BOUND, not claimed ──
select set_config('request.jwt.claims',json_build_object('sub', (select worker from _tb), 'role', 'authenticated')::text, true);
do $probe$
declare n int; v_rep text; v_auth uuid;
begin
  -- Bryan files a report but CLAIMS reported_by = the supervisor's name; the guard overwrites it to his own.
  begin
    insert into public.project_progress_logs(id, project_id, hive_id, reported_by, log_date, pct_complete, hours_worked)
      values ('d0000000-0000-4000-8000-0000000000e3',(select project from _tb),
              '084c113b-99c0-45c6-a8e8-b4b8349da46d','Leandro Marquez','2026-07-21', 10, 2);
    get diagnostics n=row_count;
    select reported_by, auth_uid into v_rep, v_auth from public.project_progress_logs where id='d0000000-0000-4000-8000-0000000000e3';
    raise notice 'RESULT bind_reported_by=%', case when v_rep='Bryan Garcia' then 'self' else coalesce(v_rep,'null') end;
    raise notice 'RESULT bind_auth=%', case when v_auth=(select worker from _tb) then 'self' else coalesce(v_auth::text,'null') end;
  exception when others then raise notice 'RESULT bind_reported_by=INSERT_FAILED sqlstate=%', sqlstate; end;
end $probe$;

-- a non-member cannot file at all
select set_config('request.jwt.claims',json_build_object('sub', (select outsider from _tb), 'role', 'authenticated')::text, true);
do $probe$
declare n int;
begin
  begin
    insert into public.project_progress_logs(id, project_id, hive_id, reported_by, log_date, pct_complete, hours_worked)
      values ('d0000000-0000-4000-8000-0000000000e4',(select project from _tb),
              '084c113b-99c0-45c6-a8e8-b4b8349da46d','Pablo Aguilar','2026-07-21', 10, 2);
    get diagnostics n=row_count; raise notice 'RESULT nonmember_files=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT nonmember_files=blocked'; end;
end $probe$;

-- ── guard_progress_log_is_a_record: a filed report is immutable ──
select set_config('request.jwt.claims',json_build_object('sub', (select worker from _tb), 'role', 'authenticated')::text, true);
do $probe$
declare n int;
begin
  begin update public.project_progress_logs set pct_complete=99 where id='d0000000-0000-4000-8000-0000000000e1';
        get diagnostics n=row_count; raise notice 'RESULT edit_pct=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT edit_pct=blocked'; end;
  begin update public.project_progress_logs set hours_worked=99 where id='d0000000-0000-4000-8000-0000000000e1';
        get diagnostics n=row_count; raise notice 'RESULT edit_hours=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT edit_hours=blocked'; end;
  begin update public.project_progress_logs set blockers='changed' where id='d0000000-0000-4000-8000-0000000000e1';
        get diagnostics n=row_count; raise notice 'RESULT edit_blockers=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT edit_blockers=blocked'; end;
  begin update public.project_progress_logs set notes='changed' where id='d0000000-0000-4000-8000-0000000000e1';
        get diagnostics n=row_count; raise notice 'RESULT edit_notes=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT edit_notes=blocked'; end;
  -- a WORKER cannot acknowledge (a report they did NOT write, so the supervisor rule is what refuses)
  begin update public.project_progress_logs set acknowledged_at=now() where id='d0000000-0000-4000-8000-0000000000e2';
        get diagnostics n=row_count; raise notice 'RESULT worker_acks_other=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT worker_acks_other=blocked'; end;
end $probe$;

-- supervisor acknowledges SOMEONE ELSE's report (allowed) and their OWN (refused)
select set_config('request.jwt.claims',json_build_object('sub', (select supervisor from _tb), 'role', 'authenticated')::text, true);
do $probe$
declare n int;
begin
  begin update public.project_progress_logs set acknowledged_at=now() where id='d0000000-0000-4000-8000-0000000000e1';
        get diagnostics n=row_count; raise notice 'RESULT sup_acks_other=%', case when n>0 then 'allowed' else 'BLOCKED' end;
  exception when others then raise notice 'RESULT sup_acks_other=BLOCKED sqlstate=%', sqlstate; end;
  begin update public.project_progress_logs set acknowledged_at=now() where id='d0000000-0000-4000-8000-0000000000e2';
        get diagnostics n=row_count; raise notice 'RESULT sup_acks_own=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT sup_acks_own=blocked'; end;
end $probe$;

rollback;
