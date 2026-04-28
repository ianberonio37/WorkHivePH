-- Analytics RPC Functions — move heavy computation from Python to Postgres
-- Performance skill rule: "Any metric requiring aggregation across more than
-- ~200 rows must be a Postgres view or RPC, not a client-side JS .reduce()."
--
-- These functions replace Python in-memory computation for the Descriptive phase.
-- Called via db.rpc() from the edge function — runs on indexed Postgres, not Python.
-- Period is a parameter so all 4 selectors (30/90/180/365 days) work correctly.

-- ── 1. MTBF per machine — ISO 14224:2016 §9.3 ────────────────────────────────
-- Mean Time Between Failures = mean interval between consecutive failure dates
-- Uses LAG() window function to compute intervals between failures per machine.

CREATE OR REPLACE FUNCTION get_mtbf_by_machine(
  p_hive_id    uuid    DEFAULT NULL,
  p_worker     text    DEFAULT NULL,
  p_period_days int   DEFAULT 90
)
RETURNS TABLE (
  machine            text,
  failure_count      bigint,
  mtbf_days          numeric,
  min_interval_days  numeric,
  max_interval_days  numeric
)
LANGUAGE sql STABLE AS $$
  WITH failures AS (
    SELECT
      machine,
      created_at,
      LAG(created_at) OVER (PARTITION BY machine ORDER BY created_at) AS prev_failure
    FROM logbook
    WHERE maintenance_type = 'Breakdown / Corrective'
      AND created_at >= NOW() - (p_period_days || ' days')::interval
      AND (p_hive_id IS NULL OR hive_id = p_hive_id)
      AND (p_worker  IS NULL OR worker_name = p_worker)
  ),
  intervals AS (
    SELECT
      machine,
      EXTRACT(EPOCH FROM (created_at - prev_failure)) / 86400.0 AS interval_days
    FROM failures
    WHERE prev_failure IS NOT NULL
  )
  SELECT
    machine,
    COUNT(*) + 1                              AS failure_count,
    ROUND(AVG(interval_days)::numeric, 1)    AS mtbf_days,
    ROUND(MIN(interval_days)::numeric, 1)    AS min_interval_days,
    ROUND(MAX(interval_days)::numeric, 1)    AS max_interval_days
  FROM intervals
  GROUP BY machine
  HAVING COUNT(*) >= 1  -- need at least 2 failures (1 interval)
  ORDER BY AVG(interval_days) ASC;  -- worst (shortest MTBF) first
$$;


-- ── 2. MTTR per machine — ISO 14224:2016 §9.4 ────────────────────────────────
-- Mean Time To Repair = avg downtime_hours per machine for closed corrective jobs

CREATE OR REPLACE FUNCTION get_mttr_by_machine(
  p_hive_id     uuid  DEFAULT NULL,
  p_worker      text  DEFAULT NULL,
  p_period_days int   DEFAULT 90
)
RETURNS TABLE (
  machine          text,
  repair_count     bigint,
  total_downtime_h numeric,
  mttr_hours       numeric
)
LANGUAGE sql STABLE AS $$
  SELECT
    machine,
    COUNT(*)                                        AS repair_count,
    ROUND(SUM(downtime_hours)::numeric, 1)          AS total_downtime_h,
    ROUND(AVG(downtime_hours)::numeric, 1)          AS mttr_hours
  FROM logbook
  WHERE maintenance_type = 'Breakdown / Corrective'
    AND status            = 'Closed'
    AND downtime_hours    > 0
    AND created_at       >= NOW() - (p_period_days || ' days')::interval
    AND (p_hive_id IS NULL OR hive_id = p_hive_id)
    AND (p_worker  IS NULL OR worker_name = p_worker)
  GROUP BY machine
  ORDER BY AVG(downtime_hours) DESC;  -- worst (longest MTTR) first
$$;


-- ── 3. Failure Frequency — ISO 14224:2016 ────────────────────────────────────
-- Count of corrective failures per machine in the period

CREATE OR REPLACE FUNCTION get_failure_frequency(
  p_hive_id     uuid  DEFAULT NULL,
  p_worker      text  DEFAULT NULL,
  p_period_days int   DEFAULT 90
)
RETURNS TABLE (
  machine        text,
  failure_count  bigint
)
LANGUAGE sql STABLE AS $$
  SELECT
    machine,
    COUNT(*) AS failure_count
  FROM logbook
  WHERE maintenance_type = 'Breakdown / Corrective'
    AND created_at >= NOW() - (p_period_days || ' days')::interval
    AND (p_hive_id IS NULL OR hive_id = p_hive_id)
    AND (p_worker  IS NULL OR worker_name = p_worker)
  GROUP BY machine
  ORDER BY COUNT(*) DESC;
$$;


-- ── 4. Downtime Pareto — 80/20 rule ──────────────────────────────────────────
-- Ranked downtime by machine with cumulative percentage

CREATE OR REPLACE FUNCTION get_downtime_pareto(
  p_hive_id     uuid  DEFAULT NULL,
  p_worker      text  DEFAULT NULL,
  p_period_days int   DEFAULT 90
)
RETURNS TABLE (
  machine           text,
  downtime_hours    numeric,
  pct_of_total      numeric,
  cumulative_pct    numeric
)
LANGUAGE sql STABLE AS $$
  WITH totals AS (
    SELECT
      machine,
      ROUND(SUM(downtime_hours)::numeric, 1) AS downtime_hours
    FROM logbook
    WHERE maintenance_type = 'Breakdown / Corrective'
      AND downtime_hours   > 0
      AND created_at      >= NOW() - (p_period_days || ' days')::interval
      AND (p_hive_id IS NULL OR hive_id = p_hive_id)
      AND (p_worker  IS NULL OR worker_name = p_worker)
    GROUP BY machine
  ),
  grand AS (SELECT SUM(downtime_hours) AS grand_total FROM totals)
  SELECT
    t.machine,
    t.downtime_hours,
    ROUND(t.downtime_hours / g.grand_total * 100, 1)   AS pct_of_total,
    ROUND(
      SUM(t.downtime_hours) OVER (ORDER BY t.downtime_hours DESC
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
      / g.grand_total * 100,
    1) AS cumulative_pct
  FROM totals t, grand g
  ORDER BY t.downtime_hours DESC;
$$;


-- ── 5. Repeat Failures — ISO 14224:2016 ──────────────────────────────────────
-- Same root_cause on same machine >= 2 times

CREATE OR REPLACE FUNCTION get_repeat_failures(
  p_hive_id     uuid  DEFAULT NULL,
  p_worker      text  DEFAULT NULL,
  p_period_days int   DEFAULT 90
)
RETURNS TABLE (
  machine      text,
  root_cause   text,
  occurrences  bigint
)
LANGUAGE sql STABLE AS $$
  SELECT
    machine,
    root_cause,
    COUNT(*) AS occurrences
  FROM logbook
  WHERE maintenance_type = 'Breakdown / Corrective'
    AND root_cause IS NOT NULL
    AND root_cause <> ''
    AND created_at >= NOW() - (p_period_days || ' days')::interval
    AND (p_hive_id IS NULL OR hive_id = p_hive_id)
    AND (p_worker  IS NULL OR worker_name = p_worker)
  GROUP BY machine, root_cause
  HAVING COUNT(*) >= 2
  ORDER BY COUNT(*) DESC;
$$;
