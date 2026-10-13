-- 20261013000005 - A PROCEDURAL MATCH WITH NO HIVE READS SOLO PROCEDURES, NOT EVERY HIVE'S (2026-10-13).
--
-- match_procedural_memories filtered `(p_hive_id IS NULL OR m.hive_id = p_hive_id)`: a NULL hive removed the hive
-- filter, so a solo caller's skill-library match - and persistEpisodic's near-duplicate check for a solo write, which
-- then bumps the match's use_count and importance - reached procedural memories in EVERY hive under the same worker
-- name. The function is service-role only (EXECUTE revoked from anon/authenticated in 20260620000016) and the gateway's
-- solo name is the caller's own e-mail, so the reach was narrow; but it is the same "no hive means no filter" shape that
-- let agent-memory-store and recallEpisodic read across hives (fixed the same day in the functions). A hive-less
-- procedural memory is written with hive_id NULL; a hive-less match now reads exactly those.
--
-- Same signature, same SECURITY DEFINER self-gate (user_can_access_hive), same supersede penalty; one predicate
-- changes. The self-tests that call it with a NULL hive (companion_dedup, companion_supersedes) seed hive-less rows,
-- so they still match. CREATE OR REPLACE keeps the privileges; the lock is restated below so this file is complete.

CREATE OR REPLACE FUNCTION public.match_procedural_memories(
  p_query_embedding vector,
  p_hive_id uuid,
  p_worker_name text DEFAULT NULL::text,
  p_match_count integer DEFAULT 5,
  p_min_similarity real DEFAULT 0.55
)
 RETURNS TABLE(id uuid, content text, importance real, use_count integer, similarity real)
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
BEGIN
  -- Tenant self-gate: the caller must be the trusted edge/cron service_role OR a member of
  -- p_hive_id. A cross-hive (or NULL-hive) client call returns zero rows instead of leaking.
  IF NOT public.user_can_access_hive(p_hive_id) THEN
    RETURN;
  END IF;

  RETURN QUERY
  SELECT
    m.id,
    m.content,
    m.importance,
    m.use_count,
    ((1 - (m.embedding <=> p_query_embedding))
      * CASE WHEN m.superseded_by IS NOT NULL THEN 0.4 ELSE 1 END)::real AS similarity
  FROM public.agent_episodic_memory m
  WHERE m.memory_type = 'procedural'
    AND m.embedding IS NOT NULL
    -- no hive means SOLO (hive_id IS NULL), never every hive (2026-10-13)
    AND (CASE WHEN p_hive_id IS NULL THEN m.hive_id IS NULL ELSE m.hive_id = p_hive_id END)
    AND (p_worker_name IS NULL OR m.worker_name = p_worker_name)
    AND ((1 - (m.embedding <=> p_query_embedding))
          * CASE WHEN m.superseded_by IS NOT NULL THEN 0.4 ELSE 1 END) >= p_min_similarity
  ORDER BY similarity DESC
  LIMIT GREATEST(1, LEAST(p_match_count, 20));
END;
$function$;

REVOKE EXECUTE ON FUNCTION public.match_procedural_memories(vector, uuid, text, integer, real) FROM public, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.match_procedural_memories(vector, uuid, text, integer, real) TO service_role;
