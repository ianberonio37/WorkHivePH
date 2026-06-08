-- Phase 0.1 — Hive Readiness Score (HRS) foundation.
--
-- The empirical backbone of the Operational Readiness reframe. Every hive
-- gets a daily-snapshot score across 5 dimensions, a composite 0-100, and
-- a Maturity Stair (0..4). The score is computed from canonical sources
-- already in the platform (asset_nodes, pm_compliance_truth, logbook,
-- audit_log, sensor_readings, etc.) so the math is auditable and the
-- evidence is reproducible.
--
-- Why this exists at all (per STRATEGIC_ROADMAP.md doctrine):
--   "We do not deploy without a Readiness Score. Every new hive sees its
--    starting score within 30 minutes of signup. We don't pretend."
--
-- Dimensions (each 0..100):
--   process_maturity_score        — asset registry depth, PM templates, SOPs, FMEA modes
--   data_quality_score            — logbook hygiene, embedding lag, inventory integrity
--   infrastructure_resilience_score — sensor presence, offline-queue usage, voice-journal use
--   leadership_engagement_score   — supervisor approvals/week, audit log activity, role coverage
--   cultural_adoption_score       — active-worker ratio, daily-use rate, voice-journal participation
--
-- Composite weighting:
--   process 25%  +  data_quality 20%  +  resilience 15%  +
--   leadership 25%  +  cultural 15%   = 100
--
-- Stair derivation (epistemic gating, not technical paywall):
--   Stair 0 (Paper):           composite < 20  OR  asset_count < 10
--   Stair 1 (Digital Logbook): asset_count >= 10  AND  active_workers < 5
--   Stair 2 (Disciplined):     active_workers >= 5  AND  pm_compliance_30d < 70
--   Stair 3 (Predictive-Ready): pm_compliance_30d >= 70 AND (history_days >= 90 OR sensors_live)
--   Stair 4 (Industry Leader): Stair 3 + (RCM 10+ approved + audit compliant + benchmarks opted-in)
--
-- Skills consulted:
--   architect (canonical sources + view + RLS pattern; snapshot table not
--     materialised view because the compute is daily not real-time)
--   maintenance-expert (PM compliance threshold 70% mirrors v_pm_compliance_truth;
--     stair criteria match the published Maturity Stack in STRATEGIC_ROADMAP.md)
--   predictive-analytics (history_days >= 90 mirrors validate_predictive's
--     "rules-then-ML" doctrine — never predict on insufficient data)
--   multitenant-engineer (hive-scoped writes only; hive-members-join RLS read)
--   enterprise-compliance (audit log row per score change; auditors and
--     insurance partners need this trail)
--   data-engineer (UNIQUE on (hive_id, snapshot_date) for idempotent re-run;
--     evidence JSONB for forensic replay)

BEGIN;

-- ────────────────────────────────────────────────────────────────────────────
-- 1. hive_readiness — daily snapshot per hive
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.hive_readiness (
  id                              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id                         uuid        NOT NULL REFERENCES public.hives(id) ON DELETE CASCADE,
  snapshot_date                   date        NOT NULL DEFAULT (timezone('Asia/Manila', now()))::date,
  -- Five dimension scores
  process_maturity_score          smallint    NOT NULL DEFAULT 0 CHECK (process_maturity_score          BETWEEN 0 AND 100),
  data_quality_score              smallint    NOT NULL DEFAULT 0 CHECK (data_quality_score              BETWEEN 0 AND 100),
  infrastructure_resilience_score smallint    NOT NULL DEFAULT 0 CHECK (infrastructure_resilience_score BETWEEN 0 AND 100),
  leadership_engagement_score     smallint    NOT NULL DEFAULT 0 CHECK (leadership_engagement_score     BETWEEN 0 AND 100),
  cultural_adoption_score         smallint    NOT NULL DEFAULT 0 CHECK (cultural_adoption_score         BETWEEN 0 AND 100),
  -- Composite (weighted; computed in PL/pgSQL not GENERATED because we want
  -- the weighting to be visible in code, not buried in a generation expression)
  composite_score                 smallint    NOT NULL DEFAULT 0 CHECK (composite_score                 BETWEEN 0 AND 100),
  -- Maturity stair (epistemic gate; 0..4)
  current_stair                   smallint    NOT NULL DEFAULT 0 CHECK (current_stair                   BETWEEN 0 AND 4),
  -- Evidence backing the score (auditable replay)
  evidence                        jsonb       NOT NULL DEFAULT '{}'::jsonb,
  -- Honest "what's blocking the next stair" (one-line, surfaced in UI)
  blocker_summary                 text,
  computed_at                     timestamptz NOT NULL DEFAULT now(),
  model_version                   text        NOT NULL DEFAULT 'hrs-v1',
  CONSTRAINT hive_readiness_unique_per_day UNIQUE (hive_id, snapshot_date)
);

COMMENT ON TABLE public.hive_readiness IS
  'Hive Readiness Score daily snapshots. 5 dimensions + weighted composite + maturity stair (0..4). Evidence JSONB captures raw signals so the score is auditable. Drives Maturity Stairway UI on hive.html and gates advanced tool surfaces per STRATEGIC_ROADMAP.md.';

CREATE INDEX IF NOT EXISTS idx_hive_readiness_hive_date
  ON public.hive_readiness (hive_id, snapshot_date DESC);

-- ────────────────────────────────────────────────────────────────────────────
-- 2. hive_readiness_audit — every stair change persisted
-- ────────────────────────────────────────────────────────────────────────────
-- Compliance + insurance asset: auditors and underwriters get a forensic
-- trail of every score / stair change with the evidence delta that drove it.

CREATE TABLE IF NOT EXISTS public.hive_readiness_audit (
  id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id             uuid        NOT NULL REFERENCES public.hives(id) ON DELETE CASCADE,
  changed_at          timestamptz NOT NULL DEFAULT now(),
  previous_stair      smallint,
  new_stair           smallint    NOT NULL,
  previous_composite  smallint,
  new_composite       smallint    NOT NULL,
  reason              text,
  evidence_delta      jsonb,
  CONSTRAINT hra_stair_range CHECK (new_stair BETWEEN 0 AND 4)
);

CREATE INDEX IF NOT EXISTS idx_hive_readiness_audit_hive_when
  ON public.hive_readiness_audit (hive_id, changed_at DESC);

-- ────────────────────────────────────────────────────────────────────────────
-- 3. compute_hive_readiness(uuid) — the math, in PL/pgSQL for transparency
-- ────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.compute_hive_readiness(p_hive_id uuid)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_asset_count               integer;
  v_pm_template_count         integer;
  v_logbook_30d               integer;
  v_fmea_modes_approved       integer;
  v_logbook_with_knowledge    integer;

  v_active_workers_7d         integer;
  v_total_members             integer;
  v_supervisor_actions_7d     integer;
  v_audit_writes_30d          integer;
  v_supervisor_count          integer;
  v_pm_compliance_30d         numeric;

  v_has_sensor_readings       boolean;
  v_offline_queue_evidence    boolean;
  v_voice_journal_30d         integer;

  v_history_days              integer;
  v_logbook_hygiene_pct       numeric;
  v_audit_compliant           boolean;
  v_benchmarks_opted_in       boolean;
  v_rcm_strategies_approved   integer;

  v_process_score             smallint;
  v_data_score                smallint;
  v_resilience_score          smallint;
  v_leadership_score          smallint;
  v_cultural_score            smallint;
  v_composite                 smallint;
  v_stair                     smallint;
  v_blocker                   text;
  v_evidence                  jsonb;

  v_today                     date := (timezone('Asia/Manila', now()))::date;
  v_prev                      record;
  v_id                        uuid;
BEGIN
  -- ─── Process maturity inputs ──────────────────────────────────────────────
  SELECT count(*) INTO v_asset_count
    FROM public.asset_nodes
    WHERE hive_id = p_hive_id AND status = 'approved';

  SELECT count(DISTINCT pa.id) INTO v_pm_template_count
    FROM public.pm_assets pa
    WHERE pa.hive_id = p_hive_id;

  SELECT count(*) INTO v_logbook_with_knowledge
    FROM public.logbook
    WHERE hive_id = p_hive_id
      AND knowledge IS NOT NULL
      AND char_length(trim(knowledge)) > 20;

  SELECT count(*) INTO v_fmea_modes_approved
    FROM public.rcm_fmea_modes
    WHERE hive_id = p_hive_id AND approved_at IS NOT NULL;

  v_process_score := LEAST(100, GREATEST(0, (
      LEAST(40, v_asset_count * 4)                        -- 10 assets = 40 pts
    + LEAST(30, v_pm_template_count * 6)                  -- 5 templates = 30 pts
    + LEAST(20, v_logbook_with_knowledge * 2)             -- 10 SOPs = 20 pts
    + LEAST(10, v_fmea_modes_approved * 1)                -- 10 FMEAs = 10 pts
  )));

  -- ─── Cultural / leadership inputs (logbook-driven) ───────────────────────
  SELECT count(DISTINCT worker_name) INTO v_active_workers_7d
    FROM public.logbook
    WHERE hive_id = p_hive_id
      AND created_at >= now() - interval '7 days';

  SELECT count(*) INTO v_total_members
    FROM public.hive_members
    WHERE hive_id = p_hive_id AND status = 'active';

  SELECT count(*) INTO v_supervisor_count
    FROM public.hive_members
    WHERE hive_id = p_hive_id AND status = 'active' AND role = 'supervisor';

  -- ─── Leadership engagement inputs ────────────────────────────────────────
  SELECT count(*) INTO v_supervisor_actions_7d
    FROM public.hive_audit_log
    WHERE hive_id = p_hive_id
      AND created_at >= now() - interval '7 days'
      AND action IN ('approve', 'reject', 'kick', 'assign', 'verify');

  SELECT count(*) INTO v_audit_writes_30d
    FROM public.hive_audit_log
    WHERE hive_id = p_hive_id
      AND created_at >= now() - interval '30 days';

  v_leadership_score := LEAST(100, GREATEST(0, (
      LEAST(50, v_supervisor_actions_7d * 10)             -- 5 approvals/week = 50 pts
    + LEAST(30, v_audit_writes_30d)                       -- 30 writes/month = 30 pts
    + CASE WHEN v_supervisor_count >= 1 THEN 20 ELSE 0 END
  )));

  -- ─── PM compliance (from canonical view) ─────────────────────────────────
  SELECT
    CASE
      WHEN sum(CASE WHEN is_due THEN 1 ELSE 0 END) = 0 THEN 100
      ELSE 100.0 * (1.0 - sum(CASE WHEN is_due THEN 1 ELSE 0 END)::numeric / count(*)::numeric)
    END
  INTO v_pm_compliance_30d
  FROM public.v_pm_compliance_truth
  WHERE hive_id = p_hive_id;
  v_pm_compliance_30d := COALESCE(v_pm_compliance_30d, 0);

  -- ─── Data quality inputs ─────────────────────────────────────────────────
  SELECT count(*) INTO v_logbook_30d
    FROM public.logbook
    WHERE hive_id = p_hive_id
      AND created_at >= now() - interval '30 days';

  -- Logbook hygiene: % with non-empty problem AND root_cause AND action
  IF v_logbook_30d > 0 THEN
    SELECT 100.0 * count(*) / v_logbook_30d INTO v_logbook_hygiene_pct
      FROM public.logbook
      WHERE hive_id = p_hive_id
        AND created_at >= now() - interval '30 days'
        AND problem    IS NOT NULL AND char_length(trim(problem))    > 0
        AND root_cause IS NOT NULL AND char_length(trim(root_cause)) > 0
        AND action     IS NOT NULL AND char_length(trim(action))     > 0;
  ELSE
    v_logbook_hygiene_pct := 0;
  END IF;

  v_data_score := LEAST(100, GREATEST(0, (
      LEAST(40, (v_logbook_hygiene_pct * 0.4)::int)       -- hygiene 100% = 40 pts
    + LEAST(30, v_logbook_30d)                            -- 30 entries/month = 30 pts
    + LEAST(30, (v_pm_compliance_30d * 0.3)::int)         -- 100% PM compliance = 30 pts
  )));

  -- ─── Infrastructure resilience inputs ────────────────────────────────────
  SELECT EXISTS (
    SELECT 1 FROM public.sensor_readings WHERE hive_id = p_hive_id LIMIT 1
  ) INTO v_has_sensor_readings;

  SELECT count(*) > 0 INTO v_offline_queue_evidence
  FROM public.logbook
  WHERE hive_id = p_hive_id
    AND created_at >= now() - interval '30 days'
    AND COALESCE((sync_meta->>'offline_queued')::boolean, false) = true;

  SELECT count(*) INTO v_voice_journal_30d
    FROM public.voice_journal_entries vje
    WHERE vje.hive_id = p_hive_id
      AND vje.created_at >= now() - interval '30 days';

  v_resilience_score := LEAST(100, GREATEST(0, (
      CASE WHEN v_has_sensor_readings    THEN 40 ELSE 0 END
    + CASE WHEN v_offline_queue_evidence THEN 30 ELSE 0 END
    + LEAST(30, v_voice_journal_30d * 3)                  -- 10 voice entries = 30 pts
  )));

  -- ─── Cultural adoption inputs ────────────────────────────────────────────
  v_cultural_score := LEAST(100, GREATEST(0, (
      CASE
        WHEN v_total_members = 0 THEN 0
        WHEN v_total_members > 0 THEN LEAST(60, (100.0 * v_active_workers_7d / v_total_members)::int * 60 / 100)
      END
    + LEAST(40, v_logbook_30d * 2)                        -- 20 entries/month per hive = 40 pts
  )));

  -- ─── History + edge gates for Stair 3+ ───────────────────────────────────
  SELECT EXTRACT(DAY FROM (now() - min(created_at)))::int INTO v_history_days
    FROM public.logbook
    WHERE hive_id = p_hive_id;
  v_history_days := COALESCE(v_history_days, 0);

  SELECT count(*) INTO v_rcm_strategies_approved
    FROM public.rcm_strategies
    WHERE hive_id = p_hive_id AND approved_at IS NOT NULL;

  v_audit_compliant := (v_audit_writes_30d >= 10);  -- placeholder; full compliance audit later
  v_benchmarks_opted_in := false;                    -- Phase 5/6 work; false by default

  -- ─── Composite (weighted) ────────────────────────────────────────────────
  v_composite := LEAST(100, GREATEST(0, (
      (v_process_score    * 25
    +  v_data_score       * 20
    +  v_resilience_score * 15
    +  v_leadership_score * 25
    +  v_cultural_score   * 15) / 100
  )));

  -- ─── Stair derivation (the epistemic gate) ──────────────────────────────
  IF v_asset_count < 10 OR v_composite < 20 THEN
    v_stair := 0;
    v_blocker := format(
      'Register %s more asset(s) and document 1 SOP to unlock Stair 1.',
      GREATEST(0, 10 - v_asset_count)
    );
  ELSIF v_active_workers_7d < 5 OR v_pm_template_count < 5 THEN
    v_stair := 1;
    -- Only list the criteria that are actually UNMET. Hardcoding both clauses
    -- surfaced a satisfied criterion as a blocker (e.g. "30 of 5 PM templates
    -- registered" when 30 >= 5 is met), which reads as nonsense in the UI.
    v_blocker := nullif(trim(concat_ws(' ',
      CASE WHEN v_active_workers_7d < 5
        THEN format('%s of 5 active workers writing entries this week.', v_active_workers_7d) END,
      CASE WHEN v_pm_template_count < 5
        THEN format('%s of 5 PM templates registered.', v_pm_template_count) END
    )), '');
  ELSIF v_pm_compliance_30d < 70 OR v_logbook_hygiene_pct < 80 OR v_supervisor_actions_7d < 5 THEN
    v_stair := 2;
    v_blocker := format(
      'PM compliance %s%% (need 70%%), logbook hygiene %s%% (need 80%%), supervisor actions %s/week (need 5).',
      round(v_pm_compliance_30d)::text, round(v_logbook_hygiene_pct)::text, v_supervisor_actions_7d
    );
  ELSIF v_history_days < 90 AND NOT v_has_sensor_readings THEN
    v_stair := 3;
    v_blocker := format(
      'Either accumulate %s more days of logbook history OR connect a sensor bridge to unlock predictive analytics.',
      GREATEST(0, 90 - v_history_days)
    );
  ELSIF v_rcm_strategies_approved < 10 OR NOT v_audit_compliant OR NOT v_benchmarks_opted_in OR NOT v_has_sensor_readings THEN
    v_stair := 3;
    v_blocker := 'Need all four of: sensor pipeline live, 10+ approved RCM strategies, audit-trail compliant, federated PH benchmarks opted-in.';
  ELSE
    v_stair := 4;
    v_blocker := 'Top of the stack. Maintain the four pillars and consider federated benchmark export.';
  END IF;

  -- ─── Evidence JSONB (for UI + audit replay) ─────────────────────────────
  v_evidence := jsonb_build_object(
    'computed_at',              now(),
    'inputs',                   jsonb_build_object(
      'asset_count',                v_asset_count,
      'pm_template_count',          v_pm_template_count,
      'logbook_with_knowledge',     v_logbook_with_knowledge,
      'fmea_modes_approved',        v_fmea_modes_approved,
      'active_workers_7d',          v_active_workers_7d,
      'total_members',              v_total_members,
      'supervisor_count',           v_supervisor_count,
      'supervisor_actions_7d',      v_supervisor_actions_7d,
      'audit_writes_30d',           v_audit_writes_30d,
      'pm_compliance_30d_pct',      round(v_pm_compliance_30d, 1),
      'logbook_30d',                v_logbook_30d,
      'logbook_hygiene_pct',        round(v_logbook_hygiene_pct, 1),
      'has_sensor_readings',        v_has_sensor_readings,
      'offline_queue_evidence',     v_offline_queue_evidence,
      'voice_journal_30d',          v_voice_journal_30d,
      'history_days',               v_history_days,
      'rcm_strategies_approved',    v_rcm_strategies_approved,
      'audit_compliant',            v_audit_compliant,
      'benchmarks_opted_in',        v_benchmarks_opted_in
    ),
    'scores',                   jsonb_build_object(
      'process_maturity',           v_process_score,
      'data_quality',               v_data_score,
      'infrastructure_resilience',  v_resilience_score,
      'leadership_engagement',      v_leadership_score,
      'cultural_adoption',          v_cultural_score,
      'composite',                  v_composite
    ),
    'thresholds_for_next_stair', CASE v_stair
      WHEN 0 THEN jsonb_build_object('need_assets', 10, 'need_sops', 1)
      WHEN 1 THEN jsonb_build_object('need_active_workers', 5, 'need_pm_templates', 5)
      WHEN 2 THEN jsonb_build_object('need_pm_compliance_pct', 70, 'need_logbook_hygiene_pct', 80, 'need_supervisor_actions_week', 5)
      WHEN 3 THEN jsonb_build_object('need_history_days', 90, 'or_sensors_live', true, 'need_rcm_approved', 10)
      ELSE        jsonb_build_object('maintain', true)
    END
  );

  -- ─── Capture previous snapshot for audit trail ───────────────────────────
  SELECT new_stair AS new_stair, new_composite AS new_composite
    INTO v_prev
    FROM public.hive_readiness_audit
    WHERE hive_id = p_hive_id
    ORDER BY changed_at DESC
    LIMIT 1;

  -- ─── Upsert today's snapshot ─────────────────────────────────────────────
  INSERT INTO public.hive_readiness (
    hive_id, snapshot_date,
    process_maturity_score, data_quality_score, infrastructure_resilience_score,
    leadership_engagement_score, cultural_adoption_score, composite_score,
    current_stair, evidence, blocker_summary, model_version
  ) VALUES (
    p_hive_id, v_today,
    v_process_score, v_data_score, v_resilience_score,
    v_leadership_score, v_cultural_score, v_composite,
    v_stair, v_evidence, v_blocker, 'hrs-v1'
  )
  ON CONFLICT (hive_id, snapshot_date) DO UPDATE SET
    process_maturity_score          = EXCLUDED.process_maturity_score,
    data_quality_score              = EXCLUDED.data_quality_score,
    infrastructure_resilience_score = EXCLUDED.infrastructure_resilience_score,
    leadership_engagement_score     = EXCLUDED.leadership_engagement_score,
    cultural_adoption_score         = EXCLUDED.cultural_adoption_score,
    composite_score                 = EXCLUDED.composite_score,
    current_stair                   = EXCLUDED.current_stair,
    evidence                        = EXCLUDED.evidence,
    blocker_summary                 = EXCLUDED.blocker_summary,
    computed_at                     = now()
  RETURNING id INTO v_id;

  -- ─── Audit-log any stair OR composite jump ≥10 points ───────────────────
  IF v_prev IS NULL
     OR v_prev.new_stair     <> v_stair
     OR abs(v_prev.new_composite - v_composite) >= 10 THEN
    INSERT INTO public.hive_readiness_audit (
      hive_id, previous_stair, new_stair,
      previous_composite, new_composite, reason, evidence_delta
    ) VALUES (
      p_hive_id,
      v_prev.new_stair,     v_stair,
      v_prev.new_composite, v_composite,
      v_blocker,
      v_evidence->'inputs'
    );
  END IF;

  RETURN v_id;
END;
$$;

GRANT EXECUTE ON FUNCTION public.compute_hive_readiness(uuid) TO authenticated, service_role;

COMMENT ON FUNCTION public.compute_hive_readiness IS
  'Compute Hive Readiness Score (5 dimensions + composite + maturity stair) for one hive and upsert today''s snapshot. Idempotent via UNIQUE(hive_id, snapshot_date). Writes audit row on stair change or composite jump >=10 points. Read-only RPCs should use get_hive_readiness_current() instead.';

-- ────────────────────────────────────────────────────────────────────────────
-- 4. get_hive_readiness_current(uuid) — read-only fetch for UI
-- ────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.get_hive_readiness_current(p_hive_id uuid)
RETURNS public.hive_readiness
LANGUAGE sql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
  SELECT *
  FROM public.hive_readiness
  WHERE hive_id = p_hive_id
  ORDER BY snapshot_date DESC, computed_at DESC
  LIMIT 1;
$$;

GRANT EXECUTE ON FUNCTION public.get_hive_readiness_current(uuid) TO anon, authenticated;

-- ────────────────────────────────────────────────────────────────────────────
-- 5. Grants + RLS
-- ────────────────────────────────────────────────────────────────────────────

GRANT SELECT, INSERT, UPDATE ON public.hive_readiness       TO anon, authenticated;
GRANT SELECT, INSERT          ON public.hive_readiness_audit TO anon, authenticated;

ALTER TABLE public.hive_readiness       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.hive_readiness_audit ENABLE ROW LEVEL SECURITY;

-- Read: any active hive member
DROP POLICY IF EXISTS hive_readiness_read ON public.hive_readiness;
CREATE POLICY hive_readiness_read ON public.hive_readiness FOR SELECT
  USING (
    auth.uid() IS NOT NULL
    AND hive_id IN (
      SELECT hm.hive_id FROM public.hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    )
  );

DROP POLICY IF EXISTS hive_readiness_audit_read ON public.hive_readiness_audit;
CREATE POLICY hive_readiness_audit_read ON public.hive_readiness_audit FOR SELECT
  USING (
    auth.uid() IS NOT NULL
    AND hive_id IN (
      SELECT hm.hive_id FROM public.hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    )
  );

-- Write: service-role only (the compute RPC + daily cron).
DROP POLICY IF EXISTS hive_readiness_write_locked ON public.hive_readiness;
CREATE POLICY hive_readiness_write_locked ON public.hive_readiness FOR INSERT
  WITH CHECK (false);

DROP POLICY IF EXISTS hive_readiness_update_locked ON public.hive_readiness;
CREATE POLICY hive_readiness_update_locked ON public.hive_readiness FOR UPDATE
  USING (false) WITH CHECK (false);

DROP POLICY IF EXISTS hive_readiness_audit_write_locked ON public.hive_readiness_audit;
CREATE POLICY hive_readiness_audit_write_locked ON public.hive_readiness_audit FOR INSERT
  WITH CHECK (false);

-- ────────────────────────────────────────────────────────────────────────────
-- 6. Realtime publication (hive.html subscribes for live stair updates)
-- ────────────────────────────────────────────────────────────────────────────

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime' AND tablename = 'hive_readiness'
  ) THEN
    EXECUTE 'ALTER PUBLICATION supabase_realtime ADD TABLE public.hive_readiness';
  END IF;
END
$$;

ALTER TABLE public.hive_readiness REPLICA IDENTITY FULL;

-- ────────────────────────────────────────────────────────────────────────────
-- 7. v_hive_readiness_truth — canonical read shape
-- ────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW public.v_hive_readiness_truth AS
SELECT DISTINCT ON (hive_id)
  hive_id, snapshot_date,
  process_maturity_score, data_quality_score, infrastructure_resilience_score,
  leadership_engagement_score, cultural_adoption_score, composite_score,
  current_stair, evidence, blocker_summary, computed_at, model_version
FROM public.hive_readiness
ORDER BY hive_id, snapshot_date DESC, computed_at DESC;

GRANT SELECT ON public.v_hive_readiness_truth TO anon, authenticated;

COMMENT ON VIEW public.v_hive_readiness_truth IS
  'Latest Hive Readiness snapshot per hive via DISTINCT ON. Registered in canonical_sources as domain=hive_readiness. Source of truth for Maturity Stairway UI and maturity gating across all advanced tool surfaces.';

-- ────────────────────────────────────────────────────────────────────────────
-- 8. Canonical sources registrations
-- ────────────────────────────────────────────────────────────────────────────

INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES (
  'hive_readiness',
  'view',
  'v_hive_readiness_truth',
  'architect',
  'daily_recompute',
  'Latest Hive Readiness snapshot per hive. 5 dimensions + composite + maturity stair (0..4) + evidence JSONB + one-line blocker. Source of truth for Maturity Stairway UI and the epistemic gating layer that controls which advanced tools render per hive.',
  jsonb_build_object(
    'key',           jsonb_build_array('hive_id'),
    'hive_scoped',   true,
    'stair_range',   jsonb_build_array(0, 4),
    'composite_range', jsonb_build_array(0, 100),
    'dimensions', jsonb_build_array(
      'process_maturity', 'data_quality', 'infrastructure_resilience',
      'leadership_engagement', 'cultural_adoption'
    ),
    'compute_rpc',   'compute_hive_readiness(uuid)',
    'read_rpc',      'get_hive_readiness_current(uuid)'
  ),
  'Phase 0.1 of STRATEGIC_ROADMAP.md. Snapshots are append-only via UNIQUE(hive_id, snapshot_date); update path is the compute_hive_readiness RPC, not direct UPSERT.'
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

INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES (
  'hive_readiness_audit',
  'table',
  'hive_readiness_audit',
  'enterprise-compliance',
  'realtime',
  'Append-only log of stair changes and composite jumps >=10 points per hive. Forensic replay trail for auditors, insurance underwriters, and banks.',
  jsonb_build_object(
    'key',         jsonb_build_array('id'),
    'hive_scoped', true,
    'append_only', true,
    'trigger',     'compute_hive_readiness() inserts on stair change OR composite delta >= 10'
  ),
  'Phase 0.1 of STRATEGIC_ROADMAP.md. Compliance asset: shows that readiness signal is monitored, not assumed.'
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

-- ─── Fuel anchor: register the snapshot TABLE separately from its view ──────
INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES (
  'hive_readiness_table',
  'table',
  'hive_readiness',
  'architect',
  'daily_recompute',
  'Per-hive per-day readiness snapshot rows. UNIQUE(hive_id, snapshot_date). Written by compute_hive_readiness RPC only; reads should go through v_hive_readiness_truth.',
  jsonb_build_object(
    'key',          jsonb_build_array('id'),
    'natural_key',  jsonb_build_array('hive_id','snapshot_date'),
    'hive_scoped',  true,
    'write_rpc',    'compute_hive_readiness'
  ),
  'Phase 0.1 of STRATEGIC_ROADMAP.md. Anchored separately from the view so validate_canonical_anchor.fuel layer recognises the underlying storage.'
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

-- ─── Engine anchor: register the two RPCs ───────────────────────────────────
INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES (
  'compute_hive_readiness_rpc',
  'rpc',
  'compute_hive_readiness',
  'architect',
  'on_demand',
  'PL/pgSQL function. Computes the 5 dimensions + composite + stair for one hive and upserts today''s snapshot. Idempotent via UNIQUE(hive_id, snapshot_date). Writes an audit row on stair change or composite delta >=10.',
  jsonb_build_object(
    'signature',  'compute_hive_readiness(p_hive_id uuid) RETURNS uuid',
    'side_effects', jsonb_build_array('hive_readiness upsert', 'hive_readiness_audit insert on stair change')
  ),
  'Phase 0.1 of STRATEGIC_ROADMAP.md. Service-role only; called by the daily cron and by the page-load fallback in hive.html.'
),
(
  'get_hive_readiness_current_rpc',
  'rpc',
  'get_hive_readiness_current',
  'architect',
  'realtime',
  'Read-only fetch of the latest readiness snapshot for one hive. Used by Maturity Stairway UI on hive.html and by the maturity-gate.js helper.',
  jsonb_build_object(
    'signature',  'get_hive_readiness_current(p_hive_id uuid) RETURNS hive_readiness',
    'side_effects', jsonb_build_array()
  ),
  'Phase 0.1 of STRATEGIC_ROADMAP.md. Anon + authenticated execute (RLS still enforced on the underlying table read).'
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
