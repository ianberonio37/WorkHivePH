-- Analytics Engine arc F1b (2026-07-10): unify OEE quality across the analytics page and the report.
--
-- BUG: get_oee_by_machine (used by analytics-orchestrator's REPORT path → analytics-report.html /
-- asset-hub) computed the OEE Quality dimension by reading ONLY production_output->>'quality_pct'
-- and over ALL logbook rows. But the seeders/UI write the {good_units, total_units} shape (Lucena:
-- 0 rows carry quality_pct, 60 carry good/total), so the RPC's quality defaulted high (~100%) and
-- OEE collapsed to Availability — the SAME "read only quality_pct" bug the Python engine
-- (descriptive.calc_oee) already fixed in May 2026 but that never reached this RPC. Result: the
-- report/asset-hub OEE ran ~10 points HIGHER than the value-validated analytics page for the same
-- asset (e.g. AC-001 96.6% vs the page's ~87%).
--
-- FIX: mirror descriptive.calc_oee exactly — (1) derive quality from good_units/total_units when
-- quality_pct is absent, and (2) scope the quality read to corrective ('Breakdown / Corrective')
-- rows, matching the Python engine (validate_analytics_correctness proves the Python OEE correct).
-- Now the RPC == the page for the same hive. Availability/Performance dimensions are unchanged.
--
-- Anti-seesaw note: the only value-consumer of this RPC is analytics-orchestrator's report path;
-- OEE is not cached (asset_risk_scores caches MTBF/risk, not OEE) and no gate hard-asserts the old
-- inflated value (analytics_correctness.js is DOM==source parity → moves with the RPC; render_sweep
-- dispositions OEE). Verified via a BEGIN/ROLLBACK transaction test before this migration.

CREATE OR REPLACE FUNCTION public.get_oee_by_machine(p_hive_id uuid, p_period_days integer DEFAULT 90)
 RETURNS TABLE(machine text, availability_pct numeric, performance_pct numeric, quality_pct numeric, oee_pct numeric, is_partial boolean)
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
  WITH params AS (
    SELECT (p_period_days * 8.0)::numeric AS total_hours
  ),
  downtime AS (
    SELECT l.machine, COALESCE(SUM(NULLIF(l.downtime_hours::text, '')::numeric), 0) AS dt_hours
    FROM public.logbook l
    WHERE l.hive_id = p_hive_id AND l.maintenance_type = 'Breakdown / Corrective'
      AND l.created_at >= NOW() - (p_period_days || ' days')::interval
    GROUP BY l.machine
  ),
  quality AS (
    SELECT l.machine,
      AVG(
        CASE
          WHEN (l.production_output ->> 'quality_pct') ~ '^[0-9]+(\.[0-9]+)?$'
            THEN (l.production_output ->> 'quality_pct')::numeric
          -- Derive from good/total when explicit quality_pct is missing (matches
          -- descriptive.calc_oee; seeders/UI write this shape, not quality_pct).
          WHEN (l.production_output ->> 'good_units')  ~ '^[0-9]+(\.[0-9]+)?$'
           AND (l.production_output ->> 'total_units') ~ '^[0-9]+(\.[0-9]+)?$'
           AND (l.production_output ->> 'total_units')::numeric > 0
            THEN ROUND((l.production_output ->> 'good_units')::numeric / (l.production_output ->> 'total_units')::numeric * 100.0, 1)
          ELSE NULL
        END
      ) AS quality_avg,
      SUM(CASE WHEN (l.production_output ->> 'units_produced') ~ '^[0-9]+(\.[0-9]+)?$'
               THEN (l.production_output ->> 'units_produced')::numeric ELSE 0 END) AS units_total
    FROM public.logbook l
    WHERE l.hive_id = p_hive_id
      AND l.maintenance_type = 'Breakdown / Corrective'   -- corrective-scoped, matches the Python engine
      AND l.created_at >= NOW() - (p_period_days || ' days')::interval
    GROUP BY l.machine
  ),
  rate AS (
    SELECT n.tag AS machine, n.ideal_cycle_time_seconds AS ideal_sec
    FROM public.asset_nodes n
    WHERE n.hive_id = p_hive_id AND n.ideal_cycle_time_seconds IS NOT NULL
  ),
  combined AS (
    SELECT COALESCE(d.machine, q.machine, r.machine) AS machine,
      ROUND(GREATEST(0, LEAST(100,
        ((SELECT total_hours FROM params) - COALESCE(d.dt_hours, 0))
        / NULLIF((SELECT total_hours FROM params), 0) * 100))::numeric, 1) AS availability_pct,
      CASE
        WHEN r.ideal_sec IS NOT NULL AND q.units_total IS NOT NULL AND q.units_total > 0
         AND ((SELECT total_hours FROM params) - COALESCE(d.dt_hours, 0)) > 0
        THEN ROUND(LEAST(100,
          (r.ideal_sec * q.units_total)
          / (((SELECT total_hours FROM params) - COALESCE(d.dt_hours, 0)) * 3600) * 100)::numeric, 1)
        ELSE NULL
      END AS performance_pct,
      ROUND(LEAST(100, COALESCE(q.quality_avg, NULL))::numeric, 1) AS quality_pct,
      r.ideal_sec
    FROM downtime d
    FULL OUTER JOIN quality q ON d.machine = q.machine
    FULL OUTER JOIN rate    r ON COALESCE(d.machine, q.machine) = r.machine
  )
  SELECT c.machine, c.availability_pct, c.performance_pct, c.quality_pct,
    CASE
      WHEN c.performance_pct IS NOT NULL AND c.availability_pct IS NOT NULL AND c.quality_pct IS NOT NULL
        THEN ROUND((c.availability_pct * c.performance_pct * c.quality_pct / 10000)::numeric, 1)
      WHEN c.availability_pct IS NOT NULL AND c.quality_pct IS NOT NULL
        THEN ROUND((c.availability_pct * c.quality_pct / 100)::numeric, 1)
      ELSE NULL
    END AS oee_pct,
    (c.performance_pct IS NULL) AS is_partial
  FROM combined c
  WHERE c.machine IS NOT NULL
  ORDER BY c.machine;
$function$;
