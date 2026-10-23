-- cross_hive_read_refused (community, P-B, generated 2026-09-05 by tools/gen_cross_hive_read_recipes.py): every
-- hive-scoped table this page reads (community_replies, community_reactions, community_xp) must refuse a foreign hive in the DATABASE. RLS USING
-- clauses FILTER rather than raise, so the probe counts rows as a member of exactly one hive: a foreign hive with
-- rows reads 0, the member's own hive reads > 0 (the control). Fixtures are chosen live; a table with rows in
-- fewer than two hives reports 'n/a' and is excluded from the expectations by the generator.
-- expect: community_replies_fixture \| t
-- expect: community_replies_foreign_rows \| 0
-- expect: community_replies_own_rows_gt0 \| t
-- expect: community_reactions_fixture \| t
-- expect: community_reactions_foreign_rows \| 0
-- expect: community_reactions_own_rows_gt0 \| t
-- expect: community_xp_fixture \| t
-- expect: community_xp_foreign_rows \| 0
-- expect: community_xp_own_rows_gt0 \| t

CREATE TEMP TABLE _fx_community_replies AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM community_replies x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM community_replies x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_community_replies TO authenticated;
SELECT 'community_replies_fixture | ' || ((SELECT me FROM _fx_community_replies) IS NOT NULL AND (SELECT foreign_hive FROM _fx_community_replies) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_community_replies)::text, 'role','authenticated')::text, true);
SELECT 'community_replies_foreign_rows | ' || (SELECT count(*) FROM community_replies WHERE hive_id = (SELECT foreign_hive FROM _fx_community_replies));
SELECT 'community_replies_own_rows_gt0 | ' || ((SELECT count(*) FROM community_replies WHERE hive_id = (SELECT mine FROM _fx_community_replies)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_community_reactions AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM community_reactions x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id AND NOT EXISTS (SELECT 1 FROM community_posts cp WHERE cp.id = x.post_id AND cp.public)
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM community_reactions x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_community_reactions TO authenticated;
SELECT 'community_reactions_fixture | ' || ((SELECT me FROM _fx_community_reactions) IS NOT NULL AND (SELECT foreign_hive FROM _fx_community_reactions) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_community_reactions)::text, 'role','authenticated')::text, true);
SELECT 'community_reactions_foreign_rows | ' || (SELECT count(*) FROM community_reactions WHERE hive_id = (SELECT foreign_hive FROM _fx_community_reactions) AND NOT EXISTS (SELECT 1 FROM community_posts cp WHERE cp.id = post_id AND cp.public));
SELECT 'community_reactions_own_rows_gt0 | ' || ((SELECT count(*) FROM community_reactions WHERE hive_id = (SELECT mine FROM _fx_community_reactions)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_community_xp AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM community_xp x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM community_xp x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_community_xp TO authenticated;
SELECT 'community_xp_fixture | ' || ((SELECT me FROM _fx_community_xp) IS NOT NULL AND (SELECT foreign_hive FROM _fx_community_xp) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_community_xp)::text, 'role','authenticated')::text, true);
SELECT 'community_xp_foreign_rows | ' || (SELECT count(*) FROM community_xp WHERE hive_id = (SELECT foreign_hive FROM _fx_community_xp));
SELECT 'community_xp_own_rows_gt0 | ' || ((SELECT count(*) FROM community_xp WHERE hive_id = (SELECT mine FROM _fx_community_xp)) > 0);
ROLLBACK;
