-- ─────────────────────────────────────────────────────────────────────────────
-- SERVICE HAILING P4: the broadcast TTL + radius-expansion sweep (§3c verdict #2).
--
-- A hail that nobody accepts must not sit "broadcasting" forever — Grab's model
-- (sequential fallback to farther partners) adapted to our broadcast: widen the
-- radius twice, then expire honestly. THE PRECEDENT IS REUSED, NOT REINVENTED:
-- expire_stale_parts_recommendations() / amc_expire_stale() — same function
-- shape, same cron idiom; this one runs every minute because hail TTLs are
-- minutes, not days.
--
-- The sweep is the SINGLE owner of TTL mechanics (no trigger sprawl):
--   pass 1: a broadcasting row with NULL offer_ttl_expires_at gets its shelf
--           life (instant: +2 min; quote: +24 h) — NULL means "not yet stamped",
--           and stamping is idempotent and journal-free;
--   widen:  an instant broadcast past its TTL with broadcast_round < 2 doubles
--           its radius (capped 100 km), bumps the round, re-arms the TTL, and
--           journals a system note so the client's timeline shows the search
--           widening rather than silence;
--   expire: past-TTL rows out of rounds (instant) or past their 24 h (quote)
--           go to 'expired' — the status change itself is journaled by
--           trg_journal_service_request, and trg_sync_provider_availability
--           has nothing to do (no provider was matched).
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE public.service_requests
  ADD COLUMN IF NOT EXISTS broadcast_round smallint NOT NULL DEFAULT 0;

CREATE OR REPLACE FUNCTION public.sweep_service_broadcasts()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  n_stamped integer := 0;
  n_widened integer := 0;
  n_expired integer := 0;
BEGIN
  -- 1. stamp shelf lives (NULL TTL = not yet stamped, never = immortal)
  UPDATE public.service_requests
     SET offer_ttl_expires_at = now() + CASE WHEN mode = 'instant' THEN interval '2 minutes' ELSE interval '24 hours' END
   WHERE status = 'broadcasting' AND offer_ttl_expires_at IS NULL;
  GET DIAGNOSTICS n_stamped = ROW_COUNT;

  -- 2. widen the search for un-accepted instant hails (twice, radius capped 100 km)
  WITH widened AS (
    UPDATE public.service_requests
       SET broadcast_radius_m = least(broadcast_radius_m * 2, 100000),
           broadcast_round = broadcast_round + 1,
           offer_ttl_expires_at = now() + interval '2 minutes',
           updated_at = now()
     WHERE status = 'broadcasting' AND mode = 'instant'
       AND offer_ttl_expires_at < now() AND broadcast_round < 2
     RETURNING id, broadcast_radius_m, broadcast_round
  )
  INSERT INTO public.service_job_events (request_id, actor_role, from_state, to_state, note)
  SELECT id, 'system', 'broadcasting', 'broadcasting',
         'search widened to ' || round(broadcast_radius_m / 1000.0, 1) || ' km (round ' || broadcast_round || ')'
    FROM widened;
  GET DIAGNOSTICS n_widened = ROW_COUNT;

  -- 3. expire what the widened search still could not place
  UPDATE public.service_requests
     SET status = 'expired', updated_at = now()
   WHERE status = 'broadcasting' AND offer_ttl_expires_at < now()
     AND (mode = 'quote' OR broadcast_round >= 2);
  GET DIAGNOSTICS n_expired = ROW_COUNT;

  RETURN jsonb_build_object('stamped', n_stamped, 'widened', n_widened, 'expired', n_expired);
END;
$function$;

COMMENT ON FUNCTION public.sweep_service_broadcasts() IS
  'Per-minute hail lifecycle sweep (SERVICE_HAILING_ROADMAP.md P4): stamps TTLs on fresh '
  'broadcasts (instant 2 min / quote 24 h), widens an un-accepted instant hail''s radius twice '
  '(doubled, capped 100 km, journaled as a system timeline note), then expires what remains. '
  'Mirrors expire_stale_parts_recommendations()/amc_expire_stale() — one platform pattern for '
  'rows with a shelf life.';

REVOKE ALL ON FUNCTION public.sweep_service_broadcasts() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.sweep_service_broadcasts() TO service_role;

SELECT cron.unschedule('service-broadcast-sweep-1min')
 WHERE EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'service-broadcast-sweep-1min');

SELECT cron.schedule(
  'service-broadcast-sweep-1min',
  '* * * * *',
  $cron$SELECT public.sweep_service_broadcasts();$cron$
);
