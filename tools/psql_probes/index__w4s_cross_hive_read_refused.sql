-- cross_hive_read_refused (index, P-B, generated 2026-09-05 by tools/gen_cross_hive_read_recipes.py): every
-- hive-scoped table this page reads (pm_assets, pm_completions, v_alert_truth, v_amc_truth, v_inventory_items_truth, v_logbook_truth, v_pm_scope_items_truth, v_risk_truth, v_sensor_truth, v_worker_truth) must refuse a foreign hive in the DATABASE. RLS USING
-- clauses FILTER rather than raise, so the probe counts rows as a member of exactly one hive: a foreign hive with
-- rows reads 0, the member's own hive reads > 0 (the control). Fixtures are chosen live; a table with rows in
-- fewer than two hives reports 'n/a' and is excluded from the expectations by the generator.
-- expect: pm_assets_fixture \| t
-- expect: pm_assets_foreign_rows \| 0
-- expect: pm_assets_own_rows_gt0 \| t
-- expect: pm_completions_fixture \| t
-- expect: pm_completions_foreign_rows \| 0
-- expect: pm_completions_own_rows_gt0 \| t
-- expect: alert_fixture \| t
-- expect: alert_foreign_rows \| 0
-- expect: alert_own_rows_gt0 \| t
-- expect: amc_fixture \| t
-- expect: amc_foreign_rows \| 0
-- expect: amc_own_rows_gt0 \| t
-- expect: inventory_items_fixture \| t
-- expect: inventory_items_foreign_rows \| 0
-- expect: inventory_items_own_rows_gt0 \| t
-- expect: logbook_fixture \| t
-- expect: logbook_foreign_rows \| 0
-- expect: logbook_own_rows_gt0 \| t
-- expect: pm_scope_items_fixture \| t
-- expect: pm_scope_items_foreign_rows \| 0
-- expect: pm_scope_items_own_rows_gt0 \| t
-- expect: risk_fixture \| t
-- expect: risk_foreign_rows \| 0
-- expect: risk_own_rows_gt0 \| t
-- expect: sensor_fixture \| t
-- expect: sensor_foreign_rows \| 0
-- expect: sensor_own_rows_gt0 \| t
-- expect: worker_fixture \| t
-- expect: worker_foreign_rows \| 0
-- expect: worker_own_rows_gt0 \| t

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

CREATE TEMP TABLE _fx_alert AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM v_alert_truth x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM v_alert_truth x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_alert TO authenticated;
SELECT 'alert_fixture | ' || ((SELECT me FROM _fx_alert) IS NOT NULL AND (SELECT foreign_hive FROM _fx_alert) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_alert)::text, 'role','authenticated')::text, true);
SELECT 'alert_foreign_rows | ' || (SELECT count(*) FROM v_alert_truth WHERE hive_id = (SELECT foreign_hive FROM _fx_alert));
SELECT 'alert_own_rows_gt0 | ' || ((SELECT count(*) FROM v_alert_truth WHERE hive_id = (SELECT mine FROM _fx_alert)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_amc AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM v_amc_truth x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM v_amc_truth x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_amc TO authenticated;
SELECT 'amc_fixture | ' || ((SELECT me FROM _fx_amc) IS NOT NULL AND (SELECT foreign_hive FROM _fx_amc) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_amc)::text, 'role','authenticated')::text, true);
SELECT 'amc_foreign_rows | ' || (SELECT count(*) FROM v_amc_truth WHERE hive_id = (SELECT foreign_hive FROM _fx_amc));
SELECT 'amc_own_rows_gt0 | ' || ((SELECT count(*) FROM v_amc_truth WHERE hive_id = (SELECT mine FROM _fx_amc)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_inventory_items AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM v_inventory_items_truth x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM v_inventory_items_truth x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_inventory_items TO authenticated;
SELECT 'inventory_items_fixture | ' || ((SELECT me FROM _fx_inventory_items) IS NOT NULL AND (SELECT foreign_hive FROM _fx_inventory_items) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_inventory_items)::text, 'role','authenticated')::text, true);
SELECT 'inventory_items_foreign_rows | ' || (SELECT count(*) FROM v_inventory_items_truth WHERE hive_id = (SELECT foreign_hive FROM _fx_inventory_items));
SELECT 'inventory_items_own_rows_gt0 | ' || ((SELECT count(*) FROM v_inventory_items_truth WHERE hive_id = (SELECT mine FROM _fx_inventory_items)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_logbook AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM v_logbook_truth x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM v_logbook_truth x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_logbook TO authenticated;
SELECT 'logbook_fixture | ' || ((SELECT me FROM _fx_logbook) IS NOT NULL AND (SELECT foreign_hive FROM _fx_logbook) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_logbook)::text, 'role','authenticated')::text, true);
SELECT 'logbook_foreign_rows | ' || (SELECT count(*) FROM v_logbook_truth WHERE hive_id = (SELECT foreign_hive FROM _fx_logbook));
SELECT 'logbook_own_rows_gt0 | ' || ((SELECT count(*) FROM v_logbook_truth WHERE hive_id = (SELECT mine FROM _fx_logbook)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_pm_scope_items AS
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
GRANT SELECT ON _fx_pm_scope_items TO authenticated;
SELECT 'pm_scope_items_fixture | ' || ((SELECT me FROM _fx_pm_scope_items) IS NOT NULL AND (SELECT foreign_hive FROM _fx_pm_scope_items) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_pm_scope_items)::text, 'role','authenticated')::text, true);
SELECT 'pm_scope_items_foreign_rows | ' || (SELECT count(*) FROM v_pm_scope_items_truth WHERE hive_id = (SELECT foreign_hive FROM _fx_pm_scope_items));
SELECT 'pm_scope_items_own_rows_gt0 | ' || ((SELECT count(*) FROM v_pm_scope_items_truth WHERE hive_id = (SELECT mine FROM _fx_pm_scope_items)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_risk AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM v_risk_truth x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM v_risk_truth x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_risk TO authenticated;
SELECT 'risk_fixture | ' || ((SELECT me FROM _fx_risk) IS NOT NULL AND (SELECT foreign_hive FROM _fx_risk) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_risk)::text, 'role','authenticated')::text, true);
SELECT 'risk_foreign_rows | ' || (SELECT count(*) FROM v_risk_truth WHERE hive_id = (SELECT foreign_hive FROM _fx_risk));
SELECT 'risk_own_rows_gt0 | ' || ((SELECT count(*) FROM v_risk_truth WHERE hive_id = (SELECT mine FROM _fx_risk)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_sensor AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM v_sensor_truth x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM v_sensor_truth x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_sensor TO authenticated;
SELECT 'sensor_fixture | ' || ((SELECT me FROM _fx_sensor) IS NOT NULL AND (SELECT foreign_hive FROM _fx_sensor) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_sensor)::text, 'role','authenticated')::text, true);
SELECT 'sensor_foreign_rows | ' || (SELECT count(*) FROM v_sensor_truth WHERE hive_id = (SELECT foreign_hive FROM _fx_sensor));
SELECT 'sensor_own_rows_gt0 | ' || ((SELECT count(*) FROM v_sensor_truth WHERE hive_id = (SELECT mine FROM _fx_sensor)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_worker AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM v_worker_truth x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM v_worker_truth x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_worker TO authenticated;
SELECT 'worker_fixture | ' || ((SELECT me FROM _fx_worker) IS NOT NULL AND (SELECT foreign_hive FROM _fx_worker) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_worker)::text, 'role','authenticated')::text, true);
SELECT 'worker_foreign_rows | ' || (SELECT count(*) FROM v_worker_truth WHERE hive_id = (SELECT foreign_hive FROM _fx_worker));
SELECT 'worker_own_rows_gt0 | ' || ((SELECT count(*) FROM v_worker_truth WHERE hive_id = (SELECT mine FROM _fx_worker)) > 0);
ROLLBACK;
