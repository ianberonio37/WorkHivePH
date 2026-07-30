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

update public.projects set meta = coalesce(meta,'{}'::jsonb) || '{"lessons_learned":"original"}'::jsonb
 where id='539e0d9a-9ff7-474b-ab03-9254406ca7dc';

-- a WORKER may not change lessons-learned
select set_config('request.jwt.claims','{"sub":"91e0d1eb-cd96-43ee-af5f-0ff2714b3923","role":"authenticated"}', true);
do $p$
declare n int;
begin
  begin update public.projects set meta = meta || '{"lessons_learned":"worker edit"}'::jsonb
          where id='539e0d9a-9ff7-474b-ab03-9254406ca7dc';
        get diagnostics n=row_count; raise notice 'RESULT worker_edits_lessons=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT worker_edits_lessons=blocked'; end;
end $p$;

-- a SUPERVISOR may — the legitimate write that separates 'supervisor-gated' from 'frozen'
select set_config('request.jwt.claims','{"sub":"bcb5a6e3-fb12-4238-bc1e-ffeb48f60d53","role":"authenticated"}', true);
do $p$
declare n int;
begin
  begin update public.projects set meta = meta || '{"lessons_learned":"sup edit"}'::jsonb
          where id='539e0d9a-9ff7-474b-ab03-9254406ca7dc';
        get diagnostics n=row_count; raise notice 'RESULT sup_edits_lessons=%', case when n>0 then 'allowed' else 'BLOCKED' end;
  exception when others then raise notice 'RESULT sup_edits_lessons=BLOCKED'; end;
end $p$;

rollback;
