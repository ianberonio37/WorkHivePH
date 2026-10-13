-- ai_quality_log: every eval row records WHICH RUN it belongs to and WHETHER IT WAS MEASURED.
--
-- THE FINDING (2026-10-07). The nightly ai-eval-runner never measured an answer: all 1,765 graded rows had
-- actual_answer "[gateway error: 401]" (it sent the service-role key to ai-gateway, which refuses a bearer
-- that is not a user for every agent but voice-journal). The judge then graded the error string, so the
-- log read "every agent fails quality" - a quality verdict about questions nobody answered. Two things in
-- the schema let that pass unseen:
--   * there was no way to tell a graded row from an infrastructure failure - both were passed=false;
--   * there was no timestamp at all (run_at was dropped 2026-05-20 as a "phantom" - nothing named it,
--     because the runner relied on its default), so "what did the LATEST run measure?" had no answer.
--
-- This migration:
--   run_at   - when the run started (the runner writes it explicitly now, one value per run)
--   run_id   - one id per run, so a run is a GROUP BY, not an inference
--   outcome  - 'graded' (an answer was judged) | 'infra_error' (no answer, or no judge) | 'heartbeat'
-- and re-labels the history honestly: a row whose answer is a gateway/transport error is an infrastructure
-- failure - its score/passed were the judge grading an error message, so they are cleared, not kept.
-- actual_answer is left exactly as it was (the evidence), so a count of '[gateway error%' rows is unchanged.
--
-- Read by: supabase/functions/ai-eval-runner (writes all three) and
--          tools/validate_ai_eval_answers_are_real.py (gate ai-eval-answers-real: FAILs when the latest
--          run is dominated by infra_error rows, or when any infra row still carries a grade).

ALTER TABLE public.ai_quality_log ADD COLUMN IF NOT EXISTS run_at  timestamptz NOT NULL DEFAULT now();
ALTER TABLE public.ai_quality_log ADD COLUMN IF NOT EXISTS run_id  uuid;
ALTER TABLE public.ai_quality_log ADD COLUMN IF NOT EXISTS outcome text;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                 WHERE conname = 'ai_quality_log_outcome_check'
                   AND conrelid = 'public.ai_quality_log'::regclass) THEN
    ALTER TABLE public.ai_quality_log
      ADD CONSTRAINT ai_quality_log_outcome_check
      CHECK (outcome IS NULL OR outcome IN ('graded', 'infra_error', 'heartbeat'));
  END IF;
END
$$;

-- A row cannot be an infrastructure failure AND carry a grade.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                 WHERE conname = 'ai_quality_log_infra_is_ungraded'
                   AND conrelid = 'public.ai_quality_log'::regclass) THEN
    -- added NOT VALID first: the history below is re-labelled, then the constraint is validated
    ALTER TABLE public.ai_quality_log
      ADD CONSTRAINT ai_quality_log_infra_is_ungraded
      CHECK (outcome IS DISTINCT FROM 'infra_error' OR (passed IS NULL AND score IS NULL)) NOT VALID;
  END IF;
END
$$;

UPDATE public.ai_quality_log
   SET outcome = 'heartbeat'
 WHERE outcome IS NULL AND agent_id = '__heartbeat__';

UPDATE public.ai_quality_log
   SET outcome        = 'infra_error',
       passed         = NULL,
       score          = NULL,
       judge_model    = 'not-judged',
       failure_reason = 'infra: ' || left(actual_answer, 200)
                        || ' (re-labelled 2026-10-07: this was graded as a quality failure, but no answer was measured)'
 WHERE outcome IS NULL
   AND (actual_answer LIKE '[gateway error:%' OR actual_answer LIKE '[gateway threw:%');

UPDATE public.ai_quality_log
   SET outcome = 'graded'
 WHERE outcome IS NULL;

ALTER TABLE public.ai_quality_log VALIDATE CONSTRAINT ai_quality_log_infra_is_ungraded;

CREATE INDEX IF NOT EXISTS idx_ai_quality_log_run_at ON public.ai_quality_log (run_at DESC);
