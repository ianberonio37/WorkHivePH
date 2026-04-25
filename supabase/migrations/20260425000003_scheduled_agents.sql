-- Phase 4 — Scheduled Proactive Agents
-- pg_cron runs agents daily/weekly across all hives automatically.
-- Results are stored in ai_reports so the UI reads pre-computed data
-- without re-running expensive queries on every page load.

-- ── EXTENSIONS ───────────────────────────────────────────────────────────────

CREATE EXTENSION IF NOT EXISTS pg_cron;
CREATE EXTENSION IF NOT EXISTS pg_net;

-- ── AUTOMATION LOG ────────────────────────────────────────────────────────────
-- Tracks every scheduled job run — success, failed, skipped.
-- Makes silent automation failures visible.

CREATE TABLE IF NOT EXISTS automation_log (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_name     text NOT NULL,
  hive_id      uuid,
  triggered_at timestamptz DEFAULT now(),
  status       text CHECK (status IN ('success', 'failed', 'skipped')),
  detail       text
);

CREATE INDEX IF NOT EXISTS idx_automation_log_job
  ON automation_log (job_name, triggered_at DESC);

-- ── AI REPORTS ────────────────────────────────────────────────────────────────
-- Pre-computed agent results per hive.
-- UI reads the most recent report per type — one fast indexed query.

CREATE TABLE IF NOT EXISTS ai_reports (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id      uuid REFERENCES hives(id) ON DELETE CASCADE,
  report_type  text NOT NULL,   -- 'pm_overdue' | 'failure_digest' | 'shift_handover' | 'predictive'
  generated_at timestamptz DEFAULT now(),
  report_json  jsonb,           -- full structured output from the agent
  summary      text             -- one-sentence plain text for notifications
);

CREATE INDEX IF NOT EXISTS idx_ai_reports_hive_type
  ON ai_reports (hive_id, report_type, generated_at DESC);

-- ── SCHEDULED JOBS ────────────────────────────────────────────────────────────
-- Each job calls the scheduled-agents edge function with a specific report_type.
-- The edge function iterates all active hives and runs the relevant agent.
--
-- Note: Replace YOUR_SERVICE_ROLE_KEY with your actual service role key
-- from Supabase Dashboard → Settings → API → service_role key.
-- This is safe — pg_cron runs server-side only, key never reaches the browser.

-- Daily PM overdue check at 06:00 UTC
SELECT cron.schedule(
  'pm-overdue-daily',
  '0 6 * * *',
  $$
  SELECT net.http_post(
    url     := 'https://hzyvnjtisfgbksicrouu.supabase.co/functions/v1/scheduled-agents',
    headers := '{"Authorization": "Bearer SUPABASE_CRON_SERVICE_KEY", "Content-Type": "application/json"}'::jsonb,
    body    := '{"report_type": "pm_overdue"}'::jsonb
  )
  $$
);

-- Weekly failure digest every Monday at 07:00 UTC
SELECT cron.schedule(
  'failure-digest-weekly',
  '0 7 * * 1',
  $$
  SELECT net.http_post(
    url     := 'https://hzyvnjtisfgbksicrouu.supabase.co/functions/v1/scheduled-agents',
    headers := '{"Authorization": "Bearer SUPABASE_CRON_SERVICE_KEY", "Content-Type": "application/json"}'::jsonb,
    body    := '{"report_type": "failure_digest"}'::jsonb
  )
  $$
);

-- Shift handover reports 3x daily — 06:00, 14:00, 22:00 UTC
SELECT cron.schedule(
  'shift-handover-morning',
  '0 6 * * *',
  $$
  SELECT net.http_post(
    url     := 'https://hzyvnjtisfgbksicrouu.supabase.co/functions/v1/scheduled-agents',
    headers := '{"Authorization": "Bearer SUPABASE_CRON_SERVICE_KEY", "Content-Type": "application/json"}'::jsonb,
    body    := '{"report_type": "shift_handover"}'::jsonb
  )
  $$
);

SELECT cron.schedule(
  'shift-handover-afternoon',
  '0 14 * * *',
  $$
  SELECT net.http_post(
    url     := 'https://hzyvnjtisfgbksicrouu.supabase.co/functions/v1/scheduled-agents',
    headers := '{"Authorization": "Bearer SUPABASE_CRON_SERVICE_KEY", "Content-Type": "application/json"}'::jsonb,
    body    := '{"report_type": "shift_handover"}'::jsonb
  )
  $$
);

SELECT cron.schedule(
  'shift-handover-night',
  '0 22 * * *',
  $$
  SELECT net.http_post(
    url     := 'https://hzyvnjtisfgbksicrouu.supabase.co/functions/v1/scheduled-agents',
    headers := '{"Authorization": "Bearer SUPABASE_CRON_SERVICE_KEY", "Content-Type": "application/json"}'::jsonb,
    body    := '{"report_type": "shift_handover"}'::jsonb
  )
  $$
);

-- Weekly predictive risk calendar every Sunday at 20:00 UTC
SELECT cron.schedule(
  'predictive-weekly',
  '0 20 * * 0',
  $$
  SELECT net.http_post(
    url     := 'https://hzyvnjtisfgbksicrouu.supabase.co/functions/v1/scheduled-agents',
    headers := '{"Authorization": "Bearer SUPABASE_CRON_SERVICE_KEY", "Content-Type": "application/json"}'::jsonb,
    body    := '{"report_type": "predictive"}'::jsonb
  )
  $$
);
