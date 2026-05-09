-- Fix: anon SELECT on worker_achievements + achievement_xp_log was blocked
-- by RLS even though USING (true) should pass. Re-apply with explicit role
-- targeting (TO anon, authenticated, public) to be unambiguous.

DROP POLICY IF EXISTS "ach_worker_read" ON worker_achievements;
CREATE POLICY "ach_worker_read"
  ON worker_achievements
  FOR SELECT
  TO anon, authenticated, public
  USING (true);

DROP POLICY IF EXISTS "ach_log_read" ON achievement_xp_log;
CREATE POLICY "ach_log_read"
  ON achievement_xp_log
  FOR SELECT
  TO anon, authenticated, public
  USING (true);

-- Re-grant to be safe (idempotent)
GRANT SELECT ON worker_achievements TO anon, authenticated;
GRANT SELECT ON achievement_xp_log  TO anon, authenticated;
