-- SL LB1 (2026-10-21): the "parts for your assets" rail showed 24 listings and never said there were more - and the 24
-- were not even the newest. The function capped itself (LIMIT 24) inside, so the page saw no cap to say anything about,
-- and it ordered by `l.id, l.created_at DESC` because DISTINCT ON (l.id) needs l.id first: the rail held the 24
-- listings with the smallest random UUIDs, an order no person can read.
--
-- The JOIN to inventory_items existed only to test "does my hive stock this part number", and a hive holding the same
-- part twice produced the same listing twice - which is the only reason DISTINCT ON was there. EXISTS asks the question
-- directly: one row per listing, no de-duplication, and the order is free to be the one a person means (newest first,
-- id as the tiebreaker).
--
-- The cap moves to the caller as p_limit, so the page can ask for one row past what it shows (24 + 1) and say "more
-- exist" when it comes back - the overflow probe every other LB1 list uses. p_limit is clamped to 1..500 so no caller
-- can turn the rail into an unbounded export.
--
-- A new signature is a DROP + CREATE (never an overload: two candidates for one call is PGRST203, and the endpoint dies).
-- DROP + CREATE also restores Supabase's default EXECUTE for anon - closed again below; the rail needs a signed-in member
-- of the hive and returns nothing to anyone else.

drop function if exists public.get_marketplace_parts_for_my_assets(uuid);

create function public.get_marketplace_parts_for_my_assets(p_hive_id uuid, p_limit integer default 24)
returns table(listing_id uuid, title text, part_number text, category text, price numeric, location text, seller_name text)
language sql
stable
security definer
set search_path = ''
as $function$
  select l.id, l.title, l.part_number, l.category, l.price, l.location, l.seller_name
  from public.marketplace_listings l
  where l.status = 'published'
    and l.section = 'parts'
    and l.hive_id is distinct from p_hive_id            -- never recommend the viewer's own listings
    and l.part_number is not null
    and exists (                                        -- a part this hive stocks (one row per listing, however many it holds)
      select 1 from public.inventory_items i
      where i.hive_id = p_hive_id
        and i.deleted_at is null
        and i.part_number is not null
        and upper(btrim(i.part_number)) = upper(btrim(l.part_number))
    )
    and exists (                                        -- caller must be an active member of p_hive_id
      select 1 from public.hive_members hm
      where hm.hive_id = p_hive_id
        and hm.auth_uid = auth.uid()
        and hm.status = 'active'
    )
  order by l.created_at desc, l.id
  limit least(greatest(coalesce(p_limit, 24), 1), 500);
$function$;

revoke execute on function public.get_marketplace_parts_for_my_assets(uuid, integer) from public, anon;
grant execute on function public.get_marketplace_parts_for_my_assets(uuid, integer) to authenticated, service_role;

notify pgrst, 'reload schema';
