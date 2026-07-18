-- ============================================================================
-- "Parts for YOUR assets" discovery (Marketplace PDDA, U-axis discovery heavyweight)
-- ----------------------------------------------------------------------------
-- The marketplace analog of Community "my people": surface published listings whose
-- part_number matches a part the viewer's plant actually stocks/uses (inventory_items).
-- This is the discovery unlock for the parts-flow fabric — a buyer sees the exact legacy
-- parts THEIR machines need, sourced from other plants.
--
-- SECURITY DEFINER because it joins PUBLIC listings against the viewer's HIVE-PRIVATE
-- inventory (RLS would otherwise block a client read of inventory across the join). SAFE:
-- it (1) requires the caller to be an ACTIVE MEMBER of p_hive_id (no reading another hive's
-- part usage), and (2) returns only PUBLISHED listings + the viewer's OWN matched part_number
-- (never any other hive's private inventory rows).
-- ============================================================================

CREATE OR REPLACE FUNCTION public.get_marketplace_parts_for_my_assets(p_hive_id uuid)
RETURNS TABLE (
  listing_id  uuid,
  title       text,
  part_number text,
  category    text,
  price       numeric,
  location    text,
  seller_name text
)
LANGUAGE sql
SECURITY DEFINER
SET search_path TO ''
STABLE
AS $$
  SELECT DISTINCT ON (l.id)
    l.id, l.title, l.part_number, l.category, l.price, l.location, l.seller_name
  FROM public.marketplace_listings l
  JOIN public.inventory_items i
    ON  i.hive_id = p_hive_id
    AND i.part_number IS NOT NULL
    AND l.part_number IS NOT NULL
    AND upper(btrim(i.part_number)) = upper(btrim(l.part_number))
  WHERE l.status = 'published'
    AND l.section = 'parts'
    AND l.hive_id IS DISTINCT FROM p_hive_id            -- never recommend the viewer's own listings
    AND EXISTS (                                        -- caller must be an active member of p_hive_id
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = p_hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.status = 'active'
    )
  ORDER BY l.id, l.created_at DESC
  LIMIT 24;
$$;

COMMENT ON FUNCTION public.get_marketplace_parts_for_my_assets(uuid) IS
  'Discovery: published parts listings whose part_number matches the viewer hive''s inventory (parts their machines use). DEFINER + active-membership-guarded so it never leaks another hive''s part usage. (Marketplace PDDA U-axis "Parts for YOUR assets")';

GRANT EXECUTE ON FUNCTION public.get_marketplace_parts_for_my_assets(uuid) TO authenticated;
