-- The undo was the one asset decision nobody could see.
--
-- WHAT IS WRONG. `audit_asset_approval_decision()` is the authoritative, server-side writer of the asset
-- approval trail - it resolves the acting identity from hive_members rather than trusting the
-- client-supplied `approved_by`, and its own comment says so. But it returns early unless
-- `NEW.status IN ('approved','rejected')`. asset-hub.html ships a supervisor control labelled "Restore
-- to pending" (`data-action="asset-restore"`, `restoreAssetNode`) that writes
-- `status='pending', approved_by=null, approved_at=null`. That write matches neither branch, so it
-- produces NO audit row at all.
--
-- The consequence is not a missing nicety. A rejection can be undone and the trail shows only the
-- rejection; the record says a decision was made and never says it was reversed, by whom, or when. On a
-- surface whose whole purpose is that a supervisor's decisions are attributable, the one action that
-- CANCELS a decision is the one action that leaves no trace.
--
-- This is recorded rather than invented: asset-hub.html:1771-1775 already says it, in the code, at the
-- exact call site - "The AFTER-UPDATE trigger is the authoritative writer for approved and rejected;
-- extending it to cover a restore to `pending` is a migration, so it is recorded rather than worked
-- around here." A client-side audit call used to stand there and was removed because it named the asset
-- from a list that holds approved nodes only, so every restore row identified the asset by a bare UUID.
-- Removing it was right; this is the other half.
--
-- WHAT CHANGES. One guard and one action name. The function keeps everything else exactly as it is: the
-- hive-less early return that stops a solo user's own edit being aborted by an audit insert, the
-- server-resolved actor, and the meta that records the claimed approver separately from the identity
-- that actually wrote, so a mismatch stays visible.
--
--   approved -> pending   and   rejected -> pending     now write `restore_asset_node`
--
-- `status_was` and `status_now` already ride in the meta, so the trail says which decision was undone.
-- The restore path nulls approved_by and approved_at, so `approved_by_claimed` is null on these rows -
-- which is the truth about a write that clears them.
--
-- Idempotent: CREATE OR REPLACE of the function the existing trigger already calls. No trigger is
-- created, dropped or re-pointed.

CREATE OR REPLACE FUNCTION public.audit_asset_approval_decision()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_actor text;
BEGIN
  -- SOLO lane (2026-09-02, VM7 walk): hive_audit_log.hive_id is NOT NULL and its audience
  -- is the hive. A hive-less row has neither; without this early return the audit INSERT
  -- ABORTS the user's own edit (proven live per-fn in rolled-back probes).
  IF NEW.hive_id IS NULL THEN
    RETURN NEW;
  END IF;

  -- Only the moment a submission is DECIDED - or the moment a decision is UNDONE. The restore to
  -- 'pending' is the third of those three moments and was the only one that wrote nothing (2026-09-15).
  IF NEW.status IS NOT DISTINCT FROM OLD.status THEN
    RETURN NEW;
  END IF;

  IF NOT (
    NEW.status IN ('approved', 'rejected')
    OR (NEW.status = 'pending' AND OLD.status IN ('approved', 'rejected'))
  ) THEN
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
    CASE
      WHEN NEW.status = 'approved' THEN 'approve_asset_node'
      WHEN NEW.status = 'rejected' THEN 'reject_asset_node'
      ELSE 'restore_asset_node'
    END,
    'asset_nodes',
    NEW.id::text,
    COALESCE(NEW.tag, NEW.name, '(unnamed asset)'),
    jsonb_build_object(
      'status_was',       OLD.status,
      'status_now',       NEW.status,
      'rejection_reason', NEW.rejection_reason,
      'submitted_by',     NEW.submitted_by,
      -- Recorded separately from `actor` so a mismatch between the claimed approver and the
      -- identity that actually wrote is visible rather than silently reconciled. On a restore the
      -- write clears approved_by, so this is null - which is what happened.
      'approved_by_claimed', NEW.approved_by,
      'decided_by',       v_actor,
      'source',           'db_trigger'
    )
  );

  RETURN NEW;
END;
$function$;

COMMENT ON FUNCTION public.audit_asset_approval_decision() IS
  'Writes the hive_audit_log row for an asset approval decision AND for a restore to pending, which '
  'undoes one. The acting identity is resolved from hive_members server-side; approved_by is recorded '
  'separately as a claim. Hive-less rows return early so a solo user''s edit is never aborted by an '
  'audit insert.';
