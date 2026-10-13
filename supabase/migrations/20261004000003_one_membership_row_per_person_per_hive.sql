-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- One membership row per person per hive, so the access gate can key on the IDENTITY (BRP-A)
-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- WHY THIS EXISTS. logbook.html's hive access gate asked `hive_members.worker_name = WORKER_NAME`, where
-- WORKER_NAME is localStorage text. A person whose display name had drifted from the one stored on their
-- membership row failed that check, the page gated them out, and the asset picker never loaded - which is
-- the real shape behind Ian's report of 2026-10-04 ("in the select an asset there is nothing there, but I
-- can see it in my asset hub"). The visible symptom was a thin dropdown; the actual symptom is being
-- locked out of your own hive. It surfaced as a prover that passed and failed on alternate runs, the
-- difference being only whether a hive was active - with no hive the check is skipped entirely.
--
-- The gate now keys on auth_uid, and it reads with .maybeSingle(), which errors (PGRST116) if more than
-- one row comes back. This index is what makes that structurally safe rather than safe-by-luck: measured
-- today there are zero duplicate (hive_id, auth_uid) pairs, and this keeps it that way.
--
-- PARTIAL, on purpose. Two membership rows carry auth_uid NULL - "Ben Reyes" and a kicked-member fixture,
-- neither with an auth user behind it - and NULLs are not comparable for uniqueness anyway. The WHERE
-- clause states that intent instead of relying on NULL semantics to be understood, and leaves those
-- fixtures alone rather than inventing identities for them.

BEGIN;

DO $$
DECLARE n_dup int;
BEGIN
  SELECT count(*) INTO n_dup FROM (
    SELECT hive_id, auth_uid FROM public.hive_members
     WHERE auth_uid IS NOT NULL GROUP BY 1, 2 HAVING count(*) > 1) d;
  IF n_dup > 0 THEN
    RAISE EXCEPTION 'refusing to add the index: % duplicate (hive_id, auth_uid) pair(s) exist. '
                    'Resolve them first - a person with two rows in one hive would break the access '
                    'gate''s .maybeSingle() read with PGRST116.', n_dup;
  END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS hive_members_one_per_person_per_hive
    ON public.hive_members (hive_id, auth_uid)
 WHERE auth_uid IS NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_indexes
                  WHERE schemaname = 'public' AND tablename = 'hive_members'
                    AND indexname = 'hive_members_one_per_person_per_hive') THEN
    RAISE EXCEPTION 'the unique index was not created';
  END IF;
  RAISE NOTICE 'hive_members: one row per (hive, person) is now enforced; the access gate may key on auth_uid';
END $$;

COMMIT;
