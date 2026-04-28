-- Knowledge Table Governance — Data Quality Validator findings (Apr 29 2026)
-- Addresses: no data ownership (Problem 07) and no version control (Problem 19)
-- Found by validate_data_governance.py

-- ── 1. Add worker_name to pm_knowledge ────────────────────────────────────────
-- PM health snapshots must be attributed to the worker who triggered the embed
-- so supervisors can audit whose view produced the knowledge snapshot.
ALTER TABLE pm_knowledge
  ADD COLUMN IF NOT EXISTS worker_name text;

-- ── 2. Add embedding_model_version to all 3 knowledge tables ─────────────────
-- When the embedding model changes, old rows must be identifiable for re-embedding.
-- Without this, cosine similarity between different model embeddings is meaningless.
ALTER TABLE fault_knowledge
  ADD COLUMN IF NOT EXISTS embedding_model text DEFAULT 'nomic-embed-text-v1_5';

ALTER TABLE skill_knowledge
  ADD COLUMN IF NOT EXISTS embedding_model text DEFAULT 'nomic-embed-text-v1_5';

ALTER TABLE pm_knowledge
  ADD COLUMN IF NOT EXISTS embedding_model text DEFAULT 'nomic-embed-text-v1_5';

-- ── 3. Add maintenance_type to fault_knowledge ────────────────────────────────
-- Enables RAG semantic search to filter by work type:
-- "Show only Breakdown failures" — currently Preventive entries pollute results.
ALTER TABLE fault_knowledge
  ADD COLUMN IF NOT EXISTS maintenance_type text;

-- Update index comment to reflect schema version
COMMENT ON TABLE fault_knowledge IS 'RAG knowledge base for fault history. Schema v2: worker_name, embedding_model, maintenance_type added 2026-04-29.';
COMMENT ON TABLE skill_knowledge IS 'RAG knowledge base for worker skill profiles. Schema v2: embedding_model added 2026-04-29.';
COMMENT ON TABLE pm_knowledge    IS 'RAG knowledge base for PM health snapshots. Schema v2: worker_name, embedding_model added 2026-04-29.';
