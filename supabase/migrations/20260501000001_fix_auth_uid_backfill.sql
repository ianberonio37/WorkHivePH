-- EMERGENCY FIX: Re-run auth_uid backfill for all tables
-- ========================================================
-- The C3 migration backfill ran when worker_profiles was empty (no accounts existed).
-- Workers who signed up AFTER the migration had auth_uid = NULL in all their records.
-- C4 RLS then made their data invisible because NULL != auth.uid().
--
-- This migration:
-- 1. Re-runs the backfill now that worker_profiles has real entries
-- 2. Adds a trigger so future signups immediately link all existing records

-- ── Re-run backfill for all affected tables ───────────────────────────────────

UPDATE hive_members hm
SET    auth_uid = wp.auth_uid
FROM   worker_profiles wp
WHERE  hm.worker_name = wp.display_name AND hm.auth_uid IS NULL;

UPDATE logbook l
SET    auth_uid = wp.auth_uid
FROM   worker_profiles wp
WHERE  l.worker_name = wp.display_name AND l.auth_uid IS NULL;

UPDATE community_posts cp
SET    auth_uid = wp.auth_uid
FROM   worker_profiles wp
WHERE  cp.author_name = wp.display_name AND cp.auth_uid IS NULL;

-- community_xp excluded: auth_uid column was never added to this table

UPDATE inventory_items ii
SET    auth_uid = wp.auth_uid
FROM   worker_profiles wp
WHERE  ii.worker_name = wp.display_name AND ii.auth_uid IS NULL;

UPDATE assets a
SET    auth_uid = wp.auth_uid
FROM   worker_profiles wp
WHERE  a.worker_name = wp.display_name AND a.auth_uid IS NULL;

UPDATE pm_assets pa
SET    auth_uid = wp.auth_uid
FROM   worker_profiles wp
WHERE  pa.worker_name = wp.display_name AND pa.auth_uid IS NULL;

UPDATE pm_completions pc
SET    auth_uid = wp.auth_uid
FROM   worker_profiles wp
WHERE  pc.worker_name = wp.display_name AND pc.auth_uid IS NULL;

UPDATE schedule_items si
SET    auth_uid = wp.auth_uid
FROM   worker_profiles wp
WHERE  si.worker_name = wp.display_name AND si.auth_uid IS NULL;

UPDATE skill_badges sb
SET    auth_uid = wp.auth_uid
FROM   worker_profiles wp
WHERE  sb.worker_name = wp.display_name AND sb.auth_uid IS NULL;

UPDATE skill_exam_attempts sea
SET    auth_uid = wp.auth_uid
FROM   worker_profiles wp
WHERE  sea.worker_name = wp.display_name AND sea.auth_uid IS NULL;

-- ── Trigger: auto-link data when a new worker_profiles row is inserted ─────────
-- Fires when a worker signs up — immediately sets auth_uid on all their
-- existing records so data becomes visible in the same session.

CREATE OR REPLACE FUNCTION sync_auth_uid_on_signup()
RETURNS trigger AS $$
BEGIN
  UPDATE hive_members        SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE logbook             SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE community_posts     SET auth_uid = NEW.auth_uid WHERE author_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE inventory_items     SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE assets              SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE pm_assets           SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE pm_completions      SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE schedule_items      SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE skill_badges        SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE skill_exam_attempts SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trg_sync_auth_uid_on_signup ON worker_profiles;
CREATE TRIGGER trg_sync_auth_uid_on_signup
  AFTER INSERT ON worker_profiles
  FOR EACH ROW EXECUTE FUNCTION sync_auth_uid_on_signup();
