-- ============================================================================
-- Community <-> Marketplace reputation bridge (X-axis keystone, Community PDDA 7th)
-- ----------------------------------------------------------------------------
-- The Community surface (community.html) and the Marketplace (marketplace.html,
-- marketplace-seller-profile.html) had ZERO cross-references. Community builds
-- TRUST; the free marketplace turns trust into jobs/trades. This migration is the
-- structural join that lets a person's community standing become a portable
-- trust signal on their marketplace profile, and vice-versa.
--
-- SAFETY MODEL (proven by live RLS probe 2026-07-11: other-hive private posts read
-- = 0 cross-hive):
--   * Reputation is PORTABLE, post CONTENT is NOT. Nothing here exposes post text.
--   * Within-hive reads  -> v_community_reputation_truth  (SECURITY INVOKER, RLS
--     applies exactly like every other _truth view; hive-mates only).
--   * Cross-hive reads    -> get_community_reputation()     (SECURITY DEFINER RPC
--     that returns ONLY curated aggregate columns AND only for workers with a
--     PUBLIC footprint — a purely-private worker is never exposed cross-hive).
--   * Exposed cross-hive counts are PUBLIC-scoped (public posts / reactions on
--     public posts) so private-activity magnitude never leaks. xp_total (the
--     reputation number itself) + the voice_of_the_hive badge + a derived
--     trust_tier are the intended trust signals.
-- ============================================================================

-- ── 1. Within-hive canonical reputation view (INVOKER; RLS-scoped) ──────────
CREATE OR REPLACE VIEW public.v_community_reputation_truth
WITH (security_invoker = true) AS
WITH participants AS (
  -- everyone with ANY community footprint in a hive (robust to missing xp rows:
  -- seeded posters bypass the XP trigger, so we must not key off community_xp alone)
  SELECT DISTINCT author_name AS worker_name, hive_id FROM public.community_posts   WHERE deleted_at IS NULL
  UNION
  SELECT DISTINCT author_name AS worker_name, hive_id FROM public.community_replies
  UNION
  SELECT DISTINCT worker_name, hive_id            FROM public.community_xp
),
post_stats AS (
  SELECT author_name AS worker_name, hive_id,
         count(*)                                   AS total_posts,
         count(*) FILTER (WHERE public)             AS public_posts,
         count(*) FILTER (WHERE category = 'safety')AS safety_posts,
         max(created_at)                            AS last_post_at,
         mode() WITHIN GROUP (ORDER BY category)    AS top_category
  FROM public.community_posts
  WHERE deleted_at IS NULL
  GROUP BY author_name, hive_id
),
reply_stats AS (
  SELECT author_name AS worker_name, hive_id,
         count(*) AS total_replies, max(created_at) AS last_reply_at
  FROM public.community_replies
  GROUP BY author_name, hive_id
),
reactions_recv AS (
  SELECT p.author_name AS worker_name, p.hive_id, count(*) AS reactions_received
  FROM public.community_reactions rx
  JOIN public.community_posts p ON p.id = rx.post_id
  WHERE p.deleted_at IS NULL
  GROUP BY p.author_name, p.hive_id
)
SELECT
  pt.worker_name,
  pt.hive_id,
  COALESCE(cx.xp_total, 0)           AS xp_total,
  COALESCE(ps.total_posts, 0)        AS total_posts,
  COALESCE(ps.public_posts, 0)       AS public_posts,
  COALESCE(ps.safety_posts, 0)       AS safety_posts,
  COALESCE(rs.total_replies, 0)      AS total_replies,
  COALESCE(rr.reactions_received, 0) AS reactions_received,
  ps.top_category,
  EXISTS (SELECT 1 FROM public.skill_badges sb
          WHERE sb.worker_name = pt.worker_name AND sb.badge_key = 'voice_of_the_hive') AS is_voice_of_hive,
  GREATEST(COALESCE(ps.last_post_at, cx.updated_at),
           COALESCE(rs.last_reply_at, cx.updated_at)) AS last_active_at,
  CASE
    WHEN EXISTS (SELECT 1 FROM public.skill_badges sb
                 WHERE sb.worker_name = pt.worker_name AND sb.badge_key = 'voice_of_the_hive') THEN 'voice_of_the_hive'
    WHEN COALESCE(cx.xp_total,0) >= 100 OR COALESCE(ps.total_posts, 0) >= 10 THEN 'top_contributor'
    WHEN COALESCE(cx.xp_total,0) >= 25  OR COALESCE(ps.total_posts, 0) >= 3  THEN 'active_contributor'
    ELSE 'new_member'
  END AS trust_tier
FROM participants pt
LEFT JOIN public.community_xp cx ON cx.worker_name = pt.worker_name AND cx.hive_id = pt.hive_id
LEFT JOIN post_stats     ps ON ps.worker_name = pt.worker_name AND ps.hive_id = pt.hive_id
LEFT JOIN reply_stats    rs ON rs.worker_name = pt.worker_name AND rs.hive_id = pt.hive_id
LEFT JOIN reactions_recv rr ON rr.worker_name = pt.worker_name AND rr.hive_id = pt.hive_id;

COMMENT ON VIEW public.v_community_reputation_truth IS
  'Within-hive community reputation (aggregate-only, no post content). SECURITY INVOKER: RLS on community_posts/xp applies, so only hive-mates read a member''s full stats. For cross-hive/marketplace use get_community_reputation().';

GRANT SELECT ON public.v_community_reputation_truth TO anon, authenticated;

-- ── 2. Cross-hive PORTABLE reputation RPC (DEFINER; curated safe columns) ────
-- Returns a single worker's reputation for a marketplace / global-feed person
-- card. PUBLIC-scoped counts only; returns NO row for a purely-private worker
-- (no public posts, no voice badge, not a seller) so activity magnitude of
-- private-only workers is never exposed to outsiders.
CREATE OR REPLACE FUNCTION public.get_community_reputation(
  p_worker_name text,
  p_hive_id     uuid
)
RETURNS TABLE (
  worker_name         text,
  hive_id             uuid,
  xp_total            integer,
  public_posts        bigint,
  safety_public_posts bigint,
  public_reactions_received bigint,
  top_public_category text,
  is_voice_of_hive    boolean,
  trust_tier          text,
  last_active_at      timestamptz
)
LANGUAGE sql
SECURITY DEFINER
SET search_path TO ''
STABLE
AS $$
  WITH pub AS (
    SELECT count(*)                                    AS public_posts,
           count(*) FILTER (WHERE category = 'safety')  AS safety_public_posts,
           mode() WITHIN GROUP (ORDER BY category)      AS top_public_category,
           max(created_at)                              AS last_public_post
    FROM public.community_posts
    WHERE author_name = p_worker_name AND hive_id = p_hive_id
      AND public = true AND deleted_at IS NULL
  ),
  rx AS (
    SELECT count(*) AS public_reactions_received
    FROM public.community_reactions r
    JOIN public.community_posts p ON p.id = r.post_id
    WHERE p.author_name = p_worker_name AND p.hive_id = p_hive_id
      AND p.public = true AND p.deleted_at IS NULL
  ),
  badge AS (
    SELECT EXISTS (SELECT 1 FROM public.skill_badges sb
                   WHERE sb.worker_name = p_worker_name AND sb.badge_key = 'voice_of_the_hive') AS is_voice
  ),
  xp AS (
    SELECT COALESCE(xp_total, 0) AS xp_total, updated_at
    FROM public.community_xp WHERE worker_name = p_worker_name AND hive_id = p_hive_id
  ),
  seller AS (
    SELECT EXISTS (SELECT 1 FROM public.marketplace_sellers ms
                   WHERE ms.worker_name = p_worker_name AND ms.hive_id = p_hive_id) AS is_seller
  )
  SELECT
    p_worker_name,
    p_hive_id,
    COALESCE((SELECT xp_total FROM xp), 0),
    COALESCE(pub.public_posts, 0),
    COALESCE(pub.safety_public_posts, 0),
    COALESCE(rx.public_reactions_received, 0),
    pub.top_public_category,
    (SELECT is_voice FROM badge),
    CASE
      WHEN (SELECT is_voice FROM badge) THEN 'voice_of_the_hive'
      WHEN COALESCE((SELECT xp_total FROM xp),0) >= 100 OR COALESCE(pub.public_posts,0) >= 10 THEN 'top_contributor'
      WHEN COALESCE((SELECT xp_total FROM xp),0) >= 25  OR COALESCE(pub.public_posts,0) >= 3  THEN 'active_contributor'
      ELSE 'new_member'
    END,
    GREATEST(pub.last_public_post, (SELECT updated_at FROM xp))
  FROM pub, rx
  -- privacy gate: only surface workers with a PUBLIC footprint (public post, badge, or seller)
  WHERE COALESCE(pub.public_posts, 0) > 0
     OR (SELECT is_voice FROM badge)
     OR (SELECT is_seller FROM seller);
$$;

COMMENT ON FUNCTION public.get_community_reputation(text, uuid) IS
  'Cross-hive PORTABLE community reputation for a marketplace/global person card. Aggregate + public-scoped only; no post content; returns no row for purely-private workers. X-axis bridge (Community PDDA 7th).';

GRANT EXECUTE ON FUNCTION public.get_community_reputation(text, uuid) TO anon, authenticated;
