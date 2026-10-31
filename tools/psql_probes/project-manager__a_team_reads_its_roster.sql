-- a_team_reads_its_roster: who may read a project's roles, and who may change them (HS L1, 2026-10-30).
--   project_roles is read by "project membership, not hive membership" (tools/tenant_declarations.mjs): a member ON the
--   project reads its whole team, a member who is not on it reads none of it, a supervisor reads it, and only a
--   supervisor writes it. Subjects from the full hive (seeders/full_hive.py): Kristine Aquino is the safety officer on
--   "Instrument air upgrade"; Joel Cruz holds no role on any project. Writes rolled back. Population printed.
-- expect: team_size \| [3-9]
-- expect: member_on_team_reads \| t
-- expect: member_off_team_reads \| 0
-- expect: supervisor_reads \| t
-- expect: member_on_team_writes \| refused
\set H '30303030-3030-4030-8030-303030303030'
CREATE TEMP TABLE _p AS SELECT id FROM projects WHERE hive_id = :'H' AND name = 'Instrument air upgrade';
GRANT SELECT ON _p TO authenticated;
SELECT 'team_size | ' || count(*) FROM project_roles WHERE project_id = (SELECT id FROM _p) AND deleted_at IS NULL;

BEGIN;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT auth_uid FROM hive_members
  WHERE worker_name = 'Kristine Aquino' AND hive_id = :'H')::text, 'role', 'authenticated')::text, true);
SET LOCAL ROLE authenticated;
SELECT 'member_on_team_reads | ' || (count(*) >= 3) FROM project_roles WHERE project_id = (SELECT id FROM _p);
CREATE TEMP TABLE _w (v text) ON COMMIT DROP;
DO $$ BEGIN
  UPDATE project_roles SET notes = 'probe' WHERE project_id = (SELECT id FROM _p);
  INSERT INTO _w VALUES (CASE WHEN FOUND THEN 'allowed' ELSE 'refused' END);
EXCEPTION WHEN insufficient_privilege THEN INSERT INTO _w VALUES ('refused'); END $$;
SELECT 'member_on_team_writes | ' || v FROM _w;
ROLLBACK;

BEGIN;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT auth_uid FROM hive_members
  WHERE worker_name = 'Joel Cruz' AND hive_id = :'H')::text, 'role', 'authenticated')::text, true);
SET LOCAL ROLE authenticated;
SELECT 'member_off_team_reads | ' || count(*) FROM project_roles WHERE project_id = (SELECT id FROM _p);
ROLLBACK;

BEGIN;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT auth_uid FROM hive_members
  WHERE worker_name = 'Ernesto Villareal' AND hive_id = :'H')::text, 'role', 'authenticated')::text, true);
SET LOCAL ROLE authenticated;
SELECT 'supervisor_reads | ' || (count(*) >= 3) FROM project_roles WHERE project_id = (SELECT id FROM _p);
ROLLBACK;
DROP TABLE _p;
