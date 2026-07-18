-- ============================================================================
-- ARC DI §10.5 ANTI-SEESAW — Embedding re-embed-on-EDIT (DI-8), fault_knowledge (2026-07-08)
-- ============================================================================
-- ONE truth (a logbook fault entry) with TWO representations: the logbook row (source text)
-- vs its embedding in fault_knowledge (the RAG index). logbook.html edit-in-place re-calls
-- embed-entry on EVERY save incl. edits, but embed-entry did a plain `.insert(row)` into
-- fault_knowledge with NO unique key on the source `logbook_id` -- so editing a logbook
-- entry ADDED a second embedding for the same source instead of REPLACING it. The RAG index
-- accumulated duplicate + STALE embeddings; semantic search could return the pre-edit text.
-- (The DB `embed-logbook` trigger is AFTER INSERT only, so it never re-embeds on UPDATE
-- either -- the frontend manual call was the only re-embed path, and it duplicated.)
--
-- DISPOSITION (§10.5 embedding seesaw): enforce ONE embedding per source entry so an edit
-- REPLACES it. A UNIQUE index on logbook_id + embed-entry UPSERTing on it (paired code change)
-- makes the source and its embedding un-divergeable; gate validate_embedding_no_stale_duplicates
-- asserts 0 duplicate-source embeddings as a down-ratchet. NON-partial index: Postgres treats
-- NULLs as distinct, so manual embeds (logbook_id NULL) still insert freely, and ON CONFLICT
-- (logbook_id) resolves without a predicate. Forward-only, idempotent.
-- ============================================================================

-- 1. Dedupe any pre-existing duplicates, keeping the most-recent embedding per source.
DELETE FROM public.fault_knowledge f
USING (
  SELECT id,
         row_number() OVER (PARTITION BY logbook_id ORDER BY created_at DESC, id DESC) AS rn
  FROM public.fault_knowledge
  WHERE logbook_id IS NOT NULL
) d
WHERE f.id = d.id AND d.rn > 1;

-- 2. One embedding per source logbook entry (NULLs stay distinct -> manual embeds unaffected).
CREATE UNIQUE INDEX IF NOT EXISTS fault_knowledge_logbook_id_uidx
  ON public.fault_knowledge (logbook_id);
