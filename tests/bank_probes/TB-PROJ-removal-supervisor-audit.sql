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

insert into public.projects(id, hive_id, worker_name, project_code, name, project_type, deleted_at)
values ('a6000000-0000-4000-8000-00000000a401'::uuid,'084c113b-99c0-45c6-a8e8-b4b8349da46d','TB P',
        'TB-PROJ-1','TB Project','capex', null);

-- a WORKER cannot remove a project
select set_config('request.jwt.claims','{"sub":"91e0d1eb-cd96-43ee-af5f-0ff2714b3923","role":"authenticated"}', true);
do $p$
declare n int;
begin
  begin update public.projects set deleted_at = now() where id='a6000000-0000-4000-8000-00000000a401';
        get diagnostics n=row_count; raise notice 'RESULT worker_removes=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT worker_removes=blocked'; end;
end $p$;

-- a SUPERVISOR can, and the removal writes an audit row describing it
select set_config('request.jwt.claims','{"sub":"bcb5a6e3-fb12-4238-bc1e-ffeb48f60d53","role":"authenticated"}', true);
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
