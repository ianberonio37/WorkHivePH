-- Phase ML-1C: pg_cron schedules for ML pipeline
-- Requires: pg_cron + pg_net extensions (enabled in Supabase by default)
--
-- Replace YOUR_PROJECT and SERVICE_ROLE_KEY with actual values before running.

-- Daily batch risk scoring: 05:00 UTC = 13:00 PHT
-- Scores all assets across all hives using rules engine (Stage 0) or
-- GBM model (Stage 1, activates when ml artifact exists).
SELECT cron.schedule(
  'batch-risk-scoring-daily',
  '0 5 * * *',
  $$ SELECT net.http_post(
    url     := 'https://YOUR_PROJECT.supabase.co/functions/v1/batch-risk-scoring',
    headers := '{"Authorization": "Bearer SERVICE_ROLE_KEY", "Content-Type": "application/json"}'::jsonb,
    body    := '{}'::jsonb
  ) $$
);

-- Weekly ML retrain: Sunday 02:00 PHT (Saturday 18:00 UTC)
-- Fetches all corrective logbook entries, builds feature matrix,
-- retrains GBM if >= 100 samples (warns if < 500).
SELECT cron.schedule(
  'ml-retrain-weekly',
  '0 18 * * 6',
  $$ SELECT net.http_post(
    url     := 'https://YOUR_PROJECT.supabase.co/functions/v1/trigger-ml-retrain',
    headers := '{"Authorization": "Bearer SERVICE_ROLE_KEY", "Content-Type": "application/json"}'::jsonb,
    body    := '{}'::jsonb
  ) $$
);
