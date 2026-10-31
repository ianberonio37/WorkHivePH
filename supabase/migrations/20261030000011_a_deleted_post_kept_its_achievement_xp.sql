-- HS (2026-10-30, the hive at thirty - found cleaning up after a walk): a deleted community post took back its
-- COMMUNITY XP but kept its ACHIEVEMENT XP. A post pays twice on insert:
--   * community_xp, through community_post_xp_awards (50 for a first post, 25 for a safety post) - reversed when the
--     post is deleted and re-applied when it is restored (20260806000059, tg_community_post_xp_lifecycle);
--   * worker_achievements 'voice_of_hive', through award_achievement_xp (20, or 60 for a safety post), logged in
--     achievement_xp_log as source_action 'community_post' - and NOTHING took this one back.
-- Measured through the product's own path (wh_trash, as Joel, rolled back): a safety post then Delete left community_xp
-- at 220 -> 220 and voice_of_hive at 360 -> 420. So post-a-safety-note, Delete, repeat paid 60 achievement XP a cycle
-- with no post left to show for it - the farm 20260806000059 closed for community XP, still open one table over.
-- The logbook closed the same hole on its side in 20260820000061 (trg_logbook_xp_reverse); the post reversal now does
-- what that trigger does: the award marked reversed, and a NEGATIVE row beside it - achievements.html sums the week's
-- xp_earned without reading reversed_at, so the week's total nets to zero only if the take-back is a row of its own.
-- A restore pays the achievement again through award_achievement_xp itself (its level-up rule included), once: only
-- while no live award for that post remains.
-- Both functions stay revoked from clients (20260820000069) - their only caller is the post lifecycle trigger.

CREATE OR REPLACE FUNCTION public.reverse_community_post_xp(p_post_id uuid)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT post_id, reason, author_name, hive_id, xp_awarded
      FROM public.community_post_xp_awards
     WHERE post_id = p_post_id AND reversed_at IS NULL
     FOR UPDATE
  LOOP
    PERFORM public.increment_community_xp(r.author_name, r.hive_id, -r.xp_awarded);
    UPDATE public.community_post_xp_awards SET reversed_at = now()
     WHERE post_id = r.post_id AND reason = r.reason;
  END LOOP;

  -- The reaction ledger has no reversed_at column and one row per post, so its reversal is recorded
  -- by zeroing the amount rather than by deleting the row: the row must SURVIVE, or the post becomes
  -- payable a second time (20260806000058's own warning).
  FOR r IN
    SELECT post_id, author_name, hive_id, xp_awarded
      FROM public.community_reaction_xp_awards
     WHERE post_id = p_post_id AND xp_awarded > 0
     FOR UPDATE
  LOOP
    PERFORM public.increment_community_xp(r.author_name, r.hive_id, -r.xp_awarded);
    UPDATE public.community_reaction_xp_awards SET xp_awarded = 0 WHERE post_id = r.post_id;
  END LOOP;

  -- The achievement the post paid (voice_of_hive), taken back the way trg_logbook_xp_reverse takes back a log entry's.
  FOR r IN
    SELECT id, worker_name, achievement_id, xp_earned, source_action
      FROM public.achievement_xp_log
     WHERE source_action = 'community_post' AND source_id = p_post_id::text
       AND reversed_at IS NULL AND xp_earned > 0
     FOR UPDATE
  LOOP
    UPDATE public.worker_achievements
       SET xp_total = GREATEST(0, xp_total - r.xp_earned)
     WHERE worker_name = r.worker_name AND achievement_id = r.achievement_id;
    UPDATE public.achievement_xp_log SET reversed_at = now() WHERE id = r.id;
    INSERT INTO public.achievement_xp_log (worker_name, achievement_id, xp_earned, source_action, source_id, reversed_at)
    VALUES (r.worker_name, r.achievement_id, -r.xp_earned, r.source_action, p_post_id::text, now());
  END LOOP;
END;
$function$;

CREATE OR REPLACE FUNCTION public.restore_community_post_xp(p_post_id uuid)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT post_id, reason, author_name, hive_id, xp_awarded
      FROM public.community_post_xp_awards
     WHERE post_id = p_post_id AND reversed_at IS NOT NULL
     FOR UPDATE
  LOOP
    PERFORM public.increment_community_xp(r.author_name, r.hive_id, r.xp_awarded);
    UPDATE public.community_post_xp_awards SET reversed_at = NULL
     WHERE post_id = r.post_id AND reason = r.reason;
  END LOOP;

  -- The achievement paid again through its own award path - once: only while no live award for this post remains,
  -- so a post deleted and restored any number of times holds exactly the one award it earned.
  FOR r IN
    SELECT DISTINCT ON (l.worker_name, l.achievement_id) l.worker_name, l.achievement_id, l.xp_earned
      FROM public.achievement_xp_log l
     WHERE l.source_action = 'community_post' AND l.source_id = p_post_id::text AND l.xp_earned > 0
       AND NOT EXISTS (SELECT 1 FROM public.achievement_xp_log v
                        WHERE v.source_action = 'community_post' AND v.source_id = p_post_id::text
                          AND v.worker_name = l.worker_name AND v.achievement_id = l.achievement_id
                          AND v.xp_earned > 0 AND v.reversed_at IS NULL)
     ORDER BY l.worker_name, l.achievement_id, l.earned_at
  LOOP
    PERFORM public.award_achievement_xp(r.worker_name, r.achievement_id, r.xp_earned, 'community_post', p_post_id::text);
  END LOOP;
END;
$function$;

REVOKE EXECUTE ON FUNCTION public.reverse_community_post_xp(uuid) FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.restore_community_post_xp(uuid) FROM PUBLIC, anon, authenticated;

-- The posts already deleted before this change still hold their achievement XP: take it back now, through the same
-- function. A post in the trash (deleted_at set) or gone altogether pays nothing; a live post is never touched.
DO $backfill$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT DISTINCT l.source_id::uuid AS post_id
      FROM public.achievement_xp_log l
     WHERE l.source_action = 'community_post' AND l.reversed_at IS NULL AND l.xp_earned > 0
       AND l.source_id ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
       AND NOT EXISTS (SELECT 1 FROM public.community_posts p WHERE p.id::text = l.source_id AND p.deleted_at IS NULL)
  LOOP
    PERFORM public.reverse_community_post_xp(r.post_id);
  END LOOP;
END
$backfill$;
