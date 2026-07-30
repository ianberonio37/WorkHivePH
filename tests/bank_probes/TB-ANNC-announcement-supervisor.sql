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

-- a WORKER cannot post an announcement in their hive
select set_config('request.jwt.claims','{"sub":"91e0d1eb-cd96-43ee-af5f-0ff2714b3923","role":"authenticated"}', true);
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
select set_config('request.jwt.claims','{"sub":"bcb5a6e3-fb12-4238-bc1e-ffeb48f60d53","role":"authenticated"}', true);
do $p$
declare n int;
begin
  begin
    insert into public.community_posts(hive_id, author_name, content, category)
      values ('084c113b-99c0-45c6-a8e8-b4b8349da46d','Leandro Marquez','TB sup announcement','announcement');
    get diagnostics n=row_count; raise notice 'RESULT sup_announces=%', case when n>0 then 'allowed' else 'BLOCKED' end;
  exception when others then raise notice 'RESULT sup_announces=BLOCKED sqlstate=%', sqlstate; end;
end $p$;

rollback;
