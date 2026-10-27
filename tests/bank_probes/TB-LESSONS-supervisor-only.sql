-- TB-LESSONS-supervisor-only.sql
--
-- `guard_lessons_learned_is_supervisor` (projects): the lessons-learned text appears on the SIGNED project
-- report, so only a supervisor of the hive may change it. An ordinary edit that does not touch
-- meta->>'lessons_learned' is none of this guard's business and passes straight through.
--
-- Found unscored 2026-07-31 (ARC 13 / F). Guard-isolated: the field is planted as postgres (backend bypass),
-- then a worker and a supervisor each attempt to change it with their jwt claims set (RLS bypassed), so the
-- trigger is what refuses. Real Baguio identities so the supervisor-role lookup resolves.
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
  if exists (select 1 from _tb where project is null or supervisor is null or worker is null) then
    raise exception 'probe fixture missing: %', (select row_to_json(_tb)::text from _tb);
  end if;
end $tb$;


update public.projects set meta = coalesce(meta,'{}'::jsonb) || '{"lessons_learned":"original"}'::jsonb
 where id=(select project from _tb);

-- a WORKER may not change lessons-learned
select set_config('request.jwt.claims',json_build_object('sub', (select worker from _tb), 'role', 'authenticated')::text, true);
do $p$
declare n int;
begin
  begin update public.projects set meta = meta || '{"lessons_learned":"worker edit"}'::jsonb
          where id=(select project from _tb);
        get diagnostics n=row_count; raise notice 'RESULT worker_edits_lessons=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT worker_edits_lessons=blocked'; end;
end $p$;

-- a SUPERVISOR may — the legitimate write that separates 'supervisor-gated' from 'frozen'
select set_config('request.jwt.claims',json_build_object('sub', (select supervisor from _tb), 'role', 'authenticated')::text, true);
do $p$
declare n int;
begin
  begin update public.projects set meta = meta || '{"lessons_learned":"sup edit"}'::jsonb
          where id=(select project from _tb);
        get diagnostics n=row_count; raise notice 'RESULT sup_edits_lessons=%', case when n>0 then 'allowed' else 'BLOCKED' end;
  exception when others then raise notice 'RESULT sup_edits_lessons=BLOCKED'; end;
end $p$;

rollback;
