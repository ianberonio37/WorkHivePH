-- ============================================================
-- Security hardening pass (2026-05-18)
-- ============================================================
-- Closes residual findings from the L-1.5 skill-rule miner:
--   - 1 SECURITY DEFINER function still missing `SET search_path`
--   - 3 RLS-enabled tables that never received explicit GRANT statements
--
-- Most other findings the miner surfaced were already retroactively
-- fixed in 20260511000002_db_hygiene_batch.sql (functions recreated
-- with `SET search_path = pg_catalog, public`) and 20260430000001
-- + 20260511000001 (GRANTs on community_* and agent_memory). This
-- migration completes the cleanup for the genuinely outstanding rows.
-- ============================================================

-- ── Part A: SECURITY DEFINER search_path lockdown ──────────────────────────
-- search_skill_knowledge was declared in the baseline migration with
-- SECURITY DEFINER but no SET search_path. ALTER FUNCTION attaches the
-- lockdown without recreating the function body.
ALTER FUNCTION public.search_skill_knowledge(query_embedding public.vector, match_hive_id uuid, match_count integer)
  SET search_path = pg_catalog, public;


-- ── Part B: GRANT on RLS-enabled tables ────────────────────────────────────
-- Three tables had ENABLE ROW LEVEL SECURITY applied in their creation
-- migrations but no companion GRANT block. Per Supabase rule, ENABLE RLS
-- without GRANT returns 401 on every query regardless of what the
-- policies allow. Granting SELECT/INSERT/UPDATE/DELETE to anon +
-- authenticated lets RLS policies be the sole enforcement boundary.
GRANT SELECT, INSERT, UPDATE, DELETE ON public.dialog_state       TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.anomaly_alerts     TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.fallback_model_faq TO anon, authenticated;


-- ── Documentation ──────────────────────────────────────────────────────────
COMMENT ON FUNCTION public.search_skill_knowledge(public.vector, uuid, integer) IS
  'Vector-similarity search over worker skills. SECURITY DEFINER with SET search_path lockdown
   (added 2026-05-18 to close skill-rule miner finding).';

COMMENT ON TABLE public.dialog_state IS
  'Phase 4 dialog turn state. RLS-protected; GRANTed to anon/authenticated 2026-05-18.';

COMMENT ON TABLE public.anomaly_alerts IS
  'Phase 5 anomaly alert queue. RLS-protected; GRANTed to anon/authenticated 2026-05-18.';

COMMENT ON TABLE public.fallback_model_faq IS
  'Phase 6 offline-mode FAQ fallback. RLS-protected; GRANTed to anon/authenticated 2026-05-18.';
