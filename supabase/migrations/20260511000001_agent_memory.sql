-- agent_memory: short-term + long-term context for the AI gateway.
--
-- Each row is one TURN in a conversation between a worker and an agent.
-- Rows scoped by (hive_id, worker_name, agent_id) so a worker's question
-- to asset-brain doesn't leak into their analytics conversation.
--
-- Two columns hold the recall surface:
--   * `turn_text`  -- raw user input + agent response (most-recent N rows)
--   * `summary`    -- LLM-generated rolling summary that compresses
--                     history older than the most-recent N turns into
--                     a paragraph. Loaded as the long-term tail.
--
-- The gateway hydrates BOTH on each call: last 10 turns + the most
-- recent summary. When the turn count crosses 10, a summarisation pass
-- collapses the oldest 5 into a new summary row.
--
-- Retention is capped at 90 days; older turns are deleted by a cron job
-- registered separately. Summaries persist longer (180 days).

CREATE TABLE IF NOT EXISTS public.agent_memory (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id      uuid REFERENCES public.hives(id) ON DELETE CASCADE,
  worker_name  text NOT NULL,
  auth_uid     uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  agent_id     text NOT NULL,                                    -- 'asset-brain', 'analytics', 'project', etc.
  kind         text NOT NULL CHECK (kind IN ('turn', 'summary')),
  turn_text    text,                                              -- present when kind='turn'
  summary      text,                                              -- present when kind='summary'
  meta         jsonb DEFAULT '{}'::jsonb,                         -- model used, latency, token counts
  created_at   timestamptz NOT NULL DEFAULT now()
);

-- The hot path: gateway reads "last 10 turns + latest summary" for
-- (hive_id, worker_name, agent_id). This composite index covers it.
CREATE INDEX IF NOT EXISTS idx_agent_memory_hive_worker_agent_created
  ON public.agent_memory (hive_id, worker_name, agent_id, created_at DESC);

-- Single-worker (no hive) variant for solo-mode lookups.
CREATE INDEX IF NOT EXISTS idx_agent_memory_worker_agent_created
  ON public.agent_memory (worker_name, agent_id, created_at DESC)
  WHERE hive_id IS NULL;

-- Auth-uid index for RLS join.
CREATE INDEX IF NOT EXISTS idx_agent_memory_auth_uid
  ON public.agent_memory (auth_uid);

ALTER TABLE public.agent_memory ENABLE ROW LEVEL SECURITY;

-- Idempotency: DROP IF EXISTS before each CREATE POLICY so re-applying
-- this migration in any environment is a no-op rather than an error.
DROP POLICY IF EXISTS agent_memory_read   ON public.agent_memory;
DROP POLICY IF EXISTS agent_memory_insert ON public.agent_memory;
DROP POLICY IF EXISTS agent_memory_update ON public.agent_memory;
DROP POLICY IF EXISTS agent_memory_delete ON public.agent_memory;

-- Grants: anon and authenticated roles need GRANT to interact with the
-- table at all -- RLS policies filter further but the GRANT is the
-- table-level access. Without it Supabase returns 401 even with valid
-- policies in place.
GRANT SELECT, INSERT, UPDATE, DELETE ON public.agent_memory TO anon, authenticated;

-- Read: own rows OR any row in a hive the worker is a member of.
CREATE POLICY agent_memory_read ON public.agent_memory
  FOR SELECT
  USING (
    auth.uid() IS NOT NULL
    AND (
      auth.uid() = auth_uid
      OR (
        hive_id IS NOT NULL
        AND EXISTS (
          SELECT 1 FROM public.hive_members hm
          WHERE hm.hive_id = agent_memory.hive_id
            AND hm.auth_uid = auth.uid()
            AND hm.status = 'active'
        )
      )
    )
  );

-- Insert: only the authenticated worker, only with their own auth_uid.
CREATE POLICY agent_memory_insert ON public.agent_memory
  FOR INSERT
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND auth.uid() = auth_uid
  );

-- Update: only the authenticated worker can update their own rows
-- (used for editing/deleting turns; agent-side writes go through service role).
CREATE POLICY agent_memory_update ON public.agent_memory
  FOR UPDATE
  USING (auth.uid() IS NOT NULL AND auth.uid() = auth_uid)
  WITH CHECK (auth.uid() IS NOT NULL AND auth.uid() = auth_uid);

-- Delete: own rows only.
CREATE POLICY agent_memory_delete ON public.agent_memory
  FOR DELETE
  USING (auth.uid() IS NOT NULL AND auth.uid() = auth_uid);
