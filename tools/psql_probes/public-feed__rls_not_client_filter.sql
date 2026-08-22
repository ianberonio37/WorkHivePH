-- rls_not_client_filter: the public/hive-only boundary is enforced by RLS at the DATABASE, not by a
-- client-side filter — under the anon ROLE even the RAW community_posts table returns only public
-- rows, while as postgres (control) the hive-only rows demonstrably exist.
-- expect: control_sees_hive_only \| t
-- expect: anon_raw_leaks \| 0
-- expect: anon_view_leaks \| 0
CREATE TEMP TABLE _rl AS
SELECT (SELECT count(*) FROM community_posts WHERE deleted_at IS NULL AND NOT public) AS hive_only;
GRANT SELECT ON _rl TO anon;
SELECT 'control_sees_hive_only | ' || ((SELECT hive_only FROM _rl) > 0);
BEGIN;
SET LOCAL ROLE anon;
SELECT 'anon_raw_leaks | ' || count(*) FROM community_posts WHERE public IS DISTINCT FROM true;
SELECT 'anon_view_leaks | ' || count(*) FROM v_community_posts_truth WHERE public IS DISTINCT FROM true;
ROLLBACK;
DROP TABLE _rl;
