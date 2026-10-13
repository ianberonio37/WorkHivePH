-- ★THE PROJECT PAGE'S AUTHORITY DECISIONS LEFT NO AUDIT ROW (2026-10-08, found authoring the UI-write recipes).
-- On project-manager.html a supervisor approves, rejects or cancels a CHANGE ORDER (it moves the project's cost and
-- schedule), assigns and removes PROJECT ROLES (they decide who may approve), and ACKNOWLEDGES a progress report.
-- None of those wrote to hive_audit_log, so the hive's audit trail - the one an auditor, the insurance bridge and a
-- second supervisor read - could not say who approved a +P250,000 change order or who granted approver rights.
-- The same page's project removal IS audited, by a database trigger (guard_and_audit_project_removal, PJ12), and so
-- are asset approvals (audit_asset_approval_decision). These decisions now follow that shape exactly:
--   hive_id, actor (resolved server-side from auth.uid(), never the client's text name), action,
--   target_type = the table, target_id = the row id, target_name = something a person can read, meta.source='db_trigger'.
--
-- A trigger rather than a client writeAuditLog call, for the reason PJ12 gave: it fires however the row changes - this
-- page, another surface, psql - and a client-side audit is skipped by every write that does not go through the page.
--
-- Person actions only: auth.uid() IS NULL (service_role, seeders, migrations) is not a decision anyone made, and the
-- seeders insert project_roles in bulk. A cascade (the project or the hive being deleted) is not a decision either -
-- the removal has its own audit row - and an audit INSERT naming a hive that is mid-delete would violate
-- hive_audit_log_hive_id_fkey and ABORT the delete, so both are skipped explicitly.

CREATE OR REPLACE FUNCTION public.audit_change_order_decision()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_actor  text;
  v_code   text;
  v_action text;
BEGIN
  IF auth.uid() IS NULL THEN RETURN NEW; END IF;
  IF NEW.status IS NOT DISTINCT FROM OLD.status THEN RETURN NEW; END IF;
  v_action := CASE NEW.status
                WHEN 'approved'  THEN 'approve_change_order'
                WHEN 'rejected'  THEN 'reject_change_order'
                WHEN 'cancelled' THEN 'cancel_change_order'
              END;
  IF v_action IS NULL THEN RETURN NEW; END IF;

  SELECT hm.worker_name INTO v_actor
    FROM public.hive_members hm
   WHERE hm.hive_id = NEW.hive_id AND hm.auth_uid = auth.uid()
   LIMIT 1;
  SELECT p.project_code INTO v_code FROM public.projects p WHERE p.id = NEW.project_id;

  INSERT INTO public.hive_audit_log (hive_id, actor, action, target_type, target_id, target_name, meta)
  VALUES (
    NEW.hive_id,
    COALESCE(v_actor, 'unknown'),
    v_action,
    'project_change_orders',
    NEW.id::text,
    COALESCE(NEW.co_number, '') || ' · ' || COALESCE(NEW.title, '(untitled change order)'),
    jsonb_build_object(
      'project_id',            NEW.project_id,
      'project_code',          v_code,
      'status_was',            OLD.status,
      'status_now',            NEW.status,
      'cost_impact_php',       NEW.cost_impact_php,
      'schedule_impact_days',  NEW.schedule_impact_days,
      'rejection_reason',      NEW.rejection_reason,
      'requested_by',          NEW.requested_by,
      'approved_by_claimed',   NEW.approved_by,
      'decided_by',            v_actor,
      'source',                'db_trigger'
    )
  );
  RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION public.audit_project_role_change()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_row    public.project_roles%ROWTYPE;
  v_actor  text;
  v_code   text;
  v_action text;
BEGIN
  IF auth.uid() IS NULL THEN RETURN COALESCE(NEW, OLD); END IF;
  IF TG_OP = 'INSERT' THEN
    v_row := NEW; v_action := 'assign_project_role';
  ELSE
    v_row := OLD; v_action := 'remove_project_role';
  END IF;

  -- a cascade from a project or hive delete: that removal is audited on its own
  IF NOT EXISTS (SELECT 1 FROM public.hives h WHERE h.id = v_row.hive_id) THEN RETURN COALESCE(NEW, OLD); END IF;
  SELECT p.project_code INTO v_code FROM public.projects p WHERE p.id = v_row.project_id;
  IF NOT FOUND THEN RETURN COALESCE(NEW, OLD); END IF;

  SELECT hm.worker_name INTO v_actor
    FROM public.hive_members hm
   WHERE hm.hive_id = v_row.hive_id AND hm.auth_uid = auth.uid()
   LIMIT 1;

  INSERT INTO public.hive_audit_log (hive_id, actor, action, target_type, target_id, target_name, meta)
  VALUES (
    v_row.hive_id,
    COALESCE(v_actor, 'unknown'),
    v_action,
    'project_roles',
    v_row.id::text,
    COALESCE(v_row.worker_name, '(unknown)') || ' · ' || COALESCE(v_row.role, '(role)'),
    jsonb_build_object(
      'project_id',    v_row.project_id,
      'project_code',  v_code,
      'worker_name',   v_row.worker_name,
      'role',          v_row.role,
      'assigned_by',   v_row.assigned_by,
      'notes',         v_row.notes,
      'decided_by',    v_actor,
      'source',        'db_trigger'
    )
  );
  RETURN COALESCE(NEW, OLD);
END;
$function$;

CREATE OR REPLACE FUNCTION public.audit_progress_log_acknowledgement()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_actor text;
  v_code  text;
BEGIN
  IF auth.uid() IS NULL THEN RETURN NEW; END IF;
  IF NOT (OLD.acknowledged_at IS NULL AND NEW.acknowledged_at IS NOT NULL) THEN RETURN NEW; END IF;

  SELECT hm.worker_name INTO v_actor
    FROM public.hive_members hm
   WHERE hm.hive_id = NEW.hive_id AND hm.auth_uid = auth.uid()
   LIMIT 1;
  SELECT p.project_code INTO v_code FROM public.projects p WHERE p.id = NEW.project_id;

  INSERT INTO public.hive_audit_log (hive_id, actor, action, target_type, target_id, target_name, meta)
  VALUES (
    NEW.hive_id,
    COALESCE(v_actor, 'unknown'),
    'acknowledge_progress_log',
    'project_progress_logs',
    NEW.id::text,
    COALESCE(NEW.reported_by, '(unknown)') || ' · ' || NEW.log_date::text || ' · ' || NEW.pct_complete::text || '%',
    jsonb_build_object(
      'project_id',              NEW.project_id,
      'project_code',            v_code,
      'reported_by',             NEW.reported_by,
      'log_date',                NEW.log_date,
      'pct_complete',            NEW.pct_complete,
      'blockers',                NEW.blockers,
      'acknowledged_by_claimed', NEW.acknowledged_by,
      'decided_by',              v_actor,
      'source',                  'db_trigger'
    )
  );
  RETURN NEW;
END;
$function$;

REVOKE ALL ON FUNCTION public.audit_change_order_decision()        FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.audit_project_role_change()          FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.audit_progress_log_acknowledgement() FROM PUBLIC, anon, authenticated;

DROP TRIGGER IF EXISTS trg_change_order_decision_audit ON public.project_change_orders;
CREATE TRIGGER trg_change_order_decision_audit
  AFTER UPDATE OF status ON public.project_change_orders
  FOR EACH ROW EXECUTE FUNCTION public.audit_change_order_decision();

DROP TRIGGER IF EXISTS trg_project_role_change_audit ON public.project_roles;
CREATE TRIGGER trg_project_role_change_audit
  AFTER INSERT OR DELETE ON public.project_roles
  FOR EACH ROW EXECUTE FUNCTION public.audit_project_role_change();

DROP TRIGGER IF EXISTS trg_progress_log_ack_audit ON public.project_progress_logs;
CREATE TRIGGER trg_progress_log_ack_audit
  AFTER UPDATE OF acknowledged_at ON public.project_progress_logs
  FOR EACH ROW EXECUTE FUNCTION public.audit_progress_log_acknowledgement();
