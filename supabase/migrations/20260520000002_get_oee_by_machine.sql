-- get_oee_by_machine RPC — Tier E (Engine) canonical OEE computation.
--
-- Promotes the OEE math from python-api/analytics/descriptive.py:calc_oee
-- to a deterministic SQL RPC so Asset Hub + Reliability Workbench + AI
-- agents can read OEE without each re-implementing it.
--
-- Formula:
--   FULL OEE    = Availability × Performance × Quality (Nakajima / ISO 22400-2:2014 §5.5)
--   PARTIAL OEE = Availability × Quality              (when Performance factor isn't captured)
--
-- The function returns BOTH variants so consumers can pick the right one
-- based on whether per-asset planned-rate data is available. Each row is
-- tagged with `is_partial = true` when the Performance factor was null/
-- unavailable and the partial formula was used.
--
-- Inputs:
--   p_hive_id     uuid   — required hive scope
--   p_period_days int    — window length, default 90
--
-- Output: one row per machine with availability_pct, performance_pct,
-- quality_pct, oee_pct, is_partial. Performance is null today (no per-
-- asset ideal cycle time yet); when that fuel field lands, the
-- performance_pct branch can be wired in without changing the RPC contract.
--
-- Standards: ISO 22400-2:2014 §5.5; Nakajima TPM (1988).
-- Contract: formula_id oee_iso_22400 (full) + oee_iso_22400_partial.

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
    SELECT (p_period_days * 8.0)::numeric AS total_hours  -- 8h shift × period_days
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
    -- Quality factor: pulled from logbook.production_output JSONB,
    -- specifically the `quality_pct` key. Falls back to NULL when missing.
    SELECT
      l.machine,
      AVG(
        CASE
          WHEN l.production_output IS NULL THEN NULL
          WHEN (l.production_output ->> 'quality_pct') ~ '^[0-9]+(\.[0-9]+)?$'
            THEN ((l.production_output ->> 'quality_pct')::numeric)
          ELSE NULL
        END
      ) AS quality_avg
    FROM public.logbook l
    WHERE l.hive_id = p_hive_id
      AND l.created_at >= NOW() - (p_period_days || ' days')::interval
    GROUP BY l.machine
  ),
  combined AS (
    SELECT
      COALESCE(d.machine, q.machine) AS machine,
      ROUND(
        GREATEST(0, LEAST(100,
          ((SELECT total_hours FROM params) - COALESCE(d.dt_hours, 0))
          / NULLIF((SELECT total_hours FROM params), 0) * 100
        ))::numeric, 1
      ) AS availability_pct,
      NULL::numeric AS performance_pct,        -- gap: per-asset ideal cycle time not yet captured
      ROUND(LEAST(100, COALESCE(q.quality_avg, NULL))::numeric, 1) AS quality_pct
    FROM downtime d
    FULL OUTER JOIN quality q ON d.machine = q.machine
  )
  SELECT
    c.machine,
    c.availability_pct,
    c.performance_pct,
    c.quality_pct,
    -- OEE: full if all 3 factors present, else partial (A × Q) if both
    -- A and Q are present, else NULL.
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
    -- Partial whenever the Performance factor is null
    (c.performance_pct IS NULL) AS is_partial
  FROM combined c
  WHERE c.machine IS NOT NULL
  ORDER BY c.machine;
$$;

COMMENT ON FUNCTION public.get_oee_by_machine IS
  'Tier E canonical OEE per machine. Returns full OEE when Performance factor is available (per-asset ideal cycle time), else partial (Availability × Quality) with is_partial=true. Pair with formula_contracts.json oee_iso_22400 / oee_iso_22400_partial.';

GRANT EXECUTE ON FUNCTION public.get_oee_by_machine(uuid, int) TO anon, authenticated;

COMMIT;
