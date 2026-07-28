-- ─────────────────────────────────────────────────────────────────────────────
-- A worker could WRITE a budget they were not allowed to READ.
--
-- FOUND BY THE PJ2 WALK (2026-07-28), on the second persona — which is the only reason it surfaced.
-- The shallow-W guard refused to credit PJ2 on one persona, so I re-probed as an ordinary worker,
-- and that probe found this:
--
--     INSERT INTO projects (..., budget_php) VALUES (..., 5000000)  as a WORKER  ->  ACCEPTED
--
-- 20260728000024 closed the READ path (dropped the table-wide SELECT grant, re-granted every column
-- except budget_php) and never touched the WRITE path. Measured after that migration,
-- information_schema.column_privileges still showed `authenticated` and `anon` holding INSERT and
-- UPDATE on budget_php. So the asymmetry was: a worker cannot see any budget, and can set one.
--
-- The page-level guard added for PJ9 (`_budgetReadable` gating the payload) does stop the UI doing
-- it — and a page-level guard is exactly what PJK3 exists to reject. The database has to say it.
--
-- WHY A SETTER RPC RATHER THAN JUST REVOKING: a supervisor legitimately sets a budget, in the create
-- wizard and the edit form. Revoking INSERT/UPDATE on the column without providing a sanctioned path
-- would break that. So the write moves to a SECURITY DEFINER function with the same supervisor test
-- as get_project_budget and wh_guard_supervisor_approval, keeping authority defined in one place.
--
-- NOTE ON CREATE: the wizard inserts a project and its budget in one statement. With INSERT on the
-- column revoked, the page now creates the project WITHOUT a budget and calls set_project_budget()
-- immediately after — two steps, and the second is allowed to fail (a project with no budget is a
-- valid state that the EVM engine already reports honestly as {available:false}).
-- ─────────────────────────────────────────────────────────────────────────────

-- 1. The sanctioned write.
CREATE OR REPLACE FUNCTION public.set_project_budget(
  p_project_id uuid,
  p_budget_php numeric
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_hive   uuid;
  v_is_sup boolean;
BEGIN
  SELECT hive_id INTO v_hive FROM public.projects WHERE id = p_project_id;
  IF v_hive IS NULL THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'not found');
  END IF;

  IF auth.uid() IS NULL THEN
    v_is_sup := true;                       -- service_role / seeders / migrations
  ELSE
    SELECT EXISTS (
      SELECT 1 FROM public.hive_members hm
       WHERE hm.hive_id = v_hive AND hm.auth_uid = auth.uid()
         AND hm.status = 'active' AND hm.role = 'supervisor'
    ) INTO v_is_sup;
  END IF;

  IF NOT v_is_sup THEN
    RETURN jsonb_build_object(
      'ok', false, 'reason', 'not a supervisor',
      'detail', 'Only a supervisor of this hive can set a project budget.');
  END IF;

  UPDATE public.projects
     SET budget_php = p_budget_php, updated_at = now()
   WHERE id = p_project_id;

  RETURN jsonb_build_object('ok', true, 'budget_php', p_budget_php);
END;
$function$;

COMMENT ON FUNCTION public.set_project_budget(uuid, numeric) IS
  'Supervisor-only write of projects.budget_php. Paired with get_project_budget: PJ9 closed the READ '
  'path and left INSERT/UPDATE on the column granted, so a worker could SET a budget they could not '
  'SEE (proven live at PHP 5,000,000). Same supervisor predicate as get_project_budget and '
  'wh_guard_supervisor_approval. PJ2/PJK3, 2026-07-28.';

REVOKE ALL ON FUNCTION public.set_project_budget(uuid, numeric) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.set_project_budget(uuid, numeric) TO authenticated, service_role;

-- 2. Close the unsanctioned write. Same mechanism as the SELECT side: the table-wide grant has to
--    go, then every OTHER column is re-granted explicitly. The list is generated below rather than
--    typed, for the same reason as before — a column missed here is an instant 42501 on a write
--    that used to work.
DO $$
DECLARE
  cols text;
BEGIN
  SELECT string_agg(quote_ident(column_name), ', ' ORDER BY ordinal_position)
    INTO cols
    FROM information_schema.columns
   WHERE table_schema = 'public' AND table_name = 'projects'
     AND column_name <> 'budget_php';

  EXECUTE 'REVOKE INSERT, UPDATE ON public.projects FROM authenticated';
  EXECUTE 'REVOKE INSERT, UPDATE ON public.projects FROM anon';
  EXECUTE format('GRANT INSERT (%s), UPDATE (%s) ON public.projects TO authenticated', cols, cols);
  EXECUTE format('GRANT INSERT (%s), UPDATE (%s) ON public.projects TO anon', cols, cols);
END $$;
