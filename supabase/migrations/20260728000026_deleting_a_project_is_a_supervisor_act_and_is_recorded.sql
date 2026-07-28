-- ─────────────────────────────────────────────────────────────────────────────
-- Any member could hide any project in their hive, and nothing recorded it.
--
-- FOUND BY THE PJ12 WALK (2026-07-28, PROJECT_MANAGER_DEEPWALK_EXPANSION_ROADMAP). Three measured
-- facts, in the order they matter:
--
--   1. A WORKER CAN SOFT-DELETE ANY PROJECT IN THEIR HIVE. deleteProject() sets deleted_at, the
--      button carries no role check, and neither does the database: projects_hive_rw is a single
--      PERMISSIVE FOR ALL testing only hive membership. Probed live as an ordinary worker —
--      UPDATE succeeded on SHD-2026-001, a shutdown project they do not own. Every view filters
--      `deleted_at IS NULL`, so the project vanishes from the fleet for everyone.
--
--   2. NOTHING RECORDS IT. hive_audit_log holds ZERO rows for target_type='projects' or any action
--      naming a project — the G2 ground finding, confirmed live. So a project disappears and the
--      log cannot say it ever existed, let alone who removed it.
--
--   3. A HARD delete cascades to all six child tables (project_items, project_links,
--      project_progress_logs, project_roles, project_change_orders, project_knowledge — every FK is
--      ON DELETE CASCADE). It is currently refused for any project carrying a change order, because
--      20260728000022's immutability trigger fires on the cascade and blocks it. That is an
--      ACCIDENTAL side effect of a fix aimed at something else, and it is recorded here rather than
--      left to be discovered: nothing legitimate breaks, since the UI only ever soft-deletes, but a
--      future admin hard-delete WILL fail with a change-order error that looks unrelated.
--
-- WHAT THIS CHANGES. Removing a project is a supervisor act, and it is recorded either way:
--   * a soft delete (deleted_at NULL -> NOT NULL) requires supervisor, and writes an audit row
--     carrying what the project was and what it took with it
--   * an un-delete (restore) likewise
--   * a HARD delete requires supervisor and is audited BEFORE the cascade, because afterwards the
--     child counts no longer exist to be recorded — the same reason trg_asset_node_delete_audit is
--     a BEFORE trigger
--
-- WHY GUARD RATHER THAN FORBID: soft-delete is the intended workflow (the UI offers it and every
-- view honours it), so the fix is authority plus evidence, not removal of the capability.
--
-- service_role / seeders keep their reach (auth.uid() IS NULL), as everywhere else in these arcs.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.guard_and_audit_project_removal()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_is_sup   boolean;
  v_actor    text;
  v_items    integer;
  v_cos      integer;
  v_logs     integer;
  v_links    integer;
  v_kind     text;
  v_hive     uuid := COALESCE(NEW.hive_id, OLD.hive_id);
BEGIN
  -- Which removal is this? An ordinary edit is none of them and must pass straight through.
  IF TG_OP = 'DELETE' THEN
    v_kind := 'hard_delete_project';
  ELSIF OLD.deleted_at IS NULL AND NEW.deleted_at IS NOT NULL THEN
    v_kind := 'delete_project';
  ELSIF OLD.deleted_at IS NOT NULL AND NEW.deleted_at IS NULL THEN
    v_kind := 'restore_project';
  ELSE
    RETURN NEW;
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
    RAISE EXCEPTION 'Removing or restoring a project is a supervisor action (%).',
                    COALESCE(OLD.project_code, NEW.project_code)
      USING ERRCODE = 'insufficient_privilege';
  END IF;

  -- Count BEFORE the statement completes: on a hard delete the cascade destroys these, and after
  -- it there is nothing left to describe what was lost.
  SELECT count(*) INTO v_items FROM public.project_items          WHERE project_id = OLD.id;
  SELECT count(*) INTO v_cos   FROM public.project_change_orders  WHERE project_id = OLD.id;
  SELECT count(*) INTO v_logs  FROM public.project_progress_logs  WHERE project_id = OLD.id;
  SELECT count(*) INTO v_links FROM public.project_links          WHERE project_id = OLD.id;

  SELECT hm.worker_name INTO v_actor
    FROM public.hive_members hm
   WHERE hm.auth_uid = auth.uid() AND (v_hive IS NULL OR hm.hive_id = v_hive)
   LIMIT 1;

  INSERT INTO public.hive_audit_log (hive_id, actor, action, target_type, target_id, target_name, meta)
  VALUES (
    v_hive,
    COALESCE(v_actor, OLD.worker_name, 'unknown'),
    v_kind,
    'projects',
    OLD.id::text,
    COALESCE(OLD.project_code, OLD.name, '(unnamed project)'),
    jsonb_build_object(
      'project_name',   OLD.name,
      'project_type',   OLD.project_type,
      'status_was',     OLD.status,
      'scope_items',    v_items,
      -- A change order is a contract amendment; how many rode along is the number that matters most.
      'change_orders',  v_cos,
      'progress_logs',  v_logs,
      'links',          v_links,
      'source',         'db_trigger'
    )
  );

  RETURN COALESCE(NEW, OLD);
END;
$function$;

DROP TRIGGER IF EXISTS trg_project_removal_guard_audit ON public.projects;
CREATE TRIGGER trg_project_removal_guard_audit
  BEFORE UPDATE OR DELETE ON public.projects
  FOR EACH ROW
  EXECUTE FUNCTION public.guard_and_audit_project_removal();

COMMENT ON FUNCTION public.guard_and_audit_project_removal() IS
  'Removing or restoring a project is a supervisor act, and is recorded either way. Before this, any '
  'active member could set deleted_at on any project in their hive (the UI button carries no role '
  'check and neither did the database) and hive_audit_log held ZERO rows for projects, so a project '
  'could vanish with nothing able to say it had existed. Counts the children BEFORE the statement '
  'because a hard delete cascades to all six child tables. PJ12/PJK1.';
