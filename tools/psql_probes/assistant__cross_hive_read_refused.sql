-- cross_hive_read_refused (assistant, P-B, generated 2026-09-05 by tools/gen_cross_hive_read_recipes.py): every
-- hive-scoped table this page reads (asset_nodes, pm_assets, voice_journal_entries) must refuse a foreign hive in the DATABASE. RLS USING
-- clauses FILTER rather than raise, so the probe counts rows as a member of exactly one hive: a foreign hive with
-- rows reads 0, the member's own hive reads > 0 (the control). Fixtures are chosen live; a table with rows in
-- fewer than two hives reports 'n/a' and is excluded from the expectations by the generator.
-- expect: asset_nodes_fixture \| t
-- expect: asset_nodes_foreign_rows \| 0
-- expect: asset_nodes_own_rows_gt0 \| t
-- expect: pm_assets_fixture \| t
-- expect: pm_assets_foreign_rows \| 0
-- expect: pm_assets_own_rows_gt0 \| t
-- expect: voice_journal_entries_fixture \| t
-- expect: voice_journal_entries_foreign_rows \| 0
-- expect: voice_journal_entries_own_rows_gt0 \| t

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

CREATE TEMP TABLE _fx_pm_assets AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM pm_assets x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
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

CREATE TEMP TABLE _fx_voice_journal_entries AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM voice_journal_entries x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM voice_journal_entries x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_voice_journal_entries TO authenticated;
SELECT 'voice_journal_entries_fixture | ' || ((SELECT me FROM _fx_voice_journal_entries) IS NOT NULL AND (SELECT foreign_hive FROM _fx_voice_journal_entries) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_voice_journal_entries)::text, 'role','authenticated')::text, true);
SELECT 'voice_journal_entries_foreign_rows | ' || (SELECT count(*) FROM voice_journal_entries WHERE hive_id = (SELECT foreign_hive FROM _fx_voice_journal_entries));
SELECT 'voice_journal_entries_own_rows_gt0 | ' || ((SELECT count(*) FROM voice_journal_entries WHERE hive_id = (SELECT mine FROM _fx_voice_journal_entries)) > 0);
ROLLBACK;
