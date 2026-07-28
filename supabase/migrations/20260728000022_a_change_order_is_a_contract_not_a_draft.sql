-- ─────────────────────────────────────────────────────────────────────────────
-- A raised change order's commercial terms are FIXED. Only its status may move.
--
-- FOUND BY THE PJ4 WALK (2026-07-28, PROJECT_MANAGER_DEEPWALK_EXPANSION_ROADMAP).
--
-- WHAT WAS ALREADY SAFE, established first so this migration does not re-litigate it:
-- wh_guard_supervisor_approval() is a trigger over six tables and project_change_orders is one of
-- them. Probed live as an ordinary worker: approve -> BLOCKED, reject -> BLOCKED, editing an
-- APPROVED order's cost -> BLOCKED. The approval ACT and signed-off work are properly protected.
--
-- WHAT WAS OPEN: the request awaiting review. A worker rewrote ANOTHER worker's PENDING change
-- order from PHP 500,000 to PHP 9,999,999 and replaced its scope text, and the row still read
-- `requested_by = Wilfredo Malabanan`. A worker could also DELETE a pending order outright.
--
-- WHY THAT IS THE WORST PLACE FOR IT TO BE OPEN. A change order is a contract amendment. The
-- supervisor approves WHAT THEY ARE SHOWN, and what they are shown was editable by anyone in the
-- hive right up to the moment they clicked. There is no auth_uid on this table (G1) and `projects`
-- writes nothing to hive_audit_log (G2), so nothing recorded that the number changed or who
-- changed it. The approval guard is sound and was simply guarding the wrong end.
--
-- THE LEGITIMATE CALLERS WERE MEASURED BEFORE TIGHTENING, because twice in the previous arc the
-- obvious guard would have broken more than the bug. There are exactly THREE update paths on this
-- table in the entire codebase — approveCO, rejectCO, cancelCO — and all three set `status` plus
-- the approver fields, nothing else. There is NO edit-CO path anywhere (`editCO` / `openEditCO` /
-- `updateCO` = 0 matches), and NO delete path in any page or edge function.
--
-- So the commercial terms are already write-once in practice. This makes the database agree:
-- immutability is a stronger and simpler guarantee than a role check, and it breaks zero callers.
-- A mistaken order is CANCELLED and re-raised, which leaves the original visible — exactly what an
-- amendment trail should do.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.guard_change_order_terms_immutable()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
BEGIN
  -- service_role / seeders / migrations keep their reach, as everywhere else in these arcs.
  IF auth.uid() IS NULL THEN
    RETURN COALESCE(NEW, OLD);
  END IF;

  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'A change order cannot be deleted (%). Cancel it instead so the request stays '
                    'visible in the amendment trail.', OLD.co_number
      USING ERRCODE = 'check_violation';
  END IF;

  -- The commercial terms of a raised order. Status, the approver fields and the rejection reason
  -- are deliberately NOT here: moving the order through its lifecycle is the whole point, and
  -- wh_guard_supervisor_approval already decides WHO may do that.
  IF NEW.co_number            IS DISTINCT FROM OLD.co_number
     OR NEW.title             IS DISTINCT FROM OLD.title
     OR NEW.scope_change      IS DISTINCT FROM OLD.scope_change
     OR NEW.reason            IS DISTINCT FROM OLD.reason
     OR NEW.cost_impact_php   IS DISTINCT FROM OLD.cost_impact_php
     OR NEW.schedule_impact_days IS DISTINCT FROM OLD.schedule_impact_days
     OR NEW.requested_by      IS DISTINCT FROM OLD.requested_by
     OR NEW.project_id        IS DISTINCT FROM OLD.project_id
     OR NEW.hive_id           IS DISTINCT FROM OLD.hive_id
  THEN
    RAISE EXCEPTION 'The terms of change order % are fixed once it is raised (cost, schedule, scope, '
                    'title and requester). Cancel it and raise a replacement so the original stays '
                    'on record.', OLD.co_number
      USING ERRCODE = 'check_violation';
  END IF;

  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_change_order_terms_immutable ON public.project_change_orders;
CREATE TRIGGER trg_change_order_terms_immutable
  BEFORE UPDATE OR DELETE ON public.project_change_orders
  FOR EACH ROW
  EXECUTE FUNCTION public.guard_change_order_terms_immutable();

COMMENT ON FUNCTION public.guard_change_order_terms_immutable() IS
  'A change order is a contract amendment: once raised, its cost, schedule, scope, title and '
  'requester are fixed, and it cannot be deleted (cancel instead). Status and the approver fields '
  'stay mutable so the lifecycle still works, with wh_guard_supervisor_approval deciding who may '
  'move it. Added after the PJ4 walk showed a worker rewriting another worker''s pending order from '
  'PHP 500,000 to PHP 9,999,999 with the original requester''s name still on it. PJ4/PJK1.';
