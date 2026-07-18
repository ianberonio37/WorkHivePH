-- ============================================================================
-- Saved-search "new matching listing" alerts (Marketplace PDDA, U-axis discovery)
-- ----------------------------------------------------------------------------
-- The killer feature for legacy-part hunters: a buyer saves a search ("obsolete PLC
-- module X") and gets told when a NEW listing matches it. This RPC is the matcher:
-- for each of the CALLER's own active saved searches, count published listings that
-- match (section + category + price band + query over title/description/part_number),
-- and how many are NEW since the search was last seen (last_sent_at). The nav badge /
-- Saved-Searches modal narrate these counts (extends the nav-hub unread-badge pattern).
--
-- SECURITY DEFINER + SELF-SCOPED by auth_worker_names() (no p_worker_name param → a
-- caller can only ever see their OWN saved searches, never probe someone else's).
-- ============================================================================

CREATE OR REPLACE FUNCTION public.get_saved_search_matches()
RETURNS TABLE (
  search_id   uuid,
  search_name text,
  section     text,
  new_count   integer,
  total_count integer
)
LANGUAGE sql
SECURITY DEFINER
SET search_path TO ''
STABLE
AS $$
  SELECT
    s.id,
    s.search_name,
    s.section,
    count(l.id) FILTER (WHERE s.last_sent_at IS NULL OR l.created_at > s.last_sent_at)::int AS new_count,
    count(l.id)::int                                                                        AS total_count
  FROM public.marketplace_saved_searches s
  LEFT JOIN public.marketplace_listings l
    ON  l.status = 'published'
    AND (s.section  IS NULL OR l.section  = s.section)
    AND (s.category IS NULL OR s.category = 'All' OR l.category = s.category)
    AND (s.price_min IS NULL OR l.price >= s.price_min)
    AND (s.price_max IS NULL OR l.price <= s.price_max)
    AND (s.query_text IS NULL OR btrim(s.query_text) = ''
         OR l.title       ILIKE '%' || s.query_text || '%'
         OR l.description ILIKE '%' || s.query_text || '%'
         OR l.part_number ILIKE '%' || s.query_text || '%')
  WHERE s.active = true
    AND s.worker_name IN (SELECT public.auth_worker_names())   -- self-scope: own searches only
  GROUP BY s.id, s.search_name, s.section, s.last_sent_at
  ORDER BY new_count DESC, s.search_name;
$$;

COMMENT ON FUNCTION public.get_saved_search_matches() IS
  'Per active saved search (CALLER''S OWN, self-scoped by auth_worker_names()), how many published listings match and how many are NEW since last_sent_at. Powers the saved-search alert badge. (Marketplace PDDA U-axis)';

GRANT EXECUTE ON FUNCTION public.get_saved_search_matches() TO authenticated;
