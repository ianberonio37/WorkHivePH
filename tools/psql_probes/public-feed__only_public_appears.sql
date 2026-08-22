-- only_public_appears: the public feed shows ONLY public, undeleted posts — under the anon ROLE the
-- truth view returns exactly the public live set, zero hive-only rows. Non-vacuity: the hive-only
-- population must exist for the exclusion to mean anything.
-- expect: hive_only_exist \| t
-- expect: anon_sees_only_public \| t
-- expect: anon_leaks \| 0
CREATE TEMP TABLE _pf AS
SELECT (SELECT count(*) FROM community_posts WHERE deleted_at IS NULL AND public) AS pub,
       (SELECT count(*) FROM community_posts WHERE deleted_at IS NULL AND NOT public) AS hive_only;
GRANT SELECT ON _pf TO anon;
SELECT 'hive_only_exist | ' || ((SELECT hive_only FROM _pf) > 0);
BEGIN;
SET LOCAL ROLE anon;
SELECT 'anon_sees_only_public | ' ||
  ((SELECT count(*) FROM v_community_posts_truth) = (SELECT pub FROM _pf));
SELECT 'anon_leaks | ' || count(*) FROM v_community_posts_truth WHERE public IS DISTINCT FROM true;
ROLLBACK;
DROP TABLE _pf;
