-- ============================================================================
-- Server-side supervisor backstop for the "worker submits pending -> supervisor
-- approves" governance gate (deep-walk dim-2, 2026-07-07).
--
-- FOUND LIVE (confirmed exploit): a non-supervisor member self-approved an
-- rcm_fmea_modes row via a direct PostgREST/RLS UPDATE (set approved_by/approved_at)
-- because the write policies gate on hive MEMBERSHIP only, never on role='supervisor'.
-- The supervisor sign-off was enforced in the UI (asset-hub.html) ONLY. The same
-- gap exists on rcm_strategies and asset_nodes (owner branch lets the submitting
-- worker flip status='approved' + approved_at on their own row, injecting unvetted
-- equipment/reliability into the canonical registry that feeds Predictive / Alert
-- Hub / Analytics). This is a broken-access-control / governance bypass (intra-tenant).
--
-- FIX: a BEFORE INSERT/UPDATE/DELETE trigger that requires the caller to be an
-- ACTIVE SUPERVISOR of the row's hive whenever the write SETS/CHANGES an approval
-- (approved_at, approved_by, or status -> 'approved') or DELETES an already-approved
-- row. The UI role-gate stays as defense-in-depth. Columns are read via to_jsonb(row)
-- so ONE function serves tables with a `status` column (asset_nodes) and without
-- (rcm_fmea_modes, rcm_strategies). Service-role / backend writes carry no JWT
-- subject (auth.uid() IS NULL) and are exempt -- RLS already vetted them.
-- ============================================================================

CREATE OR REPLACE FUNCTION public.wh_guard_supervisor_approval()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  jnew jsonb := CASE WHEN TG_OP = 'DELETE' THEN NULL ELSE to_jsonb(NEW) END;
  jold jsonb := CASE WHEN TG_OP = 'INSERT' THEN NULL ELSE to_jsonb(OLD) END;
  h uuid := (COALESCE(jnew, jold) ->> 'hive_id')::uuid;
  privileged boolean := false;
BEGIN
  -- Backend / service-role writes have no JWT subject; RLS already authorized them.
  IF auth.uid() IS NULL THEN
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
  END IF;

  IF TG_OP = 'INSERT' THEN
    -- Creating a row that is ALREADY approved is a privileged action.
    privileged := (jnew ->> 'approved_at') IS NOT NULL
               OR (jnew ->> 'approved_by') IS NOT NULL
               OR (jnew ->> 'status') = 'approved';
  ELSIF TG_OP = 'UPDATE' THEN
    -- Any change to the approval columns (either direction) is a privileged action.
    privileged := ((jnew ->> 'approved_at') IS DISTINCT FROM (jold ->> 'approved_at'))
               OR ((jnew ->> 'approved_by') IS DISTINCT FROM (jold ->> 'approved_by'))
               OR ( (jnew ->> 'status') IS DISTINCT FROM (jold ->> 'status')
                    AND ((jnew ->> 'status') = 'approved' OR (jold ->> 'status') = 'approved') );
  ELSE  -- DELETE: protect signed-off (approved) work from member deletion (data loss).
    privileged := (jold ->> 'approved_at') IS NOT NULL OR (jold ->> 'status') = 'approved';
  END IF;

  IF privileged AND h IS NOT NULL AND h NOT IN (SELECT public.user_supervisor_hive_ids()) THEN
    RAISE EXCEPTION 'Supervisor role required to approve, un-approve, or remove signed-off work (user %, hive %)', auth.uid(), h
      USING ERRCODE = '42501';  -- insufficient_privilege
  END IF;

  RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$;

COMMENT ON FUNCTION public.wh_guard_supervisor_approval() IS
  'deep-walk dim-2 backstop: approval-column writes (approved_at/approved_by/status=approved) and deletes of approved rows require active-supervisor of the row hive; service-role (auth.uid() null) exempt. Attached to rcm_fmea_modes, rcm_strategies, asset_nodes.';

DROP TRIGGER IF EXISTS tg_guard_approval ON public.rcm_fmea_modes;
CREATE TRIGGER tg_guard_approval
  BEFORE INSERT OR UPDATE OR DELETE ON public.rcm_fmea_modes
  FOR EACH ROW EXECUTE FUNCTION public.wh_guard_supervisor_approval();

DROP TRIGGER IF EXISTS tg_guard_approval ON public.rcm_strategies;
CREATE TRIGGER tg_guard_approval
  BEFORE INSERT OR UPDATE OR DELETE ON public.rcm_strategies
  FOR EACH ROW EXECUTE FUNCTION public.wh_guard_supervisor_approval();

DROP TRIGGER IF EXISTS tg_guard_approval ON public.asset_nodes;
CREATE TRIGGER tg_guard_approval
  BEFORE INSERT OR UPDATE OR DELETE ON public.asset_nodes
  FOR EACH ROW EXECUTE FUNCTION public.wh_guard_supervisor_approval();
