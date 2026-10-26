-- Grants follow the callers (2026-10-27).
--
-- 1. Two searches no visitor calls any more. semantic_search_industry_standards and semantic_search_platform_kg_facts
--    were signed-out entry points because voice-handler.js called them from the browser to build a prompt no server
--    read (BRH-AO). That browser code is gone; the only caller is ai-gateway's loadHiveKnowledge, which runs only for a
--    signed-in person and uses that person's own client. A SECURITY DEFINER function a visitor can still execute is a
--    door with no reason to be open, so anon loses EXECUTE; authenticated and service_role keep it, written here so a
--    replay grants exactly this. Every overload is closed by name in a loop over p.oid::regprocedure: Supabase grants
--    anon EXECUTE explicitly, so "from public" alone never reaches it, and a signature that differs between
--    environments must not leave one open (or fail the push).
-- 2. v_scheduled_call_health (20261026000010) revoked anon/authenticated and granted grafana_reader, and service_role
--    read it through the default privileges alone - which Supabase stops applying to new objects on 2026-10-30. The
--    grant it holds is written down, so a replay gives it the same access.

BEGIN;

DO $$
DECLARE f regprocedure;
BEGIN
  FOR f IN SELECT p.oid::regprocedure FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'public'
              AND p.proname IN ('semantic_search_industry_standards', 'semantic_search_platform_kg_facts')
  LOOP
    EXECUTE format('REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC, anon', f);
    EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO authenticated, service_role', f);
  END LOOP;
END $$;

GRANT SELECT ON public.v_scheduled_call_health TO service_role;

COMMIT;
