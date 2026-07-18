-- 20260717000002_analytics_events_attribution_pin.sql
--
-- analytics_events attribution pin (LOW — telemetry integrity) — FULLSTACK_COMPONENT_LIBRARY
-- Layer D census D-P3 (2026-07-17): INSERT policy CHECK=`true` with an auth_uid column means an
-- authenticated client can log telemetry events attributed to ANY user (skews per-user analytics;
-- same class as platform_feedback, mig 20260717000001, lowest severity of the family).
-- Anonymous events stay by design (auth.uid() NULL rows pass through). Write volume is already
-- quota-capped (Q2/Q5 gates). Mirror of the bind_* family (migs 20260713000003…20260717000001).

BEGIN;

CREATE OR REPLACE FUNCTION public.bind_analytics_events_submitter() RETURNS trigger
  LANGUAGE plpgsql SECURITY DEFINER SET search_path TO 'public' AS $fn$
BEGIN
  IF auth.uid() IS NULL THEN RETURN NEW; END IF;  -- anon telemetry / service-role: pass through
  NEW.auth_uid := auth.uid();                     -- authed events are attributed honestly
  RETURN NEW;
END;
$fn$;

DROP TRIGGER IF EXISTS trg_bind_analytics_events_submitter ON public.analytics_events;
CREATE TRIGGER trg_bind_analytics_events_submitter
  BEFORE INSERT ON public.analytics_events
  FOR EACH ROW EXECUTE FUNCTION public.bind_analytics_events_submitter();

COMMIT;
