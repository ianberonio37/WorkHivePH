-- Fix handle_community_post_xp() — community posting was 100% broken platform-wide.
--
-- The trigger trg_community_post_xp fires AFTER INSERT on community_posts and runs
-- handle_community_post_xp(), which is SECURITY DEFINER with `SET search_path TO ''`
-- (the Supabase-recommended hardening) BUT references its objects UNqualified:
--   SELECT COUNT(*) ... FROM community_posts          -- no schema
--   PERFORM increment_community_xp(...)               -- no schema
--   INSERT INTO skill_badges ...                      -- no schema
-- With an empty search_path none of those resolve, so the trigger raises
-- 42P01 "relation \"community_posts\" does not exist" and Postgres aborts the
-- INSERT. Net effect: NOBODY could post to any hive's community board (the
-- submitPost() call surfaced it as a 404). SELECTs worked because reads don't
-- fire the trigger — which is why the board still displayed existing posts.
--
-- Fix: keep `SET search_path TO ''` (don't weaken the hardening) and fully
-- schema-qualify every object reference, matching the secure pattern the sibling
-- triggers already use. Same class as compute_hive_readiness (a SECURITY DEFINER
-- function referencing objects the way its search_path can't resolve).
--
-- Forward-only. CREATE OR REPLACE preserves the existing trigger binding.

CREATE OR REPLACE FUNCTION public.handle_community_post_xp()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE
  post_count integer;
BEGIN
  SELECT COUNT(*) INTO post_count
  FROM public.community_posts
  WHERE author_name = NEW.author_name AND hive_id = NEW.hive_id;

  IF post_count = 1 THEN
    PERFORM public.increment_community_xp(NEW.author_name, NEW.hive_id, 50);
  END IF;

  IF NEW.category = 'safety' THEN
    PERFORM public.increment_community_xp(NEW.author_name, NEW.hive_id, 25);
  END IF;

  IF post_count = 10 THEN
    INSERT INTO public.skill_badges (worker_name, discipline, level, badge_key, earned_at, auth_uid)
    VALUES (NEW.author_name, 'Community', 1, 'voice_of_the_hive', now(), NEW.auth_uid)
    ON CONFLICT (worker_name, badge_key) DO NOTHING;
  END IF;

  RETURN NEW;
END;
$function$;
