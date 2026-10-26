-- 20261026000015_which_model_provider_is_failing.sql
--
-- A FAILING MODEL PROVIDER REACHED NO ONE (OWN dependency + AI failure-mode lenses, 2026-10-26). Every model call records
-- each provider slot it asked and how that slot answered - ai_cost_log.providers_tried, entries like 'groq/<model>=429',
-- 'voyage/<model>=401', 'bge-local/<model>=threw', 'openrouter/<model>=length' - and nothing read them: not the console,
-- not a dashboard. Production's Voyage key was dead for an unknown time (every call 401, every logbook embed a 500) and the
-- local embedder had been down four days (1,643 'threw' slots) before anyone looked.
--
-- founder_model_providers(p_days) gives the operator console, for a platform admin only (K5), per provider over the
-- window: how many slots were asked, how many served (a 2xx), how many failed and by what (rate limit, server error,
-- timeout, auth refused, an answer the chain could not use, threw), and the last failure. Totals, never rows (K4).

CREATE OR REPLACE FUNCTION public.founder_model_providers(p_days integer DEFAULT 1)
RETURNS TABLE (
  provider      text,
  asked         bigint,
  served        bigint,
  failed        bigint,
  rate_limited  bigint,
  server_error  bigint,
  timed_out     bigint,
  refused_auth  bigint,
  unusable      bigint,
  threw         bigint,
  last_failure  text,
  last_failed_at timestamptz
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
  IF NOT public.is_platform_admin() THEN
    RAISE EXCEPTION 'Only a platform admin can read the model providers' USING ERRCODE = '42501';
  END IF;
  RETURN QUERY
  WITH slots AS (
    SELECT split_part(t, '/', 1) AS prov,
           split_part(t, '=', array_length(string_to_array(t, '='), 1)) AS outcome,
           t AS entry, c.created_at
      FROM public.ai_cost_log c, unnest(c.providers_tried) t
     WHERE c.created_at > now() - make_interval(days => least(greatest(coalesce(p_days, 1), 1), 30))
       AND t LIKE '%/%=%'
  )
  SELECT s.prov,
         count(*),
         count(*) FILTER (WHERE s.outcome ~ '^2\d\d$'),
         count(*) FILTER (WHERE s.outcome !~ '^2\d\d$'),
         count(*) FILTER (WHERE s.outcome = '429'),
         count(*) FILTER (WHERE s.outcome ~ '^5\d\d$'),
         count(*) FILTER (WHERE s.outcome IN ('timeout', 'abort')),
         count(*) FILTER (WHERE s.outcome IN ('401', '403')),
         count(*) FILTER (WHERE s.outcome IN ('empty', 'length', 'reasoning-only', 'bad-shape', '400', '404', '413', '422')),
         count(*) FILTER (WHERE s.outcome = 'threw'),
         (array_agg(s.entry ORDER BY s.created_at DESC) FILTER (WHERE s.outcome !~ '^2\d\d$'))[1],
         max(s.created_at) FILTER (WHERE s.outcome !~ '^2\d\d$')
    FROM slots s
   GROUP BY s.prov
   ORDER BY count(*) FILTER (WHERE s.outcome !~ '^2\d\d$') DESC, s.prov;
END
$$;
REVOKE ALL ON FUNCTION public.founder_model_providers(integer) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.founder_model_providers(integer) TO authenticated;
