-- Arc R (Security / Adversarial) R0 — RE-GATE match_procedural_memories after a
-- FEATURE-MIGRATION REGRESSION of a security lock (OWASP LLM08 / A01 cross-tenant read IDOR).
-- ─────────────────────────────────────────────────────────────────────────────
-- THE REGRESSION (root cause, measured):
--   • 20260620000016_ai_retrieval_isolation.sql classified match_procedural_memories as
--     EDGE-ONLY (ai-gateway calls it via the service-role admin client with a SERVER-resolved
--     hive) and REVOKED anon/authenticated, granting service_role only. Correct lockdown.
--   • 20260624000002_episodic_supersedes.sql (C2.1 feature, 4 days later) did a
--     CREATE OR REPLACE to add the supersede down-rank penalty and ended with
--         GRANT EXECUTE ... TO anon, authenticated, service_role;
--     silently RE-GRANTING the two client roles the security arc had revoked. Its comment
--     claimed "grants unchanged" but it copied the PRE-June-20 grant — reverting the lock.
--   Net effect in the live DB: a user-callable SECURITY DEFINER function that filters by a
--   CLIENT-supplied p_hive_id with NO membership check → any authenticated user (or anon)
--   could pass another hive's id (or NULL = ALL hives) + an embedding and retrieve that
--   hive's agent procedural memories cross-tenant. Caught by validate_ai_retrieval_isolation
--   (P-lens dropped 100% → 66.7% on the Arc-R board).
--
-- THE FIX (property-level, durable — not just re-revoke):
--   Because this lock already regressed once via a re-grant, a revoke-only fix leaves the
--   same footgun (the next feature CREATE OR REPLACE can re-grant it again). So we fix the
--   PROPERTY: convert to plpgsql and add the canonical user_can_access_hive() early-return
--   self-gate (same idiom as semantic_search_kb) — cross-tenant reads now return EMPTY
--   REGARDLESS of grants. service_role callers pass the gate via the JWT role check, so the
--   edge path is unaffected. We ALSO restore least-privilege (revoke anon/authenticated) so
--   an edge-only fn is not client-callable at all. Belt AND suspenders.
--
--   The C2.1 supersede penalty (×0.4 on superseded_by IS NOT NULL) is preserved BYTE-FOR-BYTE
--   in the retrieval SELECT — this migration changes ONLY the tenancy boundary, not ranking.
--
-- Forward migration only (immutability doctrine — the matcher 20260531000001, the isolation
-- gate 20260620000016, and the C2.1 feature 20260624000002 are NOT edited).

BEGIN;

CREATE OR REPLACE FUNCTION public.match_procedural_memories(
  p_query_embedding  vector,
  p_hive_id          uuid,
  p_worker_name      text DEFAULT NULL,
  p_match_count      int  DEFAULT 5,
  p_min_similarity   real DEFAULT 0.55
)
RETURNS TABLE (
  id          uuid,
  content     text,
  importance  real,
  use_count   integer,
  similarity  real
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
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
    AND (p_hive_id     IS NULL OR m.hive_id     = p_hive_id)
    AND (p_worker_name IS NULL OR m.worker_name = p_worker_name)
    AND ((1 - (m.embedding <=> p_query_embedding))
          * CASE WHEN m.superseded_by IS NOT NULL THEN 0.4 ELSE 1 END) >= p_min_similarity
  ORDER BY similarity DESC
  LIMIT GREATEST(1, LEAST(p_match_count, 20));
END;
$function$;

COMMENT ON FUNCTION public.match_procedural_memories(vector, uuid, text, int, real) IS
  'Turn 5 + C2.1 + Arc-R R0 - semantic retrieval over the procedural skill library '
  '(agent_episodic_memory WHERE memory_type=procedural). Hive-scoped via a user_can_access_hive() '
  'self-gate (edge/service_role or member of p_hive_id; cross-tenant returns empty). Cosine distance, '
  'min-similarity gated, C2.1 supersede penalty (x0.4 on superseded_by IS NOT NULL). '
  'EDGE-ONLY: _shared/skill-library.ts matchProcedures() + _shared/episodic-memory.ts dedup call it '
  'via the service-role admin client. Re-gated after 20260624000002 re-granted anon/authenticated.';

-- Restore least-privilege: edge-only fn, clients must not call it. (Idempotent.)
REVOKE EXECUTE ON FUNCTION public.match_procedural_memories(vector, uuid, text, int, real)
  FROM public, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.match_procedural_memories(vector, uuid, text, int, real)
  TO service_role;

COMMIT;
