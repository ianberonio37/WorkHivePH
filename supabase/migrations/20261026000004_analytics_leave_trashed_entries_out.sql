-- ============================================================================
-- A TRASHED BREAKDOWN STILL COUNTED IN THE ANALYTICS (2026-10-26)
--
-- The logbook's own reads go through v_logbook_truth, which leaves a trashed
-- entry out (WHERE l.deleted_at IS NULL). The five analytics RPCs the
-- analytics page and its orchestrator read - repeat failures, failure
-- frequency, MTBF, MTTR and the downtime Pareto - read logbook directly with
-- no such filter, so an entry a worker moved to the trash kept counting as a
-- failure, a repeat and downtime. Found on the BRH.10 AI walk of
-- analytics.html. Each keeps its body and gains the view's own rule.
-- ============================================================================

CREATE OR REPLACE FUNCTION public.get_repeat_failures(p_hive_id uuid DEFAULT NULL::uuid, p_worker text DEFAULT NULL::text, p_period_days integer DEFAULT 90)
 RETURNS TABLE(machine text, root_cause text, occurrences bigint)
 LANGUAGE sql
 STABLE
 SET search_path TO 'public', 'extensions', 'pg_temp'
AS $function$
  SELECT
    machine,
    root_cause,
    COUNT(*) AS occurrences
  FROM logbook
  WHERE deleted_at IS NULL
    AND maintenance_type = 'Breakdown / Corrective'
    AND root_cause IS NOT NULL
    AND root_cause <> ''
    AND lower(btrim(root_cause)) <> 'unknown'
    AND created_at >= NOW() - (p_period_days || ' days')::interval
    AND (p_hive_id IS NULL OR hive_id = p_hive_id)
    AND (p_worker  IS NULL OR worker_name = p_worker)
  GROUP BY machine, root_cause
  HAVING COUNT(*) >= 2
  ORDER BY COUNT(*) DESC;
$function$;

CREATE OR REPLACE FUNCTION public.get_failure_frequency(p_hive_id uuid DEFAULT NULL::uuid, p_worker text DEFAULT NULL::text, p_period_days integer DEFAULT 90)
 RETURNS TABLE(machine text, failure_count bigint)
 LANGUAGE sql
 STABLE
 SET search_path TO 'public', 'extensions', 'pg_temp'
AS $function$
  SELECT
    machine,
    COUNT(*) AS failure_count
  FROM logbook
  WHERE deleted_at IS NULL
    AND maintenance_type = 'Breakdown / Corrective'
    AND created_at >= NOW() - (p_period_days || ' days')::interval
    AND (p_hive_id IS NULL OR hive_id = p_hive_id)
    AND (p_worker  IS NULL OR worker_name = p_worker)
  GROUP BY machine
  ORDER BY COUNT(*) DESC;
$function$;

CREATE OR REPLACE FUNCTION public.get_mtbf_by_machine(p_hive_id uuid DEFAULT NULL::uuid, p_worker text DEFAULT NULL::text, p_period_days integer DEFAULT 90)
 RETURNS TABLE(machine text, failure_count bigint, mtbf_days numeric, min_interval_days numeric, max_interval_days numeric)
 LANGUAGE sql
 STABLE
 SET search_path TO 'public', 'extensions', 'pg_temp'
AS $function$
  WITH failures AS (
    SELECT
      machine,
      created_at,
      LAG(created_at) OVER (PARTITION BY machine ORDER BY created_at) AS prev_failure
    FROM logbook
    WHERE deleted_at IS NULL
    AND maintenance_type = 'Breakdown / Corrective'
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
$function$;

CREATE OR REPLACE FUNCTION public.get_mttr_by_machine(p_hive_id uuid DEFAULT NULL::uuid, p_worker text DEFAULT NULL::text, p_period_days integer DEFAULT 90)
 RETURNS TABLE(machine text, repair_count bigint, total_downtime_h numeric, mttr_hours numeric)
 LANGUAGE sql
 STABLE
 SET search_path TO 'public', 'extensions', 'pg_temp'
AS $function$
  SELECT
    machine,
    COUNT(*)                                        AS repair_count,
    ROUND(SUM(downtime_hours)::numeric, 1)          AS total_downtime_h,
    ROUND(AVG(downtime_hours)::numeric, 1)          AS mttr_hours
  FROM logbook
  WHERE deleted_at IS NULL
    AND maintenance_type = 'Breakdown / Corrective'
    AND status            = 'Closed'
    AND downtime_hours    > 0
    AND created_at       >= NOW() - (p_period_days || ' days')::interval
    AND (p_hive_id IS NULL OR hive_id = p_hive_id)
    AND (p_worker  IS NULL OR worker_name = p_worker)
  GROUP BY machine
  ORDER BY AVG(downtime_hours) DESC;  -- worst (longest MTTR) first
$function$;

CREATE OR REPLACE FUNCTION public.get_downtime_pareto(p_hive_id uuid DEFAULT NULL::uuid, p_worker text DEFAULT NULL::text, p_period_days integer DEFAULT 90)
 RETURNS TABLE(machine text, downtime_hours numeric, pct_of_total numeric, cumulative_pct numeric)
 LANGUAGE sql
 STABLE
 SET search_path TO 'public', 'extensions', 'pg_temp'
AS $function$
  WITH totals AS (
    SELECT
      machine,
      ROUND(SUM(downtime_hours)::numeric, 1) AS downtime_hours
    FROM logbook
    WHERE deleted_at IS NULL
    AND maintenance_type = 'Breakdown / Corrective'
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
$function$;

