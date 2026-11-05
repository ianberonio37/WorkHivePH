-- ★A SCOPE ITEM NEVER SAID WHO PUT IT THERE (2026-11-06, GJ M9 J8 hand-off 1: "the BOM the engineer generated is on the
-- project").
--
-- An engineer imports their calculation's BOM into a project, and the manager reading the project's Scope / WBS saw
-- rows of title, owner, status and hours - nothing said who added a line, when, or that it came from the engineer's
-- calculation: project_items has no author column at all, only created_at. The record a manager signs off against
-- could not say where its own lines came from.
--
-- project_items gains added_by, stamped by the server on insert from the caller's own profile name (the same binding
-- as the trail's actor - never a value a client sends), and the scope row says "added by <name> · <when>".

BEGIN;

ALTER TABLE public.project_items ADD COLUMN IF NOT EXISTS added_by text;

CREATE OR REPLACE FUNCTION public.tg_project_items_bind_added_by()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE v_name text;
BEGIN
  IF auth.uid() IS NOT NULL THEN
    SELECT display_name INTO v_name FROM public.worker_profiles WHERE auth_uid = auth.uid() LIMIT 1;
    IF v_name IS NULL THEN
      SELECT worker_name INTO v_name FROM public.hive_members
       WHERE auth_uid = auth.uid() AND hive_id = NEW.hive_id AND status = 'active' LIMIT 1;
    END IF;
    NEW.added_by := v_name;           -- always the caller's own name; a client-sent value is overwritten
  ELSIF TG_OP = 'UPDATE' THEN
    NEW.added_by := OLD.added_by;
  END IF;
  IF TG_OP = 'UPDATE' THEN
    NEW.added_by := OLD.added_by;     -- who added a line never changes after it was added
  END IF;
  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_project_items_bind_added_by ON public.project_items;
CREATE TRIGGER trg_project_items_bind_added_by
  BEFORE INSERT OR UPDATE ON public.project_items
  FOR EACH ROW EXECUTE FUNCTION public.tg_project_items_bind_added_by();

REVOKE ALL ON FUNCTION public.tg_project_items_bind_added_by() FROM PUBLIC, anon, authenticated;

-- the truth view the page reads carries it (appended last, so every existing column keeps its position). A CREATE OR
-- REPLACE VIEW does not keep security_invoker unless it is said again - it is said again.
CREATE OR REPLACE VIEW public.v_project_items_truth WITH (security_invoker = on) AS
 SELECT i.id,
    i.project_id,
    i.hive_id,
    i.wbs_code,
    i.title,
    i.owner_name,
    i.status,
    i.pct_complete,
    i.planned_start,
    i.planned_end,
    i.actual_start,
    i.actual_end,
    i.predecessors,
    i.estimated_hours,
    i.actual_hours,
    i.notes,
    i.sort_order,
    i.created_at,
    i.updated_at,
    p.name AS project_name,
    p.project_code,
    p.status AS project_status,
    (i.status = 'pending'::text) AS is_pending,
    (i.status = 'in_progress'::text) AS is_in_progress,
    (i.status = 'done'::text) AS is_done,
    (i.status = 'blocked'::text) AS is_blocked,
    (i.status = 'skipped'::text) AS is_skipped,
    ((i.planned_end IS NOT NULL) AND (i.planned_end < ((now() AT TIME ZONE 'Asia/Manila'::text))::date) AND (i.status <> ALL (ARRAY['done'::text, 'skipped'::text]))) AS is_overdue,
    ((i.planned_start IS NOT NULL) AND (i.planned_start <= ((now() AT TIME ZONE 'Asia/Manila'::text))::date) AND (i.actual_start IS NULL) AND (i.status = 'pending'::text)) AS is_late_start,
    i.added_by
   FROM (project_items i
     LEFT JOIN projects p ON ((p.id = i.project_id)));

COMMIT;
