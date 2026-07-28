-- ─────────────────────────────────────────────────────────────────────────────
-- A project child row's PARENT must live in the same hive the row claims to.
--
-- FOUND BY THE PJ13 WALK (2026-07-28, PROJECT_MANAGER_DEEPWALK_EXPANSION_ROADMAP), and this is the
-- probe that EARNS PJK4 rather than assuming it from the AHK4 analogy.
--
-- READS ARE CORRECTLY ISOLATED, measured first and recorded as a real result: as a member of one
-- hive, `projects`, `project_items` and `project_change_orders` all return 0 rows for another hive.
--
-- WRITES HAD THE PM13 / AHK4 GAP. Every policy is a single PERMISSIVE FOR ALL whose WITH CHECK tests
-- only `hive_id IN user_hive_ids()`; nothing joins `projects`. Probed live with MY hive_id and
-- ANOTHER hive's project_id, all three accepted:
--
--     project_items          -> accepted
--     project_progress_logs  -> accepted
--     project_change_orders  -> accepted   (a change order on a project the writer cannot see)
--
-- An APPROVED change order was refused, but by wh_guard_supervisor_approval on the status, not by
-- anything tenancy-related — worth stating so the next reader does not mistake that for isolation.
--
-- AN INSTRUMENT NOTE, because the first attempt nearly recorded a false "isolation holds": the
-- initial probes failed with 23514 (a status enum I got wrong) and 23502 (a NOT NULL I omitted).
-- Neither is 42501. Verify WHAT blocked a write, never merely THAT something did — the same trap
-- the AH13 walk hit on the reliability tables.
--
-- SEVERITY, MEASURED RATHER THAN ASSUMED, and it is CONTAINED today: v_project_truth's rollup
-- subqueries (item_count, estimated_total_hours, approved_change_orders, approved_co_cost_php,
-- link_count) carry NO hive filter — they are plain `WHERE pi.project_id = p.id`. What stops an
-- injected row from landing in the VICTIM's numbers is that the view is security_invoker, so those
-- subqueries execute as the READER and RLS hides the foreign row. Proven: injecting an item with
-- 999 estimated hours left the victim's rollup at 7 items / 33.00 est hrs, and the victim could not
-- see the row.
--
-- SO WHY FIX IT. The containment rests entirely on `security_invoker` staying ON — and earlier the
-- same day, a routine CREATE OR REPLACE silently cleared that exact option from v_sensor_truth,
-- because CREATE VIEW does not carry reloptions forward. One such slip on v_project_truth would
-- turn every un-filtered rollup subquery into a cross-tenant read, instantly and silently. Closing
-- the gap at the WRITE removes the dependence on that option, and on every future consumer
-- remembering to be hive-scoped.
--
-- SAFE TO TIGHTEN, measured before applying: 0 existing rows violate this on any of the five
-- tables, so it rejects nothing that exists.
--
-- RESTRICTIVE so it ANDs with the existing permissive policies and cannot widen anything; the
-- service_role / seeder path (auth.uid() IS NULL) keeps its reach, as everywhere else in these arcs.
-- ─────────────────────────────────────────────────────────────────────────────

DO $$
DECLARE
  t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['project_items', 'project_change_orders', 'project_progress_logs',
                           'project_links', 'project_knowledge']
  LOOP
    EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', t || '_parent_hive_guard', t);
    EXECUTE format($f$
      CREATE POLICY %I ON public.%I
        AS RESTRICTIVE FOR ALL
        USING (true)
        WITH CHECK (
          auth.uid() IS NULL
          OR project_id IS NULL
          OR EXISTS (
            SELECT 1 FROM public.projects p
             WHERE p.id = %I.project_id
               AND p.hive_id IS NOT DISTINCT FROM %I.hive_id
          )
        )$f$, t || '_parent_hive_guard', t, t, t);
  END LOOP;
END $$;
