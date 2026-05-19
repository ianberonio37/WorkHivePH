-- Promote get_oee_by_machine to FULL OEE when asset_nodes.ideal_cycle_time_seconds
-- is captured for the asset.
--
-- Performance factor = (ideal_cycle_time_seconds × units_produced) / run_time_seconds
-- The platform's production_output JSONB carries per-entry units; until a
-- canonical per-asset run-time signal lands, we approximate run_time as the
-- (period_total_hours - downtime_hours) bucket already used for Availability.
--
-- Decision rule:
--   Full OEE   = A × P × Q          when ideal_cycle_time AND units_produced AND quality present
--   Partial    = A × Q              when ideal_cycle_time is null or units_produced missing
-- The is_partial boolean tells consumers which branch was taken.

BEGIN;

CREATE OR REPLACE FUNCTION public.get_oee_by_machine(
  p_hive_id     uuid,
  p_period_days int DEFAULT 90
)
RETURNS TABLE (
  machine            text,
  availability_pct   numeric,
  performance_pct    numeric,
  quality_pct        numeric,
  oee_pct            numeric,
  is_partial         boolean
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
  WITH params AS (
    SELECT (p_period_days * 8.0)::numeric AS total_hours
  ),
  downtime AS (
    SELECT
      l.machine,
      COALESCE(SUM(NULLIF(l.downtime_hours::text, '')::numeric), 0) AS dt_hours
    FROM public.logbook l
    WHERE l.hive_id = p_hive_id
      AND l.maintenance_type = 'Breakdown / Corrective'
      AND l.created_at >= NOW() - (p_period_days || ' days')::interval
    GROUP BY l.machine
  ),
  quality AS (
    SELECT
      l.machine,
      AVG(
        CASE
          WHEN (l.production_output ->> 'quality_pct') ~ '^[0-9]+(\.[0-9]+)?$'
            THEN ((l.production_output ->> 'quality_pct')::numeric)
          ELSE NULL
        END
      ) AS quality_avg,
      SUM(
        CASE
          WHEN (l.production_output ->> 'units_produced') ~ '^[0-9]+(\.[0-9]+)?$'
            THEN ((l.production_output ->> 'units_produced')::numeric)
          ELSE 0
        END
      ) AS units_total
    FROM public.logbook l
    WHERE l.hive_id = p_hive_id
      AND l.created_at >= NOW() - (p_period_days || ' days')::interval
    GROUP BY l.machine
  ),
  -- Ideal cycle time joined by asset tag (machine name = asset_nodes.tag in hive scope)
  rate AS (
    SELECT
      n.tag                          AS machine,
      n.ideal_cycle_time_seconds     AS ideal_sec
    FROM public.asset_nodes n
    WHERE n.hive_id = p_hive_id
      AND n.ideal_cycle_time_seconds IS NOT NULL
  ),
  combined AS (
    SELECT
      COALESCE(d.machine, q.machine, r.machine) AS machine,
      ROUND(
        GREATEST(0, LEAST(100,
          ((SELECT total_hours FROM params) - COALESCE(d.dt_hours, 0))
          / NULLIF((SELECT total_hours FROM params), 0) * 100
        ))::numeric, 1
      ) AS availability_pct,
      -- Performance: requires ideal_cycle_time AND units_produced.
      -- run_time_seconds = (total_hours - downtime_hours) * 3600
      -- ideal_total      = ideal_sec * units_total
      -- perf_pct         = (ideal_total / run_time_seconds) * 100, clamped to 100.
      CASE
        WHEN r.ideal_sec IS NOT NULL
         AND q.units_total IS NOT NULL
         AND q.units_total > 0
         AND ((SELECT total_hours FROM params) - COALESCE(d.dt_hours, 0)) > 0
        THEN ROUND(
          LEAST(100,
            (r.ideal_sec * q.units_total)
            / (((SELECT total_hours FROM params) - COALESCE(d.dt_hours, 0)) * 3600)
            * 100
          )::numeric, 1
        )
        ELSE NULL
      END AS performance_pct,
      ROUND(LEAST(100, COALESCE(q.quality_avg, NULL))::numeric, 1) AS quality_pct,
      r.ideal_sec
    FROM downtime d
    FULL OUTER JOIN quality q ON d.machine = q.machine
    FULL OUTER JOIN rate    r ON COALESCE(d.machine, q.machine) = r.machine
  )
  SELECT
    c.machine,
    c.availability_pct,
    c.performance_pct,
    c.quality_pct,
    CASE
      WHEN c.performance_pct IS NOT NULL
       AND c.availability_pct IS NOT NULL
       AND c.quality_pct      IS NOT NULL
        THEN ROUND((c.availability_pct * c.performance_pct * c.quality_pct / 10000)::numeric, 1)
      WHEN c.availability_pct IS NOT NULL
       AND c.quality_pct      IS NOT NULL
        THEN ROUND((c.availability_pct * c.quality_pct / 100)::numeric, 1)
      ELSE NULL
    END AS oee_pct,
    (c.performance_pct IS NULL) AS is_partial
  FROM combined c
  WHERE c.machine IS NOT NULL
  ORDER BY c.machine;
$$;

COMMENT ON FUNCTION public.get_oee_by_machine IS
  'Tier E canonical OEE per machine. Reads asset_nodes.ideal_cycle_time_seconds to compute the Performance factor. Returns full OEE = A × P × Q when ideal cycle time and units_produced are both present; otherwise returns partial (A × Q) with is_partial=true.';

GRANT EXECUTE ON FUNCTION public.get_oee_by_machine(uuid, int) TO anon, authenticated;

COMMIT;
