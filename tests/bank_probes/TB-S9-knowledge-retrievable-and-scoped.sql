-- TB-S9-knowledge-retrievable-and-scoped.sql
--
-- S9-knowledge, second cell. The existing one proves a marketplace job's writeback BECOMES a logbook entry.
-- This one asks the question that makes that worth anything: **can anyone FIND it afterwards, and only the
-- right people?** ([[feedback_write_only_index_and_hidden_nav]] — ask who READS it.)
--
-- The auto-embed arc measured the answer and it was 14%: 3,278 of 3,811 logbook entries had no
-- `fault_knowledge` row at all, so they were on the board and invisible to every search, every RAG answer and
-- every "has this happened before?". A gate (`knowledge-is-retrievable`) now tracks that ratio and a spine
-- keeps it true; this cell is the bank's own re-runnable assertion of the property, so the marketplace's
-- knowledge layer is not left resting on a platform gate alone.
--
-- FOUR PROPERTIES, each one a way the layer has actually failed or could:
--   1. RETRIEVABLE   an entry rich enough to embed HAS its knowledge row (the 86% gap)
--   2. ONE SPACE     that row carries the pinned model — a vector from another model is silently unfindable,
--                    since cosine against a foreign geometry is noise, not a worse answer
--   3. NO DUPLICATES exactly one knowledge row per entry — skill_knowledge reached 28 rows for 4 distinct
--                    keys before a conflict key was added, every stale copy competing with the current one
--   4. TENANT-SCOPED the knowledge carries the hive, so a foreign hive cannot read another's failures
--
-- Deliberately DB-level and deterministic: no live embedding call at probe time. Whether the embedder is
-- reachable is the relay's problem and the gate's; what the BANK must hold is that the resulting knowledge is
-- present, single-spaced, unduplicated and scoped.
begin;

do $probe$
declare
  v_qualifying int; v_retrievable int; v_spaces int; v_dupes int; v_unscoped int; v_foreign int;
begin
  -- 1. RETRIEVABLE — measured over entries that would actually QUALIFY (embed-entry skips anything whose
  -- composed text is under 50 chars), so this is the product's own rule, not an invented denominator.
  select count(*) filter (where tlen >= 50),
         count(*) filter (where tlen >= 50 and embedded)
    into v_qualifying, v_retrievable
    from (
      select length(concat_ws('. ',
               nullif('Equipment: '||coalesce(l.machine,''),'Equipment: '),
               nullif('Problem: '||coalesce(l.problem,''),'Problem: '),
               nullif('Root cause: '||coalesce(l.root_cause,''),'Root cause: '),
               nullif('Action taken: '||coalesce(l.action,''),'Action taken: '),
               nullif('Lesson learned: '||coalesce(l.knowledge,''),'Lesson learned: '),
               nullif('Category: '||coalesce(l.category,''),'Category: '))) as tlen,
             exists(select 1 from public.fault_knowledge f where f.logbook_id = l.id) as embedded
        from public.logbook l) s;
  raise notice 'RESULT knowledge_written_only=%', v_qualifying - v_retrievable;

  -- 2. ONE SPACE — a corpus split across models is not a degraded index, it is a silently broken one.
  select count(distinct embedding_model) into v_spaces from public.fault_knowledge where embedding is not null;
  raise notice 'RESULT knowledge_vector_spaces=%', v_spaces;

  -- 3. NO DUPLICATES — the failure skill_knowledge already lived through.
  select count(*) into v_dupes from (
    select logbook_id from public.fault_knowledge
     where logbook_id is not null group by logbook_id having count(*) > 1) d;
  raise notice 'RESULT knowledge_duplicate_sources=%', v_dupes;

  -- 4. TENANT-SCOPED — knowledge derived from a hive's failures must carry that hive, or it cannot be
  -- filtered and a search would cross the org boundary the whole platform is built on.
  select count(*) into v_unscoped from public.fault_knowledge f
    join public.logbook l on l.id = f.logbook_id
   where l.hive_id is not null and f.hive_id is distinct from l.hive_id;
  raise notice 'RESULT knowledge_hive_mismatched=%', v_unscoped;

  -- NON-VACUITY: the assertions above are only meaningful if the corpus is NOT empty and genuinely spans
  -- more than one hive. A single-tenant or empty corpus would satisfy every check above while proving
  -- nothing about isolation.
  select count(distinct hive_id) into v_foreign from public.fault_knowledge where hive_id is not null;
  raise notice 'RESULT knowledge_hives_represented=%', case when v_foreign >= 2 then 'multi' else 'SINGLE' end;
end $probe$;

rollback;
