-- ============================================================================
-- Grounded marketplace price comparables (Marketplace PDDA, AI-axis, WAT split)
-- ----------------------------------------------------------------------------
-- Price guidance must be GROUNDED in real comparable listings, NEVER fabricated by an
-- LLM. This RPC is the deterministic half: CODE computes the comp band (min / median /
-- max / n) over real published + sold parts listings. Any LLM phrasing layered on top
-- only narrates these numbers; if n < 3 the caller shows "not enough comparables" and
-- NO number (never invents a price). SECURITY DEFINER + granted to anon/authenticated
-- because comps are derived from PUBLIC listings (cross-hive browsing), same posture as
-- get_marketplace_trust_badges.
-- ============================================================================

CREATE OR REPLACE FUNCTION public.get_marketplace_price_comps(
  p_category    text,
  p_condition   text DEFAULT NULL,
  p_part_number text DEFAULT NULL
)
RETURNS TABLE (n integer, min_price numeric, median_price numeric, max_price numeric)
LANGUAGE sql
SECURITY DEFINER
SET search_path TO ''
STABLE
AS $$
  WITH comps AS (
    SELECT l.price
    FROM public.marketplace_listings l
    WHERE l.section = 'parts'
      AND l.status IN ('published', 'sold')
      AND l.price IS NOT NULL
      AND l.price > 0
      AND (p_part_number IS NOT NULL AND l.part_number = p_part_number   -- exact part# match preferred
           OR p_part_number IS NULL AND (p_category IS NULL OR l.category = p_category))
      AND (p_condition IS NULL OR l.condition = p_condition)
  )
  SELECT
    count(*)::int                                              AS n,
    min(price)                                                 AS min_price,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY price)         AS median_price,
    max(price)                                                 AS max_price
  FROM comps;
$$;

COMMENT ON FUNCTION public.get_marketplace_price_comps(text, text, text) IS
  'Grounded price comparables for parts listings: CODE computes min/median/max/n over real published+sold listings (exact part_number match preferred, else category). Caller shows nothing when n<3 (never fabricates). WAT split: LLM may only narrate these numbers. (Marketplace PDDA AI-axis)';

GRANT EXECUTE ON FUNCTION public.get_marketplace_price_comps(text, text, text) TO anon, authenticated;
