-- ★A PROJECT ROLE WAS GRANTED TO THE SUPERVISOR WHO GRANTED IT, NOT TO THE PERSON SHE PICKED (2026-10-08, found
-- proving the project-role audit trigger as `authenticated`). project-manager.html saveRole INSERTs
-- {worker_name: <the worker chosen in the picker>, role, assigned_by}. The 2026-07-17 attribution-pin sweep
-- (20260717000011) attached bind_worker_name_from_hive to project_roles, which REWRITES worker_name to the CALLER's
-- own hive name on every INSERT. That function is right for tables whose worker_name is the row's AUTHOR (a
-- knowledge entry, a voice note, a seller profile) - and wrong here, because project_roles.worker_name is the
-- ASSIGNEE. The author of a role grant is assigned_by, and that is already pinned server-side by
-- tg_bind_assigned_by (20260717000015). Measured as Pablo Aguilar (Lucena supervisor) assigning 'reviewer' to
-- Ricardo Morales: the row landed as worker_name = 'Pablo Aguilar'. Every role assigned through the page since
-- 2026-07-17 went to whoever pressed Assign, which also decides who may approve change orders.
--
-- The forge the sweep was closing does not exist on this table: project_roles is supervisor-scoped by RLS
-- (20260712000020), so only a supervisor can write a role at all, and the grant is attributed by assigned_by. What
-- the assignee DOES need is to be a real, active member of the hive, so the binding is replaced by that check.
-- worker_name stays immutable on UPDATE, as it was.

DROP TRIGGER IF EXISTS tg_bind_wname_project_roles ON public.project_roles;

CREATE OR REPLACE FUNCTION public.guard_project_role_assignee()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
BEGIN
  IF auth.uid() IS NULL THEN RETURN NEW; END IF;                          -- service_role / seeders
  IF TG_OP = 'UPDATE' THEN
    NEW.worker_name := OLD.worker_name;                                   -- the assignee of a grant is fixed
    RETURN NEW;
  END IF;
  IF NOT EXISTS (
       SELECT 1 FROM public.hive_members hm
        WHERE hm.hive_id = NEW.hive_id AND hm.worker_name = NEW.worker_name AND hm.status = 'active') THEN
    RAISE EXCEPTION '% is not an active member of this hive, so they cannot hold a project role.', NEW.worker_name
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$function$;

REVOKE ALL ON FUNCTION public.guard_project_role_assignee() FROM PUBLIC, anon, authenticated;

DROP TRIGGER IF EXISTS tg_guard_project_role_assignee ON public.project_roles;
CREATE TRIGGER tg_guard_project_role_assignee
  BEFORE INSERT OR UPDATE ON public.project_roles
  FOR EACH ROW EXECUTE FUNCTION public.guard_project_role_assignee();
