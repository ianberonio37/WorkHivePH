-- AI Cost Ledger -- closes PRODUCTION_FIXES #55
--
-- One row per callAI() invocation. Tracks (fn, hive, model, tokens, cost)
-- so per-hive AI spend is observable and budgets can be enforced.
-- The shared helper `_shared/cost-log.ts` exports `logAICost()` which
-- edge fns call after each callAI(). Rows are inserted via service role.

CREATE TABLE IF NOT EXISTS public.ai_cost_log (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fn              text NOT NULL,
  hive_id         uuid REFERENCES public.hives(id) ON DELETE SET NULL,
  worker_name     text,
  model           text NOT NULL,
  provider        text,
  prompt_tokens   integer,
  output_tokens   integer,
  total_tokens    integer GENERATED ALWAYS AS (COALESCE(prompt_tokens, 0) + COALESCE(output_tokens, 0)) STORED,
  cost_usd        numeric(12, 6),
  latency_ms      integer,
  status          text NOT NULL DEFAULT 'success' CHECK (status IN ('success', 'failed', 'fallback')),
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ai_cost_log_hive_created    ON public.ai_cost_log (hive_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_cost_log_fn_created      ON public.ai_cost_log (fn, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_cost_log_created         ON public.ai_cost_log (created_at DESC);

GRANT SELECT, INSERT ON public.ai_cost_log TO anon, authenticated;

ALTER TABLE public.ai_cost_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ai_cost_log_read   ON public.ai_cost_log;
DROP POLICY IF EXISTS ai_cost_log_insert ON public.ai_cost_log;

-- Members of the hive can read their own hive's cost log.
CREATE POLICY ai_cost_log_read ON public.ai_cost_log
  FOR SELECT USING (
    auth.uid() IS NOT NULL
    AND hive_id IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = ai_cost_log.hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.status = 'active'
    )
  );

-- Inserts go through service role only (the logAICost helper uses
-- the SUPABASE_SERVICE_ROLE_KEY). Block direct anon/auth inserts.
CREATE POLICY ai_cost_log_insert ON public.ai_cost_log
  FOR INSERT WITH CHECK (false);
