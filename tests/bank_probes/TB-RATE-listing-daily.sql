-- TB-RATE-listing-daily.sql
--
-- `check_listing_rate` is a per-hive (or per-solo-seller) anti-spam: at most 20 listings created in the last 24
-- hours. The 21st is refused. Found unscored 2026-07-31 (ARC 13 / F). Recent-window shape like the community
-- limits, just a higher threshold, so 20 are planted inside the window and the 21st trips.
--
-- Isolation: a fresh hive has zero prior listings; the only other trigger on marketplace_listings that could
-- refuse an INSERT is guard_marketplace_listing_status (a birth check), satisfied by born-'draft'. The positive
-- inserts into a SECOND fresh hive (count 0), so the limit is per hive, not a freeze.
begin;

insert into public.hives(id, name, invite_code, created_by) values
  ('a1000000-0000-4000-8000-00000000a201'::uuid, 'TB Listing Rate Hive', 'TBLR01', 'tb-probe'),
  ('a1000000-0000-4000-8000-00000000a202'::uuid, 'TB Listing Rate Hive 2', 'TBLR02', 'tb-probe');

-- 20 listings today for hive 1 -> exactly at the cap.
insert into public.marketplace_listings(id, hive_id, seller_name, section, title, status, created_at)
select gen_random_uuid(), 'a1000000-0000-4000-8000-00000000a201'::uuid, 'TB L', 'parts', 't'||g, 'draft', now()
from generate_series(1,20) g;

do $probe$
declare n int;
begin
  -- the 21st in hive 1 trips the daily limit
  begin
    insert into public.marketplace_listings(hive_id, seller_name, section, title, status)
      values ('a1000000-0000-4000-8000-00000000a201'::uuid,'TB L','parts','t21','draft');
    get diagnostics n = row_count; raise notice 'RESULT twenty_first=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT twenty_first=blocked'; end;

  -- a listing in a DIFFERENT hive is unaffected — the limit is per hive
  begin
    insert into public.marketplace_listings(hive_id, seller_name, section, title, status)
      values ('a1000000-0000-4000-8000-00000000a202'::uuid,'TB L2','parts','other','draft');
    get diagnostics n = row_count; raise notice 'RESULT other_hive=%', case when n>0 then 'allowed' else 'BLOCKED' end;
  exception when others then raise notice 'RESULT other_hive=BLOCKED'; end;
end $probe$;

rollback;
