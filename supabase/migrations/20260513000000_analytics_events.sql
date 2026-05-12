-- Phase 0: analytics_events foundation for Founder Console
--
-- Append-only product analytics table. Every page emits page_view; feature
-- pages also emit feature_use / save_success / funnel_step events. The table
-- feeds:
--   Panel 1 (Growth Pulse)   - DAU/MAU, Stickiness, K-factor, funnel
--   Panel 2 (Hive Cohorts)   - retention curves, churn, RFM (with hive_id)
--   Panel 3 (Feature Heatmap)- 30-page adoption grid via event_name='page_view'
--   Panel 4 (Power User)     - Pareto over auth_uid / hive_id counts
--
-- Writes are fire-and-forget from utils.js logEvent() - never block the user
-- action (architect skill: "Audit Log Writes Must Be Fire-and-Forget").
--
-- Retention: not enforced in Phase 0. A future migration will add a pg_cron
-- prune of rows older than 365 days, with daily/weekly rollups preserved.

CREATE TABLE IF NOT EXISTS public.analytics_events (
  id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  event_name   text        NOT NULL,
  page         text,
  props        jsonb       NOT NULL DEFAULT '{}'::jsonb,
  auth_uid     uuid,
  worker_name  text,
  hive_id      uuid,
  session_id   text,
  user_agent   text,
  created_at   timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.analytics_events IS
  'Append-only product analytics events powering Founder Console (Phase 0). '
  'INSERTs open to anon+authenticated for landing-page tracking; SELECTs '
  'restricted to platform admins via marketplace_platform_admins.';

-- ============================================================
-- RLS: append-only for everyone, read-only for platform admins
-- ============================================================
ALTER TABLE public.analytics_events ENABLE ROW LEVEL SECURITY;

-- Anyone (incl. unauthenticated landing-page visitors) can write events.
-- Standard analytics SDK pattern. No UPDATE/DELETE policies = append-only.
DROP POLICY IF EXISTS "analytics_events_insert_anyone" ON public.analytics_events;
CREATE POLICY "analytics_events_insert_anyone"
  ON public.analytics_events FOR INSERT
  TO anon, authenticated
  WITH CHECK (true);

-- SELECT restricted to platform admins (reuses marketplace_platform_admins
-- allowlist - single source of truth for admin role).
DROP POLICY IF EXISTS "analytics_events_select_admin" ON public.analytics_events;
CREATE POLICY "analytics_events_select_admin"
  ON public.analytics_events FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1
      FROM public.worker_profiles wp
      JOIN public.marketplace_platform_admins mpa
        ON mpa.worker_name = wp.display_name
      WHERE wp.auth_uid = auth.uid()
    )
  );

GRANT INSERT ON public.analytics_events TO anon, authenticated;
GRANT SELECT ON public.analytics_events TO authenticated;

-- ============================================================
-- Indexes: time-series + per-dimension lookups
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_analytics_events_created_at
  ON public.analytics_events (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_analytics_events_event_created
  ON public.analytics_events (event_name, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_analytics_events_auth_created
  ON public.analytics_events (auth_uid, created_at DESC)
  WHERE auth_uid IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_analytics_events_hive_created
  ON public.analytics_events (hive_id, created_at DESC)
  WHERE hive_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_analytics_events_page_created
  ON public.analytics_events (page, created_at DESC)
  WHERE page IS NOT NULL;

-- ============================================================
-- Canonical anchor (Fuel registration)
-- Required by validate_canonical_anchor.py L1: every new Fuel
-- table must be registered in canonical_sources so the architectural
-- gate can see who owns it and where it's consumed.
-- ============================================================
INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness,
  description, contract, notes
) VALUES (
  'analytics_events_raw', 'table', 'analytics_events',
  'analytics-engineer', 'realtime',
  'Append-only event stream for product analytics (page views, CTA clicks, feature usage). Anyone (incl. anon) can INSERT; only platform admins can SELECT.',
  jsonb_build_object(
    'key', jsonb_build_array('id'),
    'append_only', true
  ),
  'Underlies internal dashboards + funnel analysis. Not yet a canonical view; raw reads OK for admin-only surfaces.'
)
ON CONFLICT (source_name) DO NOTHING;
