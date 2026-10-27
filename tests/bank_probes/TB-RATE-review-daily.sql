-- TB-RATE-review-daily.sql
--
-- `enforce_marketplace_review_daily_cap` caps reviews at 10/day PER reviewer_name (a null auth.uid() is the
-- vetted backend path and bypasses). Found unscored 2026-07-31 (ARC 13 / F). Ten LISTING reviews (request_id
-- NULL, so guard_service_review returns immediately and does not interfere) are planted for one reviewer today;
-- the 11th by that reviewer trips.
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
  if exists (select 1 from _tb where outsider is null) then
    raise exception 'probe fixture missing: %', (select row_to_json(_tb)::text from _tb);
  end if;
end $tb$;


insert into public.hives(id, name, invite_code, created_by)
values ('a1000000-0000-4000-8000-00000000a301'::uuid, 'TB Review Cap Hive', 'TBRV01', 'tb-probe');
insert into public.marketplace_listings(id, hive_id, seller_name, section, title, status)
values ('a5000000-0000-4000-8000-00000000a301'::uuid,'a1000000-0000-4000-8000-00000000a301'::uuid,
        'TB Seller','parts','TB Item','draft');

-- 10 reviews today by one reviewer (planted as postgres -> the cap bypasses the INSERTs, but the rows exist).
insert into public.marketplace_reviews(id, listing_id, reviewer_name, rating, created_at)
select gen_random_uuid(), 'a5000000-0000-4000-8000-00000000a301'::uuid, 'TB Rev', 5, now()
from generate_series(1,10) g;

-- Act as a real user so the cap (which bypasses null auth.uid()) applies.
select set_config('request.jwt.claims',json_build_object('sub', (select outsider from _tb), 'role', 'authenticated')::text, true);
do $probe$
declare n int;
begin
  -- the 11th by the same reviewer_name trips the daily cap
  begin
    insert into public.marketplace_reviews(listing_id, reviewer_name, rating)
      values ('a5000000-0000-4000-8000-00000000a301'::uuid,'TB Rev',5);
    get diagnostics n = row_count; raise notice 'RESULT over_cap=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT over_cap=blocked'; end;

  -- a DIFFERENT reviewer_name is unaffected (per reviewer, not a freeze)
  begin
    insert into public.marketplace_reviews(listing_id, reviewer_name, rating)
      values ('a5000000-0000-4000-8000-00000000a301'::uuid,'TB Rev2',5);
    get diagnostics n = row_count; raise notice 'RESULT other_reviewer=%', case when n>0 then 'allowed' else 'BLOCKED' end;
  exception when others then raise notice 'RESULT other_reviewer=BLOCKED'; end;
end $probe$;

rollback;
