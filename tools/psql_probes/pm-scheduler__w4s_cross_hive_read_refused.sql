-- cross_hive_read_refused (pm-scheduler, P-B, generated 2026-09-05 by tools/gen_cross_hive_read_recipes.py): every
-- hive-scoped table this page reads (asset_nodes, hive_audit_log, hive_members, logbook, pm_assets, pm_completions, pm_scope_items, project_links, projects, v_asset_truth, v_pm_scope_items_truth) must refuse a foreign hive in the DATABASE. RLS USING
-- clauses FILTER rather than raise, so the probe counts rows as a member of exactly one hive: a foreign hive with
-- rows reads 0, the member's own hive reads > 0 (the control). Fixtures are chosen live; a table with rows in
-- fewer than two hives reports 'n/a' and is excluded from the expectations by the generator.
-- expect: asset_nodes_fixture \| t
-- expect: asset_nodes_foreign_rows \| 0
-- expect: asset_nodes_own_rows_gt0 \| t
-- expect: hive_audit_log_fixture \| t
-- expect: hive_audit_log_foreign_rows \| 0
-- expect: hive_audit_log_own_rows_gt0 \| t
-- expect: hive_members_fixture \| t
-- expect: hive_members_foreign_rows \| 0
-- expect: hive_members_own_rows_gt0 \| t
-- expect: logbook_fixture \| t
-- expect: logbook_foreign_rows \| 0
-- expect: logbook_own_rows_gt0 \| t
-- expect: pm_assets_fixture \| t
-- expect: pm_assets_foreign_rows \| 0
-- expect: pm_assets_own_rows_gt0 \| t
-- expect: pm_completions_fixture \| t
-- expect: pm_completions_foreign_rows \| 0
-- expect: pm_completions_own_rows_gt0 \| t
-- expect: pm_scope_items_fixture \| t
-- expect: pm_scope_items_foreign_rows \| 0
-- expect: pm_scope_items_own_rows_gt0 \| t
-- expect: project_links_fixture \| t
-- expect: project_links_foreign_rows \| 0
-- expect: project_links_own_rows_gt0 \| t
-- expect: projects_fixture \| t
-- expect: projects_foreign_rows \| 0
-- expect: projects_own_rows_gt0 \| t
-- expect: asset_fixture \| t
-- expect: asset_foreign_rows \| 0
-- expect: asset_own_rows_gt0 \| t
-- expect: v_pm_scope_items_truth_fixture \| t
-- expect: v_pm_scope_items_truth_foreign_rows \| 0
-- expect: v_pm_scope_items_truth_own_rows_gt0 \| t

CREATE TEMP TABLE _fx_asset_nodes AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM asset_nodes x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM asset_nodes x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_asset_nodes TO authenticated;
SELECT 'asset_nodes_fixture | ' || ((SELECT me FROM _fx_asset_nodes) IS NOT NULL AND (SELECT foreign_hive FROM _fx_asset_nodes) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_asset_nodes)::text, 'role','authenticated')::text, true);
SELECT 'asset_nodes_foreign_rows | ' || (SELECT count(*) FROM asset_nodes WHERE hive_id = (SELECT foreign_hive FROM _fx_asset_nodes));
SELECT 'asset_nodes_own_rows_gt0 | ' || ((SELECT count(*) FROM asset_nodes WHERE hive_id = (SELECT mine FROM _fx_asset_nodes)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_hive_audit_log AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM hive_audit_log x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM hive_audit_log x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_hive_audit_log TO authenticated;
SELECT 'hive_audit_log_fixture | ' || ((SELECT me FROM _fx_hive_audit_log) IS NOT NULL AND (SELECT foreign_hive FROM _fx_hive_audit_log) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_hive_audit_log)::text, 'role','authenticated')::text, true);
SELECT 'hive_audit_log_foreign_rows | ' || (SELECT count(*) FROM hive_audit_log WHERE hive_id = (SELECT foreign_hive FROM _fx_hive_audit_log));
SELECT 'hive_audit_log_own_rows_gt0 | ' || ((SELECT count(*) FROM hive_audit_log WHERE hive_id = (SELECT mine FROM _fx_hive_audit_log)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_hive_members AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM hive_members x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM hive_members x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_hive_members TO authenticated;
SELECT 'hive_members_fixture | ' || ((SELECT me FROM _fx_hive_members) IS NOT NULL AND (SELECT foreign_hive FROM _fx_hive_members) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_hive_members)::text, 'role','authenticated')::text, true);
SELECT 'hive_members_foreign_rows | ' || (SELECT count(*) FROM hive_members WHERE hive_id = (SELECT foreign_hive FROM _fx_hive_members));
SELECT 'hive_members_own_rows_gt0 | ' || ((SELECT count(*) FROM hive_members WHERE hive_id = (SELECT mine FROM _fx_hive_members)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_logbook AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM logbook x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM logbook x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_logbook TO authenticated;
SELECT 'logbook_fixture | ' || ((SELECT me FROM _fx_logbook) IS NOT NULL AND (SELECT foreign_hive FROM _fx_logbook) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_logbook)::text, 'role','authenticated')::text, true);
SELECT 'logbook_foreign_rows | ' || (SELECT count(*) FROM logbook WHERE hive_id = (SELECT foreign_hive FROM _fx_logbook));
SELECT 'logbook_own_rows_gt0 | ' || ((SELECT count(*) FROM logbook WHERE hive_id = (SELECT mine FROM _fx_logbook)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_pm_assets AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM pm_assets x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM pm_assets x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_pm_assets TO authenticated;
SELECT 'pm_assets_fixture | ' || ((SELECT me FROM _fx_pm_assets) IS NOT NULL AND (SELECT foreign_hive FROM _fx_pm_assets) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_pm_assets)::text, 'role','authenticated')::text, true);
SELECT 'pm_assets_foreign_rows | ' || (SELECT count(*) FROM pm_assets WHERE hive_id = (SELECT foreign_hive FROM _fx_pm_assets));
SELECT 'pm_assets_own_rows_gt0 | ' || ((SELECT count(*) FROM pm_assets WHERE hive_id = (SELECT mine FROM _fx_pm_assets)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_pm_completions AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM pm_completions x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM pm_completions x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_pm_completions TO authenticated;
SELECT 'pm_completions_fixture | ' || ((SELECT me FROM _fx_pm_completions) IS NOT NULL AND (SELECT foreign_hive FROM _fx_pm_completions) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_pm_completions)::text, 'role','authenticated')::text, true);
SELECT 'pm_completions_foreign_rows | ' || (SELECT count(*) FROM pm_completions WHERE hive_id = (SELECT foreign_hive FROM _fx_pm_completions));
SELECT 'pm_completions_own_rows_gt0 | ' || ((SELECT count(*) FROM pm_completions WHERE hive_id = (SELECT mine FROM _fx_pm_completions)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_pm_scope_items AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM pm_scope_items x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM pm_scope_items x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_pm_scope_items TO authenticated;
SELECT 'pm_scope_items_fixture | ' || ((SELECT me FROM _fx_pm_scope_items) IS NOT NULL AND (SELECT foreign_hive FROM _fx_pm_scope_items) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_pm_scope_items)::text, 'role','authenticated')::text, true);
SELECT 'pm_scope_items_foreign_rows | ' || (SELECT count(*) FROM pm_scope_items WHERE hive_id = (SELECT foreign_hive FROM _fx_pm_scope_items));
SELECT 'pm_scope_items_own_rows_gt0 | ' || ((SELECT count(*) FROM pm_scope_items WHERE hive_id = (SELECT mine FROM _fx_pm_scope_items)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_project_links AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM project_links x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM project_links x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_project_links TO authenticated;
SELECT 'project_links_fixture | ' || ((SELECT me FROM _fx_project_links) IS NOT NULL AND (SELECT foreign_hive FROM _fx_project_links) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_project_links)::text, 'role','authenticated')::text, true);
SELECT 'project_links_foreign_rows | ' || (SELECT count(*) FROM project_links WHERE hive_id = (SELECT foreign_hive FROM _fx_project_links));
SELECT 'project_links_own_rows_gt0 | ' || ((SELECT count(*) FROM project_links WHERE hive_id = (SELECT mine FROM _fx_project_links)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_projects AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM projects x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM projects x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_projects TO authenticated;
SELECT 'projects_fixture | ' || ((SELECT me FROM _fx_projects) IS NOT NULL AND (SELECT foreign_hive FROM _fx_projects) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_projects)::text, 'role','authenticated')::text, true);
SELECT 'projects_foreign_rows | ' || (SELECT count(*) FROM projects WHERE hive_id = (SELECT foreign_hive FROM _fx_projects));
SELECT 'projects_own_rows_gt0 | ' || ((SELECT count(*) FROM projects WHERE hive_id = (SELECT mine FROM _fx_projects)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_asset AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM v_asset_truth x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM v_asset_truth x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_asset TO authenticated;
SELECT 'asset_fixture | ' || ((SELECT me FROM _fx_asset) IS NOT NULL AND (SELECT foreign_hive FROM _fx_asset) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_asset)::text, 'role','authenticated')::text, true);
SELECT 'asset_foreign_rows | ' || (SELECT count(*) FROM v_asset_truth WHERE hive_id = (SELECT foreign_hive FROM _fx_asset));
SELECT 'asset_own_rows_gt0 | ' || ((SELECT count(*) FROM v_asset_truth WHERE hive_id = (SELECT mine FROM _fx_asset)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_v_pm_scope_items_truth AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM v_pm_scope_items_truth x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM v_pm_scope_items_truth x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_v_pm_scope_items_truth TO authenticated;
SELECT 'v_pm_scope_items_truth_fixture | ' || ((SELECT me FROM _fx_v_pm_scope_items_truth) IS NOT NULL AND (SELECT foreign_hive FROM _fx_v_pm_scope_items_truth) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_v_pm_scope_items_truth)::text, 'role','authenticated')::text, true);
SELECT 'v_pm_scope_items_truth_foreign_rows | ' || (SELECT count(*) FROM v_pm_scope_items_truth WHERE hive_id = (SELECT foreign_hive FROM _fx_v_pm_scope_items_truth));
SELECT 'v_pm_scope_items_truth_own_rows_gt0 | ' || ((SELECT count(*) FROM v_pm_scope_items_truth WHERE hive_id = (SELECT mine FROM _fx_v_pm_scope_items_truth)) > 0);
ROLLBACK;
