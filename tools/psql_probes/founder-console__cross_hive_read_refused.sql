-- cross_hive_read_refused (founder-console, P-B P75, 2026-09-05): the console's hive-scoped panels rest on
-- hive_audit_log (hive_audit_log_select_supervisor: a SUPERVISOR of the hive) and its platform panels on
-- platform_feedback (admin reads all; the public reads only is_public rows). Both are USING clauses that
-- FILTER, so the probe counts rows as two identities: a supervisor of exactly one hive reads 0 audit rows
-- of a foreign hive with thousands and >0 of his own; a plain member (not a platform admin) reads 0
-- non-public feedback rows.
-- expect: fixture_supervisor_foreign_hive \| t
-- expect: foreign_audit_rows_visible \| 0
-- expect: own_audit_rows_visible_gt0 \| t
-- expect: fixture_non_admin_member \| t
-- expect: nonpublic_feedback_visible_to_member \| 0
CREATE TEMP TABLE _fc AS
SELECT m.auth_uid AS sup, m.hive_id AS mine,
       (SELECT a.hive_id FROM hive_audit_log a WHERE a.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members x WHERE x.auth_uid = m.auth_uid AND x.hive_id = a.hive_id AND x.status = 'active')
        GROUP BY a.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.role = 'supervisor' AND m.status = 'active' AND EXISTS (SELECT 1 FROM hive_audit_log a WHERE a.hive_id = m.hive_id)
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active' AND y.role = 'supervisor') = 1
LIMIT 1;
CREATE TEMP TABLE _nm AS
SELECT m.auth_uid AS member FROM hive_members m JOIN worker_profiles wp ON wp.auth_uid = m.auth_uid
WHERE m.status = 'active' AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a WHERE a.worker_name = wp.display_name)
LIMIT 1;
GRANT SELECT ON _fc TO authenticated; GRANT SELECT ON _nm TO authenticated;
SELECT 'fixture_supervisor_foreign_hive | ' || ((SELECT sup FROM _fc) IS NOT NULL AND (SELECT foreign_hive FROM _fc) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT sup FROM _fc)::text, 'role','authenticated')::text, true);
SELECT 'foreign_audit_rows_visible | ' || (SELECT count(*) FROM hive_audit_log WHERE hive_id = (SELECT foreign_hive FROM _fc));
SELECT 'own_audit_rows_visible_gt0 | ' || ((SELECT count(*) FROM hive_audit_log WHERE hive_id = (SELECT mine FROM _fc)) > 0);
ROLLBACK;
SELECT 'fixture_non_admin_member | ' || ((SELECT member FROM _nm) IS NOT NULL AND (SELECT count(*) FROM platform_feedback WHERE is_public IS DISTINCT FROM true) > 0);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT member FROM _nm)::text, 'role','authenticated')::text, true);
SELECT 'nonpublic_feedback_visible_to_member | ' || (SELECT count(*) FROM platform_feedback WHERE is_public IS DISTINCT FROM true);
ROLLBACK;
