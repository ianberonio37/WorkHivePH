-- 20260622000000_fix_hive_members_update_recursion.sql
-- ============================================================================
-- FIX (Arc K K3 caught it live): a supervisor cannot REMOVE (kick) / change the
-- role/status of a hive member — every such UPDATE returns HTTP 500:
--   "infinite recursion detected in policy for relation hive_members"
--
-- ROOT CAUSE: the `hive_members_update` RLS policy checks "is the caller an active
-- supervisor of this hive" by sub-querying hive_members INSIDE the hive_members
-- policy. Postgres re-applies the policy to that inner read → infinite recursion.
-- Arc G fixed this class for the SELECT/permissive policies via the SECURITY DEFINER
-- helper user_hive_ids() (which bypasses RLS on the inner read), but the UPDATE
-- policy still self-referenced and was missed.
--
-- FIX: add a role-aware DEFINER helper user_supervisor_hive_ids() (twin of
-- user_hive_ids(), filtered to role='supervisor'), and rewrite the UPDATE policy to
-- use it — the DEFINER function reads hive_members with RLS bypassed, breaking the
-- recursion while preserving the exact same authorization (active supervisor of the
-- target row's hive). Non-breaking: the allowed set is identical to the intended
-- policy; it just no longer recurses.
-- ============================================================================

-- role-aware membership helper (DEFINER → bypasses RLS on the inner read = no recursion)
CREATE OR REPLACE FUNCTION public.user_supervisor_hive_ids()
  RETURNS SETOF uuid
  LANGUAGE sql
  STABLE
  SECURITY DEFINER
  SET search_path TO 'public'
AS $function$
  select hive_id from hive_members
  where auth_uid = auth.uid() and role = 'supervisor' and status = 'active'
$function$;

REVOKE ALL ON FUNCTION public.user_supervisor_hive_ids() FROM public;
GRANT EXECUTE ON FUNCTION public.user_supervisor_hive_ids() TO authenticated, service_role;

-- recursion-free UPDATE policy: an active supervisor may update members of their hive
DROP POLICY IF EXISTS hive_members_update ON public.hive_members;
CREATE POLICY hive_members_update ON public.hive_members
  FOR UPDATE
  USING (
    auth.uid() IS NOT NULL
    AND hive_id IN (SELECT public.user_supervisor_hive_ids())
  );
