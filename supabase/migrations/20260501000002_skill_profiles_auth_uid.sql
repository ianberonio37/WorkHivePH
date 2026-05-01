-- 20260501000002: Add auth_uid to skill_profiles + proper RLS
-- =============================================================
-- skill_profiles was created before the C3/C3b auth migration and was
-- never given auth_uid or RLS policies. C4 enforced strict RLS on all
-- other tables, leaving skill_profiles in a broken state (403 on every
-- upsert) because the anon role has no INSERT grant and no write policy.

-- ── auth_uid column ───────────────────────────────────────────────────────────
ALTER TABLE skill_profiles
  ADD COLUMN IF NOT EXISTS auth_uid uuid REFERENCES auth.users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_skill_profiles_auth_uid ON skill_profiles (auth_uid);

-- ── Backfill from worker_profiles ────────────────────────────────────────────
UPDATE skill_profiles sp
SET    auth_uid = wp.auth_uid
FROM   worker_profiles wp
WHERE  sp.worker_name = wp.display_name
  AND  sp.auth_uid IS NULL;

-- ── Grant ─────────────────────────────────────────────────────────────────────
GRANT SELECT, INSERT, UPDATE, DELETE ON skill_profiles TO anon, authenticated;

-- ── RLS ───────────────────────────────────────────────────────────────────────
ALTER TABLE skill_profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "skill_profiles_read"  ON skill_profiles;
DROP POLICY IF EXISTS "skill_profiles_write" ON skill_profiles;

-- Read open: skill boards and leaderboards are public within the platform
CREATE POLICY "skill_profiles_read" ON skill_profiles
  FOR SELECT USING (true);

-- Write: auth required; own row only
-- (auth_uid = auth.uid()) covers authenticated writes after backfill
-- (auth_uid IS NULL)      covers newly inserted rows before backfill link
CREATE POLICY "skill_profiles_write" ON skill_profiles
  FOR ALL
  USING  (auth.uid() IS NOT NULL AND (auth_uid = auth.uid() OR auth_uid IS NULL))
  WITH CHECK (auth.uid() IS NOT NULL);
