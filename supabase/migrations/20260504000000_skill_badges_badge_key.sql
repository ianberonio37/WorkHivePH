-- Add badge_key column to skill_badges + unique index for ON CONFLICT.
--
-- Why: handle_community_post_xp() trigger awards 'voice_of_the_hive' badge on
-- the 10th community post per author per hive. The trigger does:
--   INSERT INTO skill_badges (..., badge_key, ...) VALUES (..., 'voice_of_the_hive', ...)
--   ON CONFLICT (worker_name, badge_key) DO NOTHING;
-- Without this column + index, the INSERT fails with 42703 ("column badge_key does not exist")
-- on the 10th post — which is silently caught by the trigger but breaks post submission
-- because Postgres rolls back the entire INSERT on community_posts.
--
-- Discovered: 2026-05-03 by test-data-seeder/seeders/community.py when an author
-- crossed 10 posts in one hive during seeding. Until this migration ran, the seeder
-- worked around it by capping community posts per author at 9.
--
-- Status: backfill is unnecessary — no rows currently in skill_badges have a
-- meaningful badge_key (the column didn't exist, the trigger has never succeeded
-- on the badge insert).

ALTER TABLE skill_badges
  ADD COLUMN IF NOT EXISTS badge_key text;

-- exam_score is required for skill-exam badges but meaningless for community
-- badges (Voice of the Hive, etc.). Default to 0 so the trigger insert
-- (which omits exam_score for community badges) doesn't violate NOT NULL.
ALTER TABLE skill_badges
  ALTER COLUMN exam_score SET DEFAULT 0;

-- Non-partial unique index — Postgres treats NULL as distinct, so existing
-- skill_badges rows (where badge_key IS NULL) won't conflict with each other.
-- Must be non-partial so the trigger's ON CONFLICT (worker_name, badge_key)
-- can use it (Postgres requires the exact column set, no WHERE predicate).
CREATE UNIQUE INDEX IF NOT EXISTS skill_badges_worker_badge_key_idx
  ON skill_badges (worker_name, badge_key);
