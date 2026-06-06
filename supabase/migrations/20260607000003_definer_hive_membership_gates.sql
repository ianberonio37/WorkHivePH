-- ============================================================================
-- 20260607000003  SECURITY DEFINER hive-membership gates (Group A)
-- ============================================================================
-- Audit finding (2026-06-07): a class of SECURITY DEFINER, hive-scoped RPCs
-- bypassed RLS but did NOT re-check the caller's hive membership, so any
-- authenticated (or anon/PUBLIC) user could pass a foreign p_hive_id straight
-- to PostgREST and read/compute another hive's data -- a horizontal-privilege
-- (IDOR) leak invisible to RLS-policy validators.
--
-- These 6 functions ARE called from the browser with the user's JWT, so the
-- fix is the in-function gate (auth.uid() membership check), matching the
-- get_hive_dashboard reference. The 3 backend-only siblings (get_oee_by_machine,
-- match_procedural_memories, increment_community_xp) are locked down by grant
-- in the companion migration ...0004 instead.
--
-- Skills: security ("SECURITY DEFINER = an RLS bypass"), multitenant-engineer
-- ("SECURITY DEFINER RPCs Must Self-Enforce Hive Membership"), data-engineer.
-- No table/return-type changes -> no canonical/formula drift. Deploy PENDING.
-- ============================================================================

BEGIN;

create or replace function fetch_active_alerts(p_hive_id uuid)
returns table (
  alert_id bigint,
  alert_type text,
  severity text,
  description text,
  action_suggested text,
  deviation_percent real,
  detected_at timestamptz
) as $$
begin
  -- HIVE MEMBERSHIP GATE (cross-hive read/write prevention) --------------
  -- SECURITY DEFINER bypasses RLS, so this fn re-authenticates the caller:
  -- an authenticated user must be an ACTIVE member of p_hive_id. service_role
  -- (trusted edge backend) bypasses; anon has no auth.uid() so it is denied;
  -- NULL hive (solo) skips -- no tenant to leak. See security + multitenant
  -- skills: "SECURITY DEFINER RPCs Must Self-Enforce Hive Membership".
  IF p_hive_id IS NOT NULL
     AND auth.role() <> 'service_role'
     AND NOT EXISTS (
       SELECT 1 FROM public.hive_members
       WHERE hive_id = p_hive_id AND auth_uid = auth.uid() AND status = 'active'
     ) THEN
    RAISE EXCEPTION 'fetch_active_alerts: caller is not an active member of hive %', p_hive_id
      USING ERRCODE = '42501';
  END IF;

  return query
  select
    aa.id, aa.alert_type, aa.severity, aa.description,
    aa.action_suggested, aa.deviation_percent, aa.detected_at
  from anomaly_alerts aa
  where aa.hive_id = p_hive_id
    and (aa.suppressed_until is null or aa.suppressed_until < now())
    and aa.acknowledged_at is null
  order by
    case when aa.severity = 'critical' then 1
         when aa.severity = 'high' then 2
         when aa.severity = 'medium' then 3
         else 4 end,
    aa.detected_at desc
  limit 10;
end;
$$ language plpgsql security definer set search_path = public;

create or replace function semantic_search_kb(
  p_hive_id uuid,
  p_query_embedding vector,
  p_similarity_threshold real default 0.7,
  p_limit int default 5
)
returns table (
  chunk_id bigint,
  doc_id bigint,
  doc_title text,
  chunk_text text,
  similarity_score real
) as $$
begin
  -- HIVE MEMBERSHIP GATE (cross-hive read/write prevention) --------------
  -- SECURITY DEFINER bypasses RLS, so this fn re-authenticates the caller:
  -- an authenticated user must be an ACTIVE member of p_hive_id. service_role
  -- (trusted edge backend) bypasses; anon has no auth.uid() so it is denied;
  -- NULL hive (solo) skips -- no tenant to leak. See security + multitenant
  -- skills: "SECURITY DEFINER RPCs Must Self-Enforce Hive Membership".
  IF p_hive_id IS NOT NULL
     AND auth.role() <> 'service_role'
     AND NOT EXISTS (
       SELECT 1 FROM public.hive_members
       WHERE hive_id = p_hive_id AND auth_uid = auth.uid() AND status = 'active'
     ) THEN
    RAISE EXCEPTION 'semantic_search_kb: caller is not an active member of hive %', p_hive_id
      USING ERRCODE = '42501';
  END IF;

  return query
  select
    kc.id,
    kc.doc_id,
    kd.title,
    kc.text,
    (kc.embedding <=> p_query_embedding) as sim
  from kb_chunks kc
  join kb_documents kd on kc.doc_id = kd.id
  where kd.hive_id = p_hive_id
    and kc.embedding is not null
    and (kc.embedding <=> p_query_embedding) <= (1 - p_similarity_threshold)
  order by kc.embedding <=> p_query_embedding
  limit p_limit;
end;
$$ language plpgsql security definer set search_path = public;

CREATE OR REPLACE FUNCTION semantic_search_kg_facts(
  p_hive_id               uuid,
  p_query_embedding       vector,
  p_similarity_threshold  real DEFAULT 0.5,
  p_limit                 int  DEFAULT 5,
  p_min_confidence        real DEFAULT 0.5
)
RETURNS TABLE (
  fact_id          uuid,
  subject_ref      text,
  predicate        text,
  object_ref       text,
  claim_text       text,
  confidence       numeric,
  source_type      text,
  source_ref       text,
  similarity_score real
) AS $$
BEGIN
  -- HIVE MEMBERSHIP GATE (cross-hive read/write prevention) --------------
  -- SECURITY DEFINER bypasses RLS, so this fn re-authenticates the caller:
  -- an authenticated user must be an ACTIVE member of p_hive_id. service_role
  -- (trusted edge backend) bypasses; anon has no auth.uid() so it is denied;
  -- NULL hive (solo) skips -- no tenant to leak. See security + multitenant
  -- skills: "SECURITY DEFINER RPCs Must Self-Enforce Hive Membership".
  IF p_hive_id IS NOT NULL
     AND auth.role() <> 'service_role'
     AND NOT EXISTS (
       SELECT 1 FROM public.hive_members
       WHERE hive_id = p_hive_id AND auth_uid = auth.uid() AND status = 'active'
     ) THEN
    RAISE EXCEPTION 'semantic_search_kg_facts: caller is not an active member of hive %', p_hive_id
      USING ERRCODE = '42501';
  END IF;

  RETURN QUERY
  SELECT
    f.id                                AS fact_id,
    f.subject_ref,
    f.predicate,
    f.object_ref,
    f.claim_text,
    f.confidence,
    f.source_type,
    f.source_ref,
    (f.embedding <=> p_query_embedding)::real AS similarity_score
  FROM public.knowledge_graph_facts f
  WHERE f.hive_id     = p_hive_id
    AND f.active      = true
    AND f.embedding   IS NOT NULL
    AND f.confidence  >= p_min_confidence
    AND (f.embedding <=> p_query_embedding) <= (1 - p_similarity_threshold)
  ORDER BY f.embedding <=> p_query_embedding
  LIMIT p_limit;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

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
  -- HIVE MEMBERSHIP GATE (cross-hive read/write prevention) --------------
  -- SECURITY DEFINER bypasses RLS, so this fn re-authenticates the caller:
  -- an authenticated user must be an ACTIVE member of p_hive_id. service_role
  -- (trusted edge backend) bypasses; anon has no auth.uid() so it is denied;
  -- NULL hive (solo) skips -- no tenant to leak. See security + multitenant
  -- skills: "SECURITY DEFINER RPCs Must Self-Enforce Hive Membership".
  IF p_hive_id IS NOT NULL
     AND auth.role() <> 'service_role'
     AND NOT EXISTS (
       SELECT 1 FROM public.hive_members
       WHERE hive_id = p_hive_id AND auth_uid = auth.uid() AND status = 'active'
     ) THEN
    RAISE EXCEPTION 'compute_anomaly_signals: caller is not an active member of hive %', p_hive_id
      USING ERRCODE = '42501';
  END IF;

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
      -- Walkthrough fix: column is `value`, not `reading_value`.
      SELECT sr.asset_id,
             an.name AS machine,
             count(*) AS n_alerts,
             LEAST(100, count(*) * 25)::smallint AS score,
             max(sr.value) AS peak
        FROM public.sensor_readings sr
        LEFT JOIN public.asset_nodes an ON an.id = sr.asset_id
        WHERE sr.hive_id = p_hive_id
          AND sr.recorded_at >= now() - interval '7 days'
          AND sr.value IS NOT NULL
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
      -- Walkthrough fix: inventory_transactions has no FK to logbook
      -- (its actual columns are item_id + job_ref text), so we cannot bind
      -- a parts-spend signal to a specific machine without a heuristic
      -- text-match on job_ref. Leaving this CTE empty until the schema
      -- gains a stronger FK or we add an asset_id column to
      -- inventory_transactions. Anomaly Engine 2.0 continues with the
      -- other 4 sources (logbook cluster + sensor zscore + pm drift +
      -- failure signature) which is still meaningful.
      SELECT NULL::text AS machine,
             0::integer AS recent_uses,
             0::smallint AS score
      WHERE false
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

CREATE OR REPLACE FUNCTION public.get_hive_readiness_current(p_hive_id uuid)
RETURNS public.hive_readiness
LANGUAGE sql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
  -- HIVE MEMBERSHIP GATE: WHERE-guard preserves the original 0-or-1-row
  -- cardinality (a non-member simply gets no row, never another hive's row).
  -- service_role (backend) bypasses; anon has no auth.uid() so EXISTS is false.
  SELECT *
  FROM public.hive_readiness
  WHERE hive_id = p_hive_id
    AND (
      auth.role() = 'service_role'
      OR EXISTS (
        SELECT 1 FROM public.hive_members
        WHERE hive_id = p_hive_id AND auth_uid = auth.uid() AND status = 'active'
      )
    )
  ORDER BY snapshot_date DESC, computed_at DESC
  LIMIT 1;
$$;

CREATE OR REPLACE FUNCTION public.get_adoption_risk_current(p_hive_id uuid)
RETURNS public.hive_adoption_score
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
  -- HIVE MEMBERSHIP GATE: WHERE-guard preserves the original 0-or-1-row
  -- cardinality. service_role bypasses; anon has no auth.uid().
  SELECT *
    FROM public.hive_adoption_score
    WHERE hive_id = p_hive_id
      AND (
        auth.role() = 'service_role'
        OR EXISTS (
          SELECT 1 FROM public.hive_members
          WHERE hive_id = p_hive_id AND auth_uid = auth.uid() AND status = 'active'
        )
      )
    ORDER BY snapshot_date DESC
    LIMIT 1;
$$;

-- Grant tightening: hive data is for authenticated members (gated above)
-- + the trusted service_role backend only. anon must never reach it.
REVOKE EXECUTE ON FUNCTION public.fetch_active_alerts(uuid) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION public.fetch_active_alerts(uuid) TO authenticated, service_role;

REVOKE EXECUTE ON FUNCTION public.semantic_search_kb(uuid, vector, real, int) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION public.semantic_search_kb(uuid, vector, real, int) TO authenticated, service_role;

REVOKE EXECUTE ON FUNCTION public.semantic_search_kg_facts(uuid, vector, real, int, real) FROM anon;
GRANT  EXECUTE ON FUNCTION public.semantic_search_kg_facts(uuid, vector, real, int, real) TO authenticated, service_role;

REVOKE EXECUTE ON FUNCTION public.get_hive_readiness_current(uuid) FROM anon;
GRANT  EXECUTE ON FUNCTION public.get_hive_readiness_current(uuid) TO authenticated, service_role;

COMMIT;
