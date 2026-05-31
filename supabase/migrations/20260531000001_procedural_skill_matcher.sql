-- ─────────────────────────────────────────────────────────────────────────
-- Memory-stack Turn 5 (Procedural / layer 04): runtime skill library + matcher.
--
-- The "procedural" memory_type in agent_episodic_memory IS the distilled skill
-- library ("P-203 bearing fix: replace SKF 6205-2RS") - the agentic-rag-loop
-- Checker writes these, and ai-gateway recalls them. BUT recall ranks by
-- importance x log(1+use_count) + crude keyword overlap, NOT semantic
-- similarity to the current problem, and the embeddings were never filled
-- (persistEpisodic wrote embedding=null; the column comment literally says
-- "nullable: enrichment fills later"). There was also NO vector index. So a
-- proven procedure phrased differently from the current fault was never
-- surfaced.
--
-- Turn 5 closes that:
--   1. semantic-fact-extractor sibling: persistEpisodic now embeds PROCEDURAL
--      memories at store time (best-effort) so the library is searchable.
--   2. this migration adds the vector index + match_procedural_memories RPC.
--   3. _shared/skill-library.ts matchProcedures() + ai-gateway wiring inject the
--      top semantically-matched procedures for fix-oriented agents.
--
-- Mirrors the semantic_search_kg_facts / search_fault_knowledge pattern:
-- SECURITY DEFINER + locked search_path, cosine distance, min-similarity gate.
-- ─────────────────────────────────────────────────────────────────────────

BEGIN;

-- Vector index for cosine search over the procedural skill library. ivfflat
-- lists=50 matches the fault_knowledge / skill_knowledge / pm_knowledge
-- siblings. The RPC filters memory_type + scope in its WHERE; the index just
-- accelerates the <=> ordering.
CREATE INDEX IF NOT EXISTS idx_aem_embedding
  ON public.agent_episodic_memory USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 50);

-- match_procedural_memories — hive-scoped (worker optional) cosine retrieval of
-- the distilled procedure library. A proven fix from any teammate helps, so the
-- default scope is the whole hive; pass p_worker_name to narrow to one worker.
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
    (1 - (m.embedding <=> p_query_embedding))::real AS similarity
  FROM public.agent_episodic_memory m
  WHERE m.memory_type = 'procedural'
    AND m.embedding IS NOT NULL
    AND (p_hive_id     IS NULL OR m.hive_id     = p_hive_id)
    AND (p_worker_name IS NULL OR m.worker_name = p_worker_name)
    AND (1 - (m.embedding <=> p_query_embedding)) >= p_min_similarity
  ORDER BY m.embedding <=> p_query_embedding
  LIMIT GREATEST(1, LEAST(p_match_count, 20));
$$ LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public;

COMMENT ON FUNCTION match_procedural_memories IS
  'Turn 5 - semantic retrieval over the procedural skill library (agent_episodic_memory WHERE memory_type=procedural). Hive-scoped, worker optional. Cosine distance, min-similarity gated. _shared/skill-library.ts matchProcedures() calls this; ai-gateway injects the result for fix-oriented agents.';

GRANT EXECUTE ON FUNCTION match_procedural_memories(vector, uuid, text, int, real)
  TO anon, authenticated, service_role;

COMMIT;
