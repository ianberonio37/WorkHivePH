-- 20260713000004_logbook_attribution_pin.sql
--
-- logbook attribution spoof (MED — maintenance-record integrity) — bug-hunt 2026-07-13, logbook.html P5.
--
-- logbook_insert WITH CHECK gates hive_id (a member can only insert into a hive they belong to) but
-- does NOT pin auth_uid on the hive-scoped branch, so within their OWN hive a member could log a
-- maintenance entry falsely attributed to ANOTHER worker's auth_uid + worker_name. LIVE-CONFIRMED
-- (rolled back): bryangarcia (Baguio worker) INSERTed a Baguio logbook row with auth_uid=<pablo> and
-- worker_name='Leandro Marquez' -> 201. For a maintenance CMMS the logbook author is load-bearing
-- (who did/observed the work + the audit trail), so false attribution is a real integrity gap.
--
-- Same class as asset_nodes P5-04 (mig 20260713000003). FIX: bind auth_uid + worker_name server-side
-- on member INSERTs, mirroring bind_asset_nodes_submitter (feedback_authuid_attribution_on_every_write).
-- No display churn: 0 existing member rows have a worker_name that differs from their hive_members name.
-- A service-role/seeder batch (auth.uid() NULL) keeps its values; a personal null-hive log keeps its name.

BEGIN;

CREATE OR REPLACE FUNCTION public.bind_logbook_submitter() RETURNS trigger
  LANGUAGE plpgsql SECURITY DEFINER SET search_path TO 'public' AS $fn$
DECLARE v_name text;
BEGIN
  IF auth.uid() IS NOT NULL THEN
    NEW.auth_uid := auth.uid();
    IF NEW.hive_id IS NOT NULL THEN
      SELECT worker_name INTO v_name FROM public.hive_members
        WHERE auth_uid = auth.uid() AND hive_id = NEW.hive_id AND status = 'active' LIMIT 1;
      IF v_name IS NOT NULL THEN NEW.worker_name := v_name; END IF;
    END IF;
  END IF;
  RETURN NEW;
END; $fn$;
DROP TRIGGER IF EXISTS trg_bind_submitter_logbook ON public.logbook;
CREATE TRIGGER trg_bind_submitter_logbook BEFORE INSERT ON public.logbook
  FOR EACH ROW EXECUTE FUNCTION public.bind_logbook_submitter();

COMMIT;
