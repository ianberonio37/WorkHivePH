-- 20260731000008_sweep_reads_d9_knobs.sql
--
-- Make the D9 knobs REAL. 20260731000007 created them; a knob nobody reads is write-only configuration, so
-- this points the sweep at the resolver. `sweep_service_broadcasts` owns all TTL mechanics (no trigger
-- sprawl), which is exactly why it is the right and only consumer to change.
--
-- READ FROM THE MIGRATION, NOT FROM prosrc. Every line below that is not a knob lookup is byte-identical to
-- 20260728000042: the three passes, their order, the journal note's wording, the GET DIAGNOSTICS counters
-- and the jsonb return. Earlier today I rebuilt a different function from THREE TRUNCATED substring() reads
-- of prosrc and silently dropped a cast, re-opening a bug closed a month before
-- ([[feedback_i_rebuilt_a_guard_from_a_partial_read]]). The source of truth for a function body is the
-- migration that defines it.
--
-- PER-ROW, NOT PER-SWEEP. The knob is resolved against EACH request's own hive, because the whole point is
-- that a sparse rural hive can widen further and wait longer than a dense urban one. A NULL hive_id (a
-- consumer-segment hail with no hive) resolves to the platform default, which is what service_knob() returns
-- for an unknown hive anyway — so the solo path needs no special case.

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
  UPDATE public.service_requests r
     SET offer_ttl_expires_at = now() + (
           CASE WHEN r.mode = 'instant'
                THEN public.service_knob(r.hive_id, 'instant_ttl_seconds')
                ELSE public.service_knob(r.hive_id, 'quote_ttl_seconds')
           END * interval '1 second')
   WHERE r.status = 'broadcasting' AND r.offer_ttl_expires_at IS NULL;
  GET DIAGNOSTICS n_stamped = ROW_COUNT;

  -- 2. widen the search for un-accepted instant hails (radius doubles, capped by the hive's own ceiling)
  WITH widened AS (
    UPDATE public.service_requests r
       SET broadcast_radius_m = least(r.broadcast_radius_m * 2,
                                      public.service_knob(r.hive_id, 'broadcast_radius_max_m')),
           broadcast_round = r.broadcast_round + 1,
           offer_ttl_expires_at = now() + (public.service_knob(r.hive_id, 'instant_ttl_seconds')
                                           * interval '1 second'),
           updated_at = now()
     WHERE r.status = 'broadcasting' AND r.mode = 'instant'
       AND r.offer_ttl_expires_at < now()
       AND r.broadcast_round < public.service_knob(r.hive_id, 'broadcast_widen_rounds')
     RETURNING id, broadcast_radius_m, broadcast_round
  )
  INSERT INTO public.service_job_events (request_id, actor_role, from_state, to_state, note)
  SELECT id, 'system', 'broadcasting', 'broadcasting',
         'search widened to ' || round(broadcast_radius_m / 1000.0, 1) || ' km (round ' || broadcast_round || ')'
    FROM widened;
  GET DIAGNOSTICS n_widened = ROW_COUNT;

  -- 3. expire what the widened search still could not place
  UPDATE public.service_requests r
     SET status = 'expired', updated_at = now()
   WHERE r.status = 'broadcasting' AND r.offer_ttl_expires_at < now()
     AND (r.mode = 'quote' OR r.broadcast_round >= public.service_knob(r.hive_id, 'broadcast_widen_rounds'));
  GET DIAGNOSTICS n_expired = ROW_COUNT;

  RETURN jsonb_build_object('stamped', n_stamped, 'widened', n_widened, 'expired', n_expired);
END;
$function$;

COMMENT ON FUNCTION public.sweep_service_broadcasts() IS
  'Per-minute hail lifecycle sweep (SERVICE_HAILING_ROADMAP.md P4): stamps TTLs on fresh broadcasts, widens '
  'an un-accepted instant hail''s radius (doubled, capped, journaled as a system timeline note), then expires '
  'what remains. Every timing/reach constant is now a PER-HIVE D9 knob resolved through service_knob(), so a '
  'sparse hive can wait longer and reach further than a dense one; a hive with no row is on the platform '
  'defaults. Mirrors expire_stale_parts_recommendations()/amc_expire_stale().';

REVOKE ALL ON FUNCTION public.sweep_service_broadcasts() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.sweep_service_broadcasts() TO service_role;
