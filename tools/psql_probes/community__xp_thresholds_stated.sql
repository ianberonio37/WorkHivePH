-- xp_thresholds_stated: the XP economy the page states matches the DB's own award functions —
-- first_post = 50, safety_post = 25, badge at the 10th post, reaction +20 counted over DISTINCT
-- reactors excluding the author. All read from the trigger function sources (the values the awards
-- actually use), not from a restatement.
-- expect: first_post_50 \| t
-- expect: safety_post_25 \| t
-- expect: badge_at_10 \| t
-- expect: reaction_20_distinct_reactors \| t
SELECT 'first_post_50 | '  || (prosrc ILIKE '%''first_post''%50%')  FROM pg_proc WHERE proname='handle_community_post_xp';
SELECT 'safety_post_25 | ' || (prosrc ILIKE '%''safety_post''%25%') FROM pg_proc WHERE proname='handle_community_post_xp';
SELECT 'badge_at_10 | '    || (prosrc ILIKE '%post_count = 10%')    FROM pg_proc WHERE proname='handle_community_post_xp';
SELECT 'reaction_20_distinct_reactors | ' ||
  (prosrc ILIKE '%COUNT(DISTINCT worker_name)%' AND prosrc ILIKE '%IS DISTINCT FROM v_author%'
   AND prosrc ILIKE '%20)%')
FROM pg_proc WHERE proname='handle_community_reaction_xp';
