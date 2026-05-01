-- 20260501000003: RLS for tables missed by C3/C3b/C4 migration
-- ==============================================================
-- Four tables were never given auth_uid, GRANT, or write policies.
-- Each was user-writable from the browser and would 403 once touched
-- after C4 enforced strict RLS on all other tables.
--
-- Tables covered:
--   inventory_transactions  — worker_name + hive_id, written on every part use/restock
--   hives                   — created_by (string), written on hive creation
--   report_contacts         — hive_id scoped, insert+delete from report-sender.html
--   pm_scope_items          — asset_id scoped (no worker_name), written on PM save
--
-- Also patches trg_sync_auth_uid_on_signup to include:
--   inventory_transactions  — was missing from trigger entirely
--   skill_profiles          — added auth_uid in 20260501000002 but not in trigger


-- ═══════════════════════════════════════════════════════════════════════════════
-- inventory_transactions
-- ═══════════════════════════════════════════════════════════════════════════════

ALTER TABLE inventory_transactions
  ADD COLUMN IF NOT EXISTS auth_uid uuid REFERENCES auth.users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_inventory_transactions_auth_uid
  ON inventory_transactions (auth_uid);

-- Backfill from worker_profiles
UPDATE inventory_transactions it
SET    auth_uid = wp.auth_uid
FROM   worker_profiles wp
WHERE  it.worker_name = wp.display_name
  AND  it.auth_uid IS NULL;

GRANT SELECT, INSERT, UPDATE, DELETE ON inventory_transactions TO anon, authenticated;
ALTER TABLE inventory_transactions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "inventory_transactions_read"  ON inventory_transactions;
DROP POLICY IF EXISTS "inventory_transactions_write" ON inventory_transactions;

CREATE POLICY "inventory_transactions_read" ON inventory_transactions
  FOR SELECT USING (
    auth.uid() IS NOT NULL AND (
      (hive_id IS NOT NULL AND hive_id IN (
        SELECT hm.hive_id FROM hive_members hm
        WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
      ))
      OR (hive_id IS NULL AND auth_uid = auth.uid())
    )
  );

CREATE POLICY "inventory_transactions_write" ON inventory_transactions
  FOR ALL
  USING  (auth.uid() IS NOT NULL AND (auth_uid = auth.uid() OR auth_uid IS NULL))
  WITH CHECK (auth.uid() IS NOT NULL);


-- ═══════════════════════════════════════════════════════════════════════════════
-- hives
-- ═══════════════════════════════════════════════════════════════════════════════
-- hives has no auth_uid column (created_by is a plain string).
-- SELECT must stay open for invite-code lookup before a user joins.
-- INSERT requires authentication only — any worker can start a hive.
-- UPDATE/DELETE restricted to supervisors of that hive.

GRANT SELECT, INSERT, UPDATE, DELETE ON hives TO anon, authenticated;
ALTER TABLE hives ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "hives_read"   ON hives;
DROP POLICY IF EXISTS "hives_insert" ON hives;
DROP POLICY IF EXISTS "hives_update" ON hives;
DROP POLICY IF EXISTS "hives_delete" ON hives;

CREATE POLICY "hives_read" ON hives
  FOR SELECT USING (true);

CREATE POLICY "hives_insert" ON hives
  FOR INSERT WITH CHECK (auth.uid() IS NOT NULL);

CREATE POLICY "hives_update" ON hives
  FOR UPDATE USING (
    auth.uid() IS NOT NULL AND id IN (
      SELECT hive_id FROM hive_members
      WHERE auth_uid = auth.uid() AND role = 'supervisor' AND status = 'active'
    )
  );

CREATE POLICY "hives_delete" ON hives
  FOR DELETE USING (
    auth.uid() IS NOT NULL AND id IN (
      SELECT hive_id FROM hive_members
      WHERE auth_uid = auth.uid() AND role = 'supervisor' AND status = 'active'
    )
  );


-- ═══════════════════════════════════════════════════════════════════════════════
-- report_contacts
-- ═══════════════════════════════════════════════════════════════════════════════

GRANT SELECT, INSERT, UPDATE, DELETE ON report_contacts TO anon, authenticated;
ALTER TABLE report_contacts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "report_contacts_read"  ON report_contacts;
DROP POLICY IF EXISTS "report_contacts_write" ON report_contacts;

CREATE POLICY "report_contacts_read" ON report_contacts
  FOR SELECT USING (
    auth.uid() IS NOT NULL AND hive_id IN (
      SELECT hive_id FROM hive_members
      WHERE auth_uid = auth.uid() AND status = 'active'
    )
  );

CREATE POLICY "report_contacts_write" ON report_contacts
  FOR ALL
  USING (
    auth.uid() IS NOT NULL AND hive_id IN (
      SELECT hive_id FROM hive_members
      WHERE auth_uid = auth.uid() AND status = 'active'
    )
  )
  WITH CHECK (auth.uid() IS NOT NULL);


-- ═══════════════════════════════════════════════════════════════════════════════
-- pm_scope_items
-- ═══════════════════════════════════════════════════════════════════════════════
-- pm_scope_items has no worker_name or hive_id directly.
-- Scoped via asset_id → pm_assets.hive_id → hive_members.

GRANT SELECT, INSERT, UPDATE, DELETE ON pm_scope_items TO anon, authenticated;
ALTER TABLE pm_scope_items ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "pm_scope_items_read"  ON pm_scope_items;
DROP POLICY IF EXISTS "pm_scope_items_write" ON pm_scope_items;

CREATE POLICY "pm_scope_items_read" ON pm_scope_items
  FOR SELECT USING (
    auth.uid() IS NOT NULL AND asset_id IN (
      SELECT pa.id FROM pm_assets pa
      JOIN hive_members hm ON pa.hive_id = hm.hive_id
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    )
  );

CREATE POLICY "pm_scope_items_write" ON pm_scope_items
  FOR ALL
  USING (
    auth.uid() IS NOT NULL AND asset_id IN (
      SELECT pa.id FROM pm_assets pa
      JOIN hive_members hm ON pa.hive_id = hm.hive_id
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    )
  )
  WITH CHECK (auth.uid() IS NOT NULL);


-- ═══════════════════════════════════════════════════════════════════════════════
-- Patch trg_sync_auth_uid_on_signup
-- ═══════════════════════════════════════════════════════════════════════════════
-- Adds inventory_transactions and skill_profiles to the trigger so that
-- workers who sign up after existing records exist get their auth_uid linked.

CREATE OR REPLACE FUNCTION sync_auth_uid_on_signup()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  UPDATE hive_members        SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE logbook             SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE community_posts     SET auth_uid = NEW.auth_uid WHERE author_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE inventory_items     SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE inventory_transactions SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE assets              SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE pm_assets           SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE pm_completions      SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE schedule_items      SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE skill_profiles      SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE skill_badges        SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE skill_exam_attempts SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  RETURN NEW;
END;
$$;
