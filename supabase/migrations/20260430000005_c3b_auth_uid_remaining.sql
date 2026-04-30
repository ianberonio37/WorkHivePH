-- C3b: auth_uid for remaining 7 tables
-- ======================================
-- Completes the auth_uid coverage started in C3 (hive_members, logbook, community_posts).
-- Same dual RLS pattern: authenticated users get strict enforcement,
-- anon users fall through (transition period — remove anon fallback in C4).
--
-- Tables: inventory_items, assets, pm_assets, pm_completions,
--         schedule_items, skill_badges, skill_exam_attempts

-- ── inventory_items ───────────────────────────────────────────────────────────

ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS auth_uid uuid REFERENCES auth.users(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_inventory_items_auth_uid ON inventory_items (auth_uid);

UPDATE inventory_items ii
SET    auth_uid = wp.auth_uid
FROM   worker_profiles wp
WHERE  ii.worker_name = wp.display_name AND ii.auth_uid IS NULL;

GRANT SELECT, INSERT, UPDATE, DELETE ON inventory_items TO anon, authenticated;
ALTER TABLE inventory_items ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "inventory_items_read"   ON inventory_items;
DROP POLICY IF EXISTS "inventory_items_write"  ON inventory_items;
CREATE POLICY "inventory_items_read" ON inventory_items FOR SELECT USING (
  (auth.uid() IS NOT NULL AND hive_id IN (
    SELECT hm.hive_id FROM hive_members hm WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
  ))
  OR auth.uid() IS NULL
);
CREATE POLICY "inventory_items_write" ON inventory_items FOR ALL USING (
  (auth.uid() IS NOT NULL AND (auth_uid = auth.uid() OR EXISTS (
    SELECT 1 FROM hive_members hm
    WHERE hm.hive_id = inventory_items.hive_id AND hm.auth_uid = auth.uid() AND hm.status = 'active'
  )))
  OR auth.uid() IS NULL
);

-- ── assets ────────────────────────────────────────────────────────────────────

ALTER TABLE assets ADD COLUMN IF NOT EXISTS auth_uid uuid REFERENCES auth.users(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_assets_auth_uid ON assets (auth_uid);

UPDATE assets a
SET    auth_uid = wp.auth_uid
FROM   worker_profiles wp
WHERE  a.worker_name = wp.display_name AND a.auth_uid IS NULL;

GRANT SELECT, INSERT, UPDATE, DELETE ON assets TO anon, authenticated;
ALTER TABLE assets ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "assets_read"   ON assets;
DROP POLICY IF EXISTS "assets_write"  ON assets;
CREATE POLICY "assets_read" ON assets FOR SELECT USING (
  (auth.uid() IS NOT NULL AND hive_id IN (
    SELECT hm.hive_id FROM hive_members hm WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
  ))
  OR auth.uid() IS NULL
);
CREATE POLICY "assets_write" ON assets FOR ALL USING (
  (auth.uid() IS NOT NULL AND (auth_uid = auth.uid() OR EXISTS (
    SELECT 1 FROM hive_members hm
    WHERE hm.hive_id = assets.hive_id AND hm.auth_uid = auth.uid() AND hm.role = 'supervisor' AND hm.status = 'active'
  )))
  OR auth.uid() IS NULL
);

-- ── pm_assets ─────────────────────────────────────────────────────────────────

ALTER TABLE pm_assets ADD COLUMN IF NOT EXISTS auth_uid uuid REFERENCES auth.users(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_pm_assets_auth_uid ON pm_assets (auth_uid);

UPDATE pm_assets pa
SET    auth_uid = wp.auth_uid
FROM   worker_profiles wp
WHERE  pa.worker_name = wp.display_name AND pa.auth_uid IS NULL;

GRANT SELECT, INSERT, UPDATE, DELETE ON pm_assets TO anon, authenticated;
ALTER TABLE pm_assets ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anon read pm_assets"    ON pm_assets;
DROP POLICY IF EXISTS "anon insert pm_assets"  ON pm_assets;
DROP POLICY IF EXISTS "anon delete pm_assets"  ON pm_assets;
DROP POLICY IF EXISTS "pm_assets_read"         ON pm_assets;
DROP POLICY IF EXISTS "pm_assets_write"        ON pm_assets;
CREATE POLICY "pm_assets_read" ON pm_assets FOR SELECT USING (
  (auth.uid() IS NOT NULL AND (
    hive_id IN (SELECT hm.hive_id FROM hive_members hm WHERE hm.auth_uid = auth.uid() AND hm.status = 'active')
    OR (hive_id IS NULL AND auth_uid = auth.uid())
  ))
  OR auth.uid() IS NULL
);
CREATE POLICY "pm_assets_write" ON pm_assets FOR ALL USING (
  (auth.uid() IS NOT NULL AND (auth_uid = auth.uid() OR EXISTS (
    SELECT 1 FROM hive_members hm
    WHERE hm.hive_id = pm_assets.hive_id AND hm.auth_uid = auth.uid() AND hm.status = 'active'
  )))
  OR auth.uid() IS NULL
);

-- ── pm_completions ────────────────────────────────────────────────────────────

ALTER TABLE pm_completions ADD COLUMN IF NOT EXISTS auth_uid uuid REFERENCES auth.users(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_pm_completions_auth_uid ON pm_completions (auth_uid);

UPDATE pm_completions pc
SET    auth_uid = wp.auth_uid
FROM   worker_profiles wp
WHERE  pc.worker_name = wp.display_name AND pc.auth_uid IS NULL;

GRANT SELECT, INSERT, UPDATE, DELETE ON pm_completions TO anon, authenticated;
ALTER TABLE pm_completions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anon read pm_completions"   ON pm_completions;
DROP POLICY IF EXISTS "anon insert pm_completions" ON pm_completions;
DROP POLICY IF EXISTS "pm_completions_read"        ON pm_completions;
DROP POLICY IF EXISTS "pm_completions_write"       ON pm_completions;
CREATE POLICY "pm_completions_read" ON pm_completions FOR SELECT USING (
  (auth.uid() IS NOT NULL AND (
    hive_id IN (SELECT hm.hive_id FROM hive_members hm WHERE hm.auth_uid = auth.uid() AND hm.status = 'active')
    OR (hive_id IS NULL AND auth_uid = auth.uid())
  ))
  OR auth.uid() IS NULL
);
CREATE POLICY "pm_completions_write" ON pm_completions FOR ALL USING (
  (auth.uid() IS NOT NULL AND auth_uid = auth.uid())
  OR auth.uid() IS NULL
);

-- ── schedule_items ────────────────────────────────────────────────────────────

ALTER TABLE schedule_items ADD COLUMN IF NOT EXISTS auth_uid uuid REFERENCES auth.users(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_schedule_items_auth_uid ON schedule_items (auth_uid);

UPDATE schedule_items si
SET    auth_uid = wp.auth_uid
FROM   worker_profiles wp
WHERE  si.worker_name = wp.display_name AND si.auth_uid IS NULL;

GRANT SELECT, INSERT, UPDATE, DELETE ON schedule_items TO anon, authenticated;
ALTER TABLE schedule_items ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "schedule_items_read"  ON schedule_items;
DROP POLICY IF EXISTS "schedule_items_write" ON schedule_items;
CREATE POLICY "schedule_items_read" ON schedule_items FOR SELECT USING (
  (auth.uid() IS NOT NULL AND auth_uid = auth.uid())
  OR auth.uid() IS NULL
);
CREATE POLICY "schedule_items_write" ON schedule_items FOR ALL USING (
  (auth.uid() IS NOT NULL AND auth_uid = auth.uid())
  OR auth.uid() IS NULL
);

-- ── skill_badges ──────────────────────────────────────────────────────────────

ALTER TABLE skill_badges ADD COLUMN IF NOT EXISTS auth_uid uuid REFERENCES auth.users(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_skill_badges_auth_uid ON skill_badges (auth_uid);

UPDATE skill_badges sb
SET    auth_uid = wp.auth_uid
FROM   worker_profiles wp
WHERE  sb.worker_name = wp.display_name AND sb.auth_uid IS NULL;

GRANT SELECT, INSERT, UPDATE, DELETE ON skill_badges TO anon, authenticated;
ALTER TABLE skill_badges ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "skill_badges_read"  ON skill_badges;
DROP POLICY IF EXISTS "skill_badges_write" ON skill_badges;
CREATE POLICY "skill_badges_read" ON skill_badges FOR SELECT USING (true);
CREATE POLICY "skill_badges_write" ON skill_badges FOR ALL USING (
  (auth.uid() IS NOT NULL AND auth_uid = auth.uid())
  OR auth.uid() IS NULL
);

-- ── skill_exam_attempts ───────────────────────────────────────────────────────

ALTER TABLE skill_exam_attempts ADD COLUMN IF NOT EXISTS auth_uid uuid REFERENCES auth.users(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_skill_exam_attempts_auth_uid ON skill_exam_attempts (auth_uid);

UPDATE skill_exam_attempts sea
SET    auth_uid = wp.auth_uid
FROM   worker_profiles wp
WHERE  sea.worker_name = wp.display_name AND sea.auth_uid IS NULL;

GRANT SELECT, INSERT, UPDATE, DELETE ON skill_exam_attempts TO anon, authenticated;
ALTER TABLE skill_exam_attempts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "skill_exam_attempts_read"  ON skill_exam_attempts;
DROP POLICY IF EXISTS "skill_exam_attempts_write" ON skill_exam_attempts;
CREATE POLICY "skill_exam_attempts_read" ON skill_exam_attempts FOR SELECT USING (
  (auth.uid() IS NOT NULL AND auth_uid = auth.uid())
  OR auth.uid() IS NULL
);
CREATE POLICY "skill_exam_attempts_write" ON skill_exam_attempts FOR ALL USING (
  (auth.uid() IS NOT NULL AND auth_uid = auth.uid())
  OR auth.uid() IS NULL
);
