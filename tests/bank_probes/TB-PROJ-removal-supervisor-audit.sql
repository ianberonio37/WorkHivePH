-- TB-PROJ-removal-supervisor-audit.sql
--
-- `guard_and_audit_project_removal` (projects) does two jobs on a delete / soft-delete / restore: it REFUSES
-- the removal unless the caller is a supervisor of the project's hive, and it WRITES a hive_audit_log row
-- describing what was lost (counting the scope items, change orders, logs and links before a hard delete's
-- cascade erases them). Found unscored 2026-07-31 (ARC 13 / F).
--
-- Guard-isolated: the project is planted as postgres (auth.uid() null -> the backend branch, treated as
-- supervisor), then the soft-delete (deleted_at NULL -> now()) is attempted with each identity's jwt claims set.
-- A deleted_at-only change does not touch lessons_learned, so guard_lessons_learned_is_supervisor returns
-- immediately; this guard is the sole gate. Real Baguio worker + supervisor so the role lookup resolves.
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
  if exists (select 1 from _tb where supervisor is null or worker is null) then
    raise exception 'probe fixture missing: %', (select row_to_json(_tb)::text from _tb);
  end if;
end $tb$;


insert into public.projects(id, hive_id, worker_name, project_code, name, project_type, deleted_at)
values ('a6000000-0000-4000-8000-00000000a401'::uuid,'084c113b-99c0-45c6-a8e8-b4b8349da46d','TB P',
        'TB-PROJ-1','TB Project','capex', null);

-- a WORKER cannot remove a project
select set_config('request.jwt.claims',json_build_object('sub', (select worker from _tb), 'role', 'authenticated')::text, true);
do $p$
declare n int;
begin
  begin update public.projects set deleted_at = now() where id='a6000000-0000-4000-8000-00000000a401';
        get diagnostics n=row_count; raise notice 'RESULT worker_removes=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT worker_removes=blocked'; end;
end $p$;

-- a SUPERVISOR can, and the removal writes an audit row describing it
select set_config('request.jwt.claims',json_build_object('sub', (select supervisor from _tb), 'role', 'authenticated')::text, true);
do $p$
declare n int; v_audit int;
begin
  begin update public.projects set deleted_at = now() where id='a6000000-0000-4000-8000-00000000a401';
        get diagnostics n=row_count; raise notice 'RESULT sup_removes=%', case when n>0 then 'allowed' else 'BLOCKED' end;
  exception when others then raise notice 'RESULT sup_removes=BLOCKED sqlstate=%', sqlstate; end;
  select count(*) into v_audit from public.hive_audit_log
   where action='delete_project' and target_id='a6000000-0000-4000-8000-00000000a401';
  raise notice 'RESULT audit_written=%', v_audit;
end $p$;

rollback;
