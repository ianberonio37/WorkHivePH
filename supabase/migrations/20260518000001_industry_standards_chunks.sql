-- ─────────────────────────────────────────────────────────────────────────
-- Day 4 of Azure $200 sprint — platform-wide standards RAG.
--
-- Mirrors the kb_chunks pattern (20260516000004_kb_rag_phase3.sql) but at
-- PLATFORM scope, not hive scope. industry_standards holds the canon every
-- hive aligns to (ISO 14224, ASHRAE 90.1, PSME, DOLE D.O. 198-18, ...).
-- Chunks store full-text passages from each standard's PDF / reference doc.
--
-- Why a separate table from kb_chunks:
--   - kb_chunks is hive-scoped (per-hive equipment manuals, internal SOPs)
--   - industry_standards_chunks is platform-scoped (regulatory + best-practice
--     canon, identical for every hive)
--   - Different RLS, different freshness cadence, different RAG retrieval RPC
--
-- Retrieval pattern (voice-handler.js):
--   - Worker asks "what does ISO 14224 say about MTBF?"
--   - Embed query (Voyage->Jina chain)
--   - Call semantic_search_industry_standards (platform-wide, NO hive filter)
--   - Concat top hits with kb_chunks results, hand to AI for synthesis
-- ─────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.industry_standards_chunks (
  id              bigserial   PRIMARY KEY,
  standard_id     uuid        NOT NULL REFERENCES public.industry_standards(id) ON DELETE CASCADE,
  chunk_num       integer     NOT NULL,
  section         text,                            -- e.g. "5.2.3 Failure Modes"
  text            text        NOT NULL,
  embedding       vector(384),                     -- Voyage 512->384 or Jina native 384
  source_pdf      text,                            -- "nist-800-82.pdf", "us-army-tm-5-698.pdf", ...
  created_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (standard_id, chunk_num)
);

COMMENT ON TABLE public.industry_standards_chunks IS
  'Day 4 — full-text chunks of industry standards, embedded for semantic search. Platform-scoped (hive-agnostic). Populated by tools/day4_chunk_standards_pdfs.py.';

CREATE INDEX IF NOT EXISTS idx_industry_standards_chunks_standard
  ON public.industry_standards_chunks (standard_id, chunk_num);

CREATE INDEX IF NOT EXISTS idx_industry_standards_chunks_embedding
  ON public.industry_standards_chunks
  USING hnsw (embedding vector_cosine_ops);

-- RLS: read for everyone (it's a platform catalog), no writes from app code.
ALTER TABLE public.industry_standards_chunks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS isc_read ON public.industry_standards_chunks;
CREATE POLICY isc_read ON public.industry_standards_chunks
  FOR SELECT USING (true);

DROP POLICY IF EXISTS isc_write_locked ON public.industry_standards_chunks;
CREATE POLICY isc_write_locked ON public.industry_standards_chunks
  FOR INSERT WITH CHECK (false);

GRANT SELECT ON public.industry_standards_chunks TO anon, authenticated;

-- ─────────────────────────────────────────────────────────────────────────
-- RPC: semantic_search_industry_standards
-- Platform-wide retrieval. NO hive filter. Returns top-N chunks by cosine
-- distance, joined with the parent industry_standards row for citation.
-- ─────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION semantic_search_industry_standards(
  p_query_embedding       vector,
  p_similarity_threshold  real    DEFAULT 0.6,
  p_limit                 int     DEFAULT 5,
  p_family                text    DEFAULT NULL    -- optional: 'iso', 'iec', 'philippine', ...
)
RETURNS TABLE (
  chunk_id           bigint,
  standard_id        uuid,
  standard_code      text,
  standard_title     text,
  family             text,
  section            text,
  chunk_text         text,
  similarity_score   real,
  source_url         text
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    isc.id              AS chunk_id,
    s.id                AS standard_id,
    s.standard_code,
    s.title             AS standard_title,
    s.family,
    isc.section,
    isc.text            AS chunk_text,
    (isc.embedding <=> p_query_embedding)::real AS similarity_score,
    s.source_url
  FROM public.industry_standards_chunks isc
  JOIN public.industry_standards        s ON isc.standard_id = s.id
  WHERE isc.embedding IS NOT NULL
    AND (p_family IS NULL OR s.family = p_family)
    AND (isc.embedding <=> p_query_embedding) <= (1 - p_similarity_threshold)
  ORDER BY isc.embedding <=> p_query_embedding
  LIMIT p_limit;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

COMMENT ON FUNCTION semantic_search_industry_standards IS
  'Day 4 — platform-wide semantic retrieval over industry standards corpus. Mirrors semantic_search_kb but with NO hive filter (standards are global). Optional p_family narrows to specific bodies (iso/iec/philippine/etc).';

GRANT EXECUTE ON FUNCTION semantic_search_industry_standards(vector, real, int, text) TO anon, authenticated;

-- ─────────────────────────────────────────────────────────────────────────
-- Convenience view: which standards have body content vs. metadata only
-- ─────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW v_industry_standards_coverage AS
SELECT
  s.id,
  s.standard_code,
  s.family,
  s.title,
  COUNT(isc.id)::int                    AS chunk_count,
  COUNT(isc.id) FILTER (WHERE isc.embedding IS NOT NULL)::int AS embedded_chunks,
  CASE
    WHEN COUNT(isc.id) = 0 THEN 'metadata_only'
    WHEN COUNT(isc.id) FILTER (WHERE isc.embedding IS NOT NULL) = COUNT(isc.id) THEN 'full_text_searchable'
    ELSE 'partially_embedded'
  END                                   AS coverage_status
FROM public.industry_standards s
LEFT JOIN public.industry_standards_chunks isc ON isc.standard_id = s.id
GROUP BY s.id, s.standard_code, s.family, s.title;

COMMENT ON VIEW v_industry_standards_coverage IS
  'Day 4 — at-a-glance coverage: which standards are metadata-only vs. have searchable full text via chunks.';

GRANT SELECT ON v_industry_standards_coverage TO anon, authenticated;
