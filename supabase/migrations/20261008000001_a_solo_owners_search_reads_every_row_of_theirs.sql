-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- A solo owner's knowledge search reads EVERY row of theirs, not the ones an approximate index probed
-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- Found 2026-10-08, proving ai-gateway's and semantic-search's new solo path live (both now ask
-- search_fault_knowledge for match_hive_id NULL + match_owner = the verified caller). 20261007000014 gave
-- search_fault_knowledge and search_all_knowledge their own scope as ONE predicate:
--
--     WHERE embedding IS NOT NULL
--       AND (hive_id = match_hive_id OR (match_hive_id IS NULL AND hive_id IS NULL AND auth_uid = <owner>))
--     ORDER BY embedding <=> query_embedding LIMIT match_count
--
-- Correct in meaning, and its gate proved it - with LITERAL arguments, where the planner folds match_hive_id NULL
-- away and reads the hive-less rows through idx_fault_knowledge_hive, exactly. PostgREST never sends literals: an RPC
-- binds its arguments, the plan is generic, the OR cannot be folded, and the cheapest plan is
-- idx_fault_knowledge_embedding - ivfflat, lists=50, probes=1 - ordered by distance with the owner test applied AFTER
-- the index. That scan visits ONE list (~500 of the table's 24,923 rows), so a person's own rows come back only when
-- they happen to sit in the list nearest the question. Measured: semantic-search for boyet (3 embedded hive-less rows),
-- match_count 10, returned 1; the same call under plan_cache_mode = force_generic_plan returned the same single id;
-- with literals, all 3. A solo owner's AI answers would have used their own records only by luck.
--
-- The own scope is a handful of rows by construction - one person's hive-less entries - so it is searched EXACTLY:
-- the person's rows are selected first in a MATERIALIZED CTE (a materialized result cannot be ordered by the vector
-- index), then ordered by distance.
--
-- The HIVE scope had the same regression, unnoticed: before 20261007000014 its plain `hive_id = match_hive_id`
-- predicate planned (generic) as idx_fault_knowledge_hive + sort - exact, 5 ms on the largest hive (7,700 rows). The
-- OR moved it onto the ivfflat scan: one probed list, 311 ms, and only the hive rows that list happened to hold.
-- Split back into its own branch, the hive scope returns to the plan it had (measured after: btree + sort, exact,
-- ~10 ms). It also gains `match_hive_id IS NOT NULL`, which `hive_id = match_hive_id` already implied (NULL equals
-- nothing), so a solo call skips that branch as a one-time filter. Same signatures and return types, so CREATE OR
-- REPLACE keeps the grants, SECURITY INVOKER and the one-candidate-per-name rule (PGRST203) 20261007000014 set.

BEGIN;

CREATE OR REPLACE FUNCTION public.search_fault_knowledge(
  query_embedding vector, match_hive_id uuid, match_count integer DEFAULT 5, match_owner uuid DEFAULT NULL)
RETURNS TABLE(id uuid, machine text, problem text, root_cause text, action text, knowledge text,
              worker_name text, similarity double precision)
LANGUAGE sql
STABLE
AS $function$
  SELECT id, machine, problem, root_cause, action, knowledge, worker_name, similarity FROM (
    -- HIVE scope: the pre-20261007000014 predicate, so it plans as it did (hive index + distance sort).
    SELECT h.id, h.machine, h.problem, h.root_cause, h.action, h.knowledge, h.worker_name, h.similarity FROM (
      SELECT f.id, f.machine, f.problem, f.root_cause, f.action, f.knowledge, f.worker_name,
             1 - (f.embedding <=> query_embedding) AS similarity
        FROM fault_knowledge f
       WHERE match_hive_id IS NOT NULL AND f.embedding IS NOT NULL AND f.hive_id = match_hive_id
       ORDER BY f.embedding <=> query_embedding
       LIMIT match_count
    ) h
    UNION ALL
    -- OWN scope: a hive-less row belongs to the person who wrote its entry. The owner is the CALLER (auth.uid());
    -- match_owner is honoured only for a server role that has already resolved the person. Exact, never probed.
    SELECT o.id, o.machine, o.problem, o.root_cause, o.action, o.knowledge, o.worker_name, o.similarity FROM (
      WITH mine AS MATERIALIZED (
        SELECT f.id, f.machine, f.problem, f.root_cause, f.action, f.knowledge, f.worker_name, f.embedding
          FROM fault_knowledge f
         WHERE match_hive_id IS NULL AND f.hive_id IS NULL AND f.embedding IS NOT NULL
           AND f.auth_uid = COALESCE(auth.uid(),
                                     CASE WHEN current_user IN ('service_role', 'postgres') THEN match_owner END)
      )
      SELECT m.id, m.machine, m.problem, m.root_cause, m.action, m.knowledge, m.worker_name,
             1 - (m.embedding <=> query_embedding) AS similarity
        FROM mine m
       ORDER BY m.embedding <=> query_embedding
       LIMIT match_count
    ) o
  ) r
  ORDER BY similarity DESC;
$function$;

COMMENT ON FUNCTION public.search_fault_knowledge(vector, uuid, integer, uuid) IS
  'Semantic search over fault_knowledge. match_hive_id = a hive: that hive''s rows (RLS still applies to the '
  'caller). match_hive_id NULL: the caller''s OWN hive-less rows (auth.uid()), searched exactly '
  '(20261008000001); match_owner is honoured only for service_role/postgres callers that already resolved the person.';

CREATE OR REPLACE FUNCTION public.search_all_knowledge(
  query_embedding vector, match_hive_id uuid, match_count integer DEFAULT 3, match_owner uuid DEFAULT NULL)
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
    WHERE match_hive_id IS NOT NULL AND embedding IS NOT NULL AND hive_id = match_hive_id
    ORDER BY embedding <=> query_embedding LIMIT match_count
  ) f

  UNION ALL

  -- OWN scope (hive-less person): only fault_knowledge carries an owner column, so it is the only branch that
  -- answers it; the branches below keep hive_id = match_hive_id, which a NULL never meets. Exact, never probed.
  SELECT source, summary, similarity FROM (
    WITH mine AS MATERIALIZED (
      SELECT machine, problem, root_cause, action, embedding
        FROM fault_knowledge
       WHERE match_hive_id IS NULL AND hive_id IS NULL AND embedding IS NOT NULL
         AND auth_uid = COALESCE(auth.uid(),
                                 CASE WHEN current_user IN ('service_role', 'postgres') THEN match_owner END)
    )
    SELECT 'fault' AS source,
      CONCAT('Machine: ', machine, ' | Problem: ', problem,
             ' | Root cause: ', root_cause, ' | Fix: ', action) AS summary,
      1 - (embedding <=> query_embedding) AS similarity
    FROM mine
    ORDER BY embedding <=> query_embedding LIMIT match_count
  ) fo

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

COMMENT ON FUNCTION public.search_all_knowledge(vector, uuid, integer, uuid) IS
  'Companion RAG over fault/skill/pm/project knowledge. match_hive_id NULL: the caller''s OWN hive-less fault '
  'rows (only fault_knowledge carries an owner), searched exactly (20261008000001). match_owner is honoured only '
  'for service_role/postgres.';

-- ── verification: refuse to commit a half-applied change ────────────────────────────────────────
DO $verify$
DECLARE v_n int;
BEGIN
  SELECT count(*) INTO v_n FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
   WHERE n.nspname = 'public' AND p.proname IN ('search_fault_knowledge', 'search_all_knowledge');
  IF v_n <> 2 THEN RAISE EXCEPTION 'expected exactly one search_fault_knowledge + one search_all_knowledge, found %', v_n; END IF;
  IF EXISTS (SELECT 1 FROM pg_proc p WHERE p.proname IN ('search_fault_knowledge', 'search_all_knowledge') AND p.prosecdef) THEN
    RAISE EXCEPTION 'the knowledge searches must stay SECURITY INVOKER';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_proc p WHERE p.proname IN ('search_fault_knowledge', 'search_all_knowledge')
               AND pg_get_functiondef(p.oid) NOT LIKE '%AS MATERIALIZED%') THEN
    RAISE EXCEPTION 'a knowledge search lost its exact own-scope branch';
  END IF;
  IF NOT has_function_privilege('authenticated', 'public.search_fault_knowledge(vector, uuid, integer, uuid)', 'EXECUTE')
     OR NOT has_function_privilege('service_role', 'public.search_all_knowledge(vector, uuid, integer, uuid)', 'EXECUTE') THEN
    RAISE EXCEPTION 'a knowledge search lost its EXECUTE grant';
  END IF;
END
$verify$;

COMMIT;
