-- Worker Profiles — WorkHive Platform
-- Links Supabase Auth uid to a display name and unique username.
-- auth.uid() is the real identity; worker_name (display_name) is what colleagues see.
--
-- Design decisions:
--   username     — globally unique, used only for login, immutable after signup
--   display_name — shown in UI (replaces wh_last_worker), matches existing worker_name
--                  in all DB records for backward compat; locked until C3 migration
--   email        — optional, for B2 weekly digest and account recovery
--   synthetic    — Supabase Auth stores username@auth.workhiveph.com internally;
--                  workers only ever type username + password, never see the email
--
-- PREREQUISITE: Disable "Enable email confirmations" in Supabase Dashboard
--   Authentication → Settings → Email Auth → Confirm email = OFF
--   Without this, signUp() silently fails because the synthetic email can't receive mail.

CREATE TABLE IF NOT EXISTS worker_profiles (
  id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  auth_uid     uuid        NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
  username     text        NOT NULL UNIQUE CHECK (username ~ '^[a-z0-9_]{3,30}$'),
  display_name text        NOT NULL CHECK (char_length(display_name) BETWEEN 1 AND 50),
  email        text,
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_worker_profiles_username
  ON worker_profiles (username);

CREATE INDEX IF NOT EXISTS idx_worker_profiles_auth_uid
  ON worker_profiles (auth_uid);

GRANT SELECT, INSERT, UPDATE ON worker_profiles TO anon, authenticated;

ALTER TABLE worker_profiles ENABLE ROW LEVEL SECURITY;

-- Anyone can check username availability and read display names (needed for hive boards)
DROP POLICY IF EXISTS "profiles open read" ON worker_profiles;
CREATE POLICY "profiles open read"
  ON worker_profiles FOR SELECT USING (true);

-- Anon can insert during signup (auth_uid comes from Supabase Auth signUp response)
DROP POLICY IF EXISTS "profiles insert own" ON worker_profiles;
CREATE POLICY "profiles insert own"
  ON worker_profiles FOR INSERT WITH CHECK (true);

-- Authenticated users can update only their own profile
DROP POLICY IF EXISTS "profiles update own" ON worker_profiles;
CREATE POLICY "profiles update own"
  ON worker_profiles FOR UPDATE
  USING (auth.uid() = auth_uid);
