-- tenant boundary on community posts, asked as a real MEMBER of another hive: a foreign hive's
-- public=false post is INVISIBLE (0 rows for a row that demonstrably exists), while a foreign
-- public=true post IS visible - cross-hive by design, which the surface states in words ("public
-- posts are visible across hives"). Both directions pinned to specific existing ids so neither
-- answer can be vacuous. Read-only; the txn exists only to scope role+claims.
-- expect: fixture_found \| t
-- expect: foreign_private_exists \| 1
-- expect: member_sees_foreign_private \| 0
-- expect: member_sees_foreign_public \| 1
CREATE TEMP TABLE _tb AS
SELECT hm.auth_uid AS member_uid, hm.hive_id AS my_hive,
       (SELECT cp.id FROM community_posts cp
         WHERE cp.public = false AND cp.deleted_at IS NULL AND cp.hive_id <> hm.hive_id
           AND cp.hive_id NOT IN (SELECT h2.hive_id FROM hive_members h2 WHERE h2.auth_uid = hm.auth_uid)
         LIMIT 1) AS foreign_private_id,
       (SELECT cp2.id FROM community_posts cp2
         WHERE cp2.public = true AND cp2.deleted_at IS NULL AND cp2.hive_id <> hm.hive_id
           AND cp2.hive_id NOT IN (SELECT h3.hive_id FROM hive_members h3 WHERE h3.auth_uid = hm.auth_uid)
         LIMIT 1) AS foreign_public_id
FROM hive_members hm
WHERE hm.status = 'active' AND hm.auth_uid IS NOT NULL
ORDER BY hm.worker_name
LIMIT 1;
GRANT SELECT ON _tb TO authenticated;
SELECT 'fixture_found | ' || (EXISTS (SELECT 1 FROM _tb WHERE foreign_private_id IS NOT NULL AND foreign_public_id IS NOT NULL));
SELECT 'foreign_private_exists | ' || count(*) FROM community_posts WHERE id = (SELECT foreign_private_id FROM _tb);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT member_uid FROM _tb)::text, 'role', 'authenticated')::text, true);
SELECT 'member_sees_foreign_private | ' || count(*) FROM community_posts WHERE id = (SELECT foreign_private_id FROM _tb);
SELECT 'member_sees_foreign_public | ' || count(*) FROM community_posts WHERE id = (SELECT foreign_public_id FROM _tb);
ROLLBACK;
DROP TABLE _tb;
