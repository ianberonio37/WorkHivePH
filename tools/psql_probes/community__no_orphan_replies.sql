-- no_orphan_replies (community): a deleted post leaves no reply rendered without its context. A reply
-- whose post is gone is not untidiness - it is half a conversation shown with no question above it,
-- and on a moderated feed it is how a removed post's content outlives its own removal.
-- The mechanism is the FK: community_replies.post_id REFERENCES community_posts ON DELETE CASCADE, so
-- the database takes the replies with the post instead of trusting every delete path to remember.
--
-- THE FIXTURE IS SELF-GROUNDED, AND THAT IS THE POINT (2026-08-31). community_replies is EMPTY today
-- while 111 posts exist, so the obvious probe - find a post with replies, delete it, watch them go -
-- silently degenerates: the fixture subquery returns NULL, the DELETE matches nothing, and the
-- assertion "its replies are gone" is satisfied by a delete that never happened. It PASSES, greenly,
-- proving nothing. So the probe MAKES its own post and replies inside the transaction, and asserts it
-- really created them before drawing any conclusion from their absence.
-- expect: fk_is_on_delete_cascade \| t
-- expect: orphans_now \| 0
-- expect: fixture_created_replies \| 3
-- expect: replies_gone_with_post \| t
-- expect: orphans_after_delete \| 0
-- expect: rows_restored_after_rollback \| t
SELECT 'fk_is_on_delete_cascade | ' || EXISTS (
  SELECT 1 FROM pg_constraint WHERE conrelid='public.community_replies'::regclass AND contype='f'
    AND pg_get_constraintdef(oid) ILIKE '%REFERENCES community_posts(id) ON DELETE CASCADE%');
SELECT 'orphans_now | ' || count(*) FROM community_replies r
 WHERE NOT EXISTS (SELECT 1 FROM community_posts p WHERE p.id = r.post_id);

CREATE TEMP TABLE _base AS SELECT (SELECT count(*) FROM community_replies) AS r0,
                                  (SELECT count(*) FROM community_posts)   AS p0,
                                  (SELECT hive_id FROM community_posts LIMIT 1) AS hive;

BEGIN;
-- build the situation the invariant is about, rather than hoping the database is already in it
CREATE TEMP TABLE _mk AS
WITH p AS (
  INSERT INTO community_posts (hive_id, author_name, content)
  SELECT hive, 'WH-PROBE author', 'WH-PROBE post for the cascade recipe' FROM _base
  RETURNING id, hive_id)
, r AS (
  INSERT INTO community_replies (post_id, hive_id, author_name, content)
  SELECT p.id, p.hive_id, 'WH-PROBE replier', 'WH-PROBE reply ' || g
  FROM p, generate_series(1,3) g
  RETURNING post_id)
SELECT (SELECT id FROM p) AS post_id, (SELECT count(*) FROM r) AS n_replies;
SELECT 'fixture_created_replies | ' || (SELECT n_replies FROM _mk);

DELETE FROM community_posts WHERE id = (SELECT post_id FROM _mk);
SELECT 'replies_gone_with_post | ' ||
  ((SELECT count(*) FROM community_replies WHERE post_id = (SELECT post_id FROM _mk)) = 0);
SELECT 'orphans_after_delete | ' || (SELECT count(*) FROM community_replies r
  WHERE NOT EXISTS (SELECT 1 FROM community_posts p WHERE p.id = r.post_id));
ROLLBACK;

SELECT 'rows_restored_after_rollback | ' ||
  ((SELECT count(*) FROM community_replies) = (SELECT r0 FROM _base)
   AND (SELECT count(*) FROM community_posts) = (SELECT p0 FROM _base));
DROP TABLE _base;
