-- worker_achievements + achievement_xp_log are world-readable by design
-- (leaderboards, profile frames). Two prior RLS fix attempts didn't take
-- effect for anon role. Disabling RLS on these two tables is the right
-- move because:
--   * GRANT SELECT to anon already covers read access
--   * No INSERT/UPDATE/DELETE grants exist for anon, so writes blocked at
--     privilege layer
--   * award_achievement_xp() function is REVOKE'd from anon, so XP
--     can't be awarded from the client
--
-- achievement_definitions keeps RLS on (it works there).

ALTER TABLE worker_achievements DISABLE ROW LEVEL SECURITY;
ALTER TABLE achievement_xp_log  DISABLE ROW LEVEL SECURITY;

-- Make sure GRANTs are explicit
REVOKE INSERT, UPDATE, DELETE ON worker_achievements FROM anon, authenticated;
REVOKE INSERT, UPDATE, DELETE ON achievement_xp_log  FROM anon, authenticated;

GRANT SELECT ON worker_achievements TO anon, authenticated;
GRANT SELECT ON achievement_xp_log  TO anon, authenticated;

NOTIFY pgrst, 'reload schema';
