-- ─────────────────────────────────────────────────────────────────────────────
-- An approval decision is the governance act. Record it where it cannot be bypassed.
--
-- FOUND BY THE AHK1 SWEEP (2026-07-28, ASSET_HUB_DEEPWALK_EXPANSION_ROADMAP):
-- 83 asset_nodes sit in a decided state (approved or rejected) and NOT ONE of those decisions is
-- recorded anywhere. Measured: 11 approve/reject rows exist in hive_audit_log, every one of them
-- CLIENT-written, and zero with target_type='asset_nodes'.
--
-- A client-written audit row is skipped by any write that does not go through the page — and AH3
-- proved that path is reachable, not hypothetical: before 20260728000013 a worker could set their
-- own submission to 'rejected' straight through the db client, writing the reviewer's
-- rejection_reason with it, and nothing would have been recorded. The guard now refuses that, but
-- refusal and evidence are different jobs: the guard says who MAY decide, and this says who DID.
--
-- Same shape as trg_pm_completion_amendment_audit (PM11) and trg_pm_asset_delete_audit (PM12): the
-- DATABASE writes the row, so it is present regardless of which client performed the write.
--
-- SCOPE. Fires only on a transition INTO a reviewer state — the moment a submission is decided.
-- An edit to an already-approved asset's location or criticality is not a governance decision and
-- does not belong in this trail; that keeps the log readable enough to actually be audited, the same
-- scoping judgement the PM completion trigger makes.
--
-- WHAT IT RECORDS, and why each field earns its place:
--   status_was / status_now  the decision itself
--   rejection_reason         the reviewer's stated reason — the sentence the submitter is owed
--   submitted_by             who is affected by the decision
--   decided_by               resolved from auth.uid() via hive_members, NOT from the client-supplied
--                            approved_by TEXT column, which is forgeable (the other half of AHK1)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.audit_asset_approval_decision()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_actor text;
BEGIN
  -- Only the moment a submission is DECIDED.
  IF NEW.status IS NOT DISTINCT FROM OLD.status
     OR NEW.status NOT IN ('approved', 'rejected') THEN
    RETURN NEW;
  END IF;

  -- The deciding identity, resolved server-side. approved_by is a client-supplied TEXT name and
  -- cannot be trusted to say who actually performed the write.
  SELECT hm.worker_name INTO v_actor
    FROM public.hive_members hm
   WHERE hm.auth_uid = auth.uid()
     AND (NEW.hive_id IS NULL OR hm.hive_id = NEW.hive_id)
   LIMIT 1;

  INSERT INTO public.hive_audit_log (hive_id, actor, action, target_type, target_id, target_name, meta)
  VALUES (
    NEW.hive_id,
    COALESCE(v_actor, 'unknown'),
    CASE WHEN NEW.status = 'approved' THEN 'approve_asset_node' ELSE 'reject_asset_node' END,
    'asset_nodes',
    NEW.id::text,
    COALESCE(NEW.tag, NEW.name, '(unnamed asset)'),
    jsonb_build_object(
      'status_was',       OLD.status,
      'status_now',       NEW.status,
      'rejection_reason', NEW.rejection_reason,
      'submitted_by',     NEW.submitted_by,
      -- Recorded separately from `actor` so a mismatch between the claimed approver and the
      -- identity that actually wrote is visible rather than silently reconciled.
      'approved_by_claimed', NEW.approved_by,
      'decided_by',       v_actor,
      'source',           'db_trigger'
    )
  );

  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_asset_approval_decision_audit ON public.asset_nodes;
CREATE TRIGGER trg_asset_approval_decision_audit
  AFTER UPDATE ON public.asset_nodes
  FOR EACH ROW
  EXECUTE FUNCTION public.audit_asset_approval_decision();
