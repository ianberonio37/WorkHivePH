-- 20261027000002_an_unreachable_provider_did_not_answer.sql
--
-- AN UNREACHABLE EMBEDDER WAS COUNTED AS NOTHING (OWN55 walk, 2026-10-27). The embedding chain recorded a refused or
-- unreachable provider as '<provider>/<model>=101' - three digits from the transport error's "(os error 101)" read as an
-- HTTP status - and a timeout as '=threw', because Deno says "Signal timed out." and the classifier looked for "timeout".
-- embedding-chain.ts now records '=unreachable' and '=timeout'. founder_model_providers had no bucket for 'unreachable'
-- (a '101' had fallen into none either): the slot counted as failed with no reason beside it. It belongs where the
-- console says "did not answer" - the provider never answered - so it joins 'threw'. Same signature, same grants.

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
         count(*) FILTER (WHERE s.outcome IN ('threw', 'unreachable')),
         (array_agg(s.entry ORDER BY s.created_at DESC) FILTER (WHERE s.outcome !~ '^2\d\d$'))[1],
         max(s.created_at) FILTER (WHERE s.outcome !~ '^2\d\d$')
    FROM slots s
   GROUP BY s.prov
   ORDER BY count(*) FILTER (WHERE s.outcome !~ '^2\d\d$') DESC, s.prov;
END
$$;
REVOKE ALL ON FUNCTION public.founder_model_providers(integer) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.founder_model_providers(integer) TO authenticated;
