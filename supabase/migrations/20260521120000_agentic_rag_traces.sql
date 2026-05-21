-- Agentic RAG Traces (Phase 1 of AGENTIC_RAG_ROADMAP.md)
--
-- One row per agentic-rag-loop invocation. Captures the full per-run audit:
-- which route the Router picked, each stage's latency + token shape, every
-- retrieved chunk + its grader score + whether it was kept, retry count,
-- whether Grader / Checker passed, citation count, the final answer, and the
-- aggregate latency. No cost_usd column: this platform is permanently on the
-- free-tier multi-provider chain ($0 LLM spend by constraint; see
-- AGENTIC_RAG_ROADMAP.md §2.5 and feedback_free_tier_only_models.md).
--
-- Read by: future agentic-rag-observability.html (Phase 8). Today, queried
-- ad-hoc to debug hallucinations and prompt drift.

-- canonical-allow: infrastructure audit log (per-run RAG trace) — not user-facing data, no truth view
CREATE TABLE IF NOT EXISTS public.agentic_rag_traces (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id         uuid REFERENCES public.hives(id) ON DELETE CASCADE,
  worker_name     text,
  question        text NOT NULL,
  route           text NOT NULL CHECK (route IN ('simple_recency','semantic','orchestrator','temporal','cold_archive','unknown')),
  stages          jsonb NOT NULL DEFAULT '[]'::jsonb,
  retrievals      jsonb NOT NULL DEFAULT '[]'::jsonb,
  retries         integer NOT NULL DEFAULT 0,
  grader_passed   boolean,
  checker_passed  boolean,
  citation_count  integer DEFAULT 0,
  final_answer    text,
  total_tokens    integer DEFAULT 0,
  latency_ms      integer DEFAULT 0,
  user_rating     integer,
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agentic_rag_traces_hive_created ON public.agentic_rag_traces (hive_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agentic_rag_traces_route        ON public.agentic_rag_traces (route, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agentic_rag_traces_created      ON public.agentic_rag_traces (created_at DESC);

GRANT SELECT, INSERT ON public.agentic_rag_traces TO anon, authenticated;

ALTER TABLE public.agentic_rag_traces ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS agentic_rag_traces_read   ON public.agentic_rag_traces;
DROP POLICY IF EXISTS agentic_rag_traces_insert ON public.agentic_rag_traces;

-- Members of the hive can read their own hive's traces. Mirrors ai_cost_log
-- policy so the observability dashboard can join the two tables freely.
CREATE POLICY agentic_rag_traces_read ON public.agentic_rag_traces
  FOR SELECT USING (
    auth.uid() IS NOT NULL
    AND hive_id IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = agentic_rag_traces.hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.status = 'active'
    )
  );

-- Inserts go through service role only (the edge function uses
-- SUPABASE_SERVICE_ROLE_KEY). Block direct anon/auth inserts to keep the
-- audit trail tamper-resistant.
CREATE POLICY agentic_rag_traces_insert ON public.agentic_rag_traces
  FOR INSERT WITH CHECK (false);
