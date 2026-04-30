-- C3: Add auth_uid to hive_members, logbook, community_posts
-- ============================================================
-- Dual RLS pattern during the transition period:
--   Authenticated users: strict auth.uid()-based enforcement
--   Anon users (guest workers): open fallback (same security as before C3)
--
-- Remove the dual fallback in C4 once all workers have auth accounts.
--
-- Backfill: links existing records to auth accounts via
--   worker_name = worker_profiles.display_name
--
-- PREREQUISITE: worker_profiles table and Supabase Auth must be live (C1).

-- ── hive_members ─────────────────────────────────────────────────────────────

ALTER TABLE hive_members ADD COLUMN IF NOT EXISTS auth_uid uuid REFERENCES auth.users(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_hive_members_auth_uid ON hive_members (auth_uid);

-- Backfill auth_uid for existing membership rows
UPDATE hive_members hm
SET    auth_uid = wp.auth_uid
FROM   worker_profiles wp
WHERE  hm.worker_name = wp.display_name
  AND  hm.auth_uid IS NULL;

GRANT SELECT, INSERT, UPDATE, DELETE ON hive_members TO anon, authenticated;
ALTER TABLE hive_members ENABLE ROW LEVEL SECURITY;

-- Read: open — workers need to see all hive members on the board
DROP POLICY IF EXISTS "hive_members_read" ON hive_members;
CREATE POLICY "hive_members_read" ON hive_members FOR SELECT USING (true);

-- Join a hive: authenticated must supply their own auth_uid; anon fallback allowed
DROP POLICY IF EXISTS "hive_members_insert" ON hive_members;
CREATE POLICY "hive_members_insert" ON hive_members FOR INSERT WITH CHECK (
  (auth.uid() IS NOT NULL AND (auth_uid = auth.uid() OR auth_uid IS NULL))
  OR auth.uid() IS NULL
);

-- Approve / kick / promote: authenticated supervisors only; anon fallback
DROP POLICY IF EXISTS "hive_members_update" ON hive_members;
CREATE POLICY "hive_members_update" ON hive_members FOR UPDATE USING (
  (auth.uid() IS NOT NULL AND EXISTS (
    SELECT 1 FROM hive_members sup
    WHERE sup.hive_id   = hive_members.hive_id
      AND sup.auth_uid  = auth.uid()
      AND sup.role      = 'supervisor'
      AND sup.status    = 'active'
  ))
  OR auth.uid() IS NULL
);

-- Delete own membership: authenticated worker only; anon fallback
DROP POLICY IF EXISTS "hive_members_delete" ON hive_members;
CREATE POLICY "hive_members_delete" ON hive_members FOR DELETE USING (
  (auth.uid() IS NOT NULL AND auth_uid = auth.uid())
  OR auth.uid() IS NULL
);

-- ── logbook ───────────────────────────────────────────────────────────────────

ALTER TABLE logbook ADD COLUMN IF NOT EXISTS auth_uid uuid REFERENCES auth.users(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_logbook_auth_uid ON logbook (auth_uid);

UPDATE logbook l
SET    auth_uid = wp.auth_uid
FROM   worker_profiles wp
WHERE  l.worker_name = wp.display_name
  AND  l.auth_uid IS NULL;

GRANT SELECT, INSERT, UPDATE, DELETE ON logbook TO anon, authenticated;
ALTER TABLE logbook ENABLE ROW LEVEL SECURITY;

-- Read: authenticated workers see their hive's logbook; anon open
DROP POLICY IF EXISTS "logbook_read" ON logbook;
CREATE POLICY "logbook_read" ON logbook FOR SELECT USING (
  (auth.uid() IS NOT NULL AND (
    -- Hive mode: member of the hive
    (hive_id IS NOT NULL AND hive_id IN (
      SELECT hm.hive_id FROM hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    ))
    -- Solo mode: own records only
    OR (hive_id IS NULL AND auth_uid = auth.uid())
  ))
  OR auth.uid() IS NULL
);

-- Insert: authenticated workers write to their own hive; anon open
DROP POLICY IF EXISTS "logbook_insert" ON logbook;
CREATE POLICY "logbook_insert" ON logbook FOR INSERT WITH CHECK (
  (auth.uid() IS NOT NULL AND (
    (hive_id IS NOT NULL AND hive_id IN (
      SELECT hm.hive_id FROM hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    ))
    OR (hive_id IS NULL AND (auth_uid = auth.uid() OR auth_uid IS NULL))
  ))
  OR auth.uid() IS NULL
);

-- Update / delete: authenticated worker owns the row; anon open
DROP POLICY IF EXISTS "logbook_update" ON logbook;
CREATE POLICY "logbook_update" ON logbook FOR UPDATE USING (
  (auth.uid() IS NOT NULL AND auth_uid = auth.uid())
  OR auth.uid() IS NULL
);

DROP POLICY IF EXISTS "logbook_delete" ON logbook;
CREATE POLICY "logbook_delete" ON logbook FOR DELETE USING (
  (auth.uid() IS NOT NULL AND auth_uid = auth.uid())
  OR auth.uid() IS NULL
);

-- ── community_posts ───────────────────────────────────────────────────────────

ALTER TABLE community_posts ADD COLUMN IF NOT EXISTS auth_uid uuid REFERENCES auth.users(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_community_posts_auth_uid ON community_posts (auth_uid);

UPDATE community_posts cp
SET    auth_uid = wp.auth_uid
FROM   worker_profiles wp
WHERE  cp.author_name = wp.display_name
  AND  cp.auth_uid IS NULL;

-- community_posts already has GRANT + RLS from 20260430000001_community_grants.sql
-- Only add new auth_uid-based policies (alongside existing open ones)

-- Replace the existing open policies with dual policies
DROP POLICY IF EXISTS "anon read community_posts"       ON community_posts;
DROP POLICY IF EXISTS "anon insert community_posts"     ON community_posts;
DROP POLICY IF EXISTS "anon update community_posts"     ON community_posts;
DROP POLICY IF EXISTS "anon delete community_posts"     ON community_posts;

-- Read: hive members see their hive; anon open
DROP POLICY IF EXISTS "community_posts_read" ON community_posts;
CREATE POLICY "community_posts_read" ON community_posts FOR SELECT USING (
  (auth.uid() IS NOT NULL AND hive_id IN (
    SELECT hm.hive_id FROM hive_members hm
    WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
  ))
  OR auth.uid() IS NULL
);

-- Insert: authenticated must be hive member; anon open
DROP POLICY IF EXISTS "community_posts_insert" ON community_posts;
CREATE POLICY "community_posts_insert" ON community_posts FOR INSERT WITH CHECK (
  (auth.uid() IS NOT NULL AND
    (auth_uid = auth.uid() OR auth_uid IS NULL) AND
    hive_id IN (
      SELECT hm.hive_id FROM hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    )
  )
  OR auth.uid() IS NULL
);

-- Update (pin/flag): authenticated post author or supervisor; anon open
DROP POLICY IF EXISTS "community_posts_update" ON community_posts;
CREATE POLICY "community_posts_update" ON community_posts FOR UPDATE USING (
  (auth.uid() IS NOT NULL AND (
    auth_uid = auth.uid()
    OR EXISTS (
      SELECT 1 FROM hive_members hm
      WHERE hm.hive_id  = community_posts.hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.role     = 'supervisor'
        AND hm.status   = 'active'
    )
  ))
  OR auth.uid() IS NULL
);

-- Delete: authenticated post author or supervisor; anon open
DROP POLICY IF EXISTS "community_posts_delete" ON community_posts;
CREATE POLICY "community_posts_delete" ON community_posts FOR DELETE USING (
  (auth.uid() IS NOT NULL AND (
    auth_uid = auth.uid()
    OR EXISTS (
      SELECT 1 FROM hive_members hm
      WHERE hm.hive_id  = community_posts.hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.role     = 'supervisor'
        AND hm.status   = 'active'
    )
  ))
  OR auth.uid() IS NULL
);
