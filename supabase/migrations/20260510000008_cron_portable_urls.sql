-- ─── Cron config drift fix — adopt portable URL/key pattern ─────────────────
--
-- Problem (PRODUCTION_FIXES.md #35, surfaced by validate_cron_schedule_integrity):
--   8 active cron jobs across 2 historical migrations hardcode the project
--   host (`hzyvnjtisfgbksicrouu.supabase.co`) and embed placeholder bearer
--   tokens (`SUPABASE_CRON_SERVICE_KEY`, `YOUR_PROJECT`, `SERVICE_ROLE_KEY`)
--   that the deployer was meant to fill in manually post-deploy. The live
--   cron.job table got patched on the live project, but every clone /
--   staging / customer self-host gets the misleading defaults.
--
-- Fix:
--   pg_cron is last-writer-wins per job_name. Re-call cron.schedule(...) for
--   each of the 8 jobs with the portable form already in use by
--   20260505000002_project_knowledge.sql:
--     url     := current_setting('app.supabase_functions_url') || '/<fn-name>'
--     headers := jsonb_build_object('Authorization', 'Bearer ' ||
--                                   current_setting('app.service_role_key'))
--   Both settings are configured per-project by Supabase (no manual rotation
--   needed across projects). The unschedule first means the job is removed
--   cleanly before the new definition lands, so even a partial-apply leaves
--   no zombie schedule.
--
-- Jobs migrated to portable form (8 total):
--   ┌─ from 20260425000003_scheduled_agents.sql ─────────────────────────────
--   │  pm-overdue-daily          → /scheduled-agents  body=pm_overdue
--   │  failure-digest-weekly     → /scheduled-agents  body=failure_digest
--   │  shift-handover-morning    → /scheduled-agents  body=shift_handover
--   │  shift-handover-afternoon  → /scheduled-agents  body=shift_handover
--   │  shift-handover-night      → /scheduled-agents  body=shift_handover
--   │  predictive-weekly         → /scheduled-agents  body=predictive
--   ├─ from 20260508000001_risk_scoring_cron.sql ────────────────────────────
--   │  batch-risk-scoring-daily  → /batch-risk-scoring
--   │  ml-retrain-weekly         → /trigger-ml-retrain
--   └────────────────────────────────────────────────────────────────────────
--
-- Wrapped in DO blocks with `IF EXISTS (... pg_cron)` so this is a no-op on
-- environments without pg_cron (local Supabase by default).

-- ─── 1. Unschedule the 8 historical jobs ────────────────────────────────────
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
    PERFORM cron.unschedule('pm-overdue-daily');
    PERFORM cron.unschedule('failure-digest-weekly');
    PERFORM cron.unschedule('shift-handover-morning');
    PERFORM cron.unschedule('shift-handover-afternoon');
    PERFORM cron.unschedule('shift-handover-night');
    PERFORM cron.unschedule('predictive-weekly');
    PERFORM cron.unschedule('batch-risk-scoring-daily');
    PERFORM cron.unschedule('ml-retrain-weekly');
  END IF;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- ─── 2. Re-schedule each with portable URL + portable bearer ────────────────
-- scheduled-agents fan-out: 6 jobs share the same URL + bearer pattern,
-- differ only in cron expression and the report_type body.

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
    PERFORM cron.schedule('pm-overdue-daily', '0 6 * * *',
      'SELECT net.http_post(url := current_setting(''app.supabase_functions_url'') || ''/scheduled-agents'', headers := jsonb_build_object(''Authorization'', ''Bearer '' || current_setting(''app.service_role_key''), ''Content-Type'', ''application/json''), body := ''{"report_type":"pm_overdue"}''::jsonb);');
  END IF;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
    PERFORM cron.schedule('failure-digest-weekly', '0 7 * * 1',
      'SELECT net.http_post(url := current_setting(''app.supabase_functions_url'') || ''/scheduled-agents'', headers := jsonb_build_object(''Authorization'', ''Bearer '' || current_setting(''app.service_role_key''), ''Content-Type'', ''application/json''), body := ''{"report_type":"failure_digest"}''::jsonb);');
  END IF;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
    PERFORM cron.schedule('shift-handover-morning', '0 6 * * *',
      'SELECT net.http_post(url := current_setting(''app.supabase_functions_url'') || ''/scheduled-agents'', headers := jsonb_build_object(''Authorization'', ''Bearer '' || current_setting(''app.service_role_key''), ''Content-Type'', ''application/json''), body := ''{"report_type":"shift_handover"}''::jsonb);');
  END IF;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
    PERFORM cron.schedule('shift-handover-afternoon', '0 14 * * *',
      'SELECT net.http_post(url := current_setting(''app.supabase_functions_url'') || ''/scheduled-agents'', headers := jsonb_build_object(''Authorization'', ''Bearer '' || current_setting(''app.service_role_key''), ''Content-Type'', ''application/json''), body := ''{"report_type":"shift_handover"}''::jsonb);');
  END IF;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
    PERFORM cron.schedule('shift-handover-night', '0 22 * * *',
      'SELECT net.http_post(url := current_setting(''app.supabase_functions_url'') || ''/scheduled-agents'', headers := jsonb_build_object(''Authorization'', ''Bearer '' || current_setting(''app.service_role_key''), ''Content-Type'', ''application/json''), body := ''{"report_type":"shift_handover"}''::jsonb);');
  END IF;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
    PERFORM cron.schedule('predictive-weekly', '0 20 * * 0',
      'SELECT net.http_post(url := current_setting(''app.supabase_functions_url'') || ''/scheduled-agents'', headers := jsonb_build_object(''Authorization'', ''Bearer '' || current_setting(''app.service_role_key''), ''Content-Type'', ''application/json''), body := ''{"report_type":"predictive"}''::jsonb);');
  END IF;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- Direct-target jobs (not via scheduled-agents fan-out)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
    PERFORM cron.schedule('batch-risk-scoring-daily', '0 5 * * *',
      'SELECT net.http_post(url := current_setting(''app.supabase_functions_url'') || ''/batch-risk-scoring'', headers := jsonb_build_object(''Authorization'', ''Bearer '' || current_setting(''app.service_role_key''), ''Content-Type'', ''application/json''), body := ''{}''::jsonb);');
  END IF;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
    PERFORM cron.schedule('ml-retrain-weekly', '0 18 * * 6',
      'SELECT net.http_post(url := current_setting(''app.supabase_functions_url'') || ''/trigger-ml-retrain'', headers := jsonb_build_object(''Authorization'', ''Bearer '' || current_setting(''app.service_role_key''), ''Content-Type'', ''application/json''), body := ''{}''::jsonb);');
  END IF;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;
