-- 20260713000005_projects_attribution_pin.sql
--
-- projects attribution spoof (MED — project accountability) — bug-hunt 2026-07-13, cross-page sibling sweep.
--
-- The projects_hive_rw policy (FOR ALL) WITH CHECK is `(auth.uid() IS NOT NULL AND hive_id IN
-- user_hive_ids())` — it gates the hive but does NOT pin auth_uid on INSERT. LIVE-CONFIRMED (rolled
-- back): bryangarcia (Baguio worker) INSERTed a Baguio project with auth_uid=<pablo> and
-- owner_name='Leandro Marquez' -> 201, storing the spoofed identity. Same class as asset_nodes P5-04
-- (mig …003) + logbook (mig …004); the auth_uid-attribution rule (feedback_authuid_attribution_on_every_write)
-- was applied to those but projects was a siblings-skipped miss.
--
-- FIX: bind auth_uid = auth.uid() server-side on member INSERTs (the authoritative identity). owner_name
-- is left app-managed — projects legitimately ASSIGN an owner who may differ from the creator, so it is
-- not force-bound; the security-relevant identity (auth_uid) is what an audit/ownership check trusts.
-- A service-role/seeder batch (auth.uid() NULL) keeps its supplied values.

BEGIN;

CREATE OR REPLACE FUNCTION public.bind_projects_submitter() RETURNS trigger
  LANGUAGE plpgsql SECURITY DEFINER SET search_path TO 'public' AS $fn$
BEGIN
  IF auth.uid() IS NOT NULL THEN
    NEW.auth_uid := auth.uid();
  END IF;
  RETURN NEW;
END; $fn$;
DROP TRIGGER IF EXISTS trg_bind_submitter_projects ON public.projects;
CREATE TRIGGER trg_bind_submitter_projects BEFORE INSERT ON public.projects
  FOR EACH ROW EXECUTE FUNCTION public.bind_projects_submitter();

COMMIT;
