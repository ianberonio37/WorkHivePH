-- Fix attempt 2: previous migration's TO clause got reduced to PUBLIC by
-- Supabase, but PUBLIC apparently isn't granting access to anon for these
-- two tables. Recreate policies with explicit anon + authenticated only
-- (no public mention so Postgres doesn't strip the role list).

DROP POLICY IF EXISTS "ach_worker_read" ON worker_achievements;
CREATE POLICY "ach_worker_read"
  ON worker_achievements
  AS PERMISSIVE
  FOR SELECT
  TO anon, authenticated
  USING (true);

DROP POLICY IF EXISTS "ach_log_read" ON achievement_xp_log;
CREATE POLICY "ach_log_read"
  ON achievement_xp_log
  AS PERMISSIVE
  FOR SELECT
  TO anon, authenticated
  USING (true);

GRANT SELECT ON worker_achievements TO anon, authenticated;
GRANT SELECT ON achievement_xp_log  TO anon, authenticated;

-- Bump table privileges to be sure (idempotent)
GRANT USAGE ON SCHEMA public TO anon, authenticated;

-- Reload PostgREST schema cache so the policy change takes effect immediately
NOTIFY pgrst, 'reload schema';
