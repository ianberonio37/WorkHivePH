-- AI Quality Log -- closes PRODUCTION_FIXES #52 (Phase B/C: log + cron)
--
-- Stores LLM-as-judge scores for canonical-question fixtures. Each
-- eval run inserts one row per (agent_id, question_id, model_judged).
-- The dashboard reads aggregate trends per agent to surface quality
-- regression before users complain.

CREATE TABLE IF NOT EXISTS public.ai_quality_log (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id        text NOT NULL,
  question_id     text NOT NULL,
  question_text   text,
  expected_keywords jsonb,
  actual_answer   text,
  score           numeric(5, 2),    -- 0.00 - 100.00
  passed          boolean,
  judge_model     text,
  failure_reason  text,
  run_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ai_quality_log_agent_run   ON public.ai_quality_log (agent_id, run_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_quality_log_failed      ON public.ai_quality_log (agent_id, passed, run_at DESC)
  WHERE passed = false;
CREATE INDEX IF NOT EXISTS idx_ai_quality_log_run_at      ON public.ai_quality_log (run_at DESC);

GRANT SELECT, INSERT ON public.ai_quality_log TO anon, authenticated;

ALTER TABLE public.ai_quality_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ai_quality_log_read   ON public.ai_quality_log;
DROP POLICY IF EXISTS ai_quality_log_insert ON public.ai_quality_log;

-- Read: any authenticated user (eval results are platform-wide, not
-- hive-scoped -- canonical questions are platform-level fixtures).
CREATE POLICY ai_quality_log_read ON public.ai_quality_log
  FOR SELECT USING (auth.uid() IS NOT NULL);

-- Insert: service role only (the eval runner uses service key).
CREATE POLICY ai_quality_log_insert ON public.ai_quality_log
  FOR INSERT WITH CHECK (false);


-- Daily eval cron at 03:30 UTC (after the rest of the cron pile).
-- Wrapped in DO block + EXCEPTION so the migration is a no-op on
-- environments without pg_cron.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
    PERFORM cron.unschedule('ai-eval-daily');
  END IF;
EXCEPTION WHEN OTHERS THEN
  NULL;
END
$$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
    PERFORM cron.schedule(
      'ai-eval-daily',
      '30 3 * * *',
      $cron$
      SELECT net.http_post(
        url     := current_setting('app.supabase_functions_url') || '/ai-eval-runner',
        headers := jsonb_build_object('Authorization', 'Bearer ' || current_setting('app.service_role_key'))
      );
      $cron$
    );
  END IF;
EXCEPTION WHEN OTHERS THEN
  NULL;
END
$$;
