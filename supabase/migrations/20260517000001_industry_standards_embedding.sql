-- ─────────────────────────────────────────────────────────────────────────
-- Day 3 of Azure $200 sprint — semantic search over industry_standards
--
-- Adds a 384-dim embedding column to industry_standards so the platform
-- can do semantic retrieval over the standards corpus (matches the same
-- vector(384) shape used by kb_rag, voice_journal_entries, etc.).
--
-- Source text per row: standard_code || title || notes
-- Provider chain: Voyage (voyage-3.5-lite → 384) → Jina (jina-embeddings-v3 → 384)
-- See: supabase/functions/_shared/embedding-chain.ts
-- ─────────────────────────────────────────────────────────────────────────

ALTER TABLE public.industry_standards
  ADD COLUMN IF NOT EXISTS embedding vector(384);

COMMENT ON COLUMN public.industry_standards.embedding IS
  'Day 3 — 384-dim embedding of standard_code + title + notes. Populated by tools/day3_embed_industry_standards.py via Voyage→Jina chain. Used for semantic standards retrieval.';

-- HNSW index for cosine similarity (faster than IVFFlat on small catalogs)
CREATE INDEX IF NOT EXISTS idx_industry_standards_embedding
  ON public.industry_standards
  USING hnsw (embedding vector_cosine_ops);
