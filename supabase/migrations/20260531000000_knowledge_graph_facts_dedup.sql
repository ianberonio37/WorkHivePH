-- ─────────────────────────────────────────────────────────────────────────
-- Memory-stack Turn 4 (Semantic / layer 03): make hive-scoped KG fact writes
-- idempotent so the per-hive logbook entity extractor (semantic-fact-extractor)
-- can re-run safely without exploding the table with near-duplicate triples.
--
-- Why this is needed now:
--   knowledge_graph_facts was created in phase6 (20260513000007) with three
--   NON-unique indexes (hive_active, subject, predicate) but NO dedupe key.
--   Its PLATFORM sibling (platform_knowledge_graph_facts, 20260518/19) DOES
--   have UNIQUE (subject_ref, predicate, object_ref, source_ref) — the hive
--   table was simply never given the matching key because, until now, only the
--   one-shot day5 standards extractor wrote to KG facts (and it wrote to the
--   platform table). Turn 4 adds the first WRITER of hive-scoped logbook facts;
--   it upserts ON CONFLICT, which requires a real unique constraint to target.
--
-- Scope difference vs. the platform sibling: hive_id is part of the key here.
--   The same triple ("pump_a -> causes -> seal_failure") is a DISTINCT fact per
--   hive (Baguio's pump != Manila's pump), so hive_id leads the unique tuple.
--
-- Safety: the table is empty at migration time (0 rows, verified 2026-05-31),
-- so CREATE UNIQUE INDEX cannot fail on a pre-existing duplicate. IF NOT EXISTS
-- keeps the migration idempotent on re-run.
-- ─────────────────────────────────────────────────────────────────────────

BEGIN;

CREATE UNIQUE INDEX IF NOT EXISTS uq_kgf_triple_source
  ON public.knowledge_graph_facts (hive_id, subject_ref, predicate, object_ref, source_ref);

COMMENT ON INDEX public.uq_kgf_triple_source IS
  'Turn 4 — dedupe key for hive-scoped KG fact upserts. Mirrors the platform sibling''s UNIQUE (subject_ref, predicate, object_ref, source_ref) but leads with hive_id since the same triple is a distinct claim per hive. semantic-fact-extractor upserts ON CONFLICT against this index.';

COMMIT;
