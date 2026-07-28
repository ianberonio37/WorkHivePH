-- ─────────────────────────────────────────────────────────────────────────────
-- Rejecting is a reviewer's act too. Guard it like approving.
--
-- FOUND BY THE AH3 WALK (2026-07-28, ASSET_HUB_DEEPWALK_EXPANSION_ROADMAP):
-- `wh_guard_supervisor_approval` correctly refuses a non-supervisor who approves — probed live, a
-- worker approving their OWN pending asset is rejected 42501 with a message naming the user and
-- hive. That half is well built and stays exactly as it is.
--
-- But its UPDATE clause treats a status change as privileged only when 'approved' is on one side:
--
--     OR ( status IS DISTINCT FROM old.status
--          AND (new.status = 'approved' OR old.status = 'approved') )
--
-- so **pending -> rejected slips through**, because neither side is 'approved'. ('rejected' does
-- appear in `sup_states`, but that array is only consulted for the `wo_state` column.)
--
-- REACHABLE, not theoretical. asset-hub's own reject happens to be caught, because it also writes
-- `approved_by`/`approved_at` and the guard notices those. hive.html's `rejectItem(table, id, ...)`
-- does NOT — it updates `{ status: 'rejected' }` alone, gated only by a client-side
-- `if (HIVE_ROLE !== 'supervisor')`. Probed live: a WORKER set their own pending asset to
-- 'rejected' and wrote `rejection_reason` = "Rejected by the supervisor - not fit for the register."
-- 1 row, no error.
--
-- WHY IT MATTERS BEYOND THE ROW: `rejection_reason` is the REVIEWER'S VOICE. The asset-hub queue
-- renders it to the submitter as "**Why:** <reason>", and the PDDA arc added it precisely so a
-- rejection would explain itself. A submitter who can write that field can author a verdict in a
-- supervisor's name — and the next supervisor reading the queue cannot tell.
--
-- ONE CLAUSE, SIX TABLES. This guard is attached to asset_nodes, inventory_items, logbook,
-- project_change_orders, rcm_fmea_modes and rcm_strategies, so the same hole existed on every
-- approval queue the platform has. Fixing it centrally closes them together.
--
-- SAFE TO TIGHTEN, measured before applying: both legitimate reject paths (asset-hub and hive.html)
-- are already supervisor-only in their UI, so no non-supervisor flow depends on this; and
-- service_role / the seeders are exempt via the existing `auth.uid() IS NULL` early return.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.wh_guard_supervisor_approval()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
DECLARE
  jnew jsonb := CASE WHEN TG_OP = 'DELETE' THEN NULL ELSE to_jsonb(NEW) END;
  jold jsonb := CASE WHEN TG_OP = 'INSERT' THEN NULL ELSE to_jsonb(OLD) END;
  h uuid := (COALESCE(jnew, jold) ->> 'hive_id')::uuid;
  sup_states text[] := ARRAY['approved','assigned','verified','rejected'];
  -- The states only a REVIEWER may put a submission into. Approving and refusing are the same
  -- authority exercised two ways; the guard used to recognise only the first.
  reviewer_states text[] := ARRAY['approved','rejected'];
  privileged boolean := false;
BEGIN
  IF auth.uid() IS NULL THEN                       -- backend/service-role: RLS already authorized
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
  END IF;

  IF TG_OP = 'INSERT' THEN
    privileged := (jnew ->> 'approved_at') IS NOT NULL
               OR (jnew ->> 'approved_by') IS NOT NULL
               OR (jnew ->> 'status') = ANY (reviewer_states)
               OR (jnew ->> 'wo_state') = ANY (sup_states);
  ELSIF TG_OP = 'UPDATE' THEN
    privileged := ((jnew ->> 'approved_at') IS DISTINCT FROM (jold ->> 'approved_at'))
               OR ((jnew ->> 'approved_by') IS DISTINCT FROM (jold ->> 'approved_by'))
               OR ( (jnew ->> 'status') IS DISTINCT FROM (jold ->> 'status')
                    AND ( (jnew ->> 'status') = ANY (reviewer_states)
                          OR (jold ->> 'status') = ANY (reviewer_states) ) )
               -- The reviewer's written verdict is theirs to write.
               OR ((jnew ->> 'rejection_reason') IS DISTINCT FROM (jold ->> 'rejection_reason'))
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
$function$;
