-- profile_identity_pinned: the worker_profiles row written is the CALLER'S OWN, proven by auth_uid and
-- never by the name in the form. If a client could choose the auth_uid it writes, it could mint a profile
-- for someone else and every downstream attribution - logbook authorship, XP, hive membership - would
-- inherit that lie from the identity layer down.
-- THE MECHANISM IS RLS, and specifically the WITH CHECK half: INSERT carries
-- WITH CHECK (auth.uid() IS NOT NULL AND auth_uid = auth.uid()), UPDATE carries USING (auth.uid() = auth_uid).
-- Those two halves fail differently and both matter - a WITH CHECK REFUSES the write, a USING silently
-- filters it to zero rows - so the probe asserts the policies EXIST with the right shape and then proves
-- the WITH CHECK actually bites.
-- PROVEN AS `authenticated`, never as the table owner: postgres bypasses RLS entirely and would report a
-- clean pass over a policy that does nothing. The identity is assumed from a LIVE profile row.
-- expect: profiles_checked \| [1-9][0-9]*
-- expect: rows_without_auth_uid \| 0
-- expect: insert_with_check_present \| t
-- expect: update_using_present \| t
-- expect: teeth_fixture_found \| t
-- expect: new row violates row-level security policy
-- expect: rows_restored_after_rollback \| t

SELECT 'profiles_checked | ' || count(*)::text
     || E'\nrows_without_auth_uid | ' || count(*) FILTER (WHERE auth_uid IS NULL)::text
FROM worker_profiles;

SELECT 'insert_with_check_present | ' || EXISTS (
  SELECT 1 FROM pg_policies WHERE tablename = 'worker_profiles' AND cmd = 'INSERT'
    AND with_check ILIKE '%auth_uid%' AND with_check ILIKE '%auth.uid()%');
SELECT 'update_using_present | ' || EXISTS (
  SELECT 1 FROM pg_policies WHERE tablename = 'worker_profiles' AND cmd = 'UPDATE'
    AND qual ILIKE '%auth_uid%' AND qual ILIKE '%auth.uid()%');

-- one live identity to act as, and a DIFFERENT one to try to impersonate
CREATE TEMP TABLE _fix AS
SELECT w.auth_uid AS me,
       (SELECT o.auth_uid FROM worker_profiles o WHERE o.auth_uid IS DISTINCT FROM w.auth_uid LIMIT 1) AS someone_else,
       (SELECT count(*) FROM worker_profiles) AS n0
FROM worker_profiles w WHERE w.auth_uid IS NOT NULL LIMIT 1;
SELECT 'teeth_fixture_found | ' || EXISTS (SELECT 1 FROM _fix WHERE someone_else IS NOT NULL);
-- the role we are about to assume cannot read a temp table it does not own; without this the INSERT
-- never runs and the missing RLS error reads as "RLS did not fire" - a probe bug wearing a finding's face.
GRANT SELECT ON _fix TO authenticated;

BEGIN;
-- TEETH: act as ME, try to write a profile pinned to SOMEONE ELSE. The WITH CHECK must refuse it.
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT me::text FROM _fix), 'role', 'authenticated')::text, true);
SET LOCAL ROLE authenticated;
INSERT INTO worker_profiles (auth_uid, display_name)
SELECT someone_else, 'WH-PROBE impersonation' FROM _fix;
ROLLBACK;

SELECT 'rows_restored_after_rollback | ' || ((SELECT count(*) FROM worker_profiles) = (SELECT n0 FROM _fix));
