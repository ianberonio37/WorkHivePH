-- write_authz_depth (project-manager, P-B P100, 2026-09-05): a project is created INTO a hive. projects_hive_rw
-- carries WITH CHECK (hive_id IN user_hive_ids()), and a WITH CHECK failure RAISES (42501) where a USING clause
-- would merely filter - so the probe catches the raise for a foreign hive and proves the control: the same
-- member inserting into HIS hive succeeds (inside a transaction that is rolled back, so nothing persists).
-- expect: fixture_single_hive_member \| t
-- expect: foreign_hive_insert_refused \| t
-- expect: own_hive_insert_allowed \| t
-- expect: rows_restored_after_rollback \| t
CREATE TEMP TABLE _pm AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT h.id FROM hives h WHERE h.id <> m.hive_id LIMIT 1) AS foreign_hive,
       (SELECT count(*) FROM projects) AS n0,
       (SELECT wp.display_name FROM worker_profiles wp WHERE wp.auth_uid = m.auth_uid LIMIT 1) AS wname
FROM hive_members m
WHERE m.status = 'active' AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM worker_profiles wp WHERE wp.auth_uid = m.auth_uid)
LIMIT 1;
GRANT SELECT ON _pm TO authenticated;
SELECT 'fixture_single_hive_member | ' || ((SELECT me FROM _pm) IS NOT NULL AND (SELECT foreign_hive FROM _pm) IS NOT NULL);
CREATE TEMP TABLE _res (k text, v text);
GRANT ALL ON _res TO authenticated;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _pm)::text, 'role','authenticated')::text, true);
DO $$
BEGIN
  INSERT INTO projects (hive_id, worker_name, auth_uid, project_code, name, project_type, status, priority, meta)
  VALUES ((SELECT foreign_hive FROM _pm), (SELECT wname FROM _pm), (SELECT me FROM _pm), 'PRB-AUTHZ-F', 'authz probe (foreign)', 'workorder', 'planning', 'medium', '{}'::jsonb);
  INSERT INTO _res VALUES ('foreign', 'inserted');
EXCEPTION WHEN insufficient_privilege OR check_violation THEN
  INSERT INTO _res VALUES ('foreign', 'refused:' || SQLSTATE);
END $$;
DO $$
BEGIN
  INSERT INTO projects (hive_id, worker_name, auth_uid, project_code, name, project_type, status, priority, meta)
  VALUES ((SELECT mine FROM _pm), (SELECT wname FROM _pm), (SELECT me FROM _pm), 'PRB-AUTHZ-O', 'authz probe (own)', 'workorder', 'planning', 'medium', '{}'::jsonb);
  INSERT INTO _res VALUES ('own', 'inserted');
EXCEPTION WHEN OTHERS THEN
  INSERT INTO _res VALUES ('own', 'refused:' || SQLSTATE || ' ' || left(SQLERRM, 60));
END $$;
SELECT 'foreign_hive_insert_refused | ' || ((SELECT v FROM _res WHERE k = 'foreign') LIKE 'refused:42501%');
SELECT 'own_hive_insert_allowed | ' || ((SELECT v FROM _res WHERE k = 'own') = 'inserted') || CASE WHEN (SELECT v FROM _res WHERE k = 'own') = 'inserted' THEN '' ELSE ' -- ' || (SELECT v FROM _res WHERE k = 'own') END;
ROLLBACK;
SELECT 'rows_restored_after_rollback | ' || ((SELECT count(*) FROM projects) = (SELECT n0 FROM _pm));
