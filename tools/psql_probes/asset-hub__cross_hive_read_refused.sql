-- cross_hive_read_refused (asset-hub, P-B, generated 2026-09-05 by tools/gen_cross_hive_read_recipes.py): every
-- hive-scoped table this page reads (asset_nodes, pm_completions, rcm_fmea_modes) must refuse a foreign hive in the DATABASE. RLS USING
-- clauses FILTER rather than raise, so the probe counts rows as a member of exactly one hive: a foreign hive with
-- rows reads 0, the member's own hive reads > 0 (the control). Fixtures are chosen live; a table with rows in
-- fewer than two hives reports 'n/a' and is excluded from the expectations by the generator.
-- expect: asset_nodes_fixture \| t
-- expect: asset_nodes_foreign_rows \| 0
-- expect: asset_nodes_own_rows_gt0 \| t
-- expect: pm_completions_fixture \| t
-- expect: pm_completions_foreign_rows \| 0
-- expect: pm_completions_own_rows_gt0 \| t
-- expect: rcm_fmea_modes_fixture \| t
-- expect: rcm_fmea_modes_foreign_rows \| 0
-- expect: rcm_fmea_modes_own_rows_gt0 \| t

CREATE TEMP TABLE _fx_asset_nodes AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM asset_nodes x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
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

CREATE TEMP TABLE _fx_pm_completions AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM pm_completions x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
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

CREATE TEMP TABLE _fx_rcm_fmea_modes AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM rcm_fmea_modes x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM rcm_fmea_modes x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_rcm_fmea_modes TO authenticated;
SELECT 'rcm_fmea_modes_fixture | ' || ((SELECT me FROM _fx_rcm_fmea_modes) IS NOT NULL AND (SELECT foreign_hive FROM _fx_rcm_fmea_modes) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_rcm_fmea_modes)::text, 'role','authenticated')::text, true);
SELECT 'rcm_fmea_modes_foreign_rows | ' || (SELECT count(*) FROM rcm_fmea_modes WHERE hive_id = (SELECT foreign_hive FROM _fx_rcm_fmea_modes));
SELECT 'rcm_fmea_modes_own_rows_gt0 | ' || ((SELECT count(*) FROM rcm_fmea_modes WHERE hive_id = (SELECT mine FROM _fx_rcm_fmea_modes)) > 0);
ROLLBACK;
