-- T185 (2026-08-26): renaming a worker has to move the profile AND every membership at once.
--
-- WHY THIS EXISTS: the namesake fix (20260826000006) lets a second Juan Dela Cruz join under a
-- distinguishing name. Writing that name only into hive_members would have been WORSE than the
-- bug it fixed. utils.js restoreIdentityFromSession() reconciles the cached worker name from
-- v_worker_truth.worker_name - which is worker_profiles.display_name - on every identity restore,
-- so a hive-only rename is reverted on the next page load, and from then on this person's writes
-- carry "Juan Dela Cruz", which in that hive is SOMEBODY ELSE. A cross-attribution between two
-- real people is a worse outcome than a refused join.
--
-- ★THE INVARIANT IS REAL AND MEASURED: 18 linked members, 0 rows where hive_members.worker_name
-- differs from the member's worker_profiles.display_name. The platform means what utils.js says -
-- "the name is the person, the fan-out is the membership" - so a rename must hold that, not break
-- it. This function is the only way to change a worker's name because it is the only way to change
-- it EVERYWHERE, in one transaction that either lands whole or not at all.
--
-- ★IT REFUSES RATHER THAN COLLIDES: if the new name is already held by a DIFFERENT person in any
-- hive this worker belongs to, it raises HIVE_NAME_TAKEN instead of letting the per-hive unique
-- index fail halfway through the update. The caller already knows how to explain that word.
--
-- Re-drive: covered by tools/validate_join_names_the_namesake.py (invariant assertion).

CREATE OR REPLACE FUNCTION public.set_worker_display_name(p_name text)
 RETURNS text
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_uid  uuid := auth.uid();
  v_name text := btrim(coalesce(p_name, ''));
BEGIN
  IF v_uid IS NULL THEN
    RAISE EXCEPTION 'HIVE_JOIN_UNAUTHENTICATED';
  END IF;
  IF v_name = '' THEN
    RAISE EXCEPTION 'HIVE_JOIN_NO_WORKER_NAME';
  END IF;

  -- Someone else already answers to this name in a hive we share: refuse by name rather than
  -- letting the unique index break the rename partway through.
  IF EXISTS (
    SELECT 1 FROM public.hive_members other
    WHERE other.worker_name = v_name
      AND other.auth_uid IS DISTINCT FROM v_uid
      AND other.hive_id IN (SELECT hm.hive_id FROM public.hive_members hm WHERE hm.auth_uid = v_uid)
  ) THEN
    RAISE EXCEPTION 'HIVE_NAME_TAKEN';
  END IF;

  -- One transaction, both halves: the person, and every membership that names them.
  UPDATE public.worker_profiles SET display_name = v_name WHERE auth_uid = v_uid;
  UPDATE public.hive_members    SET worker_name  = v_name WHERE auth_uid = v_uid;

  RETURN v_name;
END;
$function$;

REVOKE ALL ON FUNCTION public.set_worker_display_name(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.set_worker_display_name(text) TO authenticated;
