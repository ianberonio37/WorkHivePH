-- P3/attribution (bug-hunt roadmap, 2026-07-18, skillmatrix). The LAST deferred worker_name-forge item
-- from the sweep (mig 000011 skipped it because skill_profiles has NO hive_id — per-user own profile).
-- RLS (skill_profiles_write WITH CHECK auth_uid = auth.uid()) self-scopes the ROW, but worker_name is
-- still client-set — a user can display a FAKE name on their own skill profile (self-misrepresentation
-- in the skill matrix). Fix with the auth_uid variant of the bind pattern: derive worker_name from the
-- caller's canonical identity (worker_profiles.display_name) on every write. Service-role/seeder no-op.
CREATE OR REPLACE FUNCTION public.bind_skill_profile_worker_name() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE v_name text;
BEGIN
  IF auth.uid() IS NULL THEN RETURN NEW; END IF;                 -- service-role / seeder: trust the batch
  SELECT display_name INTO v_name FROM public.worker_profiles WHERE auth_uid = auth.uid() LIMIT 1;
  IF v_name IS NOT NULL THEN NEW.worker_name := v_name; END IF;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS tg_bind_skill_profile_worker_name ON public.skill_profiles;
CREATE TRIGGER tg_bind_skill_profile_worker_name BEFORE INSERT OR UPDATE ON public.skill_profiles
  FOR EACH ROW EXECUTE FUNCTION public.bind_skill_profile_worker_name();
