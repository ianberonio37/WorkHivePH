-- tenant_isolation (project-report): a foreign hive's projects are invisible - through the TABLE and
-- through v_project_truth, the view the report actually reads. A view is the classic hole here: unless
-- it is security_invoker it runs as its OWNER and silently bypasses every policy beneath it, so the
-- probe asserts that property directly as well as measuring the rows.
-- expect: truth_view_is_security_invoker \| t
-- expect: control_sees_foreign \| t
-- expect: member_projects_own_only \| t
-- expect: member_truth_view_own_only \| t
-- expect: member_sees_at_least_own \| t
SELECT 'truth_view_is_security_invoker | ' || COALESCE(
  (SELECT option_value FROM pg_class c, pg_options_to_table(c.reloptions)
    WHERE c.relname='v_project_truth' AND option_name='security_invoker'), 'unset');
CREATE TEMP TABLE _ti AS
SELECT hm.hive_id, hm.auth_uid,
       (SELECT count(*) FROM projects        WHERE hive_id <> hm.hive_id) AS f_proj,
       (SELECT count(*) FROM v_project_truth WHERE hive_id <> hm.hive_id) AS f_view,
       (SELECT count(*) FROM projects        WHERE hive_id  = hm.hive_id) AS own_proj
FROM hive_members hm WHERE hm.status='active' AND hm.auth_uid IS NOT NULL
  AND EXISTS (SELECT 1 FROM projects p WHERE p.hive_id = hm.hive_id) LIMIT 1;
GRANT SELECT ON _ti TO authenticated;
SELECT 'control_sees_foreign | ' || ((SELECT f_proj FROM _ti) > 0 AND (SELECT f_view FROM _ti) > 0);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT auth_uid FROM _ti)::text, 'role','authenticated')::text, true);
SELECT 'member_projects_own_only | '   || ((SELECT count(*) FROM projects        WHERE hive_id <> (SELECT hive_id FROM _ti)) = 0);
SELECT 'member_truth_view_own_only | ' || ((SELECT count(*) FROM v_project_truth WHERE hive_id <> (SELECT hive_id FROM _ti)) = 0);
SELECT 'member_sees_at_least_own | '   || ((SELECT count(*) FROM projects) >= (SELECT own_proj FROM _ti));
ROLLBACK;
DROP TABLE _ti;
