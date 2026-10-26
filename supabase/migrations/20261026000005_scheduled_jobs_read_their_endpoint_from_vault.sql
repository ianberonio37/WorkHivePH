-- ============================================================================
-- PRODUCTION'S SCHEDULED JOBS NEVER REACHED A FUNCTION (2026-10-26)
--
-- Sixteen pg_cron jobs call edge functions with net.http_post, reading the
-- functions URL and the service key from two database parameters,
-- app.supabase_functions_url and app.service_role_key. Production has never
-- had either: every run in the last 30 days failed with
--   ERROR: unrecognized configuration parameter "app.supabase_functions_url"
-- (76 failures in 7 days, 0 successes) - the 06:00 AMC brief, the daily
-- failure-signature scan, risk scoring, PM-overdue alerts, the weekly digests,
-- predictive and ML retraining, and the daily AI evals. drain_service_outbox
-- reads the same two and refuses, so service-hailing deliveries also wait.
--
-- They cannot simply be set: on the hosted database the postgres role is not
-- a superuser, and setting a custom parameter is refused (42501, measured).
-- The supported way is Supabase Vault. One reader serves both stacks:
--   private.wh_setting(name)  ->  the database parameter app.<name> when it is
--                                 set (the local stack), else the Vault secret
--                                 named app.<name> (production)
-- in a schema the API does not expose, executable by no API role. Every job's
-- command and drain_service_outbox read through it. The secrets themselves
-- are written to Vault out of band, never into a file in this repository.
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS private;
REVOKE ALL ON SCHEMA private FROM PUBLIC;
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN EXECUTE 'REVOKE ALL ON SCHEMA private FROM anon'; END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN EXECUTE 'REVOKE ALL ON SCHEMA private FROM authenticated'; END IF;
END $$;

CREATE OR REPLACE FUNCTION private.wh_setting(p_name text)
 RETURNS text
 LANGUAGE sql
 STABLE
 SECURITY DEFINER
 SET search_path TO 'pg_catalog'
AS $function$
  SELECT coalesce(
    nullif(current_setting('app.' || p_name, true), ''),
    (SELECT s.decrypted_secret FROM vault.decrypted_secrets s WHERE s.name = 'app.' || p_name
      ORDER BY s.created_at DESC LIMIT 1)
  )
$function$;
REVOKE ALL ON FUNCTION private.wh_setting(text) FROM PUBLIC;
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN EXECUTE 'REVOKE ALL ON FUNCTION private.wh_setting(text) FROM anon'; END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN EXECUTE 'REVOKE ALL ON FUNCTION private.wh_setting(text) FROM authenticated'; END IF;
END $$;

-- every scheduled command that read the two parameters reads them through the one reader
DO $$
DECLARE j record; v_new text;
BEGIN
  FOR j IN SELECT jobid, command FROM cron.job WHERE command ~ 'current_setting\(''app\.(supabase_functions_url|service_role_key)''' LOOP
    v_new := regexp_replace(j.command,
               'current_setting\(''app\.(supabase_functions_url|service_role_key)''(\s*,\s*true)?\)',
               'private.wh_setting(''\1'')', 'g');
    PERFORM cron.alter_job(j.jobid, command := v_new);
  END LOOP;
END $$;

CREATE OR REPLACE FUNCTION public.drain_service_outbox(p_limit integer DEFAULT 20)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
DECLARE
  r       record;
  n_sent  int := 0;
  v_url   text := private.wh_setting('supabase_functions_url');
  v_key   text := private.wh_setting('service_role_key');
  v_req   bigint;
BEGIN
  -- Honest refusal: without the endpoint there is no way to deliver. Say so instead of burning attempts
  -- and dead-lettering perfectly good rows (this is exactly how 9 platform cron jobs silently died).
  IF v_url IS NULL OR v_url = '' OR v_key IS NULL OR v_key = '' THEN
    RETURN jsonb_build_object('ok', false, 'reason',
      'the functions URL / service key are set neither as app.* parameters nor in Vault on this database', 'sent', 0);
  END IF;

  FOR r IN
    SELECT id, consumer, payload
    FROM public.service_outbox
    WHERE status = 'pending' AND next_attempt_at <= now()
    ORDER BY created_at
    FOR UPDATE SKIP LOCKED
    LIMIT p_limit
  LOOP
    SELECT net.http_post(
      url     := v_url || '/' || r.consumer,
      body    := r.payload,
      headers := jsonb_build_object('Authorization', 'Bearer ' || v_key,
                                    'Content-Type',  'application/json'),
      timeout_milliseconds := 10000
    ) INTO v_req;

    UPDATE public.service_outbox
       SET status = 'in_flight', request_id = v_req, attempts = attempts + 1, updated_at = now()
     WHERE id = r.id;
    n_sent := n_sent + 1;
  END LOOP;

  RETURN jsonb_build_object('ok', true, 'sent', n_sent);
END;
$function$;
