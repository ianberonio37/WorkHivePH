-- ─────────────────────────────────────────────────────────────────────────────
-- get_pm_ontime_delivery — how much of the PM program was actually done ON SCHEDULE.
--
-- FOUND BY THE PM7 WALK (2026-07-28, PM_DEEPWALK_EXPANSION_ROADMAP, class PMK1):
--   supervisor / Lucena : "0 of 31 on track now  ·  88% PM compliance (SMRP)"   (20 overdue)
--   worker     / Manila : "3 of 30 on track now  ·  86% PM compliance (SMRP)"   (24 overdue)
-- Both read as near-world-class against the 90% benchmark while almost nothing was on track.
-- Measured at the DB: of 1,224 consecutive-completion intervals, 331 (27.0%) ran past the item's
-- own `frequency_days`. `get_pm_compliance_smrp` counts every one of those as compliant, because
-- SMRP 2.1.1 is completed/scheduled and says nothing about lateness — a documented property of the
-- standard, not a bug in the RPC ("does not account for late PMs", substrate/external/
-- external-pm-schedule-compliance-metric.md).
--
-- THE DISPOSITION. `get_pm_compliance_smrp` is NOT changed: it implements a named standard, holds
-- verified parity with Analytics, and a plant acts on it. Redefining it silently would break a
-- documented contract. Instead the missing half of the picture gets its own honest number, and the
-- two are shown side by side, so a supervisor reading 88% can see that 27% of the work ran late.
--
-- WHY AN RPC RATHER THAN A CLIENT-SIDE SUM. The measure existed only inside a validator's inline
-- SQL. Had the page re-implemented it in JS there would be two expressions of "on time" that agree
-- only while nobody edits one of them — precisely the three-ways-to-say-"corrective" time bomb the
-- logbook arc closed (LG2). One definition lives here; the validator asserts parity against it.
--
-- ON-TIME IS INTERVAL-BASED ON PURPOSE: the gap to the PREVIOUS completion of the same scope item
-- must not exceed that item's frequency. It needs no stored due-date history and cannot be gamed by
-- a later reschedule, so it measures the delivery that actually happened. A scope item's FIRST ever
-- completion has no previous gap and is excluded rather than assumed on-time.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.get_pm_ontime_delivery(
  p_hive_id uuid,
  p_period_days integer DEFAULT 90
)
RETURNS jsonb
LANGUAGE plpgsql
STABLE SECURITY DEFINER
SET search_path TO 'public', 'pg_temp'
AS $function$
DECLARE
  v_is_member boolean;
  v_total     bigint;
  v_ontime    bigint;
BEGIN
  -- Hive isolation gate, same shape as get_pm_compliance_smrp. A NULL hive means platform-wide and
  -- is reserved for server-to-server callers (service_role / psql), never an authenticated user.
  IF auth.uid() IS NOT NULL THEN
    IF p_hive_id IS NULL THEN
      RAISE EXCEPTION 'get_pm_ontime_delivery: a platform-wide read requires service_role'
        USING ERRCODE = '42501';
    END IF;
    SELECT EXISTS (
      SELECT 1 FROM public.hive_members
      WHERE hive_id  = p_hive_id
        AND auth_uid = auth.uid()
        AND status   = 'active'
    ) INTO v_is_member;
    IF NOT v_is_member THEN
      RAISE EXCEPTION
        'get_pm_ontime_delivery: caller is not an active member of hive %', p_hive_id
        USING ERRCODE = '42501';
    END IF;
  END IF;

  WITH gaps AS (
    SELECT pc.completed_at,
           s.frequency_days,
           LAG(pc.completed_at) OVER (PARTITION BY pc.scope_item_id ORDER BY pc.completed_at) AS prev_at
    FROM public.pm_completions pc
    JOIN public.v_pm_scope_items_truth s ON s.scope_item_id = pc.scope_item_id
    WHERE pc.status = 'done'
      AND (p_hive_id IS NULL OR pc.hive_id = p_hive_id)
  )
  SELECT count(*) FILTER (WHERE prev_at IS NOT NULL
                            AND completed_at >= now() - (p_period_days || ' days')::interval),
         count(*) FILTER (WHERE prev_at IS NOT NULL
                            AND completed_at >= now() - (p_period_days || ' days')::interval
                            AND completed_at <= prev_at + (frequency_days || ' days')::interval)
    INTO v_total, v_ontime
    FROM gaps;

  RETURN jsonb_build_object(
    'standard',    'interval delivery vs the item''s own frequency',
    'period_days', p_period_days,
    -- NULL, not 0, when there is nothing to measure: a fresh PM program with no repeat completions
    -- has no on-time record, and showing it as 0% would read as a failing program.
    'ontime_pct',  CASE WHEN v_total = 0 THEN NULL
                        ELSE round(100.0 * v_ontime::numeric / v_total, 1) END,
    'intervals',   COALESCE(v_total, 0),
    'ontime',      COALESCE(v_ontime, 0),
    'late',        COALESCE(v_total, 0) - COALESCE(v_ontime, 0)
  );
END;
$function$;

REVOKE ALL ON FUNCTION public.get_pm_ontime_delivery(uuid, integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.get_pm_ontime_delivery(uuid, integer) TO authenticated, service_role;
