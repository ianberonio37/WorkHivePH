-- ─────────────────────────────────────────────────────────────────────────
-- Day 8 — split KG facts by scope (parallel to the kb_chunks split).
--
-- Why this exists:
--   knowledge_graph_facts.hive_id is NOT NULL, designed for HIVE-specific
--   claims ("Motor M-3 at Baguio has failed 4 times since 2025-Q3"). When
--   the day5 extractor produced 1,535 STANDARDS-derived triples (NIST,
--   OSHA, US Army, NIST IR 8183, DOE), we broadcast them to all 3 hives
--   to satisfy the NOT NULL. That triplicated identical content (4,605 rows).
--
-- Correct architecture (matches the kb_chunks vs. industry_standards_chunks
-- precedent from 2026-05-18):
--   HIVE-scoped  → knowledge_graph_facts            (this hive's claims)
--   PLATFORM     → platform_knowledge_graph_facts   (regulatory + canon)
--
-- Voice handler now queries both in parallel and merges citations, same
-- pattern it already uses for kb + industry_standards.
-- ─────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.platform_knowledge_graph_facts (
  id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  subject_type    text        NOT NULL CHECK (subject_type ~ '^[a-z][a-z0-9_]{0,30}$'),
  subject_ref     text        NOT NULL,
  predicate       text        NOT NULL CHECK (predicate ~ '^[a-z][a-z0-9_]{0,30}$'),
  object_type     text        NOT NULL CHECK (object_type ~ '^[a-z][a-z0-9_]{0,30}$'),
  object_ref      text        NOT NULL,
  claim_text      text,
  payload         jsonb       NOT NULL DEFAULT '{}'::jsonb,
  confidence      numeric(4,3) NOT NULL DEFAULT 0.5 CHECK (confidence BETWEEN 0 AND 1),
  -- source_type intentionally narrowed: this table is for canon, not opinions
  source_type     text        NOT NULL CHECK (source_type IN ('standard', 'sop', 'ai_extraction', 'external_import')),
  source_ref      text,
  embedding       vector(384),
  superseded_by   uuid        REFERENCES public.platform_knowledge_graph_facts(id) ON DELETE SET NULL,
  active          boolean     NOT NULL DEFAULT true,
  created_by      text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  -- Dedupe key — same triple from the same source should not appear twice
  UNIQUE (subject_ref, predicate, object_ref, source_ref)
);

COMMENT ON TABLE public.platform_knowledge_graph_facts IS
  'Day 8 — PLATFORM-scoped subject/predicate/object triples derived from regulatory canon + best-practice standards. Sibling to knowledge_graph_facts (HIVE-scoped). Replaces the broadcast-to-all-hives pattern. Single source of truth for cross-hive facts.';

CREATE INDEX IF NOT EXISTS idx_pkgf_active_created
  ON public.platform_knowledge_graph_facts (active, created_at DESC)
  WHERE active = true;

CREATE INDEX IF NOT EXISTS idx_pkgf_predicate
  ON public.platform_knowledge_graph_facts (predicate);

CREATE INDEX IF NOT EXISTS idx_pkgf_subject_type
  ON public.platform_knowledge_graph_facts (subject_type);

CREATE INDEX IF NOT EXISTS idx_pkgf_embedding
  ON public.platform_knowledge_graph_facts
  USING hnsw (embedding vector_cosine_ops);

-- RLS — same pattern as industry_standards_chunks: read-all, no writes from
-- app code (only service-role / one-shot tools populate this).
ALTER TABLE public.platform_knowledge_graph_facts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS pkgf_read ON public.platform_knowledge_graph_facts;
CREATE POLICY pkgf_read ON public.platform_knowledge_graph_facts
  FOR SELECT USING (true);

DROP POLICY IF EXISTS pkgf_write_locked ON public.platform_knowledge_graph_facts;
CREATE POLICY pkgf_write_locked ON public.platform_knowledge_graph_facts
  FOR INSERT WITH CHECK (false);

GRANT SELECT ON public.platform_knowledge_graph_facts TO anon, authenticated;

-- ─────────────────────────────────────────────────────────────────────────
-- RPC: semantic_search_platform_kg_facts
-- Mirrors semantic_search_kg_facts but with NO hive filter. Voice handler
-- calls both — hive-scoped and platform — and merges citations.
-- ─────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION semantic_search_platform_kg_facts(
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
  FROM public.platform_knowledge_graph_facts f
  WHERE f.active     = true
    AND f.embedding  IS NOT NULL
    AND f.confidence >= p_min_confidence
    AND (f.embedding <=> p_query_embedding) <= (1 - p_similarity_threshold)
  ORDER BY f.embedding <=> p_query_embedding
  LIMIT p_limit;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

COMMENT ON FUNCTION semantic_search_platform_kg_facts IS
  'Day 8 — platform-wide semantic retrieval over standards-derived KG triples. Mirrors semantic_search_kg_facts (hive-scoped) shape but takes no hive_id. Voice handler calls both and merges.';

GRANT EXECUTE ON FUNCTION semantic_search_platform_kg_facts(vector, real, int, real)
  TO anon, authenticated;
