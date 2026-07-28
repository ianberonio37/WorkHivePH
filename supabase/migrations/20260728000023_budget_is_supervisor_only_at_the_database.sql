-- ─────────────────────────────────────────────────────────────────────────────
-- "Budget visibility is restricted to supervisors" was true only in the renderer.
--
-- FOUND BY THE PJ9 WALK (2026-07-28, PROJECT_MANAGER_DEEPWALK_EXPANSION_ROADMAP):
-- renderBudget() shows a non-supervisor "Budget visibility is restricted to supervisors", while
-- `projects_hive_rw` grants every active member SELECT on the whole row. Probed as an ordinary
-- worker: read `budget_php` straight off the table — CAP-2026-001 PHP 1,850,000, CON-2026-001
-- PHP 280,000. The page renders a refusal; the database hands the number over.
--
-- WIDER THAN THE PANE, which is what makes it worth a migration rather than a patch: `budget_php`
-- is in the MAIN project-list select for every user, and BAC is computed client-side afterwards.
-- The figure is already in the browser of everyone who opens the page, before any pane decides
-- whether to display it. Hiding a rendered pane cannot fix a value that already arrived.
--
-- LEGITIMATE READERS MEASURED FIRST (the discipline that saved two writes in the previous arc):
--   * project-manager.html — the list select, the edit form, and the client-side EVM
--   * project-orchestrator + project-progress edge fns — both run SERVICE-ROLE, so they are
--     unaffected by anything that gates the `authenticated` client path
-- Nothing else on the platform reads it.
--
-- SHAPE OF THE FIX, matching what this codebase already does twice (sync_asset_identity,
-- ensure_pm_asset_for_node): the privileged read becomes a SECURITY DEFINER RPC that checks the
-- caller's role ITSELF, and the client stops selecting the column. Postgres RLS is row-level, so
-- it cannot hide one column of a row a member is otherwise entitled to read — the RPC is the
-- mechanism that can.
--
-- The supervisor test is `hive_members.role = 'supervisor' AND status = 'active'`, the same
-- predicate wh_guard_supervisor_approval uses, so authority is defined in ONE place.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.get_project_budget(p_project_id uuid)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_row   public.projects%ROWTYPE;
  v_is_sup boolean;
BEGIN
  SELECT * INTO v_row FROM public.projects WHERE id = p_project_id;
  IF NOT FOUND THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'not found');
  END IF;

  -- service_role / server-to-server keeps its reach, as everywhere else in these arcs.
  IF auth.uid() IS NULL THEN
    v_is_sup := true;
  ELSE
    SELECT EXISTS (
      SELECT 1 FROM public.hive_members hm
       WHERE hm.hive_id  = v_row.hive_id
         AND hm.auth_uid = auth.uid()
         AND hm.status   = 'active'
         AND hm.role     = 'supervisor'
    ) INTO v_is_sup;
  END IF;

  IF NOT v_is_sup THEN
    -- Say WHY rather than returning a silent null: a worker who can see an Earned Value pane
    -- exists should learn that the figure is withheld, not that the project has no budget.
    RETURN jsonb_build_object(
      'ok', false,
      'reason', 'not a supervisor',
      'detail', 'Budget figures are visible to supervisors of this hive.');
  END IF;

  RETURN jsonb_build_object(
    'ok', true,
    'budget_php', v_row.budget_php,
    'start_date', v_row.start_date,
    'end_date',   v_row.end_date);
END;
$function$;

COMMENT ON FUNCTION public.get_project_budget(uuid) IS
  'Supervisor-only read of a project''s budget_php (plus the dates Earned Value needs). Exists '
  'because RLS is ROW-level and cannot withhold one column of a row a member may otherwise read, '
  'while project-manager.html claimed in its renderer that budget visibility was supervisor-only. '
  'Measured 2026-07-28: a worker read PHP 1,850,000 straight off the table. Uses the same '
  'supervisor predicate as wh_guard_supervisor_approval so authority is defined in one place. PJ9/PJK3.';

REVOKE ALL ON FUNCTION public.get_project_budget(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.get_project_budget(uuid) TO authenticated, service_role;

-- Canonical anchor (same-change rule, and the second time today I needed reminding of it):
-- a get_* RPC is an ENGINE-layer item and must be registered in canonical_sources or the
-- canonical-anchor gate counts it as un-anchored.
INSERT INTO public.canonical_sources
  (domain, source_kind, source_name, owner_skill, freshness, contract, description, notes)
VALUES (
  'get_project_budget_rpc', 'rpc', 'get_project_budget', 'architect', 'on_demand',
  '{"signature": "get_project_budget(p_project_id uuid) RETURNS jsonb", "side_effects": []}'::jsonb,
  'Supervisor-only read of projects.budget_php plus the start/end dates Earned Value needs. Exists '
  'because RLS is ROW-level and cannot withhold one column of a row a member may otherwise read. '
  'Returns {ok:false, reason:''not a supervisor''} with a stated detail rather than a null, so a '
  'refusal is never mistaken for "this project has no budget".',
  'PJ9, 2026-07-28. Paired with 20260728000024, which drops the table-wide SELECT grant and re-grants '
  'every column except budget_php - a column-level REVOKE alone is a no-op while a table-level grant '
  'stands.'
)
ON CONFLICT (domain) DO UPDATE
  SET source_kind = EXCLUDED.source_kind, source_name = EXCLUDED.source_name,
      owner_skill = EXCLUDED.owner_skill, freshness = EXCLUDED.freshness,
      contract = EXCLUDED.contract, description = EXCLUDED.description, notes = EXCLUDED.notes;
