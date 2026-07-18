-- 20260713000001_close_xhive_read_leak_truth_views.sql
--
-- CROSS-TENANT READ LEAK (HIGH, platform-wide isolation failure) — bug-hunt 2026-07-13, hive.html P5.
--
-- Three hive-scoped truth views were created WITHOUT `security_invoker`, so they execute with the
-- (superuser) view-owner's privileges and BYPASS their base table's row-level security. Any
-- authenticated user could therefore read ANY OTHER hive's data simply by querying the view with a
-- foreign hive_id — the client-side `.eq('hive_id', HIVE_ID)` filter is the ONLY thing that kept
-- tenants apart, and it is trivially bypassed at the PostgREST layer.
--
-- LIVE-CONFIRMED (rolled-back two-tenant probe): signed in as leandromarquez (supervisor of Baguio
-- 636cf7e8, NOT a member of Lucena c9def338), a plain `db.from('v_logbook_truth').eq('hive_id', <Lucena>)`
-- returned 1105 rows of real Lucena logbook content (TT-001 "Lubricate per OEM spec" by Pablo Aguilar,
-- TT-002 "Reading -40C (sensor open)", ...). error:null. Baseline read as a non-member should have been 0.
--
-- The other 30+ v_*_truth views already carry security_invoker=on; these THREE were siblings-skipped by
-- the sweep that set the rest. FIX = enable security_invoker so each view enforces the base table's
-- EXISTING, already-correct SELECT RLS:
--   * v_logbook_truth              -> logbook.logbook_read   (hive_id IN user active hives)  [private]
--   * v_project_truth              -> projects.projects_hive_rw (hive_id IN user_hive_ids())  [private]
--   * v_marketplace_listings_truth -> marketplace_listings.mkt_listings_read
--                                       (status='published' OR own seller OR admin)          [published=public
--                                        by design; this ALSO stops the current cross-hive DRAFT leak]
-- All three base tables already GRANT SELECT to authenticated (verified), so invoker-mode does not
-- 403 legitimate reads; it only re-applies the intended per-row visibility.
--
-- Plus: community_xp_read was `auth.uid() IS NOT NULL` only — it leaked EVERY hive's worker roster, XP,
-- and hive_id UUIDs to any authenticated user (the oracle that arms the hive_members self-join hole,
-- fixed separately in 20260713000002). Scope it to the caller's own hives via user_hive_ids().

BEGIN;

ALTER VIEW public.v_logbook_truth              SET (security_invoker = on);
ALTER VIEW public.v_project_truth              SET (security_invoker = on);
ALTER VIEW public.v_marketplace_listings_truth SET (security_invoker = on);

DROP POLICY IF EXISTS community_xp_read ON public.community_xp;
CREATE POLICY community_xp_read ON public.community_xp
  FOR SELECT
  USING (hive_id IN (SELECT public.user_hive_ids()));

COMMIT;
