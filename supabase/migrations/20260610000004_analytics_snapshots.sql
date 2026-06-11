-- Phase 1 (open-fast, 2026-06-10): analytics.html currently fires 4 heavy
-- orchestrator->python computations on EVERY page open. Per the compute rule
-- (NO pg_cron): the first view of the day computes + SAVES; everyone else
-- reads the saved copy instantly; the Refresh button forces a recompute.
-- The analytics-orchestrator (service role) upserts one row per
-- (hive, phase, period) after each successful UNFILTERED compute; the page
-- hydrates from rows computed today (PHT) and shows "Updated Xh ago".
-- Filtered views (criticality/discipline) are never persisted - always live.

CREATE TABLE IF NOT EXISTS public.analytics_snapshots (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id      uuid NOT NULL,
  phase        text NOT NULL CHECK (phase IN ('descriptive','diagnostic','predictive','prescriptive')),
  period_days  integer NOT NULL,
  payload      jsonb NOT NULL,
  computed_at  timestamptz NOT NULL DEFAULT now(),
  computed_by  text,
  UNIQUE (hive_id, phase, period_days)
);

CREATE INDEX IF NOT EXISTS idx_analytics_snapshots_hive
  ON public.analytics_snapshots (hive_id, period_days, computed_at DESC);

ALTER TABLE public.analytics_snapshots ENABLE ROW LEVEL SECURITY;

-- Hive members read their hive's snapshots (mirrors ai_reply_feedback_read).
-- NO client INSERT/UPDATE/DELETE policies: only the orchestrator's service
-- role (RLS-bypassing) writes snapshots, so a client can never poison the
-- cached copy another member renders.
CREATE POLICY analytics_snapshots_member_read ON public.analytics_snapshots
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = analytics_snapshots.hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.status = 'active'
    )
  );

GRANT SELECT ON public.analytics_snapshots TO authenticated;
