-- T90 (2026-08-25): arm the hierarchical-summaries weekly cron — the deferred follow-up
-- recorded in PRODUCTION_FIXES (F13b) and the fn header's own corrected design.
--
-- WHY: canonical_period_summaries is READ by three fns (agentic-rag-loop, ai-gateway,
-- temporal-rag-orchestrator) but nothing produced rows on a schedule — the table held ONE
-- row, so temporal answers worked from raw rows and the 5-year-horizon digestion the
-- AGENTIC_RAG Phase-2 arc built silently underdelivered as data ages (a trust signal needs
-- a living producer).
--
-- The fn's empty-body self-fanning mode (same release) loops active hives × due levels:
-- previous WEEK always, previous MONTH during a month's first 7 days. Service-role only.
--
-- Portable-URL pattern (identical local + prod), per 20260712000014_arm_intelligence_crons:
-- validate_cron_schedule_integrity L5 keys on this job name matching the fn header's claim.
-- Sunday 21:00 UTC = Monday 05:00 PHT — the rollup lands before the Monday-morning briefs.
-- Re-runnable: unschedule-if-exists first.

DO $$
BEGIN
  PERFORM cron.unschedule('hierarchical-summaries-weekly')
  WHERE EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'hierarchical-summaries-weekly');
END $$;

SELECT cron.schedule(
  'hierarchical-summaries-weekly',
  '0 21 * * 0',
  $$
  SELECT net.http_post(
    url := current_setting('app.supabase_functions_url') || '/hierarchical-summarizer',
    headers := jsonb_build_object(
      'Authorization', 'Bearer ' || current_setting('app.service_role_key'),
      'Content-Type', 'application/json'
    ),
    body := '{}'::jsonb
  );
  $$
);
