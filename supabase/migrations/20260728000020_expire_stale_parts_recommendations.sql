-- ─────────────────────────────────────────────────────────────────────────────
-- Nothing ever moved a parts recommendation to 'expired'. Give the state a producer.
--
-- FROM THE AH14 WALK (2026-07-28, ASSET_HUB_DEEPWALK_EXPANSION_ROADMAP §10):
-- `parts_staging_recommendations.status` has allowed 'expired' since the table was created —
--     CHECK (status = ANY (ARRAY['pending','accepted','dismissed','expired']))
-- and NOTHING has ever written it. No job, no trigger, no sweep. So a recommendation stays
-- 'pending' forever and `status = 'pending'` does not mean "current": measured during the walk,
-- all 3 rows carrying an expiry had already passed it and were still pending.
--
-- AH14 fixed the two SURFACES to stop acting on a stale recommendation (asset-hub marks it expired
-- and refuses the write; alert-hub filters it out of the attention feed). This closes the other
-- half — the DATA saying what it is, rather than every future reader having to remember to compare
-- against now(). A state in a CHECK constraint with no producer is the same shape as AHK3's
-- "a workflow state with no rows is a state nobody has walked", one layer down: here the state was
-- not merely unseeded, it was unreachable.
--
-- THE PRECEDENT IS REUSED, NOT REINVENTED: amc_expire_stale() + the amc-expire-stale-0555pht cron
-- job do exactly this for amc_briefings. Same function shape, same schedule idiom, so there is one
-- pattern on this platform for "a row with a shelf life", not two.
--
-- Scheduled 05:50 PHT — five minutes ahead of the 05:55 AMC sweep and well before the 06:00 brief,
-- so the morning's first read of the attention feed already sees a truthful set.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.expire_stale_parts_recommendations()
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  n integer;
BEGIN
  -- Only 'pending' moves. An accepted or dismissed recommendation has been ACTED on, and
  -- overwriting that with 'expired' would destroy the record of a human decision.
  --
  -- `expires_at IS NOT NULL` is deliberate: a row with no expiry never declared a shelf life,
  -- which is not the same as one whose shelf life has run out. Both surfaces already treat NULL
  -- as live, and this must agree with them or the data and the UI would disagree about the same row.
  UPDATE public.parts_staging_recommendations
     SET status = 'expired'
   WHERE status = 'pending'
     AND expires_at IS NOT NULL
     AND now() > expires_at;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n;
END;
$function$;

COMMENT ON FUNCTION public.expire_stale_parts_recommendations() IS
  'Moves pending parts_staging_recommendations past their expires_at to status=''expired''. The '
  'state has been in the table CHECK since creation with no producer, so "pending" did not mean '
  '"current" — measured 2026-07-28, every row carrying an expiry had already passed it and was '
  'still pending. Leaves accepted/dismissed alone (those record a human decision) and leaves a '
  'NULL expires_at alone (no shelf life declared is not the same as expired). Mirrors '
  'amc_expire_stale(). AH14.';

REVOKE ALL ON FUNCTION public.expire_stale_parts_recommendations() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.expire_stale_parts_recommendations() TO service_role;

-- 05:50 PHT = 21:50 UTC. Ahead of amc-expire-stale (21:55) and the 06:00 brief, so the first
-- read of the morning already sees a truthful set.
SELECT cron.unschedule('parts-recs-expire-0550pht')
 WHERE EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'parts-recs-expire-0550pht');

SELECT cron.schedule(
  'parts-recs-expire-0550pht',
  '50 21 * * *',
  $cron$SELECT public.expire_stale_parts_recommendations();$cron$
);
