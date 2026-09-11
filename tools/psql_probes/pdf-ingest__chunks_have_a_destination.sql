-- chunks_have_a_destination (pdf-ingest): the ingester's write can actually LAND, and the shape it
-- used to write still cannot. This is the database half of W3-FN row W31154 - the half that can be
-- asserted without a browser and without the edge runtime, so it holds the fix in place whether or not
-- the function has been invoked lately.
--
-- ★WHAT WAS WRONG, AND WHY THE OBVIOUS FIX WOULD HAVE BEEN THE WRONG ONE (2026-09-10). pdf-ingest built
-- one generic row - { hive_id, embedding, content, meta, source } - and inserted it into whatever
-- `pdf_jobs.target_table` named, a destination a database-level CHECK restricts to six knowledge
-- tables. Not one of the six has a `content` column or a `meta` column, so EVERY insert it could
-- attempt failed on EVERY permitted destination - after the embedding call, which succeeds first, so
-- each attempt spent embedding budget on a row that could not land. The function's own header called
-- for "a per-target field mapping". That premise was wrong: five of those six are DERIVED SUMMARY
-- tables - one row per asset (pm_knowledge), per worker (skill_knowledge), per calculation
-- (calc_knowledge) - so a page of a manual was never a row they could hold under ANY column name.
-- The platform already had the right store and it needed no migration: kb_documents + kb_chunks.
--
-- So this asserts the DESTINATION, both directions, with the old shape as a live CONTROL: a lock that
-- only checked "kb_chunks accepts a row" would pass just as happily on the day someone re-points the
-- ingester back at a summary table.
-- expect: destination_tables_present \| t
-- expect: chunk_carries_text_and_vector \| t
-- expect: chunk_is_bound_to_its_document \| t
-- expect: orphan_chunks \| 0
-- expect: old_shape_is_still_refused \| t
-- expect: new_shape_lands \| t
-- expect: chunk_reads_back_through_its_document \| t
-- expect: residue_after_rollback \| 0
SELECT 'destination_tables_present | ' || (
  (SELECT count(*) FROM information_schema.tables
    WHERE table_schema='public' AND table_name IN ('kb_documents','kb_chunks')) = 2);

-- ★THE KEY THE SCHEMA ALWAYS MEANT TO HAVE, AND THE SIBLING THAT PROVES IT IS THE HOUSE SHAPE
-- (2026-09-10). kb_rag_phase3 creates kb_chunks with `doc_id ... references kb_documents(id) on
-- delete cascade`, and the live table had the NOT NULL and NO foreign key - what `create table if
-- not exists` does when the table is already there: it skips the whole definition, so half the
-- intent landed and half never did. The cost was not theoretical. All six chunks pointed at a
-- doc_id that did not exist while kb_documents sat empty, and the only reader, semantic_search_kb,
-- INNER JOINs the two - so six embedded chunks of real maintenance knowledge were returnable to
-- nobody, in any hive, by any query. The platform's OTHER chunk corpus settles what the right shape
-- is: industry_standards_chunks (781 rows) carries exactly this key, cascade and all, plus a unique
-- (standard_id, chunk_num), and holds zero orphans. This asserts the repair rather than trusting the
-- migration to stay applied, because a constraint that can be dropped by the next `if not exists`
-- is a constraint worth re-checking on every run.
SELECT 'chunk_is_bound_to_its_document | ' || EXISTS (
  SELECT 1 FROM pg_constraint
   WHERE conrelid = 'kb_chunks'::regclass AND contype = 'f'
     AND pg_get_constraintdef(oid) ILIKE '%REFERENCES kb_documents(id)%'
     AND pg_get_constraintdef(oid) ILIKE '%ON DELETE CASCADE%');

-- and the state that key exists to make impossible
SELECT 'orphan_chunks | ' || (
  SELECT count(*) FROM kb_chunks c
   WHERE NOT EXISTS (SELECT 1 FROM kb_documents d WHERE d.id = c.doc_id));

-- the columns the function writes, named one by one: a rename would break the ingester silently
SELECT 'chunk_carries_text_and_vector | ' || (
  (SELECT count(*) FROM information_schema.columns
    WHERE table_schema='public' AND table_name='kb_chunks'
      AND column_name IN ('doc_id','chunk_num','text','embedding')) = 4);

BEGIN;
-- THE CONTROL: the shape pdf-ingest used to write, against a destination its CHECK allowed. It must
-- still be refused - if this ever starts succeeding, someone has added content/meta to a summary
-- table and the old design is back.
SAVEPOINT s_old;
DO $$
DECLARE ok_flag boolean := false;
BEGIN
  BEGIN
    EXECUTE $q$INSERT INTO fault_knowledge (hive_id, embedding, content, meta, source)
              VALUES ((SELECT id FROM hives LIMIT 1),
                      (SELECT ('['||string_agg('0.01',',')||']')::vector FROM generate_series(1,384)),
                      'a page of a manual', '{}'::jsonb, 'pdf_ingest')$q$;
  EXCEPTION WHEN undefined_column THEN
    ok_flag := true;                       -- refused for exactly the documented reason
  END;
  RAISE NOTICE 'old_shape_is_still_refused | %', ok_flag;
END $$;
ROLLBACK TO s_old;

-- THE CLAIM: a document, then a chunk filed under it - what the function now does.
INSERT INTO kb_documents (hive_id, title, content_type, embedding_status)
VALUES ((SELECT id FROM hives LIMIT 1), 'probe-pdf-ingest-destination', 'fault_knowledge', 'processing');

INSERT INTO kb_chunks (doc_id, chunk_num, text, embedding)
VALUES ((SELECT id FROM kb_documents WHERE title='probe-pdf-ingest-destination'), 1,
        'a page of a manual',
        (SELECT ('['||string_agg('0.01',',')||']')::vector FROM generate_series(1,384)));

SELECT 'new_shape_lands | ' || (
  (SELECT count(*) FROM kb_documents WHERE title='probe-pdf-ingest-destination') = 1);

-- and the chunk must be reachable FROM its document, which is the whole reason to file it under one:
-- a chunk whose doc_id points nowhere is the scattered-row problem with extra steps.
SELECT 'chunk_reads_back_through_its_document | ' || (
  (SELECT count(*) FROM kb_chunks c JOIN kb_documents d ON d.id = c.doc_id
    WHERE d.title='probe-pdf-ingest-destination' AND c.text <> '' AND c.embedding IS NOT NULL) = 1);
ROLLBACK;

-- ★A COUNT-BASED RESTORATION CHECK IS BROKEN BY ANY CONCURRENT WRITER (2026-09-10). This asserts THIS
-- probe's own residue by its marker title rather than comparing a before/after count, so a journey
-- walk writing kb rows in another connection cannot turn this red.
SELECT 'residue_after_rollback | ' || (
  SELECT count(*) FROM kb_documents WHERE title='probe-pdf-ingest-destination');
