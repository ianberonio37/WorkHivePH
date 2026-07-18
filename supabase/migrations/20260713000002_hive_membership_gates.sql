-- 20260713000002_hive_membership_gates.sql
--
-- Two HIGH multi-tenant membership holes — bug-hunt 2026-07-13, hive.html P5.
--
-- P5-01  SELF-JOIN ANY HIVE (cross-tenant access). hive_members_insert WITH CHECK was only
--        (auth.uid() IS NOT NULL AND auth_uid=auth.uid() AND (role<>'supervisor' OR NOT
--        hive_has_other_members)) — NO invite-code / approval / prior-membership predicate. The
--        6-char code was verified ONLY client-side (find_hive_by_code lookup then a direct client
--        INSERT). LIVE-CONFIRMED (rolled-back): leandromarquez (Baguio) POSTed {hive_id:<Lucena>,
--        auth_uid:self, role:'worker', status:'active'} -> 201, then read Lucena's 6-member roster
--        (was 0 as a non-member). Any authed user with a hive_id UUID could join any tenant as an
--        active worker and read its data.
--
-- P5-02  KICKED WORKER SELF-RESTORE. hive_members_delete USING was (auth_uid=auth.uid()) with no
--        status guard, so a kicked worker could DELETE their own 'kicked' row (204) and then
--        re-INSERT status='active' (201) — defeating kickMember()'s "cannot rejoin unless a
--        supervisor re-approves" promise entirely, with zero supervisor action.
--
-- FIX
--  (1) join_hive_by_code(p_code, p_worker_name) SECURITY DEFINER RPC: re-resolves the invite code
--      server-side, refuses a kicked identity, is idempotent for an existing active member, and
--      inserts the membership bound to auth.uid() — so the code is now a real server-enforced secret.
--  (2) Narrow hive_members_insert to the FOUNDER path only (create a brand-new EMPTY hive as its
--      supervisor). Every worker join now goes through the RPC (DEFINER, bypasses RLS); a raw
--      PostgREST self-insert into an arbitrary hive is refused.
--  (3) Make a 'kicked' row STICKY: forbid self-DELETE of a kicked row, so UNIQUE(hive_id,worker_name)
--      then blocks any self re-insert; reactivation must go through the supervisor-only UPDATE policy.
--      Active members can still leave (self-delete) normally.

BEGIN;

-- (1) server-verified join ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.join_hive_by_code(p_code text, p_worker_name text)
RETURNS TABLE(hive_id uuid, hive_name text, member_status text)
LANGUAGE plpgsql
VOLATILE
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $fn$
DECLARE
  v_uid      uuid := auth.uid();
  v_hive     public.hives%ROWTYPE;
  v_existing public.hive_members%ROWTYPE;
BEGIN
  IF v_uid IS NULL THEN
    RAISE EXCEPTION 'HIVE_JOIN_UNAUTHENTICATED';
  END IF;
  IF p_worker_name IS NULL OR btrim(p_worker_name) = '' THEN
    RAISE EXCEPTION 'HIVE_JOIN_NO_WORKER_NAME';
  END IF;

  SELECT * INTO v_hive FROM public.hives WHERE invite_code = p_code;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'HIVE_CODE_NOT_FOUND';
  END IF;

  -- existing membership for THIS auth identity in the resolved hive
  SELECT * INTO v_existing
  FROM public.hive_members
  WHERE public.hive_members.hive_id = v_hive.id AND auth_uid = v_uid
  LIMIT 1;

  IF FOUND THEN
    IF v_existing.status = 'kicked' THEN
      RAISE EXCEPTION 'HIVE_MEMBER_KICKED';
    END IF;
    RETURN QUERY SELECT v_hive.id, v_hive.name, v_existing.status;  -- already a member: idempotent
    RETURN;
  END IF;

  -- defense in depth: block reviving a kicked row that exists under the same worker_name
  -- (e.g. a legacy/other auth_uid) — the ban is by (hive, worker_name), not just auth identity.
  IF EXISTS (SELECT 1 FROM public.hive_members
             WHERE public.hive_members.hive_id = v_hive.id
               AND worker_name = p_worker_name AND status = 'kicked') THEN
    RAISE EXCEPTION 'HIVE_MEMBER_KICKED';
  END IF;

  INSERT INTO public.hive_members (hive_id, worker_name, role, status, auth_uid)
  VALUES (v_hive.id, p_worker_name, 'worker', 'active', v_uid);

  RETURN QUERY SELECT v_hive.id, v_hive.name, 'active'::text;
END;
$fn$;

REVOKE ALL ON FUNCTION public.join_hive_by_code(text, text) FROM public;
GRANT EXECUTE ON FUNCTION public.join_hive_by_code(text, text) TO authenticated;

-- (2) founder-only direct INSERT ---------------------------------------------------------------
DROP POLICY IF EXISTS hive_members_insert ON public.hive_members;
CREATE POLICY hive_members_insert ON public.hive_members
  FOR INSERT
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND auth_uid = auth.uid()
    AND role = 'supervisor'
    AND status = 'active'
    AND NOT public.hive_has_other_members(hive_id)
  );

-- (3) sticky kicked row (block self-delete of a kicked membership) ------------------------------
DROP POLICY IF EXISTS hive_members_delete ON public.hive_members;
CREATE POLICY hive_members_delete ON public.hive_members
  FOR DELETE
  USING (
    auth.uid() IS NOT NULL
    AND auth_uid = auth.uid()
    AND status <> 'kicked'
  );

COMMIT;
