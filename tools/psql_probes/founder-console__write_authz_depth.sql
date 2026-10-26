-- write_authz_depth (founder-console, P-B, generated 2026-09-05 by tools/gen_write_authz_recipes.py): the hive-scoped
-- tables this page WRITES (marketplace_listings, marketplace_sellers) must refuse a foreign hive in the DATABASE. A USING clause on
-- UPDATE/DELETE filters, so a no-op UPDATE (pk = pk) and a DELETE on a foreign hive's row must touch 0 rows; the
-- own-hive control must touch >= 1 where the write policy is hive-member ALL (owner/supervisor-scoped tables keep
-- only the refusal half and say so). Everything runs inside a rolled-back transaction; counts are re-checked after.
-- expect: marketplace_listings_fixture \| t
-- expect: marketplace_listings_foreign_update_touched \| (0\b|refused)
-- expect: marketplace_listings_foreign_delete_touched \| (0\b|refused)
-- expect: marketplace_listings_move_into_foreign \| (0\b|refused)
-- forbid: marketplace_listings_move_into_foreign \| [1-9]
-- expect: marketplace_listings_rows_restored \| t
-- expect: marketplace_sellers_fixture \| t
-- expect: marketplace_sellers_foreign_update_touched \| (0\b|refused)
-- expect: marketplace_sellers_foreign_delete_touched \| (0\b|refused)
-- expect: marketplace_sellers_move_into_foreign \| (0\b|refused)
-- forbid: marketplace_sellers_move_into_foreign \| [1-9]
-- expect: marketplace_sellers_rows_restored \| t

CREATE TEMP TABLE _wx_marketplace_listings AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM marketplace_listings x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM marketplace_listings x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT x.hive_id FROM marketplace_listings x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_hive,
       (SELECT count(*) FROM marketplace_listings) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM marketplace_listings x WHERE x.hive_id = m.hive_id)
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a WHERE a.auth_uid = m.auth_uid)   -- by account, never by display name
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_marketplace_listings TO authenticated;
SELECT 'marketplace_listings_fixture | ' || ((SELECT me FROM _wx_marketplace_listings) IS NOT NULL AND (SELECT foreign_row FROM _wx_marketplace_listings) IS NOT NULL);
-- every write probe runs through ONE exception-safe function (2026-10-14): a refused write (42501, a missing grant, a
-- guard trigger) returns 'refused <SQLSTATE>' instead of aborting the rolled-back transaction and every probe after it
CREATE FUNCTION pg_temp.wx_try_marketplace_listings(op text) RETURNS text LANGUAGE plpgsql AS $wx$
DECLARE n int;
BEGIN
  IF op = 'foreign_update' THEN UPDATE marketplace_listings SET id = id WHERE id = (SELECT foreign_row FROM _wx_marketplace_listings);
  ELSIF op = 'foreign_delete' THEN DELETE FROM marketplace_listings WHERE id = (SELECT foreign_row FROM _wx_marketplace_listings);
  ELSIF op = 'own_update' THEN UPDATE marketplace_listings SET id = id WHERE id = (SELECT own_row FROM _wx_marketplace_listings);
  ELSIF op = 'move' THEN UPDATE marketplace_listings SET hive_id = (SELECT foreign_hive FROM _wx_marketplace_listings) WHERE id = (SELECT own_row FROM _wx_marketplace_listings);
  END IF;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n::text;
EXCEPTION WHEN insufficient_privilege THEN RETURN 'refused 42501';
  WHEN others THEN RETURN 'refused ' || SQLSTATE;
END $wx$;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_marketplace_listings)::text, 'role','authenticated')::text, true);
SELECT 'marketplace_listings_foreign_update_touched | ' || pg_temp.wx_try_marketplace_listings('foreign_update');
SELECT 'marketplace_listings_foreign_delete_touched | ' || pg_temp.wx_try_marketplace_listings('foreign_delete');
SELECT 'marketplace_listings_move_into_foreign | ' || pg_temp.wx_try_marketplace_listings('move');
ROLLBACK;
SELECT 'marketplace_listings_rows_restored | ' || ((SELECT count(*) FROM marketplace_listings) = (SELECT n0 FROM _wx_marketplace_listings));

CREATE TEMP TABLE _wx_marketplace_sellers AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM marketplace_sellers x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM marketplace_sellers x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT x.hive_id FROM marketplace_sellers x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_hive,
       (SELECT count(*) FROM marketplace_sellers) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM marketplace_sellers x WHERE x.hive_id = m.hive_id)
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a WHERE a.auth_uid = m.auth_uid)   -- by account, never by display name
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_marketplace_sellers TO authenticated;
SELECT 'marketplace_sellers_fixture | ' || ((SELECT me FROM _wx_marketplace_sellers) IS NOT NULL AND (SELECT foreign_row FROM _wx_marketplace_sellers) IS NOT NULL);
-- every write probe runs through ONE exception-safe function (2026-10-14): a refused write (42501, a missing grant, a
-- guard trigger) returns 'refused <SQLSTATE>' instead of aborting the rolled-back transaction and every probe after it
CREATE FUNCTION pg_temp.wx_try_marketplace_sellers(op text) RETURNS text LANGUAGE plpgsql AS $wx$
DECLARE n int;
BEGIN
  IF op = 'foreign_update' THEN UPDATE marketplace_sellers SET id = id WHERE id = (SELECT foreign_row FROM _wx_marketplace_sellers);
  ELSIF op = 'foreign_delete' THEN DELETE FROM marketplace_sellers WHERE id = (SELECT foreign_row FROM _wx_marketplace_sellers);
  ELSIF op = 'own_update' THEN UPDATE marketplace_sellers SET id = id WHERE id = (SELECT own_row FROM _wx_marketplace_sellers);
  ELSIF op = 'move' THEN UPDATE marketplace_sellers SET hive_id = (SELECT foreign_hive FROM _wx_marketplace_sellers) WHERE id = (SELECT own_row FROM _wx_marketplace_sellers);
  END IF;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n::text;
EXCEPTION WHEN insufficient_privilege THEN RETURN 'refused 42501';
  WHEN others THEN RETURN 'refused ' || SQLSTATE;
END $wx$;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_marketplace_sellers)::text, 'role','authenticated')::text, true);
SELECT 'marketplace_sellers_foreign_update_touched | ' || pg_temp.wx_try_marketplace_sellers('foreign_update');
SELECT 'marketplace_sellers_foreign_delete_touched | ' || pg_temp.wx_try_marketplace_sellers('foreign_delete');
SELECT 'marketplace_sellers_move_into_foreign | ' || pg_temp.wx_try_marketplace_sellers('move');
SELECT 'marketplace_sellers_own_update_touched_gt0 | ' || (pg_temp.wx_try_marketplace_sellers('own_update') ~ '^[1-9]');
ROLLBACK;
SELECT 'marketplace_sellers_rows_restored | ' || ((SELECT count(*) FROM marketplace_sellers) = (SELECT n0 FROM _wx_marketplace_sellers));
