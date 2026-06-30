-- ============================================================================
-- Arc Y (THE INTUITION GRADIENT) · Y3 — Alert agency: dismissals for DERIVED alerts
-- ============================================================================
-- Finding F (Y0.5): ~80% of alert-hub alerts have NO acknowledge/dismiss — only
-- AMC briefs + anomaly signals are actionable. The other kinds (PM-overdue, risk,
-- stock, pattern, staging, system) are DERIVED on the fly from truth views, so
-- there is no row to "mark handled" — a supervisor cannot triage them, they just
-- pile up (65 alerts, 60 high-sev = the overwhelm Ian named).
--
-- Fix: a per-hive dismissals ledger keyed by a STABLE per-alert key (e.g.
-- 'pm:<asset_id>', 'stock:<part_id>', 'risk:<asset_id>'). The alert-hub feed
-- filters out alerts with an ACTIVE dismissal:
--   * handled       — hidden until the underlying signal CHANGES (a new key re-fires)
--   * snoozed       — hidden until snooze_until passes
--   * acknowledged  — kept visible but marked seen (no hide)
-- "PM-complete drops the alert" needs NO row here: derived alerts auto-recompute
-- from v_pm_scope_items_truth, so completing a PM removes its overdue alert on the
-- next load. This ledger is for the ACKNOWLEDGE/SNOOZE/HANDLE agency gap only.
--
-- Multi-tenant: hive-member-scoped RLS (mirrors analytics_snapshots_member_read,
-- the canonical hive-membership predicate). One active dismissal per (hive, key)
-- → UPSERT on the unique index. Additive + reversible (drop table) + idempotent.
-- Forward-only.
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.alert_dismissals (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id      uuid NOT NULL,
  alert_key    text NOT NULL,        -- stable per-alert key: '<kind>:<stable-target-id>'
  action       text NOT NULL CHECK (action IN ('handled','snoozed','acknowledged')),
  actor        text,                 -- WORKER_NAME, for display + audit (not the auth principal)
  snooze_until timestamptz,          -- set only when action='snoozed'
  created_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (hive_id, alert_key)        -- one active disposition per alert per hive (upsert target)
);

CREATE INDEX IF NOT EXISTS idx_alert_dismissals_hive
  ON public.alert_dismissals (hive_id, action, snooze_until);

ALTER TABLE public.alert_dismissals ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.alert_dismissals TO authenticated;

-- Hive members read their hive's dismissals (so every supervisor sees the same
-- triaged state — matches how anomaly ack is hive-shared).
DROP POLICY IF EXISTS alert_dismissals_member_read   ON public.alert_dismissals;
DROP POLICY IF EXISTS alert_dismissals_member_write  ON public.alert_dismissals;
DROP POLICY IF EXISTS alert_dismissals_member_update ON public.alert_dismissals;
DROP POLICY IF EXISTS alert_dismissals_member_delete ON public.alert_dismissals;

CREATE POLICY alert_dismissals_member_read ON public.alert_dismissals
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = alert_dismissals.hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.status = 'active'
    )
  );

-- Members of the hive may CREATE a dismissal for THEIR hive only (the WITH CHECK
-- binds the row's hive_id to the writer's active membership — a client can never
-- dismiss another tenant's alerts).
CREATE POLICY alert_dismissals_member_write ON public.alert_dismissals
  FOR INSERT TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = alert_dismissals.hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.status = 'active'
    )
  );

CREATE POLICY alert_dismissals_member_update ON public.alert_dismissals
  FOR UPDATE TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = alert_dismissals.hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.status = 'active'
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = alert_dismissals.hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.status = 'active'
    )
  );

-- Members may un-dismiss (delete) their hive's dispositions (e.g. re-surface a
-- snoozed alert early).
CREATE POLICY alert_dismissals_member_delete ON public.alert_dismissals
  FOR DELETE TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = alert_dismissals.hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.status = 'active'
    )
  );
