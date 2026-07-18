-- ============================================================================
-- Browse-grid "Community-trusted" badge — batch, DEFINER (Community PDDA 7th, X-axis)
-- ----------------------------------------------------------------------------
-- BUG THIS FIXES: the marketplace browse grid computed the "Community-trusted"
-- chip by reading skill_badges DIRECTLY from the client
-- (`skill_badges.badge_key='voice_of_the_hive' IN (sellerNames)`). But skill_badges
-- RLS is `auth_uid = auth.uid()` (SELF-ONLY) — so that read returns rows ONLY for
-- the viewer's OWN badges. For every OTHER seller it returns nothing → the grid
-- chip was RLS-DEAD (it could only ever light up on your own listing). The
-- listing-DETAIL path already did this correctly via get_community_reputation()
-- (DEFINER), so grid and detail disagreed.
--
-- FIX + DEEPEN: one batch DEFINER RPC that returns the community trust signal for
-- a set of sellers, and widens the bar from voice-of-the-hive ONLY to
-- voice-of-the-hive OR top_contributor (matching the listing-detail chip predicate).
--
-- SAFETY: only MARKETPLACE SELLERS (public identities) ever appear; trust_tier is
-- derived from PUBLIC-scoped counts (public posts) + xp_total — the same signal
-- already exposed on the public seller profile via get_community_reputation. No
-- private activity, no post content, no non-seller is ever returned. Public like
-- the rest of the marketplace, so granted to anon (cross-hive browsing).
-- ============================================================================

CREATE OR REPLACE FUNCTION public.get_marketplace_trust_badges(p_seller_names text[])
RETURNS TABLE (
  worker_name      text,
  is_voice_of_hive boolean,
  trust_tier       text
)
LANGUAGE sql
SECURITY DEFINER
SET search_path TO ''
STABLE
AS $$
  WITH sellers AS (
    SELECT DISTINCT ms.worker_name, ms.hive_id
    FROM public.marketplace_sellers ms
    WHERE ms.worker_name = ANY (p_seller_names)
  ),
  rep AS (
    SELECT
      s.worker_name,
      EXISTS (SELECT 1 FROM public.skill_badges sb
              WHERE sb.worker_name = s.worker_name
                AND sb.badge_key = 'voice_of_the_hive')                       AS is_voice,
      COALESCE((SELECT cx.xp_total FROM public.community_xp cx
                WHERE cx.worker_name = s.worker_name AND cx.hive_id = s.hive_id), 0) AS xp_total,
      COALESCE((SELECT count(*) FROM public.community_posts p
                WHERE p.author_name = s.worker_name AND p.hive_id = s.hive_id
                  AND p.public = true AND p.deleted_at IS NULL), 0)          AS public_posts
    FROM sellers s
  )
  SELECT
    worker_name,
    is_voice,
    CASE
      WHEN is_voice                                THEN 'voice_of_the_hive'
      WHEN xp_total >= 100 OR public_posts >= 10   THEN 'top_contributor'
      WHEN xp_total >= 25  OR public_posts >= 3    THEN 'active_contributor'
      ELSE 'new_member'
    END AS trust_tier
  FROM rep
  -- only sellers who actually carry a trust signal (voice OR top_contributor) —
  -- matches the listing-detail chip predicate so grid + detail agree; a plain
  -- new/active member gets no grid chip.
  WHERE is_voice OR xp_total >= 100 OR public_posts >= 10;
$$;

COMMENT ON FUNCTION public.get_marketplace_trust_badges(text[]) IS
  'Batch community-trust badge for the marketplace browse grid (voice-of-hive OR top_contributor). SECURITY DEFINER because skill_badges RLS is self-only (a client cannot read peers'' badges); returns only marketplace sellers + public-scoped trust tier. X-axis (Community PDDA 7th).';

GRANT EXECUTE ON FUNCTION public.get_marketplace_trust_badges(text[]) TO anon, authenticated;
