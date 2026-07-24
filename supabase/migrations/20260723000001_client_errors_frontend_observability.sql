-- 20260723000001_client_errors_frontend_observability.sql
-- ============================================================================
-- D21 · FRONTEND OBSERVABILITY — light up the dark half.
--
-- FOUND (2026-07-23, §12 dimension-expansion flywheel loop 5): PLATFORM_DEEPWALK_
-- FLYWHEEL_ROADMAP ranks "frontend RUM/error-capture is dark" as an unowned gap.
-- Confirmed by reading the code: utils.js ALREADY has the capture backbone —
-- window.whLogError() as the single sink + global 'error'/'unhandledrejection'
-- listeners (the uncaught net, platform-wide, zero per-page code) — but the sink
-- only calls console.error(). Its own comment marks it the single upgrade point:
--   "To add real aggregation later (Sentry / a /ingest endpoint / logEvent) edit
--    THIS ONE function — every surface upgrades at once, zero re-chipping."
-- So a field tech's production crash is a console line NOBODY EVER SEES.
--
-- DECISION: keep it IN-PLATFORM (a table), not an external error service —
-- honours "build our own, minimize dependencies" + "all work stays local".
-- No new infra, no DSN, no third party receives our users' error payloads, and
-- it is queryable with the tooling/RLS we already run.
--
-- PRIVACY: this table stores DIAGNOSTICS ONLY. The client sender is forbidden
-- from including form values / row payloads / tokens; it sends the error message,
-- a truncated stack, the page path, and a coarse UA. hive_id + worker_name are
-- included for triage scope (which hive is hurting), matching every other
-- hive-scoped table. Stack + message are length-capped client-side AND here.
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.client_errors (
  id           bigserial PRIMARY KEY,
  hive_id      uuid        REFERENCES public.hives(id) ON DELETE CASCADE,
  worker_name  text,
  auth_uid     uuid        DEFAULT auth.uid(),      -- attribution on every client write
  context      text        NOT NULL,                -- 'uncaught-error' | 'unhandled-rejection' | a call-site tag
  message      text        NOT NULL,
  stack        text,
  page         text,                                -- location.pathname only (never the query string: it can carry ids)
  user_agent   text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT client_errors_message_len CHECK (char_length(message) <= 2000),
  CONSTRAINT client_errors_stack_len   CHECK (stack IS NULL OR char_length(stack) <= 4000),
  CONSTRAINT client_errors_context_len CHECK (char_length(context) <= 120)
);

-- Triage reads are "newest first, scoped to my hive".
CREATE INDEX IF NOT EXISTS client_errors_hive_created_idx
  ON public.client_errors (hive_id, created_at DESC);

ALTER TABLE public.client_errors ENABLE ROW LEVEL SECURITY;

-- WRITE: any signed-in member may report an error for a hive they belong to.
-- (Errors are diagnostics, not privileged data — but we still scope by membership
--  so one hive cannot inject noise into another hive's triage view.)
DROP POLICY IF EXISTS client_errors_insert ON public.client_errors;
CREATE POLICY client_errors_insert ON public.client_errors
  FOR INSERT TO authenticated
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND (
      hive_id IS NULL                              -- pre-hive surfaces (login / onboarding) may still report
      OR EXISTS (
        SELECT 1 FROM public.hive_members hm
        WHERE hm.hive_id = client_errors.hive_id
          AND hm.auth_uid = auth.uid()
          AND hm.status = 'active'
      )
    )
  );

-- READ: supervisors of the hive (triage is a supervisor job); founders use the
-- service role / founder console. A worker does not need to read the error log.
DROP POLICY IF EXISTS client_errors_read ON public.client_errors;
CREATE POLICY client_errors_read ON public.client_errors
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = client_errors.hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.status = 'active'
        AND hm.role = 'supervisor'
    )
  );

-- GRANTs: RLS sits ON TOP of table privileges — without these Postgres raises
-- 42501 at the GRANT layer before RLS is ever consulted (the marketplace_sellers
-- lesson, mig 20260722000001). INSERT only for the reporter; SELECT for triage.
GRANT INSERT, SELECT ON public.client_errors TO authenticated;
GRANT USAGE, SELECT ON SEQUENCE public.client_errors_id_seq TO authenticated;

COMMENT ON TABLE public.client_errors IS
  'D21 frontend observability: client-side JS errors captured by utils.js whLogError. Diagnostics only - never form values, payloads or tokens. Hive-scoped insert; supervisor-scoped read.';

-- ── Fuel-layer anchor ────────────────────────────────────────────────────────
-- Every new raw table must declare its canonical source (validate_canonical_anchor
-- L1 "Fuel"), so no table exists without a documented owner + contract. Idempotent.
INSERT INTO public.canonical_sources
  (domain, source_kind, source_name, owner_skill, freshness, contract, description)
VALUES (
  'observability',
  'table',
  'client_errors',
  'devops',
  'realtime',
  jsonb_build_object(
    'key',            jsonb_build_array('id'),
    'scope',          'hive',
    'write',          'any active hive member (client error reporter)',
    'read',           'hive supervisor only (triage)',
    'retention_hint', 'transient diagnostics; safe to wipe (in reset.py RESET_TABLES)',
    'pii',            'none - message + truncated stack + pathname + coarse UA only'
  ),
  'D21 frontend observability: client-side JS errors captured by utils.js whLogError (global error + unhandledrejection net). Diagnostics only, never form values/payloads/tokens; 20-per-load cap + dedupe.'
)
ON CONFLICT DO NOTHING;
