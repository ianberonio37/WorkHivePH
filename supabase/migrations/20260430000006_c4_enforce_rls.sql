-- C4: Enforce RLS — remove anon fallback from all policies
-- ===========================================================
-- Removes "OR auth.uid() IS NULL" from every policy created in C3/C3b.
-- After this migration, ALL data access requires a valid Supabase Auth session.
-- Guest workers (no account) will see empty data and cannot write anything.
--
-- PREREQUISITE: All workers must have auth accounts (C1/C2 complete).
-- ROLLBACK: Re-add "OR auth.uid() IS NULL" to each policy to restore guest access.
--
-- Also adds strict RLS to tables not covered in C3/C3b:
--   community_replies, community_reactions, community_xp, worker_profiles INSERT

-- ── hive_members ─────────────────────────────────────────────────────────────
-- Read stays open (member lists shown on hive board, not sensitive)
-- Write: auth.uid() required

DROP POLICY IF EXISTS "hive_members_insert" ON hive_members;
CREATE POLICY "hive_members_insert" ON hive_members FOR INSERT WITH CHECK (
  auth.uid() IS NOT NULL AND (auth_uid = auth.uid() OR auth_uid IS NULL)
);

DROP POLICY IF EXISTS "hive_members_update" ON hive_members;
CREATE POLICY "hive_members_update" ON hive_members FOR UPDATE USING (
  auth.uid() IS NOT NULL AND EXISTS (
    SELECT 1 FROM hive_members sup
    WHERE sup.hive_id  = hive_members.hive_id
      AND sup.auth_uid = auth.uid()
      AND sup.role     = 'supervisor'
      AND sup.status   = 'active'
  )
);

DROP POLICY IF EXISTS "hive_members_delete" ON hive_members;
CREATE POLICY "hive_members_delete" ON hive_members FOR DELETE USING (
  auth.uid() IS NOT NULL AND auth_uid = auth.uid()
);

-- ── logbook ───────────────────────────────────────────────────────────────────

DROP POLICY IF EXISTS "logbook_read" ON logbook;
CREATE POLICY "logbook_read" ON logbook FOR SELECT USING (
  auth.uid() IS NOT NULL AND (
    (hive_id IS NOT NULL AND hive_id IN (
      SELECT hm.hive_id FROM hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    ))
    OR (hive_id IS NULL AND auth_uid = auth.uid())
  )
);

DROP POLICY IF EXISTS "logbook_insert" ON logbook;
CREATE POLICY "logbook_insert" ON logbook FOR INSERT WITH CHECK (
  auth.uid() IS NOT NULL AND (
    (hive_id IS NOT NULL AND hive_id IN (
      SELECT hm.hive_id FROM hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    ))
    OR (hive_id IS NULL AND (auth_uid = auth.uid() OR auth_uid IS NULL))
  )
);

DROP POLICY IF EXISTS "logbook_update" ON logbook;
CREATE POLICY "logbook_update" ON logbook FOR UPDATE USING (
  auth.uid() IS NOT NULL AND auth_uid = auth.uid()
);

DROP POLICY IF EXISTS "logbook_delete" ON logbook;
CREATE POLICY "logbook_delete" ON logbook FOR DELETE USING (
  auth.uid() IS NOT NULL AND auth_uid = auth.uid()
);

-- ── community_posts ───────────────────────────────────────────────────────────

DROP POLICY IF EXISTS "community_posts_read" ON community_posts;
CREATE POLICY "community_posts_read" ON community_posts FOR SELECT USING (
  auth.uid() IS NOT NULL AND hive_id IN (
    SELECT hm.hive_id FROM hive_members hm
    WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
  )
);

DROP POLICY IF EXISTS "community_posts_insert" ON community_posts;
CREATE POLICY "community_posts_insert" ON community_posts FOR INSERT WITH CHECK (
  auth.uid() IS NOT NULL AND
  (auth_uid = auth.uid() OR auth_uid IS NULL) AND
  hive_id IN (
    SELECT hm.hive_id FROM hive_members hm
    WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
  )
);

DROP POLICY IF EXISTS "community_posts_update" ON community_posts;
CREATE POLICY "community_posts_update" ON community_posts FOR UPDATE USING (
  auth.uid() IS NOT NULL AND (
    auth_uid = auth.uid()
    OR EXISTS (
      SELECT 1 FROM hive_members hm
      WHERE hm.hive_id = community_posts.hive_id AND hm.auth_uid = auth.uid()
        AND hm.role = 'supervisor' AND hm.status = 'active'
    )
  )
);

DROP POLICY IF EXISTS "community_posts_delete" ON community_posts;
CREATE POLICY "community_posts_delete" ON community_posts FOR DELETE USING (
  auth.uid() IS NOT NULL AND (
    auth_uid = auth.uid()
    OR EXISTS (
      SELECT 1 FROM hive_members hm
      WHERE hm.hive_id = community_posts.hive_id AND hm.auth_uid = auth.uid()
        AND hm.role = 'supervisor' AND hm.status = 'active'
    )
  )
);

-- ── community_replies ─────────────────────────────────────────────────────────

DROP POLICY IF EXISTS "anon read community_replies"   ON community_replies;
DROP POLICY IF EXISTS "anon insert community_replies" ON community_replies;
DROP POLICY IF EXISTS "community_replies_read"        ON community_replies;
DROP POLICY IF EXISTS "community_replies_write"       ON community_replies;

CREATE POLICY "community_replies_read" ON community_replies FOR SELECT USING (
  auth.uid() IS NOT NULL AND hive_id IN (
    SELECT hm.hive_id FROM hive_members hm
    WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
  )
);

CREATE POLICY "community_replies_write" ON community_replies FOR ALL USING (
  auth.uid() IS NOT NULL AND hive_id IN (
    SELECT hm.hive_id FROM hive_members hm
    WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
  )
);

-- ── community_reactions ───────────────────────────────────────────────────────

DROP POLICY IF EXISTS "anon read community_reactions"   ON community_reactions;
DROP POLICY IF EXISTS "anon insert community_reactions" ON community_reactions;
DROP POLICY IF EXISTS "community_reactions_read"        ON community_reactions;
DROP POLICY IF EXISTS "community_reactions_write"       ON community_reactions;

CREATE POLICY "community_reactions_read" ON community_reactions FOR SELECT USING (
  auth.uid() IS NOT NULL AND hive_id IN (
    SELECT hm.hive_id FROM hive_members hm
    WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
  )
);

CREATE POLICY "community_reactions_write" ON community_reactions FOR ALL USING (
  auth.uid() IS NOT NULL AND hive_id IN (
    SELECT hm.hive_id FROM hive_members hm
    WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
  )
);

-- ── community_xp ──────────────────────────────────────────────────────────────
-- Read stays open (leaderboard shown to all hive members)
-- Write: triggers use SECURITY DEFINER (bypass RLS) — policy is a safety net

DROP POLICY IF EXISTS "hive xp open write"    ON community_xp;
DROP POLICY IF EXISTS "community_xp_write"    ON community_xp;

CREATE POLICY "community_xp_write" ON community_xp FOR ALL USING (
  auth.uid() IS NOT NULL  -- triggers bypass this via SECURITY DEFINER
);

-- ── inventory_items ───────────────────────────────────────────────────────────

DROP POLICY IF EXISTS "inventory_items_read"  ON inventory_items;
DROP POLICY IF EXISTS "inventory_items_write" ON inventory_items;

CREATE POLICY "inventory_items_read" ON inventory_items FOR SELECT USING (
  auth.uid() IS NOT NULL AND hive_id IN (
    SELECT hm.hive_id FROM hive_members hm WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
  )
);

CREATE POLICY "inventory_items_write" ON inventory_items FOR ALL USING (
  auth.uid() IS NOT NULL AND (auth_uid = auth.uid() OR EXISTS (
    SELECT 1 FROM hive_members hm
    WHERE hm.hive_id = inventory_items.hive_id AND hm.auth_uid = auth.uid() AND hm.status = 'active'
  ))
);

-- ── assets ────────────────────────────────────────────────────────────────────

DROP POLICY IF EXISTS "assets_read"  ON assets;
DROP POLICY IF EXISTS "assets_write" ON assets;

CREATE POLICY "assets_read" ON assets FOR SELECT USING (
  auth.uid() IS NOT NULL AND hive_id IN (
    SELECT hm.hive_id FROM hive_members hm WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
  )
);

CREATE POLICY "assets_write" ON assets FOR ALL USING (
  auth.uid() IS NOT NULL AND (auth_uid = auth.uid() OR EXISTS (
    SELECT 1 FROM hive_members hm
    WHERE hm.hive_id = assets.hive_id AND hm.auth_uid = auth.uid()
      AND hm.role = 'supervisor' AND hm.status = 'active'
  ))
);

-- ── pm_assets ─────────────────────────────────────────────────────────────────

DROP POLICY IF EXISTS "pm_assets_read"  ON pm_assets;
DROP POLICY IF EXISTS "pm_assets_write" ON pm_assets;

CREATE POLICY "pm_assets_read" ON pm_assets FOR SELECT USING (
  auth.uid() IS NOT NULL AND (
    (hive_id IS NOT NULL AND hive_id IN (
      SELECT hm.hive_id FROM hive_members hm WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    ))
    OR (hive_id IS NULL AND auth_uid = auth.uid())
  )
);

CREATE POLICY "pm_assets_write" ON pm_assets FOR ALL USING (
  auth.uid() IS NOT NULL AND (auth_uid = auth.uid() OR EXISTS (
    SELECT 1 FROM hive_members hm
    WHERE hm.hive_id = pm_assets.hive_id AND hm.auth_uid = auth.uid() AND hm.status = 'active'
  ))
);

-- ── pm_completions ────────────────────────────────────────────────────────────

DROP POLICY IF EXISTS "pm_completions_read"  ON pm_completions;
DROP POLICY IF EXISTS "pm_completions_write" ON pm_completions;

CREATE POLICY "pm_completions_read" ON pm_completions FOR SELECT USING (
  auth.uid() IS NOT NULL AND (
    (hive_id IS NOT NULL AND hive_id IN (
      SELECT hm.hive_id FROM hive_members hm WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    ))
    OR (hive_id IS NULL AND auth_uid = auth.uid())
  )
);

CREATE POLICY "pm_completions_write" ON pm_completions FOR ALL USING (
  auth.uid() IS NOT NULL AND auth_uid = auth.uid()
);

-- ── schedule_items ────────────────────────────────────────────────────────────

DROP POLICY IF EXISTS "schedule_items_read"  ON schedule_items;
DROP POLICY IF EXISTS "schedule_items_write" ON schedule_items;

CREATE POLICY "schedule_items_read" ON schedule_items FOR SELECT USING (
  auth.uid() IS NOT NULL AND auth_uid = auth.uid()
);

CREATE POLICY "schedule_items_write" ON schedule_items FOR ALL USING (
  auth.uid() IS NOT NULL AND auth_uid = auth.uid()
);

-- ── skill_badges ──────────────────────────────────────────────────────────────
-- Read stays open (public leaderboards, hive skill boards)

DROP POLICY IF EXISTS "skill_badges_write" ON skill_badges;

CREATE POLICY "skill_badges_write" ON skill_badges FOR ALL USING (
  auth.uid() IS NOT NULL AND auth_uid = auth.uid()
);

-- ── skill_exam_attempts ───────────────────────────────────────────────────────

DROP POLICY IF EXISTS "skill_exam_attempts_read"  ON skill_exam_attempts;
DROP POLICY IF EXISTS "skill_exam_attempts_write" ON skill_exam_attempts;

CREATE POLICY "skill_exam_attempts_read" ON skill_exam_attempts FOR SELECT USING (
  auth.uid() IS NOT NULL AND auth_uid = auth.uid()
);

CREATE POLICY "skill_exam_attempts_write" ON skill_exam_attempts FOR ALL USING (
  auth.uid() IS NOT NULL AND auth_uid = auth.uid()
);

-- ── worker_profiles ───────────────────────────────────────────────────────────
-- Read stays open (username availability checks, display names on boards)
-- INSERT: now restricted to authenticated users only (signUp() creates session first)

DROP POLICY IF EXISTS "profiles insert own" ON worker_profiles;
CREATE POLICY "profiles insert own" ON worker_profiles FOR INSERT WITH CHECK (
  auth.uid() IS NOT NULL AND auth_uid = auth.uid()
);
