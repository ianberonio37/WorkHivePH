-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- Every vector search reads its WHOLE scope, not the slice an approximate index happened to probe
-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- 20261008000001 found it for the solo owner's fault search: given a scope filter (a hive, a person, a family) and
-- `ORDER BY embedding <=> q LIMIT k`, Postgres may serve the ORDER BY from the approximate vector index - ivfflat
-- lists=50 probes=1 walks ONE list (~1/50th of the table), hnsw ef_search=40 yields 40 candidates - and apply the scope
-- AFTER. A scope whose rows sit outside that list comes back partial or empty. Whether the planner does it depends on
-- the plan: a generic plan (PostgREST binds an RPC's arguments) or a custom one (the values known - a literal call, a
-- plpgsql RETURN QUERY's first executions) can each pick it, and a table's statistics can flip it either way.
--
-- tools/validate_vector_search_recall.py measured every vector search that way - PREPAREd with bound parameters under
-- force_generic_plan AND force_custom_plan, as the real principal, largest and smallest scope, against the exact truth
-- (the same call with enable_indexscan = off) - recall@10, worst question / mean, before this migration:
--
--   search_pm_knowledge          hive 4eec150e (147 rows)     generic 0.00 / 0.14   custom 0.00 / 0.14  (index plan, both)
--   search_pm_knowledge          hive 2807e679 (1 row)        generic 0.00 / 0.14   custom 1.00
--   search_fault_knowledge       hive b4f7fe63 (7,700 rows)   generic 1.00          custom 0.00 / 0.65
--   search_all_knowledge         hive b4f7fe63                generic 0.67 / 0.68   custom 0.33 / 0.56  (pm + project)
--   search_bom_knowledge         1,200-row hive, service_role generic 1.00          custom 0.20 / 0.70  (seeded)
--   search_calc_knowledge        1,200-row hive, service_role generic 1.00          custom 0.10 / 0.43  (seeded)
--   semantic_search_platform_kg_facts  confidence >= 0.95     generic 1.00          custom 0.00 / 0.09  (seeded, hnsw)
--   semantic_search_kb           every member call            ERROR - "Returned type double precision does not match
--                                expected type real in column 5": it never returned a row to anyone (see below)
--
-- Measured exact on today's data but built the same way, so a statistics change flips them: search_skill_knowledge
-- (9 rows), search_voice_journal_entries (243 rows for the largest person), semantic_search_industry_standards (781
-- chunks, hnsw; the family filter is a scope). They get the same fence. Exact BY CONSTRUCTION and left alone:
-- match_procedural_memories (orders by a weighted similarity no index can serve), match_persona_knowledge and
-- semantic_search_kg_facts (no vector index on their tables) - the gate holds them, so adding an index later is caught.
--
-- THE FENCE. Each scope is read in a subquery that computes the distance as a column and ends in OFFSET 0; the outer
-- query orders by that column. A subquery with OFFSET/LIMIT is never pulled up into its parent, and a subquery with no
-- ORDER BY of its own has no use for an ordering-only index (ivfflat and hnsw answer ORDER BY <=> and nothing else), so
-- the scope is read through its btree (or a seq scan) and EVERY row in it is ranked. Measured on the largest scope
-- (fault_knowledge, hive b4f7fe63, 7,700 rows): 17 ms exact. A MATERIALIZED CTE - 20261008000001's form for the
-- one-person scope, kept there - took 405 ms here: it copies every 384-dim vector into a tuplestore that spills past
-- work_mem (4MB). The per-scope exact scan is the right trade at these sizes (largest hive 7,700; a per-hive scope past
-- ~50k rows would want a per-hive partial index or iterative index scans instead - noted in the gate).
--
-- semantic_search_kb also gets the one-character repair it needed: its RETURN QUERY selected `embedding <=> q`
-- (double precision) into similarity_score (real), which plpgsql refuses before the first row - so voice-handler.js's
-- document search errored for every member of every hive. ::real, as its three sibling functions already cast.
--
-- Everything else is kept exactly: signatures, argument names and defaults, return columns, volatility, SECURITY
-- INVOKER / DEFINER, SET search_path, the membership self-gates, the own-scope branches of 20261008000001, the
-- similarity thresholds. Same signatures, so CREATE OR REPLACE keeps grants, owners and comments and adds no overload
-- (PGRST203).

BEGIN;

-- ── fault_knowledge: the hive branch fenced; the own branch is 20261008000001's, unchanged ─────────
CREATE OR REPLACE FUNCTION public.search_fault_knowledge(
  query_embedding vector, match_hive_id uuid, match_count integer DEFAULT 5, match_owner uuid DEFAULT NULL)
RETURNS TABLE(id uuid, machine text, problem text, root_cause text, action text, knowledge text,
              worker_name text, similarity double precision)
LANGUAGE sql
STABLE
AS $function$
  SELECT id, machine, problem, root_cause, action, knowledge, worker_name, similarity FROM (
    -- HIVE scope: every row of the hive ranked (OFFSET 0 fence - the vector index cannot serve the ORDER BY).
    SELECT h.id, h.machine, h.problem, h.root_cause, h.action, h.knowledge, h.worker_name, 1 - h.dist AS similarity
      FROM (
        SELECT f.id, f.machine, f.problem, f.root_cause, f.action, f.knowledge, f.worker_name,
               f.embedding <=> query_embedding AS dist
          FROM fault_knowledge f
         WHERE match_hive_id IS NOT NULL AND f.embedding IS NOT NULL AND f.hive_id = match_hive_id
        OFFSET 0
      ) h
     ORDER BY h.dist
     LIMIT match_count
  ) hb
  UNION ALL
  SELECT id, machine, problem, root_cause, action, knowledge, worker_name, similarity FROM (
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
  ) ob
  ORDER BY similarity DESC;
$function$;

-- ── the companion RAG: every hive branch fenced; the own branch unchanged ───────────────────────
CREATE OR REPLACE FUNCTION public.search_all_knowledge(
  query_embedding vector, match_hive_id uuid, match_count integer DEFAULT 3, match_owner uuid DEFAULT NULL)
RETURNS TABLE(source text, summary text, similarity double precision)
LANGUAGE sql
STABLE
AS $function$
  -- Each hive branch ranks EVERY row of the hive: the OFFSET 0 fence keeps the vector index off its ORDER BY.
  SELECT source, summary, similarity FROM (
    SELECT 'fault'::text AS source, f.summary, 1 - f.dist AS similarity FROM (
      SELECT CONCAT('Machine: ', machine, ' | Problem: ', problem,
                    ' | Root cause: ', root_cause, ' | Fix: ', action) AS summary,
             embedding <=> query_embedding AS dist
        FROM fault_knowledge
       WHERE match_hive_id IS NOT NULL AND embedding IS NOT NULL AND hive_id = match_hive_id
      OFFSET 0
    ) f
    ORDER BY f.dist LIMIT match_count
  ) fb

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
    SELECT 'skill'::text AS source, s.summary, 1 - s.dist AS similarity FROM (
      SELECT CONCAT('Worker: ', worker_name, ' | Discipline: ', discipline,
                    ' | Level: ', level::text, ' | Primary: ', primary_skill) AS summary,
             embedding <=> query_embedding AS dist
        FROM skill_knowledge
       WHERE hive_id = match_hive_id AND embedding IS NOT NULL
      OFFSET 0
    ) s
    ORDER BY s.dist LIMIT match_count
  ) sb

  UNION ALL

  SELECT source, summary, similarity FROM (
    SELECT 'pm'::text AS source, p.summary, 1 - p.dist AS similarity FROM (
      SELECT CONCAT('Asset: ', asset_name, ' | Category: ', category,
                    ' | Overdue tasks: ', overdue_count::text, ' | ', health_summary) AS summary,
             embedding <=> query_embedding AS dist
        FROM pm_knowledge
       WHERE hive_id = match_hive_id AND embedding IS NOT NULL
      OFFSET 0
    ) p
    ORDER BY p.dist LIMIT match_count
  ) pb

  UNION ALL

  -- PJ15: project lessons and scope items.
  SELECT source, summary, similarity FROM (
    SELECT 'project'::text AS source, pr.summary, 1 - pr.dist AS similarity FROM (
      SELECT CONCAT('Project: ', COALESCE(project_code, '?'),
                    ' (', COALESCE(project_type, 'project'), ')',
                    ' | Record: ', COALESCE(source_type, 'note'),
                    ' | ', COALESCE(text_chunk, '')) AS summary,
             embedding <=> query_embedding AS dist
        FROM project_knowledge
       WHERE hive_id = match_hive_id AND embedding IS NOT NULL
      OFFSET 0
    ) pr
    ORDER BY pr.dist LIMIT match_count
  ) prb;
$function$;

-- ── the single-table hive searches ───────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.search_skill_knowledge(query_embedding vector, match_hive_id uuid, match_count integer DEFAULT 5)
 RETURNS TABLE(id uuid, worker_name text, discipline text, level integer, primary_skill text, similarity double precision)
 LANGUAGE sql
 STABLE
 SET search_path TO 'pg_catalog', 'public'
AS $function$
  SELECT s.id, s.worker_name, s.discipline, s.level, s.primary_skill, 1 - s.dist AS similarity
    FROM (
      SELECT id, worker_name, discipline, level, primary_skill, embedding <=> query_embedding AS dist
        FROM skill_knowledge
       WHERE hive_id = match_hive_id
         AND embedding IS NOT NULL
      OFFSET 0
    ) s
   ORDER BY s.dist
   LIMIT match_count;
$function$;

CREATE OR REPLACE FUNCTION public.search_pm_knowledge(query_embedding vector, match_hive_id uuid, match_count integer DEFAULT 5)
 RETURNS TABLE(id uuid, asset_name text, category text, overdue_count integer, last_completed timestamp with time zone, health_summary text, similarity double precision)
 LANGUAGE sql
 STABLE
AS $function$
  SELECT p.id, p.asset_name, p.category, p.overdue_count, p.last_completed, p.health_summary, 1 - p.dist AS similarity
    FROM (
      SELECT id, asset_name, category, overdue_count, last_completed, health_summary,
             embedding <=> query_embedding AS dist
        FROM pm_knowledge
       WHERE hive_id = match_hive_id
         AND embedding IS NOT NULL
      OFFSET 0
    ) p
   ORDER BY p.dist
   LIMIT match_count;
$function$;

CREATE OR REPLACE FUNCTION public.search_bom_knowledge(query_embedding vector, match_hive_id uuid, match_count integer DEFAULT 5)
 RETURNS TABLE(id uuid, project_name text, calc_type text, key_spec text, item_count integer, notes text, similarity double precision)
 LANGUAGE sql
 STABLE
AS $function$
  SELECT b.id, b.project_name, b.calc_type, b.key_spec, b.item_count, b.notes, 1 - b.dist AS similarity
    FROM (
      SELECT id, project_name, calc_type, key_spec, item_count, notes, embedding <=> query_embedding AS dist
        FROM bom_knowledge
       WHERE hive_id = match_hive_id
         AND embedding IS NOT NULL
      OFFSET 0
    ) b
   ORDER BY b.dist
   LIMIT match_count;
$function$;

CREATE OR REPLACE FUNCTION public.search_calc_knowledge(query_embedding vector, match_hive_id uuid, match_count integer DEFAULT 5)
 RETURNS TABLE(id uuid, calc_type text, project_ref text, key_inputs jsonb, key_outputs jsonb, notes text, similarity double precision)
 LANGUAGE sql
 STABLE
AS $function$
  SELECT c.id, c.calc_type, c.project_ref, c.key_inputs, c.key_outputs, c.notes, 1 - c.dist AS similarity
    FROM (
      SELECT id, calc_type, project_ref, key_inputs, key_outputs, notes, embedding <=> query_embedding AS dist
        FROM calc_knowledge
       WHERE hive_id = match_hive_id
         AND embedding IS NOT NULL
      OFFSET 0
    ) c
   ORDER BY c.dist
   LIMIT match_count;
$function$;

-- ── one person's voice journal ───────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.search_voice_journal_entries(query_embedding vector, match_auth_uid uuid, match_count integer DEFAULT 5)
 RETURNS TABLE(id uuid, transcript text, reply text, lang text, created_at timestamp with time zone, similarity double precision)
 LANGUAGE sql
 STABLE
 SET search_path TO 'public', 'pg_catalog'
AS $function$
  -- Per-user scope only. hive_id is intentionally NOT part of the filter:
  -- the voice journal is a private per-worker diary, not a hive-scoped
  -- knowledge surface. Isolation is enforced by auth_uid alignment with
  -- the RLS policies on voice_journal_entries. Other vector search RPCs
  -- (search_calc_knowledge, search_bom_knowledge, etc.) scope by hive_id
  -- because their underlying tables are hive-shared; this one is not.
  -- Every entry of the person is ranked (OFFSET 0 fence, 20261008000002).
  SELECT v.id, v.transcript, v.reply, v.lang, v.created_at, 1 - v.dist AS similarity
    FROM (
      SELECT vje.id, vje.transcript, vje.reply, vje.lang, vje.created_at,
             vje.embedding <=> query_embedding AS dist
        FROM public.voice_journal_entries vje
       WHERE vje.auth_uid = match_auth_uid
         AND vje.embedding IS NOT NULL
      OFFSET 0
    ) v
   ORDER BY v.dist
   LIMIT match_count;
$function$;

-- ── the SECURITY DEFINER searches voice-handler.js calls (self-gates unchanged) ─────────────────
CREATE OR REPLACE FUNCTION public.semantic_search_kb(p_hive_id uuid, p_query_embedding vector, p_similarity_threshold real DEFAULT 0.7, p_limit integer DEFAULT 5)
 RETURNS TABLE(chunk_id bigint, doc_id bigint, doc_title text, chunk_text text, similarity_score real)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
begin
  if not public.user_can_access_hive(p_hive_id) then return; end if;
  return query
  select k.id, k.doc_id, k.title, k.text, k.dist::real
    from (
      select kc.id, kc.doc_id, kd.title, kc.text, (kc.embedding <=> p_query_embedding) as dist
        from kb_chunks kc join kb_documents kd on kc.doc_id = kd.id
       where kd.hive_id = p_hive_id and kc.embedding is not null
      offset 0
    ) k
   where k.dist <= (1 - p_similarity_threshold)
   order by k.dist
   limit p_limit;
end;
$function$;

CREATE OR REPLACE FUNCTION public.semantic_search_platform_kg_facts(p_query_embedding vector, p_similarity_threshold real DEFAULT 0.5, p_limit integer DEFAULT 5, p_min_confidence real DEFAULT 0.5)
 RETURNS TABLE(fact_id uuid, subject_ref text, predicate text, object_ref text, claim_text text, confidence numeric, source_type text, source_ref text, similarity_score real)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
BEGIN
  RETURN QUERY
  SELECT
    f.id,
    f.subject_ref,
    f.predicate,
    f.object_ref,
    f.claim_text,
    f.confidence,
    f.source_type,
    f.source_ref,
    f.dist::real AS similarity_score
  FROM (
    SELECT p.id, p.subject_ref, p.predicate, p.object_ref, p.claim_text, p.confidence, p.source_type, p.source_ref,
           (p.embedding <=> p_query_embedding) AS dist
      FROM public.platform_knowledge_graph_facts p
     WHERE p.active     = true
       AND p.embedding  IS NOT NULL
       AND p.confidence >= p_min_confidence
    OFFSET 0
  ) f
  WHERE f.dist <= (1 - p_similarity_threshold)
  ORDER BY f.dist
  LIMIT p_limit;
END;
$function$;

CREATE OR REPLACE FUNCTION public.semantic_search_industry_standards(p_query_embedding vector, p_similarity_threshold real DEFAULT 0.6, p_limit integer DEFAULT 5, p_family text DEFAULT NULL::text)
 RETURNS TABLE(chunk_id bigint, standard_id uuid, standard_code text, standard_title text, family text, section text, chunk_text text, similarity_score real, source_url text)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
BEGIN
  RETURN QUERY
  SELECT
    c.chunk_id,
    c.standard_id,
    c.standard_code,
    c.standard_title,
    c.family,
    c.section,
    c.chunk_text,
    c.dist::real AS similarity_score,
    c.source_url
  FROM (
    SELECT
      isc.id              AS chunk_id,
      s.id                AS standard_id,
      s.standard_code,
      s.title             AS standard_title,
      s.family,
      isc.section,
      isc.text            AS chunk_text,
      (isc.embedding <=> p_query_embedding) AS dist,
      s.source_url
    FROM public.industry_standards_chunks isc
    JOIN public.industry_standards        s ON isc.standard_id = s.id
    WHERE isc.embedding IS NOT NULL
      AND (p_family IS NULL OR s.family = p_family)
    OFFSET 0
  ) c
  WHERE c.dist <= (1 - p_similarity_threshold)
  ORDER BY c.dist
  LIMIT p_limit;
END;
$function$;

-- ── verification: refuse to commit a half-applied change ────────────────────────────────────────
DO $verify$
DECLARE
  v_fns text[] := ARRAY['search_fault_knowledge', 'search_all_knowledge', 'search_skill_knowledge',
                        'search_pm_knowledge', 'search_bom_knowledge', 'search_calc_knowledge',
                        'search_voice_journal_entries', 'semantic_search_kb', 'semantic_search_platform_kg_facts',
                        'semantic_search_industry_standards'];
  v_fn text;
  v_n int;
BEGIN
  FOREACH v_fn IN ARRAY v_fns LOOP
    SELECT count(*) INTO v_n FROM pg_proc p WHERE p.pronamespace = 'public'::regnamespace AND p.proname = v_fn;
    IF v_n <> 1 THEN RAISE EXCEPTION '% has % definitions - an overload makes PostgREST answer PGRST203', v_fn, v_n; END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_proc p WHERE p.pronamespace = 'public'::regnamespace AND p.proname = v_fn
                     AND p.prosrc ~* 'offset 0') THEN
      RAISE EXCEPTION '% lost its scope fence (OFFSET 0)', v_fn;
    END IF;
  END LOOP;
  IF EXISTS (SELECT 1 FROM pg_proc p WHERE p.pronamespace = 'public'::regnamespace AND p.prosecdef
               AND p.proname IN ('search_fault_knowledge', 'search_all_knowledge', 'search_skill_knowledge',
                                 'search_pm_knowledge', 'search_bom_knowledge', 'search_calc_knowledge',
                                 'search_voice_journal_entries')) THEN
    RAISE EXCEPTION 'the invoker searches must stay SECURITY INVOKER';
  END IF;
  IF (SELECT count(*) FROM pg_proc p WHERE p.pronamespace = 'public'::regnamespace AND p.prosecdef
        AND p.proname IN ('semantic_search_kb', 'semantic_search_platform_kg_facts',
                          'semantic_search_industry_standards')) <> 3 THEN
    RAISE EXCEPTION 'the semantic_search_* functions must stay SECURITY DEFINER';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_proc p WHERE p.proname = 'semantic_search_kb'
                   AND p.prosrc LIKE '%user_can_access_hive(p_hive_id)%') THEN
    RAISE EXCEPTION 'semantic_search_kb lost its membership self-gate';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_proc p WHERE p.proname IN ('search_fault_knowledge', 'search_all_knowledge')
               AND pg_get_functiondef(p.oid) NOT LIKE '%AS MATERIALIZED%') THEN
    RAISE EXCEPTION 'a knowledge search lost its exact own-scope branch (20261008000001)';
  END IF;
  IF NOT has_function_privilege('authenticated', 'public.search_fault_knowledge(vector, uuid, integer, uuid)', 'EXECUTE')
     OR NOT has_function_privilege('service_role', 'public.search_all_knowledge(vector, uuid, integer, uuid)', 'EXECUTE')
     OR NOT has_function_privilege('authenticated', 'public.semantic_search_kb(uuid, vector, real, integer)', 'EXECUTE')
     OR NOT has_function_privilege('service_role', 'public.search_voice_journal_entries(vector, uuid, integer)', 'EXECUTE')
     OR has_function_privilege('authenticated', 'public.search_voice_journal_entries(vector, uuid, integer)', 'EXECUTE') THEN
    RAISE EXCEPTION 'a search''s EXECUTE grants changed';
  END IF;
END
$verify$;

COMMIT;
