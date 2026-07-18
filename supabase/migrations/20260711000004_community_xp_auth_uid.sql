-- ============================================================================
-- community_xp.auth_uid — the structure that makes spoof-safe cross-hive reputation possible
-- (Community PDDA 7th, X-axis identityJoin prerequisite)
-- ----------------------------------------------------------------------------
-- community_xp was keyed (worker_name, hive_id) with NO auth_uid, so a per-worker reputation summed
-- across hives could pull a DIFFERENT same-named person's XP (proven live: two "Ricardo Morales" in
-- different hives → summed to 150). Posts/reactions/badges/sellers all carry auth_uid; community_xp is
-- the only gap. This adds it (backfilled per-hive, where worker_name+hive_id is unique to one person),
-- sets it on every future write via the DEFINER XP RPC, and rebuilds the by_auth reputation to filter
-- community_xp on auth_uid directly — fully spoof-safe.
-- ============================================================================

ALTER TABLE public.community_xp ADD COLUMN IF NOT EXISTS auth_uid uuid;

-- Backfill: within a single hive, (worker_name, hive_id) resolves to exactly one active member's auth_uid.
UPDATE public.community_xp cx
SET auth_uid = hm.auth_uid
FROM public.hive_members hm
WHERE hm.worker_name = cx.worker_name AND hm.hive_id = cx.hive_id AND hm.status = 'active'
  AND cx.auth_uid IS NULL;

-- Set auth_uid on every future XP write (the RPC is the sole writer; still SECURITY DEFINER + locked-down).
CREATE OR REPLACE FUNCTION public.increment_community_xp(p_worker_name text, p_hive_id uuid, p_amount integer)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO ''
AS $function$
DECLARE
  v_auth_uid uuid;
BEGIN
  SELECT hm.auth_uid INTO v_auth_uid
  FROM public.hive_members hm
  WHERE hm.worker_name = p_worker_name AND hm.hive_id = p_hive_id AND hm.status = 'active'
  LIMIT 1;

  INSERT INTO public.community_xp (worker_name, hive_id, xp_total, updated_at, auth_uid)
  VALUES (p_worker_name, p_hive_id, p_amount, now(), v_auth_uid)
  ON CONFLICT (worker_name, hive_id) DO UPDATE
  SET xp_total   = public.community_xp.xp_total + p_amount,
      updated_at = now(),
      auth_uid   = COALESCE(public.community_xp.auth_uid, EXCLUDED.auth_uid);
END;
$function$;

-- Spoof-safe cross-hive reputation, now filtering community_xp on auth_uid directly.
CREATE OR REPLACE FUNCTION public.get_community_reputation_by_auth(p_auth_uid uuid)
RETURNS TABLE (
  auth_uid                  uuid,
  xp_total                  bigint,
  public_posts              bigint,
  safety_public_posts       bigint,
  public_reactions_received bigint,
  hives_contributed         bigint,
  is_voice_of_hive          boolean,
  trust_tier                text,
  last_active_at            timestamptz
)
LANGUAGE sql
SECURITY DEFINER
SET search_path TO ''
STABLE
AS $$
  WITH my_posts AS (
    SELECT id, hive_id, category, public, created_at
    FROM public.community_posts
    WHERE auth_uid = p_auth_uid AND deleted_at IS NULL
  ),
  pub AS (
    SELECT count(*) FILTER (WHERE public)                        AS public_posts,
           count(*) FILTER (WHERE public AND category='safety')  AS safety_public_posts,
           count(DISTINCT hive_id) FILTER (WHERE public)         AS hives_contributed,
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
    SELECT COALESCE(SUM(xp_total), 0) AS xp_total, MAX(updated_at) AS updated_at
    FROM public.community_xp WHERE auth_uid = p_auth_uid
  ),
  badge AS (
    SELECT EXISTS (
      SELECT 1 FROM public.skill_badges sb
      WHERE sb.auth_uid = p_auth_uid AND sb.badge_key = 'voice_of_the_hive'
    ) AS is_voice
  )
  SELECT
    p_auth_uid,
    (SELECT xp_total FROM xp),
    COALESCE(pub.public_posts, 0),
    COALESCE(pub.safety_public_posts, 0),
    COALESCE(rx.public_reactions_received, 0),
    COALESCE(pub.hives_contributed, 0),
    (SELECT is_voice FROM badge),
    CASE
      WHEN (SELECT is_voice FROM badge) THEN 'voice_of_the_hive'
      WHEN (SELECT xp_total FROM xp) >= 100 OR COALESCE(pub.public_posts,0) >= 10 THEN 'top_contributor'
      WHEN (SELECT xp_total FROM xp) >= 25  OR COALESCE(pub.public_posts,0) >= 3  THEN 'active_contributor'
      ELSE 'new_member'
    END,
    GREATEST(pub.last_public_post, (SELECT updated_at FROM xp))
  FROM pub, rx
  WHERE COALESCE(pub.public_posts, 0) > 0
     OR (SELECT is_voice FROM badge)
     OR EXISTS (SELECT 1 FROM public.marketplace_sellers ms WHERE ms.auth_uid = p_auth_uid);
$$;

COMMENT ON FUNCTION public.get_community_reputation_by_auth(uuid) IS
  'Spoof-safe PORTABLE community reputation summed across a worker''s hives, keyed on auth_uid (community_xp.auth_uid added same migration). Public-scoped aggregates only. X-axis identityJoin (Community PDDA 7th).';

GRANT EXECUTE ON FUNCTION public.get_community_reputation_by_auth(uuid) TO anon, authenticated;
