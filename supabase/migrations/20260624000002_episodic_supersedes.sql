-- Companion-Memory C2.1: store-level supersedes / contradiction down-rank (SAFETY).
-- ─────────────────────────────────────────────────────────────────────────────
-- The episodic store (agent_episodic_memory) had NO retrieval-time obsolescence
-- handling: when a worker CORRECTS a fact/procedure (new torque spec, changed
-- part number, reversed plan), BOTH the old and the new memory co-surface at
-- recall — and in a maintenance tool an outdated procedure presented as current
-- is a SAFETY hazard. This is the native port of Memento M3.2's `supersedes`
-- down-rank (tools/memory_supersedes.py, SUPERSEDE_PENALTY ×0.4) onto this
-- pg+pgvector substrate (shared pattern ported natively, not a shared lib).
--
-- Mechanism: a memory row carries `superseded_by` → the id of the memory that
-- replaced it. A row IS obsolete iff superseded_by IS NOT NULL. At retrieval
-- (recallEpisodic in JS, match_procedural_memories in SQL) the obsolete row's
-- effective score is multiplied by SUPERSEDE_PENALTY (0.4), so its replacement
-- ranks above it and an obsolete procedure usually falls below the min-similarity
-- gate entirely. GUARDED: a row with superseded_by NULL is scored byte-identically
-- to before (empty-supersedes = strict no-op, exactly like the Memento guard).
--
-- Writes to superseded_by are service-role-only (the existing aem_update policy
-- already blocks anon/auth UPDATE with USING(false)); the extraction/correction
-- path sets it via the admin client (supersedeEpisodic() in episodic-memory.ts).
-- Forward migration only (immutability doctrine — the original table migration
-- 20260521122000 and the matcher 20260531000001 are NOT edited).

BEGIN;

-- 1) The supersedes link. ON DELETE SET NULL so deleting a replacement does not
--    cascade-delete the (now un-superseded) original; it simply becomes current
--    again rather than vanishing.
ALTER TABLE public.agent_episodic_memory
  ADD COLUMN IF NOT EXISTS superseded_by uuid
    REFERENCES public.agent_episodic_memory(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS superseded_at timestamptz;

-- Partial index: only the (small) set of obsolete rows, for audit/recall filters.
CREATE INDEX IF NOT EXISTS idx_aem_superseded_by
  ON public.agent_episodic_memory (superseded_by)
  WHERE superseded_by IS NOT NULL;

COMMENT ON COLUMN public.agent_episodic_memory.superseded_by IS
  'C2.1: id of the memory that REPLACED this one. NOT NULL => obsolete => down-ranked ×0.4 at retrieval (recallEpisodic + match_procedural_memories) so a corrected fact/procedure cannot co-surface as current. Service-role write only.';

-- 2) Re-define the procedural matcher to apply the supersede penalty. The
--    effective similarity = raw cosine × (0.4 if superseded else 1); the
--    min-similarity gate AND the ordering both use the penalized value, so an
--    obsolete procedure ranks below its replacement and usually drops below the
--    0.55 floor. Signature / grants / SECURITY DEFINER / search_path unchanged.
CREATE OR REPLACE FUNCTION match_procedural_memories(
  p_query_embedding  vector,
  p_hive_id          uuid,
  p_worker_name      text DEFAULT NULL,
  p_match_count      int  DEFAULT 5,
  p_min_similarity   real DEFAULT 0.55
)
RETURNS TABLE (
  id          uuid,
  content     text,
  importance  real,
  use_count   integer,
  similarity  real
) AS $$
  SELECT
    m.id,
    m.content,
    m.importance,
    m.use_count,
    ((1 - (m.embedding <=> p_query_embedding))
      * CASE WHEN m.superseded_by IS NOT NULL THEN 0.4 ELSE 1 END)::real AS similarity
  FROM public.agent_episodic_memory m
  WHERE m.memory_type = 'procedural'
    AND m.embedding IS NOT NULL
    AND (p_hive_id     IS NULL OR m.hive_id     = p_hive_id)
    AND (p_worker_name IS NULL OR m.worker_name = p_worker_name)
    AND ((1 - (m.embedding <=> p_query_embedding))
          * CASE WHEN m.superseded_by IS NOT NULL THEN 0.4 ELSE 1 END) >= p_min_similarity
  ORDER BY similarity DESC
  LIMIT GREATEST(1, LEAST(p_match_count, 20));
$$ LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public;

COMMENT ON FUNCTION match_procedural_memories IS
  'Turn 5 + C2.1 - semantic retrieval over the procedural skill library (agent_episodic_memory WHERE memory_type=procedural). Hive-scoped, worker optional. Cosine distance, min-similarity gated, with a C2.1 supersede penalty (×0.4 on superseded_by IS NOT NULL) so an obsoleted procedure ranks below its replacement. _shared/skill-library.ts matchProcedures() calls this.';

GRANT EXECUTE ON FUNCTION match_procedural_memories(vector, uuid, text, int, real)
  TO anon, authenticated, service_role;

COMMIT;
