-- Autonomous Maintenance Crew (AMC) Phase A1: briefings table.
--
-- The AMC is a daily multi-agent loop that runs at 06:00 PHT and writes a
-- single briefing row per hive containing 5 sub-agent outputs:
--   1. Top-3 highest-risk assets (Failure-Predictor sub-agent)
--   2. Top-5 PM tasks due in next 7 days (PM-Planner sub-agent)
--   3. Top-5 parts to stage (Parts-Stager sub-agent)
--   4. Per-asset crew suggestions (Crew-Builder sub-agent)
--   5. One-paragraph narrative summary (Briefing-Composer sub-agent, LLM)
--
-- The supervisor sees the brief in alert-hub.html (kind=amc), reviews the
-- batched recommendations, and approves with a single tap. Approval flips
-- status -> 'approved'; subsequent writes (PM scope items, parts reservations,
-- task assignments) are still TODO in v2 and not enforced by the table.
-- For v1, approval is a tracked decision; no automatic side-effects.
--
-- Briefings older than 36h are auto-expired by pg_cron (set status='expired'
-- where now() > expires_at AND status='pending'). Reasoning: a brief past its
-- shift is no longer actionable; an unapproved brief that lingers is noise.
--
-- Skills consulted:
--   architect (single row per (hive, day), idempotent via UNIQUE constraint
--     so a misfire of the cron does not duplicate; jsonb brief column with
--     versioned shape for forward-compat)
--   multitenant-engineer (hive_members JOIN policy, role gate at column for
--     approval, not at table level)
--   realtime-engineer (REPLICA IDENTITY FULL so DELETE filters work on hive_id;
--     supabase_realtime publication for alert-hub live update)
--   notifications (computed-state pattern: the brief replaces yesterday's,
--     never appended; UI must filter to latest pending per hive)
--   security (no PII in brief JSONB - it carries asset names and worker names
--     which are already visible to hive members; service-role writes only)
--   data-engineer (composite index on (hive_id, status, generated_at DESC)
--     for the alert-hub feed query)
--   ai-engineer (model_version column tracks brief schema generation; v1
--     is "amc-v1", future LLM upgrades bump this)

BEGIN;

-- ─── 1. The table ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.amc_briefings (
  id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id           uuid        NOT NULL REFERENCES public.hives(id) ON DELETE CASCADE,
  generated_at      timestamptz NOT NULL DEFAULT now(),
  shift_date        date        NOT NULL DEFAULT (timezone('Asia/Manila', now()))::date,
  status            text        NOT NULL DEFAULT 'pending'
                                CHECK (status IN ('pending','approved','rejected','expired')),
  brief             jsonb       NOT NULL DEFAULT '{}'::jsonb,
  model_version     text        NOT NULL DEFAULT 'amc-v1',
  approved_by       text,
  approved_at       timestamptz,
  approved_notes    text,
  expires_at        timestamptz NOT NULL DEFAULT (now() + interval '36 hours'),
  -- Surrogate columns surfaced for cheap filtering / display
  asset_count       smallint    GENERATED ALWAYS AS (
                                  COALESCE(jsonb_array_length(brief->'top_assets'), 0)
                                ) STORED,
  pm_count          smallint    GENERATED ALWAYS AS (
                                  COALESCE(jsonb_array_length(brief->'pm_due'), 0)
                                ) STORED,
  parts_count       smallint    GENERATED ALWAYS AS (
                                  COALESCE(jsonb_array_length(brief->'parts_to_stage'), 0)
                                ) STORED
);

COMMENT ON TABLE public.amc_briefings IS
  'Autonomous Maintenance Crew daily briefing. One row per (hive, shift_date). brief JSONB carries the 5 sub-agent outputs. Supervisor approves in batch via alert-hub.html.';

-- One brief per (hive, shift_date) - re-running cron is idempotent.
CREATE UNIQUE INDEX IF NOT EXISTS uq_amc_briefings_hive_shift
  ON public.amc_briefings (hive_id, shift_date);

-- Alert-hub feed query: latest pending per hive, ordered by generated_at desc.
CREATE INDEX IF NOT EXISTS idx_amc_briefings_hive_status_gen
  ON public.amc_briefings (hive_id, status, generated_at DESC);

-- Expiry cron query: pending rows past expires_at.
CREATE INDEX IF NOT EXISTS idx_amc_briefings_expires
  ON public.amc_briefings (expires_at)
  WHERE status = 'pending';

-- ─── 2. Grants ───────────────────────────────────────────────────────────────

GRANT SELECT, INSERT, UPDATE, DELETE ON public.amc_briefings TO anon, authenticated;

-- ─── 3. RLS ──────────────────────────────────────────────────────────────────

ALTER TABLE public.amc_briefings ENABLE ROW LEVEL SECURITY;

-- Read: any active hive member.
DROP POLICY IF EXISTS amc_briefings_read ON public.amc_briefings;
CREATE POLICY amc_briefings_read ON public.amc_briefings FOR SELECT
  USING (
    auth.uid() IS NOT NULL
    AND hive_id IN (
      SELECT hm.hive_id FROM public.hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    )
  );

-- Update (approve / reject / note): supervisors only.
DROP POLICY IF EXISTS amc_briefings_update_supervisor ON public.amc_briefings;
CREATE POLICY amc_briefings_update_supervisor ON public.amc_briefings FOR UPDATE
  USING (
    auth.uid() IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = amc_briefings.hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.role = 'supervisor'
        AND hm.status = 'active'
    )
  )
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = amc_briefings.hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.role = 'supervisor'
        AND hm.status = 'active'
    )
  );

-- Insert / Delete are locked from the client. The amc-orchestrator edge
-- function writes as service-role (bypasses RLS). The expiry cron runs as
-- the service-role pg_cron job and uses UPDATE only.
DROP POLICY IF EXISTS amc_briefings_insert_locked ON public.amc_briefings;
CREATE POLICY amc_briefings_insert_locked ON public.amc_briefings FOR INSERT
  WITH CHECK (false);

DROP POLICY IF EXISTS amc_briefings_delete_locked ON public.amc_briefings;
CREATE POLICY amc_briefings_delete_locked ON public.amc_briefings FOR DELETE
  USING (false);

-- ─── 4. Realtime publication ─────────────────────────────────────────────────

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime' AND tablename = 'amc_briefings'
  ) THEN
    EXECUTE 'ALTER PUBLICATION supabase_realtime ADD TABLE public.amc_briefings';
  END IF;
END
$$;

-- REPLICA IDENTITY FULL so DELETE filters on non-PK columns (status, hive_id)
-- work cleanly (per realtime-engineer skill - Default REPLICA IDENTITY = PK
-- silently drops DELETE filters on non-PK columns).
ALTER TABLE public.amc_briefings REPLICA IDENTITY FULL;

-- ─── 5. Auto-expire helper function ──────────────────────────────────────────

-- Called by a daily pg_cron job at 06:00 PHT just before AMC runs, so any
-- stale pending brief from the previous shift is flipped to 'expired' before
-- the new one inserts. The amc-orchestrator skips writing a new brief if a
-- non-expired pending one already exists for today (idempotency).
CREATE OR REPLACE FUNCTION public.amc_expire_stale()
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  n integer;
BEGIN
  UPDATE public.amc_briefings
  SET status = 'expired'
  WHERE status = 'pending'
    AND now() > expires_at;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n;
END
$$;

GRANT EXECUTE ON FUNCTION public.amc_expire_stale() TO authenticated;

-- ─── 6. Canonical sources registration ───────────────────────────────────────

INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES (
  'amc_brief',
  'table',
  'amc_briefings',
  'ai-engineer',
  'daily_06_pht',
  'Daily Autonomous Maintenance Crew briefing per hive. One row per (hive, shift_date). brief JSONB carries 5 sub-agent outputs: top_assets, pm_due, parts_to_stage, crew, summary. Supervisor flips status to approved via alert-hub.html batch action.',
  jsonb_build_object(
    'key', jsonb_build_array('hive_id', 'shift_date'),
    'hive_scoped', true,
    'status_values', jsonb_build_array('pending','approved','rejected','expired'),
    'brief_shape', jsonb_build_object(
      'top_assets',     'array of {asset_id, asset_name, risk_score, risk_level, top_factors}',
      'pm_due',         'array of {pm_asset_id, asset_name, category, criticality, days_since_last_completion}',
      'parts_to_stage', 'array of {recommendation_id, asset_name, parts, rationale, confidence}',
      'crew',           'array of {asset_name, suggested_worker, discipline, current_level, reason}',
      'summary',        'string - LLM-generated narrative paragraph'
    ),
    'sub_agents', jsonb_build_array(
      'failure_predictor', 'pm_planner', 'parts_stager', 'crew_builder', 'briefing_composer'
    ),
    'model_version_default', 'amc-v1'
  ),
  'Phase A1 contract. Brief expires after 36h (covers the shift + handover). amc_expire_stale() can be cronned just before the next 06:00 run. Approval is a tracked decision in v1 - no automatic downstream writes yet.'
)
ON CONFLICT (domain) DO UPDATE
  SET source_kind   = EXCLUDED.source_kind,
      source_name   = EXCLUDED.source_name,
      owner_skill   = EXCLUDED.owner_skill,
      freshness     = EXCLUDED.freshness,
      description   = EXCLUDED.description,
      contract      = EXCLUDED.contract,
      notes         = EXCLUDED.notes,
      registered_at = now();

COMMIT;
