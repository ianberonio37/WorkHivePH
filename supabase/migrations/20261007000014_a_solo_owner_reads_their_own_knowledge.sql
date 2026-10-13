-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- A solo owner reads their OWN knowledge rows (and only theirs)
-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- Found 2026-10-07 from source, while making photo defect capture work for solo owners: a signed-in person
-- with no hive saves a logbook entry, trg_embed_outbox_logbook queues it, and the outbox drain writes that
-- entry's fault_knowledge row with hive_id NULL. Twelve such rows exist. NOBODY could read any of them:
--
--   fault_knowledge_read           auth.uid() IS NOT NULL AND hive_id IN (the caller's active hives)
--   search_fault_knowledge         WHERE hive_id = match_hive_id
--   search_all_knowledge (fault)   WHERE hive_id = match_hive_id
--   v_knowledge_truth              security_invoker, so it inherits the policy above
--
-- NULL is never IN a list and never = anything, so the "Past repairs on this machine" panel on logbook.html
-- was ALWAYS empty for a solo owner, however many repairs they had logged on that machine. Their knowledge
-- was written and could never be read back - the write-only-index class, on the lane a new audience travels.
--
-- Four changes, all additive for hive rows:
--
--   1. OWNER BINDING FROM THE SOURCE ENTRY. A hive-less row can only be read by its owner if it says who that
--      is, and 6 of the 12 did not: neither writer of fault_knowledge (tools/drain_embedding_outbox.py's direct
--      upsert, embed-entry's PostgREST upsert) stamped auth_uid. 20261004000007 gave this table no binding
--      trigger because auth.uid() is NULL on every path that writes it - true, and beside the point: the owner
--      is not the CALLER here, it is the AUTHOR of the logbook entry the row is a copy of, and that entry
--      carries auth_uid. So a BEFORE trigger copies logbook.auth_uid onto the row whenever logbook_id names an
--      entry that has one. It OVERRIDES a supplied value on purpose: with an owner policy keyed on this column,
--      a writer that stamped someone else's uid would hand them the row. Deriving it from the entry is the only
--      source that cannot be wrong about whose repair it was. Plain SECURITY INVOKER: the writers are
--      service_role / postgres (both see every logbook row), and member INSERT/UPDATE is locked to false.
--   2. THE POLICY gains the platform's canonical hive-less branch - the SAME shape logbook_read, pm_assets_read,
--      pm_completions_read and engineering_calcs_read already carry:
--         (hive_id IS NOT NULL AND hive_id IN my active hives) OR (hive_id IS NULL AND auth_uid = auth.uid())
--      The hive branch is unchanged in meaning (hive_id IN (...) was never true for a NULL hive_id). Nothing is
--      loosened for hive rows; a hive member gains no view of anyone's hive-less rows.
--   3. THE SEARCHES take an "own" scope. match_hive_id NULL now means "the caller's own hive-less rows" - the
--      precedent get_pm_compliance_smrp set for the solo lane (p_hive_id IS NULL = the caller's own scope). The
--      owner is auth.uid(); a new optional match_owner is honoured ONLY when the caller is service_role or
--      postgres (an edge function that already resolved the person, e.g. ai-gateway's solo branch), so a
--      signed-in caller can never name somebody else and anon names nobody. The old 3-argument signature is
--      DROPPED, not overloaded: two candidates for the same named-argument call is PGRST203, which kills the
--      endpoint. Every existing caller passes (query_embedding, match_hive_id, match_count), which still binds.
--   4. v_knowledge_truth exposes auth_uid (appended last), the identity its fault branch already binds - the
--      same move 20261004000001 made for v_logbook_truth, so a reader can ask "mine" by uid. The branches whose
--      base tables carry no owner column (skill/pm/bom/calc/project) answer NULL, which names nobody.
--
-- ★security_invoker IS RESTATED. a replace of a view discards its reloptions, and a view that loses
-- security_invoker reads as its OWNER - the mistake that once opened anon to 437 rows here. The verification
-- block below FAILS the migration if it comes back without it.

BEGIN;

-- ── 1. owner binding from the source entry ──────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.bind_fault_knowledge_owner_from_entry()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $fn$
DECLARE v_uid uuid;
BEGIN
  IF NEW.logbook_id IS NOT NULL THEN
    SELECT l.auth_uid INTO v_uid FROM public.logbook l WHERE l.id = NEW.logbook_id;
    -- The entry's author is the row's owner. An entry with no bound author (a legacy service-role write)
    -- leaves whatever the writer supplied: a hive-less row with no owner is readable by NOBODY, which fails
    -- closed, never open.
    IF v_uid IS NOT NULL THEN NEW.auth_uid := v_uid; END IF;
  END IF;
  RETURN NEW;
END
$fn$;

COMMENT ON FUNCTION public.bind_fault_knowledge_owner_from_entry() IS
  'Copies logbook.auth_uid onto the fault_knowledge row derived from that entry (BEFORE INSERT OR UPDATE). '
  'The knowledge row''s owner is the AUTHOR of the entry it copies, not the caller - every writer of this '
  'table is service-role, where auth.uid() is NULL. fault_knowledge_read''s hive-less branch keys on this column.';

REVOKE ALL ON FUNCTION public.bind_fault_knowledge_owner_from_entry() FROM PUBLIC, anon, authenticated;

DROP TRIGGER IF EXISTS tg_bind_owner_fault_knowledge ON public.fault_knowledge;
CREATE TRIGGER tg_bind_owner_fault_knowledge
  BEFORE INSERT OR UPDATE ON public.fault_knowledge
  FOR EACH ROW EXECUTE FUNCTION public.bind_fault_knowledge_owner_from_entry();

-- Backfill: every row whose entry names an author but the row does not agree. Measured before this
-- migration: 6 rows, all hive-less (Miguel Santos's NDS 8214 history, 2026-09-02), every hive row already
-- bound by 20261004000007. bind_worker_name_from_hive returns early when auth.uid() IS NULL, and the daily
-- row cap fires on INSERT only, so the UPDATE touches nothing but auth_uid.
UPDATE public.fault_knowledge f
   SET auth_uid = l.auth_uid
  FROM public.logbook l
 WHERE l.id = f.logbook_id
   AND l.auth_uid IS NOT NULL
   AND f.auth_uid IS DISTINCT FROM l.auth_uid;

-- ── 2. the policy: the canonical hive-less owner branch ─────────────────────────────────────────
ALTER POLICY fault_knowledge_read ON public.fault_knowledge
  USING (
    (auth.uid() IS NOT NULL)
    AND (
      ((hive_id IS NOT NULL) AND (hive_id IN (SELECT hm.hive_id FROM public.hive_members hm
                                               WHERE hm.auth_uid = auth.uid() AND hm.status = 'active')))
      OR ((hive_id IS NULL) AND (auth_uid = auth.uid()))
    )
  );

-- ── 3. the searches: match_hive_id NULL = the caller's own hive-less rows ───────────────────────
DROP FUNCTION IF EXISTS public.search_fault_knowledge(vector, uuid, integer);
CREATE FUNCTION public.search_fault_knowledge(
  query_embedding vector, match_hive_id uuid, match_count integer DEFAULT 5, match_owner uuid DEFAULT NULL)
RETURNS TABLE(id uuid, machine text, problem text, root_cause text, action text, knowledge text,
              worker_name text, similarity double precision)
LANGUAGE sql
STABLE
AS $function$
  SELECT
    id, machine, problem, root_cause, action, knowledge, worker_name,
    1 - (embedding <=> query_embedding) AS similarity
  FROM fault_knowledge
  WHERE embedding IS NOT NULL
    AND (
      hive_id = match_hive_id
      -- OWN scope: a hive-less row belongs to the person who wrote its entry. The owner is the CALLER
      -- (auth.uid()); match_owner is honoured only for a server role that has already resolved the person.
      OR (match_hive_id IS NULL AND hive_id IS NULL
          AND auth_uid = COALESCE(auth.uid(),
                                  CASE WHEN current_user IN ('service_role', 'postgres') THEN match_owner END))
    )
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
$function$;

COMMENT ON FUNCTION public.search_fault_knowledge(vector, uuid, integer, uuid) IS
  'Semantic search over fault_knowledge. match_hive_id = a hive: that hive''s rows (RLS still applies to the '
  'caller). match_hive_id NULL: the caller''s OWN hive-less rows (auth.uid()); match_owner is honoured only '
  'for service_role/postgres callers that already resolved the person, never for a signed-in or anon caller.';

DROP FUNCTION IF EXISTS public.search_all_knowledge(vector, uuid, integer);
CREATE FUNCTION public.search_all_knowledge(
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
    WHERE embedding IS NOT NULL
      AND (
        hive_id = match_hive_id
        -- OWN scope (hive-less person): only fault_knowledge carries an owner column, so it is the only
        -- branch that answers it; the branches below keep hive_id = match_hive_id, which a NULL never meets.
        OR (match_hive_id IS NULL AND hive_id IS NULL
            AND auth_uid = COALESCE(auth.uid(),
                                    CASE WHEN current_user IN ('service_role', 'postgres') THEN match_owner END))
      )
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

COMMENT ON FUNCTION public.search_all_knowledge(vector, uuid, integer, uuid) IS
  'Companion RAG over fault/skill/pm/project knowledge. match_hive_id NULL: the caller''s OWN hive-less fault '
  'rows (only fault_knowledge carries an owner). match_owner is honoured only for service_role/postgres.';

-- The grants the 3-argument versions held (PUBLIC + the three API roles). Both stay SECURITY INVOKER, so RLS
-- is evaluated as the caller whatever the arguments say.
GRANT EXECUTE ON FUNCTION public.search_fault_knowledge(vector, uuid, integer, uuid) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.search_all_knowledge(vector, uuid, integer, uuid)   TO anon, authenticated, service_role;

-- ── 4. v_knowledge_truth exposes the identity its fault branch binds ────────────────────────────
CREATE OR REPLACE VIEW public.v_knowledge_truth
WITH (security_invoker = true) AS
 SELECT 'fault'::text AS source,
    fault_knowledge.id,
    fault_knowledge.hive_id,
    COALESCE(fault_knowledge.knowledge, fault_knowledge.problem, fault_knowledge.action, ''::text) AS content,
    fault_knowledge.embedding,
    fault_knowledge.created_at,
    fault_knowledge.auth_uid
   FROM fault_knowledge
UNION ALL
 SELECT 'skill'::text AS source,
    skill_knowledge.id,
    skill_knowledge.hive_id,
    COALESCE(skill_knowledge.primary_skill, skill_knowledge.discipline, ''::text) AS content,
    skill_knowledge.embedding,
    COALESCE(skill_knowledge.updated_at, now()) AS created_at,
    NULL::uuid AS auth_uid
   FROM skill_knowledge
UNION ALL
 SELECT 'pm'::text AS source,
    pm_knowledge.id,
    pm_knowledge.hive_id,
    COALESCE(pm_knowledge.health_summary, pm_knowledge.asset_name, ''::text) AS content,
    pm_knowledge.embedding,
    COALESCE(pm_knowledge.updated_at, now()) AS created_at,
    NULL::uuid AS auth_uid
   FROM pm_knowledge
UNION ALL
 SELECT 'bom'::text AS source,
    bom_knowledge.id,
    bom_knowledge.hive_id,
    COALESCE(bom_knowledge.notes, bom_knowledge.project_name, ''::text) AS content,
    bom_knowledge.embedding,
    bom_knowledge.created_at,
    NULL::uuid AS auth_uid
   FROM bom_knowledge
UNION ALL
 SELECT 'calc'::text AS source,
    calc_knowledge.id,
    calc_knowledge.hive_id,
    COALESCE(calc_knowledge.notes, calc_knowledge.calc_type, ''::text) AS content,
    calc_knowledge.embedding,
    calc_knowledge.created_at,
    NULL::uuid AS auth_uid
   FROM calc_knowledge
UNION ALL
 SELECT 'project'::text AS source,
    project_knowledge.id,
    project_knowledge.hive_id,
    project_knowledge.text_chunk AS content,
    project_knowledge.embedding,
    project_knowledge.created_at,
    NULL::uuid AS auth_uid
   FROM project_knowledge;

-- ── verification: refuse to commit a half-applied change ────────────────────────────────────────
DO $verify$
DECLARE v_qual text; v_opts text[]; v_n int;
BEGIN
  SELECT pg_get_expr(p.polqual, p.polrelid) INTO v_qual
    FROM pg_policy p WHERE p.polrelid = 'public.fault_knowledge'::regclass AND p.polname = 'fault_knowledge_read';
  IF v_qual IS NULL OR v_qual NOT LIKE '%hive_id IS NULL%' OR v_qual NOT LIKE '%auth_uid = auth.uid()%' THEN
    RAISE EXCEPTION 'fault_knowledge_read lacks the hive-less owner branch: %', v_qual;
  END IF;
  IF (SELECT count(*) FROM pg_policy p WHERE p.polrelid = 'public.fault_knowledge'::regclass
        AND p.polcmd IN ('r', '*') AND p.polpermissive) <> 1 THEN
    RAISE EXCEPTION 'fault_knowledge must have exactly ONE permissive read policy';
  END IF;

  SELECT c.reloptions INTO v_opts FROM pg_class c WHERE c.oid = 'public.v_knowledge_truth'::regclass;
  IF v_opts IS NULL OR NOT (v_opts && ARRAY['security_invoker=true', 'security_invoker=on']) THEN
    RAISE EXCEPTION 'v_knowledge_truth lost security_invoker: %', v_opts;
  END IF;
  IF NOT has_table_privilege('authenticated', 'public.v_knowledge_truth', 'SELECT') THEN
    RAISE EXCEPTION 'v_knowledge_truth lost its authenticated SELECT grant';
  END IF;

  SELECT count(*) INTO v_n FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
   WHERE n.nspname = 'public' AND p.proname IN ('search_fault_knowledge', 'search_all_knowledge');
  IF v_n <> 2 THEN RAISE EXCEPTION 'expected exactly one search_fault_knowledge + one search_all_knowledge, found %', v_n; END IF;
  IF EXISTS (SELECT 1 FROM pg_proc p WHERE p.proname IN ('search_fault_knowledge', 'search_all_knowledge') AND p.prosecdef) THEN
    RAISE EXCEPTION 'the knowledge searches must stay SECURITY INVOKER';
  END IF;

  SELECT count(*) INTO v_n FROM public.fault_knowledge f JOIN public.logbook l ON l.id = f.logbook_id
   WHERE f.hive_id IS NULL AND l.auth_uid IS NOT NULL AND f.auth_uid IS DISTINCT FROM l.auth_uid;
  IF v_n > 0 THEN RAISE EXCEPTION '% hive-less knowledge row(s) still disagree with their entry''s author', v_n; END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_trigger t WHERE t.tgrelid = 'public.fault_knowledge'::regclass
                   AND t.tgname = 'tg_bind_owner_fault_knowledge' AND t.tgenabled = 'O') THEN
    RAISE EXCEPTION 'tg_bind_owner_fault_knowledge is missing or disabled';
  END IF;
END
$verify$;

COMMIT;
