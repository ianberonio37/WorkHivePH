-- TB-RATE-review-daily.sql
--
-- `enforce_marketplace_review_daily_cap` caps reviews at 10/day PER reviewer_name (a null auth.uid() is the
-- vetted backend path and bypasses). Found unscored 2026-07-31 (ARC 13 / F). Ten LISTING reviews (request_id
-- NULL, so guard_service_review returns immediately and does not interfere) are planted for one reviewer today;
-- the 11th by that reviewer trips.
begin;

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
select set_config('request.jwt.claims','{"sub":"e2f921f2-024a-4fc3-8ea6-68b906d46040","role":"authenticated"}', true);
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
