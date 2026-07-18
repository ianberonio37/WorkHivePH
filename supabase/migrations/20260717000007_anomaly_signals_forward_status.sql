-- alert-hub P6 concurrent-edit fix (bug-hunt roadmap, 2026-07-17, found via live psql probe).
-- anomaly_signals.status had only a VALUE check (active/acknowledged/resolved/expired) but NO
-- forward-only TRANSITION guard. Two supervisors (or a stale realtime view) could race:
--   A resolves -> status='resolved';  B (saw it 'acknowledged') clicks Acknowledge
--   -> UPDATE ... SET status='acknowledged' WHERE id=X  -> REGRESSES the resolved alert.
-- Live-verified: resolved -> acknowledged succeeded (status ended 'acknowledged'). alert-hub's
-- client `.update(updates).eq('id', id)` has no state guard. Fix DB-side (authoritative): resolved
-- and expired are TERMINAL; reject a regression to active/acknowledged. Normal forward transitions
-- (active->acknowledged->resolved) and terminal no-ops are unaffected.
CREATE OR REPLACE FUNCTION public.anomaly_signals_forward_only_status() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status IN ('resolved', 'expired') AND NEW.status NOT IN ('resolved', 'expired') THEN
    RAISE EXCEPTION 'anomaly_signals: % is terminal; cannot regress to % (forward-only state machine)',
      OLD.status, NEW.status USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS tg_anomaly_signals_forward_status ON public.anomaly_signals;
CREATE TRIGGER tg_anomaly_signals_forward_status
  BEFORE UPDATE OF status ON public.anomaly_signals
  FOR EACH ROW EXECUTE FUNCTION public.anomaly_signals_forward_only_status();
