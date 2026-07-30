-- ─────────────────────────────────────────────────────────────────────────────
-- Service job → logbook writeback (SERVICE_HAILING_ROADMAP.md P5, industrial
-- moat #2): a COMPLETED hailed job becomes a logbook entry in the CLIENT's hive,
-- so the machine's service history includes outside work — the record no generic
-- marketplace can produce. Consumer (hive-less) jobs skip — there is no hive
-- logbook to write to. The entry is attributed to the client worker (who
-- commissioned the job) with the provider named in the action text; id follows
-- the platform's log-<hex> convention.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.writeback_service_job_to_logbook()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_provider text;
  v_title text;
BEGIN
  IF NEW.status <> 'completed' OR OLD.status = 'completed' OR NEW.hive_id IS NULL THEN
    RETURN NEW;
  END IF;
  SELECT display_name INTO v_provider FROM public.service_providers WHERE id = NEW.matched_provider_id;
  SELECT COALESCE(c.name, LEFT(NEW.custom_scope, 80), 'Service job')
    INTO v_title FROM (SELECT 1) _x
    LEFT JOIN public.service_catalog c ON c.id = NEW.catalog_item_id;
  INSERT INTO public.logbook (id, worker_name, date, machine, category, problem, action, status, hive_id, maintenance_type)
  VALUES (
    'log-' || substr(md5(NEW.id::text || 'svc-writeback'), 1, 12),
    COALESCE(NEW.client_worker_name, 'Service desk'),
    now(),
    -- the composer prefixes custom scope with [ASSET-TAG] on asset-context hails — reuse it
    NULLIF(substring(COALESCE(NEW.custom_scope, '') from '^\[([^\]]{1,60})\]'), ''),
    'CM',
    v_title,
    'Outside service provider ' || COALESCE(v_provider, 'unknown') || ' completed the hailed job'
      || COALESCE(' at ' || NULLIF(NEW.address, ''), '') || '. (service request ' || NEW.id || ')',
    'Closed',
    NEW.hive_id,
    'Corrective'
  )
  ON CONFLICT (id) DO NOTHING; -- idempotent: a re-fired transition never duplicates the entry
  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_service_job_logbook_writeback ON public.service_requests;
CREATE TRIGGER trg_service_job_logbook_writeback
  AFTER UPDATE OF status ON public.service_requests
  FOR EACH ROW EXECUTE FUNCTION public.writeback_service_job_to_logbook();
