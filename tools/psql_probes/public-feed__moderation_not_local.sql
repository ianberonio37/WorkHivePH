-- moderation_not_local: moderation reaches the public feed — soft-deleting a public post removes it
-- from what the feed's own filtered read returns (the truth view EXPOSES deleted_at; callers filter
-- on it — the fix class where the OLD unfiltered query leaked). Teeth inside BEGIN/ROLLBACK, and
-- flagging is exposed the same way. Rollback restores the count.
-- expect: view_exposes_flags \| t
-- expect: softdelete_removes_from_feed \| t
-- expect: restored \| t
SELECT 'view_exposes_flags | ' || (
  pg_get_viewdef('v_community_posts_truth'::regclass) ILIKE '%deleted_at%'
  AND pg_get_viewdef('v_community_posts_truth'::regclass) ILIKE '%flagged%');
CREATE TEMP TABLE _md AS
SELECT id AS victim,
       (SELECT count(*) FROM v_community_posts_truth WHERE public AND deleted_at IS NULL) AS feed0
FROM community_posts WHERE public AND deleted_at IS NULL LIMIT 1;
BEGIN;
UPDATE community_posts SET deleted_at = now() WHERE id = (SELECT victim FROM _md);
SELECT 'softdelete_removes_from_feed | ' || (
  (SELECT count(*) FROM v_community_posts_truth WHERE public AND deleted_at IS NULL)
  = (SELECT feed0 - 1 FROM _md));
ROLLBACK;
SELECT 'restored | ' || (
  (SELECT count(*) FROM v_community_posts_truth WHERE public AND deleted_at IS NULL)
  = (SELECT feed0 FROM _md));
DROP TABLE _md;
