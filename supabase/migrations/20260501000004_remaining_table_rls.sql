-- 20260501000004: RLS for the 3 remaining unprotected tables
-- ===========================================================
-- Completes the auth migration coverage across all CORE_TABLES.
--
-- engineering_calcs:
--   Has hive_id + worker_name. Browser writes (currently test page,
--   will be main app). Full treatment: auth_uid column, GRANT, policies.
--
-- ai_reports:
--   Written only by edge functions (service role bypasses RLS).
--   Browser reads from hive.html and report-sender.html.
--   Needs: GRANT SELECT + hive-membership read policy.
--   No write policy from browser — service role handles inserts.
--
-- automation_log:
--   Written only by scheduled-agents and send-report-email edge functions.
--   Referenced in report-sender.html for read.
--   Same treatment as ai_reports.


-- ═══════════════════════════════════════════════════════════════════════════════
-- engineering_calcs
-- ═══════════════════════════════════════════════════════════════════════════════

ALTER TABLE engineering_calcs
  ADD COLUMN IF NOT EXISTS auth_uid uuid REFERENCES auth.users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_engineering_calcs_auth_uid
  ON engineering_calcs (auth_uid);

-- Backfill from worker_profiles
UPDATE engineering_calcs ec
SET    auth_uid = wp.auth_uid
FROM   worker_profiles wp
WHERE  ec.worker_name = wp.display_name
  AND  ec.auth_uid IS NULL;

GRANT SELECT, INSERT, UPDATE, DELETE ON engineering_calcs TO anon, authenticated;
ALTER TABLE engineering_calcs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "engineering_calcs_read"  ON engineering_calcs;
DROP POLICY IF EXISTS "engineering_calcs_write" ON engineering_calcs;

CREATE POLICY "engineering_calcs_read" ON engineering_calcs
  FOR SELECT USING (
    auth.uid() IS NOT NULL AND (
      (hive_id IS NOT NULL AND hive_id IN (
        SELECT hm.hive_id FROM hive_members hm
        WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
      ))
      OR (hive_id IS NULL AND auth_uid = auth.uid())
    )
  );

CREATE POLICY "engineering_calcs_write" ON engineering_calcs
  FOR ALL
  USING  (auth.uid() IS NOT NULL AND (auth_uid = auth.uid() OR auth_uid IS NULL))
  WITH CHECK (auth.uid() IS NOT NULL);


-- ═══════════════════════════════════════════════════════════════════════════════
-- ai_reports
-- ═══════════════════════════════════════════════════════════════════════════════
-- Inserts done by edge functions (service role key bypasses RLS).
-- Browser only reads — hive.html and report-sender.html query this table.

GRANT SELECT ON ai_reports TO anon, authenticated;
ALTER TABLE ai_reports ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "ai_reports_read" ON ai_reports;

CREATE POLICY "ai_reports_read" ON ai_reports
  FOR SELECT USING (
    auth.uid() IS NOT NULL AND hive_id IN (
      SELECT hive_id FROM hive_members
      WHERE auth_uid = auth.uid() AND status = 'active'
    )
  );


-- ═══════════════════════════════════════════════════════════════════════════════
-- automation_log
-- ═══════════════════════════════════════════════════════════════════════════════
-- Inserts done by scheduled-agents and send-report-email edge functions.
-- May be read by browser for audit/history views.

GRANT SELECT ON automation_log TO anon, authenticated;
ALTER TABLE automation_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "automation_log_read" ON automation_log;

CREATE POLICY "automation_log_read" ON automation_log
  FOR SELECT USING (
    auth.uid() IS NOT NULL AND hive_id IN (
      SELECT hive_id FROM hive_members
      WHERE auth_uid = auth.uid() AND status = 'active'
    )
  );


-- ═══════════════════════════════════════════════════════════════════════════════
-- Add engineering_calcs to trg_sync_auth_uid_on_signup
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION sync_auth_uid_on_signup()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  UPDATE hive_members           SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE logbook                SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE community_posts        SET auth_uid = NEW.auth_uid WHERE author_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE inventory_items        SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE inventory_transactions SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE assets                 SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE pm_assets              SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE pm_completions         SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE schedule_items         SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE skill_profiles         SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE skill_badges           SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE skill_exam_attempts    SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE engineering_calcs      SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  RETURN NEW;
END;
$$;
