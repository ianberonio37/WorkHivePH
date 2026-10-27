-- TB-ANNC-announcement-supervisor.sql
--
-- `guard_community_announcement` (community_posts): a post with category='announcement' may only be created by
-- a SUPERVISOR of its hive. An ordinary post (general/safety/technical/marketplace) is anyone's to write, so
-- the guard only fires on the announcement category.
--
-- Found unscored 2026-07-31 (ARC 13 / F). Guard-isolated by identity: a single insert never trips the
-- rate-limit or daily-quota triggers on this table (count 0), so what refuses a worker's announcement is this
-- guard. Real Baguio identities so user_supervisor_hive_ids() resolves.
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


-- a WORKER cannot post an announcement in their hive
select set_config('request.jwt.claims',json_build_object('sub', (select worker from _tb), 'role', 'authenticated')::text, true);
do $p$
declare n int;
begin
  begin
    insert into public.community_posts(hive_id, author_name, content, category)
      values ('084c113b-99c0-45c6-a8e8-b4b8349da46d','Bryan Garcia','TB announcement','announcement');
    get diagnostics n=row_count; raise notice 'RESULT worker_announces=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT worker_announces=blocked'; end;

  -- but an ordinary post is fine
  begin
    insert into public.community_posts(hive_id, author_name, content, category)
      values ('084c113b-99c0-45c6-a8e8-b4b8349da46d','Bryan Garcia','TB general post','general');
    get diagnostics n=row_count; raise notice 'RESULT worker_ordinary_post=%', case when n>0 then 'allowed' else 'BLOCKED' end;
  exception when others then raise notice 'RESULT worker_ordinary_post=BLOCKED'; end;
end $p$;

-- a SUPERVISOR of the hive can post the announcement — the legitimate write
select set_config('request.jwt.claims',json_build_object('sub', (select supervisor from _tb), 'role', 'authenticated')::text, true);
do $p$
declare n int;
begin
  begin
    insert into public.community_posts(hive_id, author_name, content, category)
      values ('084c113b-99c0-45c6-a8e8-b4b8349da46d',
              (select m.worker_name from public.hive_members m where m.auth_uid = (select supervisor from _tb)
                 and m.hive_id = '084c113b-99c0-45c6-a8e8-b4b8349da46d' and m.status = 'active' limit 1),
              'TB sup announcement','announcement');
    get diagnostics n=row_count; raise notice 'RESULT sup_announces=%', case when n>0 then 'allowed' else 'BLOCKED' end;
  exception when others then raise notice 'RESULT sup_announces=BLOCKED sqlstate=%', sqlstate; end;
end $p$;

rollback;
