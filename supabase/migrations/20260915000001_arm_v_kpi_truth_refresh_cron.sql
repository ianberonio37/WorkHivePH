-- v_kpi_truth: arm the hourly refresh that has never once run.
--
-- WHAT IS WRONG, MEASURED ON THE LIVE DATABASE (2026-09-15):
--
--   v_kpi_truth rows                              90
--   ...whose hive_id still exists in `hives`       0
--   distinct hive_ids in the matview               3   (none of them a live hive)
--   live hives                                     6
--   cron jobs mentioning kpi                       0   (of 27 scheduled jobs)
--   automation_log rows for v_kpi_truth_refresh    0
--
-- So the materialised view holds a single snapshot taken when it was created, against three hives that
-- have since been deleted, and EVERY LIVE HIVE HAS ZERO MTBF / MTTR / OEE GROUNDING. The sibling truth
-- views are healthy by comparison - v_worker_skill_truth's 101 rows all point at live hives - which is
-- what makes this one stand out as stale rather than merely empty.
--
-- AND A REFRESH REALLY DOES FIX IT - checked before writing this, not assumed. The matview is built from
-- `logbook` rows of maintenance_type 'Breakdown / Corrective' in trailing windows, and the source holds
-- 254 such rows in the last 30 days, 253 of them in a live hive, spread across ALL SIX live hives. So the
-- refresh has real data to compute from for every hive that currently has none.
--
-- WHY IT NEVER RAN, AND IT IS NOT AN OVERSIGHT IN THE CODE. `public.refresh_v_kpi_truth()` exists and is
-- correct: it does REFRESH MATERIALIZED VIEW CONCURRENTLY and writes a success/failure row to
-- automation_log. Its own COMMENT says "Called hourly by pg_cron (see enable_v_kpi_truth_cron.sql)" - and
-- that file sits in the REPOSITORY ROOT, outside supabase/migrations/, carrying the instruction:
--
--     "Run this manually in the Supabase SQL editor after the 20260512000005_v_kpi_truth.sql migration
--      applies. It is NOT in the migration because pg_cron schedules can be environment-specific."
--
-- A step that depends on someone remembering is a step that does not happen. It has not happened since
-- 2026-05-12. The environment-specificity the header worries about is real and this platform already has
-- the answer for it, used by all four of its other scheduled jobs: wrap the schedule in a DO block that
-- checks for pg_cron and swallows the exception, so the migration is a no-op on a local stack or a fresh
-- project and arms itself everywhere pg_cron is installed.
--
-- WHO FEELS IT. assistant.html's FIRST starter chip is "Which of my assets has the worst MTBF, and what
-- should I do?" - the page's flagship suggestion - and ai-gateway's buildFromRegistry returns "" for an
-- empty source, so the MTBF block is silently omitted while the GROUNDING RULE line still tells the model
-- that every figure is computed from this hive's own records. The reader is invited to ask the one
-- question the platform currently cannot ground.
--
-- CADENCE unchanged from the file this supersedes: hourly, on the hour, for the reasons KPI_ENGINE.md
-- already gives - a one-hour lag is invisible on the Asset Hub and Alert Hub snapshot cards, the full
-- rollup is non-trivial CPU, and a surface needing tighter freshness falls back to the get_mtbf_by_machine
-- RPC at request time. The unschedule-then-schedule pair makes the migration idempotent.
--
-- NOTE: the root enable_v_kpi_truth_cron.sql is superseded by this file. It is left in place rather than
-- deleted so the history of the decision stays readable; it is now documentation, not a step.

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
    PERFORM cron.unschedule('v-kpi-truth-refresh-hourly');
  END IF;
EXCEPTION WHEN OTHERS THEN
  NULL;
END
$$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
    PERFORM cron.schedule(
      'v-kpi-truth-refresh-hourly',
      '0 * * * *',
      $cron$ SELECT public.refresh_v_kpi_truth(); $cron$
    );
  END IF;
EXCEPTION WHEN OTHERS THEN
  NULL;
END
$$;

-- And refresh once now, so the first hour after this applies is not another hour of a four-month-old
-- snapshot. Guarded the same way: on a stack without the matview this is a no-op rather than a failure.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_matviews WHERE matviewname = 'v_kpi_truth') THEN
    PERFORM public.refresh_v_kpi_truth();
  END IF;
EXCEPTION WHEN OTHERS THEN
  NULL;
END
$$;
