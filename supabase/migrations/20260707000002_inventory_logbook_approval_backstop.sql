-- ============================================================================
-- Extend the supervisor-approval backstop to inventory_items + logbook
-- (deep-walk dim-2, 2026-07-07 -- same class as 20260707000000).
--
-- CONFIRMED EXPLOIT: a worker (Bryan) self-approved an inventory_items row (status='approved',
-- approved_by/at) via direct RLS -- inventory_items_write is `auth_uid=auth.uid() OR active
-- member`, no role. logbook work-order transitions into supervisor states
-- (approved/assigned/verified/rejected) via `wo_state` are likewise UI-only.
--
-- The shared guard reads columns via to_jsonb so ONE function serves every shape. This migration
-- CREATE OR REPLACEs it to ALSO guard `wo_state` transitions into the four supervisor states, then
-- attaches the trigger to inventory_items + logbook. Worker-legit wo_states (requested/in_progress/
-- done) and non-approval edits pass through untouched; service-role (auth.uid() null) is exempt.
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
  sup_states text[] := ARRAY['approved','assigned','verified','rejected'];
  privileged boolean := false;
BEGIN
  IF auth.uid() IS NULL THEN                       -- backend/service-role: RLS already authorized
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
  END IF;

  IF TG_OP = 'INSERT' THEN
    privileged := (jnew ->> 'approved_at') IS NOT NULL
               OR (jnew ->> 'approved_by') IS NOT NULL
               OR (jnew ->> 'status') = 'approved'
               OR (jnew ->> 'wo_state') = ANY (sup_states);
  ELSIF TG_OP = 'UPDATE' THEN
    privileged := ((jnew ->> 'approved_at') IS DISTINCT FROM (jold ->> 'approved_at'))
               OR ((jnew ->> 'approved_by') IS DISTINCT FROM (jold ->> 'approved_by'))
               OR ( (jnew ->> 'status') IS DISTINCT FROM (jold ->> 'status')
                    AND ((jnew ->> 'status') = 'approved' OR (jold ->> 'status') = 'approved') )
               OR ( (jnew ->> 'wo_state') IS DISTINCT FROM (jold ->> 'wo_state')
                    AND (jnew ->> 'wo_state') = ANY (sup_states) );
  ELSE  -- DELETE: protect signed-off work from member deletion (data loss).
    privileged := (jold ->> 'approved_at') IS NOT NULL
               OR (jold ->> 'status') = 'approved'
               OR (jold ->> 'wo_state') IN ('approved','verified');
  END IF;

  IF privileged AND h IS NOT NULL AND h NOT IN (SELECT public.user_supervisor_hive_ids()) THEN
    RAISE EXCEPTION 'Supervisor role required to approve/assign/verify or remove signed-off work (user %, hive %)', auth.uid(), h
      USING ERRCODE = '42501';
  END IF;

  RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$;

DROP TRIGGER IF EXISTS tg_guard_approval ON public.inventory_items;
CREATE TRIGGER tg_guard_approval
  BEFORE INSERT OR UPDATE OR DELETE ON public.inventory_items
  FOR EACH ROW EXECUTE FUNCTION public.wh_guard_supervisor_approval();

DROP TRIGGER IF EXISTS tg_guard_approval ON public.logbook;
CREATE TRIGGER tg_guard_approval
  BEFORE INSERT OR UPDATE OR DELETE ON public.logbook
  FOR EACH ROW EXECUTE FUNCTION public.wh_guard_supervisor_approval();
