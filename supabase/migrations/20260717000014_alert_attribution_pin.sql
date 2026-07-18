-- P3/attribution forge (bug-hunt roadmap, 2026-07-18, found live in alert-hub). Two accountability
-- fields were client-set and NOT identity-pinned. RLS only checks the caller is a member/supervisor of
-- the hive, never that the stamped name = the caller:
--   alert_dismissals.actor  — ANY active member can ack/snooze/dismiss an alert stamped with ANOTHER
--                             member's name (broad forge; the actor is written to the audit trail).
--   anomaly_signals.acknowledged_by / resolved_by — a supervisor can stamp ANOTHER supervisor's name
--                             on an acknowledge/resolve (narrower — supervisor-only — but still a forge
--                             of a safety-alert accountability record).
-- Same class as the worker_name sweep (migs 000010/000011) but the columns are named actor/
-- acknowledged_by/resolved_by, so the worker_name-scoped sweep missed them. Fix: derive the attribution
-- from the caller's hive_members identity on write. Service-role/seeder (auth.uid() NULL) is trusted.

-- alert_dismissals.actor — set on every ack/snooze/dismiss upsert → derive on INSERT and UPDATE.
CREATE OR REPLACE FUNCTION public.bind_alert_dismissal_actor() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE v_name text;
BEGIN
  IF auth.uid() IS NULL THEN RETURN NEW; END IF;                 -- service-role / seeder: trust the batch
  IF NEW.hive_id IS NOT NULL THEN
    SELECT worker_name INTO v_name FROM public.hive_members
      WHERE auth_uid = auth.uid() AND hive_id = NEW.hive_id AND status = 'active' LIMIT 1;
    IF v_name IS NOT NULL THEN NEW.actor := v_name; END IF;
  END IF;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS tg_bind_alert_dismissal_actor ON public.alert_dismissals;
CREATE TRIGGER tg_bind_alert_dismissal_actor BEFORE INSERT OR UPDATE ON public.alert_dismissals
  FOR EACH ROW EXECUTE FUNCTION public.bind_alert_dismissal_actor();

-- anomaly_signals.acknowledged_by / resolved_by — pin to the caller whenever the field is being SET
-- to a non-null value this write (leave untouched otherwise, so a status-only update doesn't clear it).
CREATE OR REPLACE FUNCTION public.bind_anomaly_signal_attribution() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE v_name text;
BEGIN
  IF auth.uid() IS NULL THEN RETURN NEW; END IF;                 -- service-role / rules engine: trusted
  IF NEW.hive_id IS NULL THEN RETURN NEW; END IF;
  SELECT worker_name INTO v_name FROM public.hive_members
    WHERE auth_uid = auth.uid() AND hive_id = NEW.hive_id AND status = 'active' LIMIT 1;
  IF v_name IS NULL THEN RETURN NEW; END IF;
  IF NEW.acknowledged_by IS NOT NULL AND NEW.acknowledged_by IS DISTINCT FROM OLD.acknowledged_by THEN
    NEW.acknowledged_by := v_name;
  END IF;
  IF NEW.resolved_by IS NOT NULL AND NEW.resolved_by IS DISTINCT FROM OLD.resolved_by THEN
    NEW.resolved_by := v_name;
  END IF;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS tg_bind_anomaly_signal_attribution ON public.anomaly_signals;
CREATE TRIGGER tg_bind_anomaly_signal_attribution BEFORE UPDATE ON public.anomaly_signals
  FOR EACH ROW EXECUTE FUNCTION public.bind_anomaly_signal_attribution();
