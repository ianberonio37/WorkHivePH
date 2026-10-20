-- BRH-P (2026-10-21): every public table the API serves has row-level security on - and what a stranger can read is a
-- policy someone wrote, not a switch left off.
--
-- Supabase's critical email of 2026-10-20 (rls_disabled_in_public, issues as of 17 Oct): 13 tables in production served
-- by the API with RLS off, plus ai_global_budget (RLS off, no API grant, so the advisor passed it). None could be written
-- through the API - each granted anon and authenticated SELECT only - but anyone holding the site's public key could read
-- every row.
--
-- On 2026-08-04 eleven of them were DECLARED public on purpose (tools/validate_public_read_surface.py), each with a
-- reason, and for reference data that decision stands: it becomes an explicit SELECT policy, so nothing a page reads
-- changes. Read again against their columns, five declarations were wrong, and no page or shared script reads any of the
-- six below - only edge functions through the service role (which RLS does not bind) and SECURITY DEFINER functions:
--   ai_rate_limits    holds hive_id - which hives call the AI and how much (its declaration said "no identity column")
--   terminology_gaps  holds reported_by - a person's name
--   tts_cache         holds text_content - what was spoken; the Python API caches speech in local files, the table is unused
--   embedding_cache   hashes of what people asked the AI, with their embeddings
--   persona_knowledge the AI personas' internal prompt material; match_persona_knowledge is called by the ai-gateway's
--                     service-role client
--   ai_global_budget  the platform's AI throttle; consume_ai_global_budget is SECURITY DEFINER
-- They get RLS with no policy (anon and authenticated refused outright) and lose every privilege those two roles held.
--
-- Readers measured 2026-10-21 (pages, shared scripts, edge functions and their clients, SQL functions):
--   multilingual_terms, cross_hive_alerts  voice-handler.js, on pages a visitor can open
--   ph_intelligence_reports                ph-intelligence.html, which renders signed out
--   equipment_reading_templates            asset-hub.html, logbook.html
--   network_benchmarks                     hive.html (get_hive_board_dashboard is SECURITY DEFINER)
--   service_slo_targets, best_practices, avatar_animations  declared public reference data; no reader today
--
-- Every table also grants the service role explicitly: from 2026-10-30 Supabase stops granting new tables automatically,
-- and a replay of this schema would otherwise leave the edge functions without them (BRH-X).
-- Idempotent: RLS enabling is a no-op when on; a policy is created only when absent.

do $$
declare
  t text;
begin
  foreach t in array array['avatar_animations', 'best_practices', 'cross_hive_alerts', 'equipment_reading_templates',
                           'multilingual_terms', 'network_benchmarks', 'ph_intelligence_reports', 'service_slo_targets']
  loop
    if to_regclass('public.' || t) is null then
      continue;
    end if;
    execute format('alter table public.%I enable row level security', t);
    if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = t
                   and policyname = t || '_public_read') then
      execute format('create policy %I on public.%I for select to anon, authenticated using (true)', t || '_public_read', t);
    end if;
    execute format('grant select on public.%I to anon, authenticated', t);
    execute format('grant select, insert, update, delete on public.%I to service_role', t);
  end loop;

  foreach t in array array['ai_global_budget', 'ai_rate_limits', 'embedding_cache', 'persona_knowledge', 'terminology_gaps',
                           'tts_cache']
  loop
    if to_regclass('public.' || t) is null then
      continue;
    end if;
    execute format('alter table public.%I enable row level security', t);
    execute format('revoke all on public.%I from anon, authenticated', t);
    execute format('grant select, insert, update, delete on public.%I to service_role', t);
  end loop;
end
$$;
