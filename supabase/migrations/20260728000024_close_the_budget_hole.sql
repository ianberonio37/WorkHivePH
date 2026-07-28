-- ─────────────────────────────────────────────────────────────────────────────
-- Close it: budget_php becomes unreadable on the client path, everywhere.
--
-- Companion to 20260728000023, which added the sanctioned read (get_project_budget). That RPC alone
-- did NOT close anything — it added a permitted path without removing the unpermitted one. A worker
-- could still `db.from('projects').select('budget_php')`, because RLS is ROW-level and cannot
-- withhold one column of a row a member is otherwise entitled to read.
--
-- IAN'S CALL (2026-07-28), asked because the platform contradicted itself and the answer was a
-- product decision, not an engineering one: project-manager.html told non-supervisors "Budget
-- visibility is restricted to supervisors", while project-report.html — a printable, signed-off
-- client document — rendered the figure with no role check at all. Chosen: supervisor-only
-- EVERYWHERE, and the report is the surface that was wrong.
--
-- TWO CHANGES, and the second is what keeps this from breaking the platform:
--
--   1. REVOKE the column from `authenticated`. Postgres column privileges are the only mechanism
--      that can withhold ONE column of a readable row.
--
--   2. DROP budget_php from v_project_truth. This is not tidiness. The view is security_invoker, so
--      it executes with the caller's privileges — a revoked base column would make every
--      `select('*')` against the view fail outright, and project-report.html and
--      project-orchestrator both do exactly that. Removing the column from the view keeps the
--      wildcard readers working and closes the same hole at the same time.
--
-- CALLERS AUDITED BEFORE APPLYING, because a revoke is blunt and a half-applied one breaks pages:
--   * projects.select('*')      — ONE site (project-manager openDetail) -> enumerated explicitly
--   * projects list select      — budget_php removed; supervisors use the RPC
--   * the edit form             — prefilled from the RPC; the save path now OMITS the key entirely
--                                 when the caller could not read it, because sending null would
--                                 ERASE the budget. A blank field means "withheld", never "zero".
--   * clientRollup EVM fallback — asks the RPC; no figure means no EVM block, which is correct
--   * project-report.html       — reads v_project_truth with select('*'), fixed by change 2
--   * project-orchestrator /
--     project-progress edge fns — service_role, unaffected by either change
--
-- service_role keeps full access, so the seeders, the EVM backend and every server path are
-- untouched. get_project_budget is SECURITY DEFINER and therefore still reads the column.
-- ─────────────────────────────────────────────────────────────────────────────

-- 1. The column becomes unreadable on the client path.
--
--    A COLUMN-LEVEL REVOKE ALONE IS A NO-OP, and finding that out live is the only reason this
--    migration works. Postgres checks table-level privilege FIRST: while `GRANT SELECT ON projects
--    TO authenticated` stands, the grantee may read EVERY column, and `REVOKE SELECT (budget_php)`
--    changes nothing. Verified — after the revoke, information_schema.column_privileges still listed
--    authenticated/anon on budget_php and a worker still read the figure.
--
--    The working mechanism is: drop the table-wide grant, then re-grant the allowed columns
--    explicitly. The list below is GENERATED from information_schema (every column except
--    budget_php) rather than typed, because a column missed here becomes an instant 42501 on a page
--    that used to work.
REVOKE SELECT ON public.projects FROM authenticated;
REVOKE SELECT ON public.projects FROM anon;
GRANT SELECT (id, hive_id, worker_name, auth_uid, project_code, name, project_type, status, priority, owner_name, description, start_date, end_date, meta, created_at, updated_at, closed_at, deleted_at) ON public.projects TO authenticated;
GRANT SELECT (id, hive_id, worker_name, auth_uid, project_code, name, project_type, status, priority, owner_name, description, start_date, end_date, meta, created_at, updated_at, closed_at, deleted_at) ON public.projects TO anon;

-- 2. Re-create the truth view WITHOUT budget_php, preserving security_invoker.
--
--    THE DEFINITION BELOW IS THE DUMPED pg_get_viewdef OUTPUT MINUS ONE COLUMN. It is not written
--    from memory, and that mattered: my first draft of this migration WAS written from memory and
--    would have destroyed eight correlated subqueries the pages depend on (item_count, items_done,
--    estimated_total_hours, actual_total_hours, last_progress_at, approved_change_orders,
--    approved_co_cost_php, link_count), renamed actual_end_at, replaced maintenance_nature's
--    project_links-based logic with a naive type map, and dropped the `status <> 'archived'` filter
--    so archived projects would have reappeared. Dumping first is the only reason this is correct —
--    the same lesson this session already learned twice on v_weibull_truth and v_sensor_truth.
--
--    security_invoker is RESTATED because CREATE VIEW CLEARS reloptions.
DROP VIEW IF EXISTS public.v_project_truth;
CREATE VIEW public.v_project_truth
WITH (security_invoker = true) AS
 SELECT id AS project_id,
    hive_id,
    project_code,
    name,
    project_type,
    status,
    priority,
    owner_name,
    start_date,
    end_date AS target_end_date,
    closed_at AS actual_end_at,
    created_at,
    updated_at,
    ( SELECT count(*) AS count
           FROM project_items pi
          WHERE pi.project_id = p.id) AS item_count,
    ( SELECT count(*) AS count
           FROM project_items pi
          WHERE pi.project_id = p.id AND pi.status = 'done'::text) AS items_done,
    ( SELECT COALESCE(sum(pi.estimated_hours), 0::numeric) AS "coalesce"
           FROM project_items pi
          WHERE pi.project_id = p.id) AS estimated_total_hours,
    ( SELECT COALESCE(sum(pi.actual_hours), 0::numeric) AS "coalesce"
           FROM project_items pi
          WHERE pi.project_id = p.id) AS actual_total_hours,
    ( SELECT max(ppl.created_at) AS max
           FROM project_progress_logs ppl
          WHERE ppl.project_id = p.id) AS last_progress_at,
    ( SELECT count(*) AS count
           FROM project_change_orders pco
          WHERE pco.project_id = p.id AND pco.status = 'approved'::text) AS approved_change_orders,
    ( SELECT COALESCE(sum(pco.cost_impact_php), 0::numeric) AS "coalesce"
           FROM project_change_orders pco
          WHERE pco.project_id = p.id AND pco.status = 'approved'::text) AS approved_co_cost_php,
    ( SELECT count(*) AS count
           FROM project_links pl
          WHERE pl.project_id = p.id) AS link_count,
        CASE
            WHEN project_type = ANY (ARRAY['capex'::text, 'contractor'::text]) THEN 'project'::text
            WHEN project_type = 'shutdown'::text THEN 'preventive'::text
            WHEN project_type = 'workorder'::text AND (EXISTS ( SELECT 1
               FROM project_links pl
              WHERE pl.project_id = p.id AND pl.link_type = 'logbook'::text)) THEN 'reactive'::text
            WHEN project_type = 'workorder'::text AND (EXISTS ( SELECT 1
               FROM project_links pl
              WHERE pl.project_id = p.id AND pl.link_type = 'pm_completion'::text)) THEN 'preventive'::text
            ELSE 'reactive'::text
        END AS maintenance_nature
   FROM projects p
  WHERE deleted_at IS NULL AND status <> 'archived'::text;

COMMENT ON VIEW public.v_project_truth IS
  'Tier D canonical: one row per live project with rollup counts and the maintenance_nature facet. '
  'budget_php was REMOVED 2026-07-28 (PJ9): it is supervisor-only and reachable through '
  'get_project_budget(), and leaving it would have broken every select(''*'') reader once the base '
  'column was revoked, since this view is security_invoker. NOTE: approved_co_cost_php remains and '
  'is also a financial figure readable by any hive member - flagged as a follow-up, deliberately not '
  'changed here, because Ian''s decision covered the BUDGET and silently widening it would be scope '
  'creep on a security change.';
