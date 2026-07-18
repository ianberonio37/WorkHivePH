-- Attribution-forge SWEEP (bug-hunt roadmap P3, 2026-07-18). The worker_name-pinning pattern
-- (migs 010-012) missed several CLIENT-insertable, displayed-author tables — worker_name was
-- FORGEABLE (intra-hive impersonation: a member could INSERT with another member's name).
-- Confirmed via the platform audit (feedback_worker_name_pin_gap_beyond_session3): these 6 have
-- hive_id + worker_name, are client-insertable, and RLS does NOT enforce worker_name.
-- Fix: a SHARED bind fn that derives worker_name from the caller's hive_members identity on INSERT
-- and keeps it immutable on UPDATE. Service-role inserts (auth.uid() NULL, seeders/edge fns) are
-- trusted (no-op), so batch flows are unaffected. (skill_profiles has no hive_id + is per-user own
-- profile = low forge impact → deferred to a per-table variant.)
CREATE OR REPLACE FUNCTION public.bind_worker_name_from_hive() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE v_name text;
BEGIN
  IF auth.uid() IS NULL THEN RETURN NEW; END IF;                     -- service-role / seeder: trust the batch
  IF TG_OP = 'UPDATE' THEN NEW.worker_name := OLD.worker_name; RETURN NEW; END IF;  -- attribution immutable
  IF NEW.hive_id IS NOT NULL THEN
    SELECT worker_name INTO v_name FROM public.hive_members
      WHERE auth_uid = auth.uid() AND hive_id = NEW.hive_id AND status = 'active' LIMIT 1;
    IF v_name IS NOT NULL THEN NEW.worker_name := v_name; END IF;
  END IF;
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS tg_bind_wname_marketplace_sellers ON public.marketplace_sellers;
CREATE TRIGGER tg_bind_wname_marketplace_sellers BEFORE INSERT OR UPDATE ON public.marketplace_sellers
  FOR EACH ROW EXECUTE FUNCTION public.bind_worker_name_from_hive();
DROP TRIGGER IF EXISTS tg_bind_wname_fault_knowledge ON public.fault_knowledge;
CREATE TRIGGER tg_bind_wname_fault_knowledge BEFORE INSERT OR UPDATE ON public.fault_knowledge
  FOR EACH ROW EXECUTE FUNCTION public.bind_worker_name_from_hive();
DROP TRIGGER IF EXISTS tg_bind_wname_pm_knowledge ON public.pm_knowledge;
CREATE TRIGGER tg_bind_wname_pm_knowledge BEFORE INSERT OR UPDATE ON public.pm_knowledge
  FOR EACH ROW EXECUTE FUNCTION public.bind_worker_name_from_hive();
DROP TRIGGER IF EXISTS tg_bind_wname_skill_knowledge ON public.skill_knowledge;
CREATE TRIGGER tg_bind_wname_skill_knowledge BEFORE INSERT OR UPDATE ON public.skill_knowledge
  FOR EACH ROW EXECUTE FUNCTION public.bind_worker_name_from_hive();
DROP TRIGGER IF EXISTS tg_bind_wname_project_roles ON public.project_roles;
CREATE TRIGGER tg_bind_wname_project_roles BEFORE INSERT OR UPDATE ON public.project_roles
  FOR EACH ROW EXECUTE FUNCTION public.bind_worker_name_from_hive();
DROP TRIGGER IF EXISTS tg_bind_wname_shared_voice_notes ON public.shared_voice_notes;
CREATE TRIGGER tg_bind_wname_shared_voice_notes BEFORE INSERT OR UPDATE ON public.shared_voice_notes
  FOR EACH ROW EXECUTE FUNCTION public.bind_worker_name_from_hive();
