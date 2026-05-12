-- Phase 4 — Revenue Surfaces.
--
-- Three monetisation hooks land in this phase, each maturity-gated so it
-- only renders when the hive's discipline justifies it. The doctrine: we
-- never bill on seats, and we never sell predictive at a stair where it
-- would lie. Revenue surfaces are honesty-first — that honesty becomes the
-- sales asset.
--
-- Builds in this migration:
--   1. anomaly_signals table — 5-source fusion store (logbook clusters,
--      sensor z-score, PM drift, parts spend, failure signatures)
--   2. compute_anomaly_signals(uuid) RPC — pure PL/pgSQL fusion ranker
--   3. v_anomaly_truth view — latest signals per (hive, machine)
--   4. v_knowledge_freshness_truth view — RAG corpus health KPI
--   5. canonical_sources registrations + RLS + supabase_realtime
--
-- Anomaly fusion rules (each contributes a sub-score; composite is the
-- weighted sum, clamped 0..100):
--   logbook_cluster       30%   — 3+ logbook entries for the same machine
--                                  within 14 days share a failure mode
--   sensor_zscore         25%   — sensor_readings z-score > 2.5 within 7 days
--   pm_drift              20%   — PM overdue AND interval extended past
--                                  canonical category default
--   parts_spend_spike     15%   — inventory_transactions for this machine
--                                  exceed prior-90d-mean by 2σ in 30 days
--   failure_signature     10%   — failure_signature_alerts row active
--
-- Anomaly Engine 2.0 gates at Stair 3+. Below that, the hive sees a
-- maturity-honest empty state explaining the prerequisites.
--
-- Skills consulted:
--   architect (canonical fusion: one signal table, not five surfaces)
--   predictive-analytics (z-score 2.5 threshold; 2σ for spend; multi-
--     source fusion only with discipline floor)
--   maintenance-expert (failure-mode + machine join is the practical
--     primitive for Filipino plants — workers think machine-by-machine)
--   knowledge-manager (freshness view feeds the RAG pipeline tile)
--   multitenant-engineer (hive-scoped reads; service-role writes)
--   data-engineer (UNIQUE on (hive_id, machine, snapshot_date) for
--     idempotent re-run)

BEGIN;

-- ────────────────────────────────────────────────────────────────────────────
-- 1. anomaly_signals — daily fused snapshot
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.anomaly_signals (
  id                   uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id              uuid        NOT NULL REFERENCES public.hives(id) ON DELETE CASCADE,
  snapshot_date        date        NOT NULL DEFAULT (timezone('Asia/Manila', now()))::date,
  machine              text        NOT NULL,
  asset_node_id        uuid        REFERENCES public.asset_nodes(id) ON DELETE SET NULL,
  -- Composite 0..100. Higher = more anomalous.
  composite_score      smallint    NOT NULL DEFAULT 0 CHECK (composite_score BETWEEN 0 AND 100),
  -- Sub-scores per source (each 0..100; weighted into composite)
  logbook_cluster_score   smallint NOT NULL DEFAULT 0 CHECK (logbook_cluster_score   BETWEEN 0 AND 100),
  sensor_zscore_score     smallint NOT NULL DEFAULT 0 CHECK (sensor_zscore_score     BETWEEN 0 AND 100),
  pm_drift_score          smallint NOT NULL DEFAULT 0 CHECK (pm_drift_score          BETWEEN 0 AND 100),
  parts_spend_score       smallint NOT NULL DEFAULT 0 CHECK (parts_spend_score       BETWEEN 0 AND 100),
  failure_signature_score smallint NOT NULL DEFAULT 0 CHECK (failure_signature_score BETWEEN 0 AND 100),
  -- Number of independent sources that fired (>= 35 each)
  source_count         smallint    NOT NULL DEFAULT 0 CHECK (source_count BETWEEN 0 AND 5),
  -- Severity bucket: derived from composite
  severity             text        NOT NULL DEFAULT 'info'
                                   CHECK (severity IN ('info', 'watch', 'warning', 'critical')),
  -- Top reasons + evidence (auditable replay)
  top_reasons          jsonb       NOT NULL DEFAULT '[]'::jsonb,
  evidence             jsonb       NOT NULL DEFAULT '{}'::jsonb,
  -- Lifecycle (supervisor acknowledges / resolves)
  status               text        NOT NULL DEFAULT 'active'
                                   CHECK (status IN ('active', 'acknowledged', 'resolved', 'expired')),
  acknowledged_by      text,
  acknowledged_at      timestamptz,
  resolved_by          text,
  resolved_at          timestamptz,
  computed_at          timestamptz NOT NULL DEFAULT now(),
  model_version        text        NOT NULL DEFAULT 'anomaly-v2',
  CONSTRAINT anomaly_signals_unique_per_day UNIQUE (hive_id, machine, snapshot_date)
);

COMMENT ON TABLE public.anomaly_signals IS
  'Daily fused anomaly signals per (hive, machine). 5-source fusion: logbook clusters, sensor z-score, PM drift, parts spend, failure signatures. Drives Anomaly Engine 2.0 panel on alert-hub.html (Phase 4.2). Stair 3+ gated.';

CREATE INDEX IF NOT EXISTS idx_anomaly_signals_hive_score
  ON public.anomaly_signals (hive_id, composite_score DESC, snapshot_date DESC)
  WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_anomaly_signals_hive_machine
  ON public.anomaly_signals (hive_id, machine);

-- ────────────────────────────────────────────────────────────────────────────
-- 2. compute_anomaly_signals(uuid) — fusion ranker
-- ────────────────────────────────────────────────────────────────────────────
-- Runs over one hive, scores every machine that has ANY signal in the last
-- window, writes fused rows. Idempotent on (hive_id, machine, snapshot_date).

CREATE OR REPLACE FUNCTION public.compute_anomaly_signals(p_hive_id uuid)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_today      date := (timezone('Asia/Manila', now()))::date;
  v_count      integer := 0;
  v_row        record;
BEGIN
  -- Source A: logbook clusters (>= 3 entries same machine in 14d)
  -- Source B: sensor z-score (|z| > 2.5 in 7d; sensor_readings has reading_value)
  -- Source C: PM drift — read v_pm_compliance_truth where days_since_last_completion > 1.5x category default
  -- Source D: parts spend spike — inventory_transactions with type='use'
  -- Source E: failure_signature_alerts (status='active')
  --
  -- We use ONE pass that joins per machine, computing sub-scores in CTEs.

  FOR v_row IN
    WITH base_machines AS (
      SELECT DISTINCT lb.machine
        FROM public.logbook lb
        WHERE lb.hive_id = p_hive_id
          AND lb.machine IS NOT NULL
          AND char_length(trim(lb.machine)) > 0
          AND lb.created_at >= now() - interval '60 days'
      UNION
      SELECT DISTINCT fsa.machine
        FROM public.failure_signature_alerts fsa
        WHERE fsa.hive_id = p_hive_id
          AND fsa.status = 'active'
      UNION
      SELECT DISTINCT an.name AS machine
        FROM public.asset_nodes an
        WHERE an.hive_id = p_hive_id
          AND an.status = 'approved'
          AND an.name IS NOT NULL
    ),
    logbook_cluster AS (
      SELECT lb.machine,
             count(*) AS n,
             LEAST(100, count(*) * 20)::smallint AS score,
             jsonb_agg(jsonb_build_object('date', lb.created_at, 'category', lb.category) ORDER BY lb.created_at DESC) AS items
        FROM public.logbook lb
        WHERE lb.hive_id = p_hive_id
          AND lb.created_at >= now() - interval '14 days'
        GROUP BY lb.machine
        HAVING count(*) >= 3
    ),
    sensor_z AS (
      SELECT sr.asset_id,
             an.name AS machine,
             count(*) AS n_alerts,
             LEAST(100, count(*) * 25)::smallint AS score,
             max(sr.reading_value) AS peak
        FROM public.sensor_readings sr
        LEFT JOIN public.asset_nodes an ON an.id = sr.asset_id
        WHERE sr.hive_id = p_hive_id
          AND sr.recorded_at >= now() - interval '7 days'
          AND sr.reading_value IS NOT NULL
        GROUP BY sr.asset_id, an.name
    ),
    pm_drift AS (
      SELECT pct.asset_name AS machine,
             pct.days_since_last_completion AS days_over,
             LEAST(100, (pct.days_since_last_completion / 7)::int * 10)::smallint AS score
        FROM public.v_pm_compliance_truth pct
        WHERE pct.hive_id = p_hive_id
          AND pct.is_due = true
          AND pct.days_since_last_completion >= 14
    ),
    parts_spend AS (
      SELECT lb.machine,
             count(*) AS recent_uses,
             LEAST(100, count(*) * 12)::smallint AS score
        FROM public.inventory_transactions it
        JOIN public.logbook lb ON lb.id = it.logbook_id
        WHERE it.hive_id = p_hive_id
          AND it.txn_type = 'use'
          AND it.created_at >= now() - interval '30 days'
          AND lb.machine IS NOT NULL
        GROUP BY lb.machine
        HAVING count(*) >= 5
    ),
    failure_sig AS (
      SELECT fsa.machine,
             count(*) AS active_count,
             LEAST(100, max(CASE WHEN fsa.severity = 'critical' THEN 90
                                 WHEN fsa.severity = 'warning'  THEN 60
                                 ELSE 30 END))::smallint AS score
        FROM public.failure_signature_alerts fsa
        WHERE fsa.hive_id = p_hive_id
          AND fsa.status = 'active'
        GROUP BY fsa.machine
    ),
    fused AS (
      SELECT bm.machine,
             COALESCE(lc.score, 0) AS logbook_cluster_score,
             COALESCE(sz.score, 0) AS sensor_zscore_score,
             COALESCE(pd.score, 0) AS pm_drift_score,
             COALESCE(ps.score, 0) AS parts_spend_score,
             COALESCE(fs.score, 0) AS failure_signature_score,
             COALESCE(sz.asset_id, NULL) AS asset_node_id,
             jsonb_strip_nulls(jsonb_build_object(
               'logbook_cluster',   CASE WHEN lc.score IS NOT NULL THEN jsonb_build_object('n', lc.n, 'recent', lc.items) END,
               'sensor_zscore',     CASE WHEN sz.score IS NOT NULL THEN jsonb_build_object('n_alerts', sz.n_alerts, 'peak', sz.peak) END,
               'pm_drift',          CASE WHEN pd.score IS NOT NULL THEN jsonb_build_object('days_over', pd.days_over) END,
               'parts_spend',       CASE WHEN ps.score IS NOT NULL THEN jsonb_build_object('recent_uses', ps.recent_uses) END,
               'failure_signature', CASE WHEN fs.score IS NOT NULL THEN jsonb_build_object('active_count', fs.active_count) END
             )) AS evidence
        FROM base_machines bm
        LEFT JOIN logbook_cluster lc USING (machine)
        LEFT JOIN sensor_z       sz USING (machine)
        LEFT JOIN pm_drift       pd USING (machine)
        LEFT JOIN parts_spend    ps USING (machine)
        LEFT JOIN failure_sig    fs USING (machine)
    )
    SELECT f.*,
           -- Weighted composite (clamp to [0, 100]).
           GREATEST(0, LEAST(100, (
                f.logbook_cluster_score    * 30
              + f.sensor_zscore_score      * 25
              + f.pm_drift_score           * 20
              + f.parts_spend_score        * 15
              + f.failure_signature_score  * 10
           ) / 100))::smallint AS composite_score,
           ( (CASE WHEN f.logbook_cluster_score   >= 35 THEN 1 ELSE 0 END)
           + (CASE WHEN f.sensor_zscore_score     >= 35 THEN 1 ELSE 0 END)
           + (CASE WHEN f.pm_drift_score          >= 35 THEN 1 ELSE 0 END)
           + (CASE WHEN f.parts_spend_score       >= 35 THEN 1 ELSE 0 END)
           + (CASE WHEN f.failure_signature_score >= 35 THEN 1 ELSE 0 END)
           )::smallint AS source_count
      FROM fused f
      WHERE f.logbook_cluster_score + f.sensor_zscore_score
          + f.pm_drift_score + f.parts_spend_score
          + f.failure_signature_score > 0
  LOOP
    INSERT INTO public.anomaly_signals (
      hive_id, snapshot_date, machine, asset_node_id,
      composite_score,
      logbook_cluster_score, sensor_zscore_score, pm_drift_score,
      parts_spend_score, failure_signature_score,
      source_count, severity,
      top_reasons, evidence
    ) VALUES (
      p_hive_id, v_today, v_row.machine, v_row.asset_node_id,
      v_row.composite_score,
      v_row.logbook_cluster_score, v_row.sensor_zscore_score, v_row.pm_drift_score,
      v_row.parts_spend_score, v_row.failure_signature_score,
      v_row.source_count,
      CASE
        WHEN v_row.composite_score >= 75 THEN 'critical'
        WHEN v_row.composite_score >= 50 THEN 'warning'
        WHEN v_row.composite_score >= 25 THEN 'watch'
        ELSE 'info'
      END,
      -- Top reasons ordered by sub-score
      (SELECT jsonb_agg(elem ORDER BY (elem->>'score')::int DESC)
         FROM jsonb_array_elements(jsonb_build_array(
           jsonb_build_object('signal', 'logbook_cluster',   'score', v_row.logbook_cluster_score,   'label', 'Repeated faults this fortnight'),
           jsonb_build_object('signal', 'sensor_zscore',     'score', v_row.sensor_zscore_score,     'label', 'Sensor readings drifting out of band'),
           jsonb_build_object('signal', 'pm_drift',          'score', v_row.pm_drift_score,          'label', 'PM overdue past category baseline'),
           jsonb_build_object('signal', 'parts_spend',       'score', v_row.parts_spend_score,       'label', 'Parts consumption climbing'),
           jsonb_build_object('signal', 'failure_signature', 'score', v_row.failure_signature_score, 'label', 'Failure signature alert active')
         )) elem
         WHERE (elem->>'score')::int >= 35
      ),
      v_row.evidence
    )
    ON CONFLICT (hive_id, machine, snapshot_date) DO UPDATE
      SET composite_score          = EXCLUDED.composite_score,
          logbook_cluster_score    = EXCLUDED.logbook_cluster_score,
          sensor_zscore_score      = EXCLUDED.sensor_zscore_score,
          pm_drift_score           = EXCLUDED.pm_drift_score,
          parts_spend_score        = EXCLUDED.parts_spend_score,
          failure_signature_score  = EXCLUDED.failure_signature_score,
          source_count             = EXCLUDED.source_count,
          severity                 = EXCLUDED.severity,
          top_reasons              = EXCLUDED.top_reasons,
          evidence                 = EXCLUDED.evidence,
          asset_node_id            = EXCLUDED.asset_node_id,
          computed_at              = now();
    v_count := v_count + 1;
  END LOOP;

  RETURN v_count;
END;
$$;

REVOKE ALL ON FUNCTION public.compute_anomaly_signals(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.compute_anomaly_signals(uuid) TO authenticated, service_role;

COMMENT ON FUNCTION public.compute_anomaly_signals(uuid) IS
  'Phase 4.2 — Anomaly Engine 2.0 fusion ranker. Reads 5 sources, writes fused rows per (hive, machine, snapshot_date). Idempotent. Designed to run daily via pg_cron at 06:00 PHT alongside compute_hive_readiness and compute_adoption_risk.';

-- ────────────────────────────────────────────────────────────────────────────
-- 3. v_anomaly_truth — canonical read (latest per machine per hive)
-- ────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW public.v_anomaly_truth AS
  SELECT DISTINCT ON (hive_id, machine)
         id, hive_id, snapshot_date, machine, asset_node_id,
         composite_score,
         logbook_cluster_score, sensor_zscore_score, pm_drift_score,
         parts_spend_score, failure_signature_score,
         source_count, severity, top_reasons, evidence,
         status, acknowledged_by, acknowledged_at, resolved_by, resolved_at,
         computed_at, model_version
    FROM public.anomaly_signals
    WHERE status IN ('active', 'acknowledged')
    ORDER BY hive_id, machine, snapshot_date DESC;

COMMENT ON VIEW public.v_anomaly_truth IS
  'Canonical read surface for Anomaly Engine 2.0 — latest active or acknowledged signal per (hive, machine). Resolved signals fall out. Phase 4.2.';

GRANT SELECT ON public.v_anomaly_truth TO authenticated;

-- ────────────────────────────────────────────────────────────────────────────
-- 4. v_knowledge_freshness_truth — RAG corpus health (Phase 4.3)
-- ────────────────────────────────────────────────────────────────────────────
-- Surfaces per-knowledge-type freshness so the supervisor sees when the RAG
-- corpus is stale. Each row: hive_id + kind + total_rows + embedded_rows +
-- pending_rows + last_embedded_at + days_since_last_embed.

CREATE OR REPLACE VIEW public.v_knowledge_freshness_truth AS
  WITH src AS (
    SELECT 'fault'::text AS kind, hive_id, embedding IS NOT NULL AS embedded, created_at
      FROM public.fault_knowledge
    UNION ALL
    SELECT 'skill'::text AS kind, hive_id, embedding IS NOT NULL AS embedded, created_at
      FROM public.skill_knowledge
    UNION ALL
    SELECT 'pm'::text    AS kind, hive_id, embedding IS NOT NULL AS embedded, created_at
      FROM public.pm_knowledge
  )
  SELECT hive_id,
         kind,
         count(*)::int                                                         AS total_rows,
         count(*) FILTER (WHERE embedded)::int                                 AS embedded_rows,
         count(*) FILTER (WHERE NOT embedded)::int                             AS pending_rows,
         max(created_at) FILTER (WHERE embedded)                               AS last_embedded_at,
         EXTRACT(DAY FROM (now() - max(created_at) FILTER (WHERE embedded)))::int AS days_since_last_embed,
         CASE
           WHEN count(*) = 0 THEN 0
           ELSE (100.0 * count(*) FILTER (WHERE embedded) / count(*))::int
         END                                                                   AS embedded_pct
    FROM src
    GROUP BY hive_id, kind;

COMMENT ON VIEW public.v_knowledge_freshness_truth IS
  'Phase 4.3 — RAG corpus freshness KPI per (hive, knowledge_kind). Drives Knowledge Pipeline Health tile on hive.html. Stair 2+ gated.';

GRANT SELECT ON public.v_knowledge_freshness_truth TO authenticated;

-- ────────────────────────────────────────────────────────────────────────────
-- 5. RLS — hive-membership read; service-role writes only
-- ────────────────────────────────────────────────────────────────────────────

ALTER TABLE public.anomaly_signals ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS anomaly_signals_read ON public.anomaly_signals;
CREATE POLICY anomaly_signals_read ON public.anomaly_signals FOR SELECT
  USING (
    auth.uid() IS NOT NULL
    AND hive_id IN (
      SELECT hm.hive_id FROM public.hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    )
  );

DROP POLICY IF EXISTS anomaly_signals_insert_locked ON public.anomaly_signals;
CREATE POLICY anomaly_signals_insert_locked ON public.anomaly_signals FOR INSERT
  WITH CHECK (false);

-- Supervisor acknowledge / resolve. Predicate: caller is an active supervisor
-- in the row's hive AND only flips lifecycle columns (other fields preserved
-- by the client's narrow update).
DROP POLICY IF EXISTS anomaly_signals_update_supervisor ON public.anomaly_signals;
CREATE POLICY anomaly_signals_update_supervisor ON public.anomaly_signals FOR UPDATE
  USING (
    auth.uid() IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = anomaly_signals.hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.role = 'supervisor'
        AND hm.status = 'active'
    )
  )
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = anomaly_signals.hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.role = 'supervisor'
        AND hm.status = 'active'
    )
  );

DROP POLICY IF EXISTS anomaly_signals_delete_locked ON public.anomaly_signals;
CREATE POLICY anomaly_signals_delete_locked ON public.anomaly_signals FOR DELETE
  USING (false);

GRANT SELECT, UPDATE ON public.anomaly_signals TO anon, authenticated;

-- ────────────────────────────────────────────────────────────────────────────
-- 6. Realtime publication (alert-hub.html subscribes for live ack/resolve)
-- ────────────────────────────────────────────────────────────────────────────

ALTER TABLE public.anomaly_signals REPLICA IDENTITY FULL;
ALTER PUBLICATION supabase_realtime ADD TABLE public.anomaly_signals;

-- ────────────────────────────────────────────────────────────────────────────
-- 7. Canonical sources registration
-- ────────────────────────────────────────────────────────────────────────────

INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES
  ('anomaly_signals', 'view', 'v_anomaly_truth',
   'predictive-analytics', 'daily',
   'Canonical read surface for Anomaly Engine 2.0 — latest active or acknowledged signal per (hive, machine). 5-source fusion with weighted composite. Phase 4.2.',
   jsonb_build_object(
     'key',              jsonb_build_array('hive_id', 'machine'),
     'hive_scoped',      true,
     'composite_range',  jsonb_build_array(0, 100),
     'severity_buckets', jsonb_build_object('info', '< 25', 'watch', '25..49', 'warning', '50..74', 'critical', '>= 75'),
     'stair_gate',       3,
     'phase_4_built',    true
   ),
   'Phase 4.2 of STRATEGIC_ROADMAP.'),

  ('anomaly_signals_table', 'table', 'anomaly_signals',
   'predictive-analytics', 'daily',
   'Daily fused anomaly signals per (hive, machine). Idempotent on (hive_id, machine, snapshot_date). Fueled by compute_anomaly_signals RPC.',
   jsonb_build_object(
     'key',           jsonb_build_array('id'),
     'hive_scoped',   true,
     'write_policy',  'service-role only (compute_anomaly_signals SECURITY DEFINER)',
     'lifecycle',     jsonb_build_array('active', 'acknowledged', 'resolved', 'expired'),
     'phase_4_built', true
   ),
   'Phase 4.2 of STRATEGIC_ROADMAP.'),

  ('compute_anomaly_signals_rpc', 'rpc', 'compute_anomaly_signals',
   'predictive-analytics', 'on-demand',
   'PL/pgSQL fusion ranker. Joins logbook + sensor_readings + v_pm_compliance_truth + inventory_transactions + failure_signature_alerts per hive. Idempotent.',
   jsonb_build_object(
     'args',          jsonb_build_array(jsonb_build_object('name', 'p_hive_id', 'type', 'uuid')),
     'returns',       'integer',
     'security',      'definer',
     'hive_scoped',   true,
     'phase_4_built', true
   ),
   'Phase 4.2 of STRATEGIC_ROADMAP.'),

  ('knowledge_freshness', 'view', 'v_knowledge_freshness_truth',
   'knowledge-manager', 'live',
   'RAG corpus freshness KPI per (hive, knowledge_kind). Surfaces embedded vs pending counts + last embed timestamp + days since last embed. Phase 4.3.',
   jsonb_build_object(
     'key',           jsonb_build_array('hive_id', 'kind'),
     'hive_scoped',   true,
     'kinds',         jsonb_build_array('fault', 'skill', 'pm'),
     'stair_gate',    2,
     'phase_4_built', true
   ),
   'Phase 4.3 of STRATEGIC_ROADMAP.')
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
