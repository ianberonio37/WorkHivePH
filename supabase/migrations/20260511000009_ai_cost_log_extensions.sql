-- ai_cost_log extensions -- closes follow-up to PRODUCTION_FIXES #55
--
-- Adds three quality / feedback columns to the existing ledger:
--
--   schema_compliance  -- when JSON-mode was requested, did the model
--                          output parse cleanly? (bool, null = N/A)
--   user_feedback      -- +1 thumbs-up / -1 thumbs-down / 0 neutral
--                          from the worker on the AI response, if the
--                          UI surface collected one (smallint -1..1)
--   prompt_hash        -- sha-256 of the prompt + system prompt, for
--                          cache-hit accounting and prompt drift detection

ALTER TABLE public.ai_cost_log
  ADD COLUMN IF NOT EXISTS schema_compliance boolean,
  ADD COLUMN IF NOT EXISTS user_feedback     smallint
    CHECK (user_feedback IS NULL OR user_feedback BETWEEN -1 AND 1),
  ADD COLUMN IF NOT EXISTS prompt_hash       text;

CREATE INDEX IF NOT EXISTS idx_ai_cost_log_feedback
  ON public.ai_cost_log (fn, user_feedback, created_at DESC)
  WHERE user_feedback IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ai_cost_log_schema_compliance
  ON public.ai_cost_log (fn, schema_compliance, created_at DESC)
  WHERE schema_compliance = false;
