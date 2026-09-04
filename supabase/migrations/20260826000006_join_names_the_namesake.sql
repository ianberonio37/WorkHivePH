-- T185 (2026-08-26): two different people who share a name could not both join a hive, and the
-- second one was shown a Postgres error.
--
-- THE DAY-ONE SCENARIO: a plant pilots WorkHive. Five workers are handed one invite code at the
-- morning briefing. Two of them are named Juan Dela Cruz - which in a Philippine plant is not a
-- contrived edge case, it is Tuesday. The first one joins. The second, a different human being
-- with a different auth identity and the correct code, hit:
--
--   duplicate key value violates unique constraint "hive_members_hive_id_worker_name_key"
--
-- and hive.html rendered it verbatim ('Could not join: ' + joinErr.message). He could not join his
-- team, he was shown database internals, and he was offered no way forward.
--
-- ★THE CONSTRAINT IS RIGHT AND STAYS. worker_name is the attribution key across many tables; two
-- members sharing one name inside a hive would make every by-name rollup ambiguous. The defect was
-- never the constraint - it was that the function let the constraint speak to the user directly.
--
-- ★TWO CASES PRODUCE THE IDENTICAL 23505 AND MUST NOT GET THE SAME ANSWER:
--   1. a genuine NAMESAKE - a different auth identity - who needs a distinguishing name;
--   2. the SAME user double-tapping Join, where two concurrent calls both read no membership
--      (READ COMMITTED - neither sees the other's uncommitted insert) and both insert. The
--      function's idempotent 'already a member' path is bypassed by that race, so the loser used
--      to surface the same raw error. The right answer there is simply "you are in".
-- Telling them apart requires re-reading the row AFTER the violation, which is what the exception
-- handler below does: if the winning row is this caller's own, the race resolved to success.
--
-- Re-drive: the join is exercised by tools/validate_join_names_the_namesake.py.

CREATE OR REPLACE FUNCTION public.join_hive_by_code(p_code text, p_worker_name text)
 RETURNS TABLE(hive_id uuid, hive_name text, member_status text)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_uid      uuid := auth.uid();
  v_hive     public.hives%ROWTYPE;
  v_existing public.hive_members%ROWTYPE;
  v_winner   public.hive_members%ROWTYPE;
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
  -- (e.g. a legacy/other auth_uid) - the ban is by (hive, worker_name), not just auth identity.
  IF EXISTS (SELECT 1 FROM public.hive_members
             WHERE public.hive_members.hive_id = v_hive.id
               AND worker_name = p_worker_name AND status = 'kicked') THEN
    RAISE EXCEPTION 'HIVE_MEMBER_KICKED';
  END IF;

  -- T185: a namesake already holds this name in this hive. Refuse BY NAME so the page can explain
  -- it and offer a distinguishing name, rather than letting the unique index answer the user.
  IF EXISTS (SELECT 1 FROM public.hive_members
             WHERE public.hive_members.hive_id = v_hive.id
               AND worker_name = p_worker_name) THEN
    RAISE EXCEPTION 'HIVE_NAME_TAKEN';
  END IF;

  BEGIN
    INSERT INTO public.hive_members (hive_id, worker_name, role, status, auth_uid)
    VALUES (v_hive.id, p_worker_name, 'worker', 'active', v_uid);
  EXCEPTION WHEN unique_violation THEN
    -- Lost a race on (hive_id, worker_name). WHO won decides what this means.
    SELECT * INTO v_winner
    FROM public.hive_members
    WHERE public.hive_members.hive_id = v_hive.id AND worker_name = p_worker_name
    LIMIT 1;

    IF v_winner.auth_uid = v_uid THEN
      -- Our own concurrent call landed first: this is a double-tap, and the honest answer is
      -- the same one the sequential path gives - you are already in.
      IF v_winner.status = 'kicked' THEN
        RAISE EXCEPTION 'HIVE_MEMBER_KICKED';
      END IF;
      RETURN QUERY SELECT v_hive.id, v_hive.name, v_winner.status;
      RETURN;
    END IF;

    -- A different person took the name between our check and our insert.
    RAISE EXCEPTION 'HIVE_NAME_TAKEN';
  END;

  RETURN QUERY SELECT v_hive.id, v_hive.name, 'active'::text;
END;
$function$;
