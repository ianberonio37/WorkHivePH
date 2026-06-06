-- ============================================================================
-- 20260607000004  Lock backend-only SECURITY DEFINER RPCs to service_role
-- ============================================================================
-- Companion to ...0003. These 3 SECURITY DEFINER, hive-scoped functions are
-- NOT called from the browser -- their only callers run with the service key:
--   get_oee_by_machine        -> analytics-orchestrator edge fn (SERVICE_ROLE_KEY)
--   match_procedural_memories -> ai-gateway / _shared (adminClient, service key)
--   increment_community_xp    -> PERFORM inside SECURITY DEFINER community XP
--                                triggers (execute as owner -> unaffected by GRANT)
--
-- Because they are SECURITY DEFINER (bypass RLS) AND were granted to
-- anon/authenticated (increment_community_xp defaulted to PUBLIC), any user
-- could call them directly via PostgREST with a foreign p_hive_id to read
-- another hive's OEE / AI memories, or inflate any worker's XP in any hive.
-- The correct boundary for a backend-only fn is the GRANT, not an in-function
-- auth.uid() check (which would always fail under the service role). Revoking
-- from anon/authenticated/PUBLIC closes the vector while keeping every caller.
--
-- Skills: security, multitenant-engineer, data-engineer. Deploy PENDING.
-- ============================================================================

BEGIN;

REVOKE EXECUTE ON FUNCTION public.get_oee_by_machine(uuid, int) FROM PUBLIC, anon, authenticated;
GRANT  EXECUTE ON FUNCTION public.get_oee_by_machine(uuid, int) TO service_role;

REVOKE EXECUTE ON FUNCTION public.match_procedural_memories(vector, uuid, text, int, real) FROM PUBLIC, anon, authenticated;
GRANT  EXECUTE ON FUNCTION public.match_procedural_memories(vector, uuid, text, int, real) TO service_role;

REVOKE EXECUTE ON FUNCTION public.increment_community_xp(text, uuid, integer) FROM PUBLIC, anon, authenticated;
GRANT  EXECUTE ON FUNCTION public.increment_community_xp(text, uuid, integer) TO service_role;

COMMIT;
