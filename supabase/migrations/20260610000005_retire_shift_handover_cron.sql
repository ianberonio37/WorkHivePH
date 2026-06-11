-- Phase 2 (2026-06-10): Shift Handover moves from pg_cron to compute-on-first-
-- open (Ian's compute rule: "a page a person opens -> first view computes +
-- saves; NO scheduled jobs"). shift-brain.html now auto-generates the handover
-- on the first open of a planless live window (maybeAutoGenerate -> the same
-- shift-planner-orchestrator the cron called), seeded with the prior shift's
-- carry-forward items as before. The supervisor "Generate now" / "Re-run plan"
-- buttons remain the manual path.
--
-- This retires ONLY the 3 shift-handover schedules. Retention/purge jobs and
-- other cron entries are housekeeping, not user-facing page compute, and are
-- out of this rule's scope. enable_shift_brain_cron.sql (repo root) is
-- superseded by this migration - annotated, kept for history.
--
-- Idempotent: unschedule only when the job exists (fresh clones never had it).

DO $$
DECLARE
  j text;
BEGIN
  FOREACH j IN ARRAY ARRAY['shift-handover-morning','shift-handover-afternoon','shift-handover-night']
  LOOP
    IF EXISTS (SELECT 1 FROM cron.job WHERE jobname = j) THEN
      PERFORM cron.unschedule(j);
      RAISE NOTICE 'unscheduled %', j;
    END IF;
  END LOOP;
END $$;
