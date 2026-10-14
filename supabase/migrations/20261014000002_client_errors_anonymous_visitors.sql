-- 20261014000002_client_errors_anonymous_visitors.sql
-- ============================================================================
-- SL sub-layer L1 (2026-10-14): "The platform must capture every error this page throws, with the page, the person
-- and the engine, and someone must read it."
--
-- FOUND by SL walk 2. client_errors (20260723000001) accepts inserts only TO authenticated with auth.uid() set, and the
-- utils.js capture backbone needs a Supabase client. So an ANONYMOUS visitor's errors were never recorded anywhere:
-- every learn guide, every calculator, about / feedback / privacy / terms (119 public pages, none of which loads
-- utils.js), and any production page before sign-in. The public funnel - where a new crew first meets the platform -
-- was dark to the one trail that told us, on 2026-10-14, why Ian's logbook had been dying on his iPhone for a month.
--
-- DECISION: the platform's own precedent for anonymous telemetry, constrained. analytics_events already accepts
-- inserts TO anon WITH CHECK (true); platform_feedback accepts an anonymous submit under constraints. An anonymous
-- client_errors row:
--   * claims NO identity - hive_id, worker_name and auth_uid must be NULL (auth.uid() is NULL for anon, so the
--     column default stays NULL), so it can never land in, or pollute, a hive's triage view (client_errors_read is
--     scoped to a hive's supervisors; anonymous rows are read by the owner: the postgres MCP, Grafana);
--   * carries ONLY the capture backbone's two uncaught contexts - no arbitrary call-site tags from the open internet;
--   * keeps the table's existing length caps (message 2,000, stack 4,000, context 120) and adds caps on page and
--     user_agent. The sender caps itself too: deduped, at most 20 per page load, pathname only, never the query string.
-- If abuse ever shows in the volume, the move is an edge function with the platform's rate limiter in front of this
-- insert - the same path analytics_events would take.
-- ============================================================================

DROP POLICY IF EXISTS client_errors_insert_anon ON public.client_errors;
CREATE POLICY client_errors_insert_anon ON public.client_errors
  FOR INSERT TO anon
  WITH CHECK (
    auth.uid() IS NULL
    AND hive_id IS NULL
    AND worker_name IS NULL
    AND auth_uid IS NULL
    AND context IN ('uncaught-error', 'unhandled-rejection')
    AND (page IS NULL OR char_length(page) <= 300)
    AND (user_agent IS NULL OR char_length(user_agent) <= 300)
  );

-- the bigserial id needs its sequence; grant it explicitly so the policy is not defeated by a missing default grant
GRANT USAGE ON SEQUENCE public.client_errors_id_seq TO anon;
GRANT INSERT ON public.client_errors TO anon;
