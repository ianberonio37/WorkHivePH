-- T185/T62 (2026-08-26): a rename may only happen while there is no history to orphan.
--
-- WHY THIS TIGHTENS A FUNCTION ADDED HOURS AGO. 20260826000007 introduced set_worker_display_name so
-- a second Juan Dela Cruz could join under a distinguishing name, and it moves the profile and every
-- hive_members row in one transaction - which is right, and is NOT ENOUGH. worker_name is a
-- denormalised attribution label copied across the schema, and the rename does not follow it:
--
--   MEASURED for a single real worker (2026-08-26):
--     648 rows in tables that ALSO carry auth_uid  - logbook 517, voice_journal 125, schedule 6
--     933 rows in tables where the NAME IS THE ONLY LINK - achievement_xp_log 267, fault_knowledge
--         517, ai_cost_log 140, project_roles 4, skill_knowledge 4, marketplace_platform_admins 1
--   47 tables carry worker_name at all: 28 with auth_uid, 19 without.
--
-- ★THE 19 ARE WHY A GENERAL RENAME IS NOT IMPLEMENTABLE HERE, not merely expensive.
-- achievement_xp_log has NEITHER auth_uid NOR hive_id, so its 267 rows cannot be located for this
-- person at all: matching on the old name alone would sweep up a DIFFERENT worker who answers to the
-- same name in another hive - the very collision this whole arc exists to handle. Renaming anyway
-- would leave ~1,581 rows attributed to a name their owner no longer has, and because the reads
-- filter by worker_name (118 call sites), that worker's own history would simply vanish from their
-- screens, XP and standings included.
--
-- ★SO THE RENAME IS RESTRICTED TO WHEN IT IS SAFE, which is also exactly when it is needed: a worker
-- joining their FIRST hive has no history to orphan. That is the day-one scenario the namesake fix
-- was built for - five workers onboarding together, two sharing a name. Anyone who is already a
-- member somewhere may have accumulated records, so they are refused BY NAME with a reason instead
-- of being silently disconnected from their own work.
--
-- A real rename-with-history is a data migration and a product decision (it needs auth_uid
-- backfilled onto the 19, or an identity join the reads actually use). Recorded, not smuggled in.

CREATE OR REPLACE FUNCTION public.set_worker_display_name(p_name text)
 RETURNS text
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_uid       uuid := auth.uid();
  v_name      text := btrim(coalesce(p_name, ''));
  v_memberships int;
BEGIN
  IF v_uid IS NULL THEN
    RAISE EXCEPTION 'HIVE_JOIN_UNAUTHENTICATED';
  END IF;
  IF v_name = '' THEN
    RAISE EXCEPTION 'HIVE_JOIN_NO_WORKER_NAME';
  END IF;

  -- Already a member somewhere: they may have records under the current name, and this function
  -- cannot move all of them (see the header). Refuse rather than orphan.
  SELECT count(*) INTO v_memberships
  FROM public.hive_members WHERE auth_uid = v_uid;

  IF v_memberships > 0 THEN
    RAISE EXCEPTION 'HIVE_NAME_HAS_HISTORY';
  END IF;

  -- Someone else already answers to this name in a hive we share.
  IF EXISTS (
    SELECT 1 FROM public.hive_members other
    WHERE other.worker_name = v_name
      AND other.auth_uid IS DISTINCT FROM v_uid
      AND other.hive_id IN (SELECT hm.hive_id FROM public.hive_members hm WHERE hm.auth_uid = v_uid)
  ) THEN
    RAISE EXCEPTION 'HIVE_NAME_TAKEN';
  END IF;

  UPDATE public.worker_profiles SET display_name = v_name WHERE auth_uid = v_uid;
  UPDATE public.hive_members    SET worker_name  = v_name WHERE auth_uid = v_uid;

  RETURN v_name;
END;
$function$;

REVOKE ALL ON FUNCTION public.set_worker_display_name(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.set_worker_display_name(text) TO authenticated;
