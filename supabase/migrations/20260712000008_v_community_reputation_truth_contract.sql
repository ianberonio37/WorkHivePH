-- Add the truth-view contract columns (_source_count / _freshness_ts / _canonical_version)
-- to v_community_reputation_truth via CREATE OR REPLACE (a NEW migration, so the original
-- 20260711000001 stays immutable per validate_migration_immutability_strict, AND applying
-- this migration actually lands the columns in the live DB — static file-edit alone did not).
CREATE OR REPLACE VIEW public.v_community_reputation_truth
WITH (security_invoker = true) AS
WITH participants AS (
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
  END AS trust_tier,
  -- Truth-view contract columns (validate_truth_view_contract): per-hive partition
  count(*) OVER (PARTITION BY pt.hive_id)                                   AS _source_count,
  max(GREATEST(COALESCE(ps.last_post_at, cx.updated_at),
               COALESCE(rs.last_reply_at, cx.updated_at)))
      OVER (PARTITION BY pt.hive_id)                                        AS _freshness_ts,
  'community_reputation_truth:v1'                                           AS _canonical_version
FROM participants pt
LEFT JOIN public.community_xp cx ON cx.worker_name = pt.worker_name AND cx.hive_id = pt.hive_id
LEFT JOIN post_stats     ps ON ps.worker_name = pt.worker_name AND ps.hive_id = pt.hive_id
LEFT JOIN reply_stats    rs ON rs.worker_name = pt.worker_name AND rs.hive_id = pt.hive_id
LEFT JOIN reactions_recv rr ON rr.worker_name = pt.worker_name AND rr.hive_id = pt.hive_id;

GRANT SELECT ON public.v_community_reputation_truth TO anon, authenticated;
