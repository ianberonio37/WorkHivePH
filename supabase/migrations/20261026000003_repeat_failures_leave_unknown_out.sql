-- ============================================================================
-- REPEAT FAILURES LEAVE AN UNRECORDED CAUSE OUT (BRH.10 AI, 2026-10-26)
--
-- The analytics page's Repeat Failure Count is read from this function (the
-- edge fn's precompute; descriptive.calc_repeat_failures is only its
-- fallback). It counted 'Unknown' as a cause, so three breakdowns on one
-- machine with no cause found read "WALK-AI-P2 · Unknown · 3x" under a card
-- that says the same cause coming back means an ineffective repair. Measured
-- on the MCP walk of analytics.html as a supervisor, after the fallback had
-- already been fixed.
--
-- 'Unknown' is the form's word for no cause found. Every cause is now one of
-- the form's 12 (trg_logbook_listed_cause, 20261026000002), so grouping by
-- root_cause groups by the list; the comparison is case-blind in case an old
-- row predates the trigger.
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
  WHERE maintenance_type = 'Breakdown / Corrective'
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
