-- ★A MACHINE THAT SIMPLY REPORTS WAS "DRIFTING OUT OF BAND" (2026-11-05, the group-journey walk GJ J17 hand-off 1).
-- The composer's sensor source counted EVERY reading of the last 7 days - count(*) with no anomaly test - and scored
-- 25 points a reading. Any machine on a live plant bridge passed four readings within the hour and was raised to the
-- crew as "Sensor readings drifting out of band" at score 100, however normal the values. The walk posted 41 healthy
-- vibration readings (2.0-2.2 mm/s), the ingest flagged none of them, and the composer still raised an anomaly on the
-- machine. The column was named n_alerts and the label promised readings out of band: the count was meant to be of
-- flagged readings, and sensor_readings.is_anomaly (set by sensor-readings-ingest when |z| > 3 against the reading's
-- own 30-day baseline, migration 20260728000018) is that flag. The source now counts only those, and its evidence
-- carries the time of the newest one so the alert can say WHEN the machine went out of band.

CREATE OR REPLACE FUNCTION public.compute_anomaly_signals(p_hive_id uuid)
 RETURNS integer
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
DECLARE
  v_today      date := (timezone('Asia/Manila', now()))::date;
  v_count      integer := 0;
  v_row        record;
BEGIN
  -- Arc G tenant-gate: authenticated callers may only act on a hive they actively belong to;
  -- service_role (cron/edge) bypasses. anon/non-members/spoofers are blocked (auth.uid() NULL -> no match).
  if coalesce(nullif(current_setting('request.jwt.claims', true), '')::json ->> 'role', '') <> 'service_role'
     and not exists (select 1 from hive_members hm
                     where hm.hive_id = p_hive_id and hm.auth_uid = auth.uid() and hm.status = 'active') then
    raise exception 'not authorized for hive %', p_hive_id using errcode = '42501';
  end if;

  FOR v_row IN
    WITH base_machines AS (
      SELECT DISTINCT lb.machine
        FROM public.logbook lb
        WHERE lb.hive_id = p_hive_id AND lb.deleted_at IS NULL
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
        WHERE an.hive_id = p_hive_id AND an.deleted_at IS NULL
          AND an.status = 'approved'
          AND an.name IS NOT NULL
    ),
    logbook_cluster AS (
      SELECT lb.machine,
             count(*) AS n,
             LEAST(100, count(*) * 20)::smallint AS score,
             jsonb_agg(jsonb_build_object('date', lb.created_at, 'category', lb.category) ORDER BY lb.created_at DESC) AS items
        FROM public.logbook lb
        WHERE lb.hive_id = p_hive_id AND lb.deleted_at IS NULL
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
             max(sr.value) AS peak,
             max(sr.recorded_at) AS last_at
        FROM public.sensor_readings sr
        LEFT JOIN public.asset_nodes an ON an.id = sr.asset_id AND an.deleted_at IS NULL
        WHERE sr.hive_id = p_hive_id AND (sr.asset_id IS NULL OR an.id IS NOT NULL)
          AND sr.recorded_at >= now() - interval '7 days'
          AND sr.value IS NOT NULL
          -- only the readings the ingest judged 3-sigma outside their own baseline (sensor-readings-ingest)
          AND sr.is_anomaly
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
               'sensor_zscore',     CASE WHEN sz.score IS NOT NULL THEN jsonb_build_object('n_alerts', sz.n_alerts, 'peak', sz.peak, 'last', sz.last_at) END,
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
      COALESCE((SELECT jsonb_agg(elem ORDER BY (elem->>'score')::int DESC)
         FROM jsonb_array_elements(jsonb_build_array(
           jsonb_build_object('signal', 'logbook_cluster',   'score', v_row.logbook_cluster_score,   'label', 'Repeated faults this fortnight'),
           jsonb_build_object('signal', 'sensor_zscore',     'score', v_row.sensor_zscore_score,     'label', 'Sensor readings drifting out of band'),
           jsonb_build_object('signal', 'pm_drift',          'score', v_row.pm_drift_score,          'label', 'PM overdue past category baseline'),
           jsonb_build_object('signal', 'parts_spend',       'score', v_row.parts_spend_score,       'label', 'Parts consumption climbing'),
           jsonb_build_object('signal', 'failure_signature', 'score', v_row.failure_signature_score, 'label', 'Failure signature alert active')
         )) elem
         WHERE (elem->>'score')::int >= 35
      ), '[]'::jsonb),
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
$function$;
