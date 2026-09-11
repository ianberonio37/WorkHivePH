-- kb_chunks.doc_id gets back the foreign key its own creating migration already declared, and the
-- rows that key would have prevented are removed.
--
-- ★THE SCHEMA SAID ONE THING AND THE DATABASE ANOTHER, AND SIX CHUNKS DIED IN THE GAP (2026-09-10,
-- found while repairing pdf-ingest for W3-FN row W31154). 20260516000004_kb_rag_phase3.sql creates
-- kb_chunks with `doc_id bigint not null references kb_documents(id) on delete cascade`. The live
-- table carries the NOT NULL and has NO foreign key at all - only kb_chunks_pkey.
--
-- WHAT IS ESTABLISHED, AND WHAT IS A STORY. Established: the migration declares the key, the live
-- table lacks it, and the same block's NOT NULL DID land. Not established: why. The tidy
-- explanation - `create table if not exists` finding the table already present and skipping every
-- clause in it - is plausible and UNPROVEN here, because no migration in this repo drops that
-- constraint and only ONE creates the table. The local database is likely built by a reset/seed path
-- rather than by replaying migrations (supabase_migrations.schema_migrations stops at 20260613 while
-- the repo holds 606), which would explain a divergence no migration records. The repair does not
-- depend on the answer, and neither does the gate that now watches for it.
--
-- WHAT THAT COST, and it is not hypothetical. All six kb_chunks rows point at doc_id = 1, and
-- kb_documents is EMPTY. The only reader of this corpus is the RPC semantic_search_kb, which does
-- `from kb_chunks kc join kb_documents kd on kc.doc_id = kd.id where kd.hive_id = p_hive_id` - an
-- INNER join to a row that does not exist - so those six chunks (pump cavitation, motor vibration,
-- MTTR/RCM: real maintenance knowledge, seeded 2026-05-16 and embedded at a cost) can be returned to
-- nobody, in any hive, by any query. Written once, retrievable never.
--
-- WHY DELETE RATHER THAN ADOPT THEM. Attaching them would need a kb_documents row, and that table is
-- hive-scoped (hive_id NOT NULL) while this knowledge is generic - so "adopting" means CHOOSING which
-- hive suddenly starts getting new RAG answers, which changes what the assistant says to real people.
-- Deleting rows that are provably unreachable changes no answer anywhere: the only reader already
-- cannot see them. The conservative repair is the one that preserves behaviour, and if this corpus is
-- wanted the seeder should create the document alongside the chunks - which the constraint below now
-- forces it to do rather than leaving it to be remembered.

BEGIN;

-- 1. the dead rows, and ONLY the dead rows: a chunk whose document does not exist.
DELETE FROM kb_chunks c
 WHERE NOT EXISTS (SELECT 1 FROM kb_documents d WHERE d.id = c.doc_id);

-- 2. the key the schema always meant to have. ON DELETE CASCADE matches the original declaration:
--    removing a document takes its chunks with it, which is the only sane lifetime for a chunk.
ALTER TABLE kb_chunks
  DROP CONSTRAINT IF EXISTS kb_chunks_doc_id_fkey;
ALTER TABLE kb_chunks
  ADD CONSTRAINT kb_chunks_doc_id_fkey
  FOREIGN KEY (doc_id) REFERENCES kb_documents(id) ON DELETE CASCADE;

-- 3. prove it took, in the same transaction that made it - a migration that cannot show its own
--    effect is a migration somebody has to go and check by hand.
DO $$
DECLARE n_orphans int; has_fk boolean;
BEGIN
  SELECT count(*) INTO n_orphans FROM kb_chunks c
    WHERE NOT EXISTS (SELECT 1 FROM kb_documents d WHERE d.id = c.doc_id);
  SELECT EXISTS (SELECT 1 FROM pg_constraint
                  WHERE conrelid = 'kb_chunks'::regclass AND contype = 'f'
                    AND conname = 'kb_chunks_doc_id_fkey') INTO has_fk;
  IF n_orphans <> 0 OR NOT has_fk THEN
    RAISE EXCEPTION 'kb_chunks repair did not hold: orphans=% has_fk=%', n_orphans, has_fk;
  END IF;
  RAISE NOTICE 'kb_chunks: 0 orphans, foreign key present';
END $$;

COMMIT;
