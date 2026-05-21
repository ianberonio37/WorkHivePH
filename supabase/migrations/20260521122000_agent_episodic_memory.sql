-- Agent Episodic Memory (Phase 7 of AGENTIC_RAG_ROADMAP.md)
--
-- Distinct from agent_memory (which is per-conversation turn-history,
-- capped at 90 days). This table holds DURABLE facts the agentic-rag-loop
-- extracts at the end of successful runs:
--   - factual   ("worker prefers Tagalog")
--   - procedural ("P-203 bearing fix = replace SKF 6205-2RS")
--   - episodic  ("incident 2024-03-15: cooling tower VFD loose wiring")
--   - semantic  ("plant runs 2 shifts: 06:00-14:00 and 14:00-22:00")
--
-- Loaded as system-prompt context at the start of each agentic-rag-loop
-- run. LRU eviction weighted by importance × log(1 + use_count) caps
-- storage at 200 memories/worker and 1000/hive (enforced by the edge fn).
--
-- RLS: own auth_uid OR hive members can read. Service-role-only insert
-- (memories come from the agentic-rag-loop edge fn at extraction time).

-- canonical-allow: infrastructure memory store for agentic RAG (factual/procedural/episodic/semantic facts) — not a user-facing truth source
CREATE TABLE IF NOT EXISTS public.agent_episodic_memory (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id      uuid REFERENCES public.hives(id) ON DELETE CASCADE,
  worker_name  text,                                              -- nullable: hive-wide memory
  auth_uid     uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  memory_type  text NOT NULL CHECK (memory_type IN ('factual','procedural','episodic','semantic')),
  content      text NOT NULL,
  embedding    vector(384),                                       -- nullable: enrichment fills later
  importance   real NOT NULL DEFAULT 0.5 CHECK (importance BETWEEN 0 AND 1),
  use_count    integer NOT NULL DEFAULT 0,
  last_used_at timestamptz,
  source_trace_id uuid REFERENCES public.agentic_rag_traces(id) ON DELETE SET NULL,
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_aem_worker_type        ON public.agent_episodic_memory (worker_name, memory_type, last_used_at DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_aem_hive_type          ON public.agent_episodic_memory (hive_id, memory_type, last_used_at DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_aem_importance         ON public.agent_episodic_memory (importance DESC, use_count DESC);

GRANT SELECT, INSERT, UPDATE ON public.agent_episodic_memory TO anon, authenticated;

ALTER TABLE public.agent_episodic_memory ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS aem_read   ON public.agent_episodic_memory;
DROP POLICY IF EXISTS aem_insert ON public.agent_episodic_memory;
DROP POLICY IF EXISTS aem_update ON public.agent_episodic_memory;

-- Read: own auth_uid OR any row in a hive the worker is a member of.
CREATE POLICY aem_read ON public.agent_episodic_memory
  FOR SELECT USING (
    auth.uid() IS NOT NULL
    AND (
      auth.uid() = auth_uid
      OR (
        hive_id IS NOT NULL
        AND EXISTS (
          SELECT 1 FROM public.hive_members hm
          WHERE hm.hive_id = agent_episodic_memory.hive_id
            AND hm.auth_uid = auth.uid()
            AND hm.status = 'active'
        )
      )
    )
  );

-- Inserts only via service role (the agent-memory-store edge fn). Block
-- direct anon/auth writes so consumers cannot poison the memory bank.
CREATE POLICY aem_insert ON public.agent_episodic_memory
  FOR INSERT WITH CHECK (false);

-- Update (use_count + last_used_at) only via service role.
CREATE POLICY aem_update ON public.agent_episodic_memory
  FOR UPDATE USING (false);
