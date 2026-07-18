-- 20260717000003_community_reputation_membership_or_seller_gate.sql
--
-- Arc R (P / A01, LLM08) — cross-tenant retrieval hardening on the community-reputation RPCs,
-- surfaced by `validate_ai_retrieval_isolation` (live board, 2026-07-17) after the recent
-- Community↔Marketplace reputation bridge added them. Ian's call: HARDEN the over-exposure.
--
-- FINDING: get_community_reputation(worker,hive) and get_community_reputation_by_auth(auth_uid)
-- are SECURITY DEFINER, authenticated-callable, and filter by CLIENT-SUPPLIED params with NO
-- membership gate. A worker in Hive A could query any worker's reputation aggregates in any hive.
-- (Mitigated in-practice by each RPC's public-footprint WHERE gate — data is derived from
-- already-cross-hive-public posts — so severity is LOW, but the structural IDOR is real.)
--
-- FIX (property, not name-pattern): a membership-OR-seller early-return guard that preserves BOTH
-- legitimate uses:
--   * community.html shows a member's reputation to their OWN hive-mates → caller-is-member passes.
--   * marketplace shows a SELLER's reputation to buyers cross-hive     → worker-is-seller passes.
--   * an attacker querying a NON-seller cross-hive                     → neither → returns EMPTY.
-- SECURITY DEFINER + service_role-only grants are UNCHANGED (least-privilege already correct); this
-- adds the in-body caller check the §3c match_procedural_memories fix established as the pattern.
-- Query bodies are preserved byte-for-byte (only wrapped in plpgsql RETURN QUERY + the guard).

BEGIN;

CREATE OR REPLACE FUNCTION public.get_community_reputation(p_worker_name text, p_hive_id uuid)
  RETURNS TABLE(worker_name text, hive_id uuid, xp_total integer, public_posts bigint, safety_public_posts bigint, public_reactions_received bigint, top_public_category text, is_voice_of_hive boolean, trust_tier text, last_active_at timestamp with time zone)
  LANGUAGE plpgsql
  STABLE SECURITY DEFINER
  SET search_path TO ''
AS $function$
#variable_conflict use_column
BEGIN
  -- membership-OR-seller gate (Arc R P/A01): same-hive member (community use) OR the queried
  -- worker is a marketplace seller (cross-hive marketplace use). Else no cross-tenant retrieval.
  IF NOT (
    auth.uid() IS NOT NULL AND (
      EXISTS (SELECT 1 FROM public.hive_members hm
              WHERE hm.hive_id = p_hive_id AND hm.auth_uid = auth.uid() AND hm.status = 'active')
      OR EXISTS (SELECT 1 FROM public.marketplace_sellers ms
                 WHERE ms.worker_name = p_worker_name AND ms.hive_id = p_hive_id)
    )
  ) THEN
    RETURN;
  END IF;

  RETURN QUERY
  WITH pub AS (
    SELECT count(*)                                    AS public_posts,
           count(*) FILTER (WHERE category = 'safety')  AS safety_public_posts,
           mode() WITHIN GROUP (ORDER BY category)      AS top_public_category,
           max(created_at)                              AS last_public_post
    FROM public.community_posts
    WHERE author_name = p_worker_name AND community_posts.hive_id = p_hive_id
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
    SELECT COALESCE(community_xp.xp_total, 0) AS xp_total, updated_at
    FROM public.community_xp WHERE worker_name = p_worker_name AND community_xp.hive_id = p_hive_id
  ),
  seller AS (
    SELECT EXISTS (SELECT 1 FROM public.marketplace_sellers ms
                   WHERE ms.worker_name = p_worker_name AND ms.hive_id = p_hive_id) AS is_seller
  )
  SELECT
    p_worker_name,
    p_hive_id,
    COALESCE((SELECT x.xp_total FROM xp x), 0),
    COALESCE(pub.public_posts, 0),
    COALESCE(pub.safety_public_posts, 0),
    COALESCE(rx.public_reactions_received, 0),
    pub.top_public_category,
    (SELECT is_voice FROM badge),
    CASE
      WHEN (SELECT is_voice FROM badge) THEN 'voice_of_the_hive'
      WHEN COALESCE((SELECT x.xp_total FROM xp x),0) >= 100 OR COALESCE(pub.public_posts,0) >= 10 THEN 'top_contributor'
      WHEN COALESCE((SELECT x.xp_total FROM xp x),0) >= 25  OR COALESCE(pub.public_posts,0) >= 3  THEN 'active_contributor'
      ELSE 'new_member'
    END,
    GREATEST(pub.last_public_post, (SELECT updated_at FROM xp))
  FROM pub, rx
  WHERE COALESCE(pub.public_posts, 0) > 0
     OR (SELECT is_voice FROM badge)
     OR (SELECT is_seller FROM seller);
END;
$function$;

CREATE OR REPLACE FUNCTION public.get_community_reputation_by_auth(p_auth_uid uuid)
  RETURNS TABLE(auth_uid uuid, xp_total bigint, public_posts bigint, safety_public_posts bigint, public_reactions_received bigint, hives_contributed bigint, is_voice_of_hive boolean, trust_tier text, last_active_at timestamp with time zone)
  LANGUAGE plpgsql
  STABLE SECURITY DEFINER
  SET search_path TO ''
AS $function$
#variable_conflict use_column
BEGIN
  -- self OR the queried worker is a marketplace seller (the only cross-hive-legit reputation reads).
  IF NOT (
    auth.uid() IS NOT NULL AND (
      p_auth_uid = auth.uid()
      OR EXISTS (SELECT 1 FROM public.marketplace_sellers ms WHERE ms.auth_uid = p_auth_uid)
    )
  ) THEN
    RETURN;
  END IF;

  RETURN QUERY
  WITH my_posts AS (
    SELECT id, community_posts.hive_id, category, public, created_at
    FROM public.community_posts
    WHERE community_posts.auth_uid = p_auth_uid AND deleted_at IS NULL
  ),
  pub AS (
    SELECT count(*) FILTER (WHERE public)                        AS public_posts,
           count(*) FILTER (WHERE public AND category='safety')  AS safety_public_posts,
           count(DISTINCT my_posts.hive_id) FILTER (WHERE public) AS hives_contributed,
           max(created_at) FILTER (WHERE public)                 AS last_public_post
    FROM my_posts
  ),
  rx AS (
    SELECT count(*) AS public_reactions_received
    FROM public.community_reactions r
    JOIN my_posts p ON p.id = r.post_id
    WHERE p.public = true
  ),
  xp AS (
    SELECT COALESCE(SUM(community_xp.xp_total), 0) AS xp_total, MAX(updated_at) AS updated_at
    FROM public.community_xp WHERE community_xp.auth_uid = p_auth_uid
  ),
  badge AS (
    SELECT EXISTS (
      SELECT 1 FROM public.skill_badges sb
      WHERE sb.auth_uid = p_auth_uid AND sb.badge_key = 'voice_of_the_hive'
    ) AS is_voice
  )
  SELECT
    p_auth_uid,
    (SELECT x.xp_total FROM xp x),
    COALESCE(pub.public_posts, 0),
    COALESCE(pub.safety_public_posts, 0),
    COALESCE(rx.public_reactions_received, 0),
    COALESCE(pub.hives_contributed, 0),
    (SELECT is_voice FROM badge),
    CASE
      WHEN (SELECT is_voice FROM badge) THEN 'voice_of_the_hive'
      WHEN (SELECT x.xp_total FROM xp x) >= 100 OR COALESCE(pub.public_posts,0) >= 10 THEN 'top_contributor'
      WHEN (SELECT x.xp_total FROM xp x) >= 25  OR COALESCE(pub.public_posts,0) >= 3  THEN 'active_contributor'
      ELSE 'new_member'
    END,
    GREATEST(pub.last_public_post, (SELECT updated_at FROM xp))
  FROM pub, rx
  WHERE COALESCE(pub.public_posts, 0) > 0
     OR (SELECT is_voice FROM badge)
     OR EXISTS (SELECT 1 FROM public.marketplace_sellers ms WHERE ms.auth_uid = p_auth_uid);
END;
$function$;

COMMIT;
