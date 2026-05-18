-- ─────────────────────────────────────────────────────────────────────────
-- Day 5 (L5 wire-up): semantic search RPC over knowledge_graph_facts.
--
-- The day5 KG extractor populated 2,250 hive-scoped fact triples (750 per
-- hive across 3 hives) from the standards corpus. This RPC lets the voice
-- handler retrieve top-N triples by cosine similarity to a query embedding.
--
-- Mirrors the semantic_search_kb / semantic_search_industry_standards
-- pattern: same signature shape, same threshold semantics, same SECURITY
-- DEFINER + search_path lockdown.
-- ─────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION semantic_search_kg_facts(
  p_hive_id               uuid,
  p_query_embedding       vector,
  p_similarity_threshold  real DEFAULT 0.5,
  p_limit                 int  DEFAULT 5,
  p_min_confidence        real DEFAULT 0.5
)
RETURNS TABLE (
  fact_id          uuid,
  subject_ref      text,
  predicate        text,
  object_ref       text,
  claim_text       text,
  confidence       numeric,
  source_type      text,
  source_ref       text,
  similarity_score real
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    f.id                                AS fact_id,
    f.subject_ref,
    f.predicate,
    f.object_ref,
    f.claim_text,
    f.confidence,
    f.source_type,
    f.source_ref,
    (f.embedding <=> p_query_embedding)::real AS similarity_score
  FROM public.knowledge_graph_facts f
  WHERE f.hive_id     = p_hive_id
    AND f.active      = true
    AND f.embedding   IS NOT NULL
    AND f.confidence  >= p_min_confidence
    AND (f.embedding <=> p_query_embedding) <= (1 - p_similarity_threshold)
  ORDER BY f.embedding <=> p_query_embedding
  LIMIT p_limit;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

COMMENT ON FUNCTION semantic_search_kg_facts IS
  'Day 5 — hive-scoped semantic retrieval over knowledge_graph_facts triples. Returns top-N triples by cosine distance, filtered by min confidence. Voice handler calls this in parallel with semantic_search_kb (hive docs) and semantic_search_industry_standards (platform canon).';

GRANT EXECUTE ON FUNCTION semantic_search_kg_facts(uuid, vector, real, int, real)
  TO anon, authenticated;
