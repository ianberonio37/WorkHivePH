-- Patch handle_community_post_xp() to propagate the post author's auth_uid
-- onto the awarded skill_badges row. Without this, voice_of_the_hive badges
-- have NULL auth_uid, which means RLS-gated reads can't see them.
--
-- Discovered: 2026-05-04 by run_tests.py — auth_uid coverage check found
-- 2/31 skill_badges rows missing auth_uid. Both were trigger-awarded badges.
--
-- NEW.auth_uid carries through from the community_posts insert (the worker
-- writing the post is the same worker earning the badge). Just copy it.

CREATE OR REPLACE FUNCTION handle_community_post_xp()
RETURNS trigger AS $$
DECLARE
  post_count integer;
BEGIN
  SELECT COUNT(*) INTO post_count
  FROM community_posts
  WHERE author_name = NEW.author_name AND hive_id = NEW.hive_id;

  -- First post in this hive: +50 XP
  IF post_count = 1 THEN
    PERFORM increment_community_xp(NEW.author_name, NEW.hive_id, 50);
  END IF;

  -- Safety category: +25 XP (stacks with first-post bonus)
  IF NEW.category = 'safety' THEN
    PERFORM increment_community_xp(NEW.author_name, NEW.hive_id, 25);
  END IF;

  -- 10th post milestone: Voice of the Hive badge.
  -- Carry the post author's auth_uid onto the badge row so RLS-aware queries
  -- can find it. exam_score defaults to 0 (added in 20260504000000).
  IF post_count = 10 THEN
    INSERT INTO skill_badges (worker_name, discipline, level, badge_key, earned_at, auth_uid)
    VALUES (NEW.author_name, 'Community', 1, 'voice_of_the_hive', now(), NEW.auth_uid)
    ON CONFLICT (worker_name, badge_key) DO NOTHING;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
