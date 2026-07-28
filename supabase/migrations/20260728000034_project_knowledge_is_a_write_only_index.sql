-- ─────────────────────────────────────────────────────────────────────────────
-- Project knowledge was embedded and then never read by anything.
--
-- FOUND BY THE PJ15 WALK (2026-07-28) — the journey asks "what reaches the RAG, and whose?", and
-- the answer for projects was: it reaches a TABLE, and never reaches the RAG.
--
-- project-manager.html embeds on every scope-item add (`project_item`) and every lessons save
-- (`project_lesson`), through embed-entry, into `project_knowledge`. Measured:
--
--     writers of project_knowledge : embed-entry
--     readers of project_knowledge : NONE
--         - no database function references it (checked pg_get_functiondef across pg_proc)
--         - no edge function references it (checked supabase/functions)
--         - no page references it
--
-- Compare fault_knowledge, which the same edge function writes: read by search_all_knowledge and
-- search_fault_knowledge, and by five edge functions. project_knowledge is a write-only index. The
-- page pays the embedding round-trip on every save and nothing can ever retrieve the result — so a
-- supervisor asking the assistant "what went wrong on the last pump overhaul?" gets an answer that
-- cannot see the lessons that project recorded, even though they were embedded for exactly that.
--
-- search_all_knowledge unions fault + skill + pm and simply never gained a project branch when
-- Phase 6.5 added the writer. This adds it, in the same shape as the other three:
--   * hive_id = match_hive_id, so a tenant's assistant only ever sees its own projects (the
--     condition validate_vector_schema enforces on every branch);
--   * ORDER BY + LIMIT INSIDE the subquery, so one source cannot crowd out the others;
--   * embedding IS NOT NULL, so a row whose embedding failed is skipped rather than ranked at a
--     meaningless distance.
--
-- The summary names the project and what kind of record it is, because "lessons learned on
-- SHD-2026-001 (shutdown)" and "scope item on SHD-2026-001" carry very different weight in an
-- answer, and the assistant should be able to tell the reader which it is reading from.
--
-- WHY THE TABLE LOOKED FINE UNTIL NOW: it holds 0 rows in any seeded environment, because only a
-- UI action populates it — the seeder inserts projects straight into the tables and never calls the
-- page's embed path. An empty table with correct RLS passes every isolation probe vacuously. That
-- is why this was found by asking who READS it rather than by querying it.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.search_all_knowledge(
  query_embedding vector,
  match_hive_id   uuid,
  match_count     integer DEFAULT 3
)
RETURNS TABLE(source text, summary text, similarity double precision)
LANGUAGE sql
STABLE
AS $function$
  SELECT source, summary, similarity FROM (
    SELECT 'fault' AS source,
      CONCAT('Machine: ', machine, ' | Problem: ', problem,
             ' | Root cause: ', root_cause, ' | Fix: ', action) AS summary,
      1 - (embedding <=> query_embedding) AS similarity
    FROM fault_knowledge
    WHERE hive_id = match_hive_id AND embedding IS NOT NULL
    ORDER BY embedding <=> query_embedding LIMIT match_count
  ) f

  UNION ALL

  SELECT source, summary, similarity FROM (
    SELECT 'skill' AS source,
      CONCAT('Worker: ', worker_name, ' | Discipline: ', discipline,
             ' | Level: ', level::text, ' | Primary: ', primary_skill) AS summary,
      1 - (embedding <=> query_embedding) AS similarity
    FROM skill_knowledge
    WHERE hive_id = match_hive_id AND embedding IS NOT NULL
    ORDER BY embedding <=> query_embedding LIMIT match_count
  ) s

  UNION ALL

  SELECT source, summary, similarity FROM (
    SELECT 'pm' AS source,
      CONCAT('Asset: ', asset_name, ' | Category: ', category,
             ' | Overdue tasks: ', overdue_count::text, ' | ', health_summary) AS summary,
      1 - (embedding <=> query_embedding) AS similarity
    FROM pm_knowledge
    WHERE hive_id = match_hive_id AND embedding IS NOT NULL
    ORDER BY embedding <=> query_embedding LIMIT match_count
  ) p

  UNION ALL

  -- PJ15: the branch that was missing. Everything above it was readable; project lessons and scope
  -- items were embedded into a table nothing queried.
  SELECT source, summary, similarity FROM (
    SELECT 'project' AS source,
      CONCAT('Project: ', COALESCE(project_code, '?'),
             ' (', COALESCE(project_type, 'project'), ')',
             ' | Record: ', COALESCE(source_type, 'note'),
             ' | ', COALESCE(text_chunk, '')) AS summary,
      1 - (embedding <=> query_embedding) AS similarity
    FROM project_knowledge
    WHERE hive_id = match_hive_id AND embedding IS NOT NULL
    ORDER BY embedding <=> query_embedding LIMIT match_count
  ) pr;
$function$;

COMMENT ON FUNCTION public.search_all_knowledge(vector, uuid, integer) IS
  'Unified hive-scoped semantic search across fault / skill / pm / project knowledge for the AI '
  'gateway. The project branch was added 2026-07-28 (PJ15): project-manager.html had been embedding '
  'scope items and lessons into project_knowledge since Phase 6.5, and NOTHING read that table — no '
  'db function, no edge function, no page. Each branch filters on hive_id and carries its own '
  'ORDER BY + LIMIT so one source cannot crowd out the others.';
