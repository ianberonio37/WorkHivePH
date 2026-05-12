-- Phase 5c follow-up: remove the stale UPDATE public.assets reference
-- from sync_auth_uid_on_signup().
--
-- Background: Phase 5c (20260512000009_phase_5c_drop_assets.sql) dropped
-- the legacy `assets` table but missed updating this trigger function,
-- which is fired AFTER INSERT on worker_profiles. The function tries to
-- backfill auth_uid across 12 tables; one of them (public.assets) no
-- longer exists, so every new worker_profiles insert now errors out
-- with `relation "public.assets" does not exist` (code 42P01).
--
-- The fix is CREATE OR REPLACE FUNCTION with the offending line removed.
-- All other lines stay the same; asset_nodes was already in the original
-- list, so the canonical replacement is already covered.
--
-- This is purely a forward fix; the trigger definition (trg_sync_auth_uid_on_signup)
-- doesn't need to be re-created because CREATE OR REPLACE FUNCTION
-- atomically updates the function the trigger calls.
--
-- Skills consulted: data-engineer (CREATE OR REPLACE atomicity, trigger
-- function vs. trigger separation), architect (forward-fix migration
-- pattern, no schema change — only function body).

BEGIN;

CREATE OR REPLACE FUNCTION public.sync_auth_uid_on_signup()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
BEGIN
  UPDATE public.hive_members           SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE public.logbook                SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE public.inventory_items        SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE public.inventory_transactions SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  -- Phase 5c (2026-05-12) dropped public.assets — line removed in this migration.
  UPDATE public.pm_assets              SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE public.pm_completions         SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE public.schedule_items         SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE public.skill_profiles         SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE public.skill_badges           SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE public.skill_exam_attempts    SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE public.engineering_calcs      SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE public.asset_nodes            SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  RETURN NEW;
END;
$$;

COMMIT;
