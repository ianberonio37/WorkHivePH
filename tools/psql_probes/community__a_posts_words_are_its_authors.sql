-- a_posts_words_are_its_authors: what each role may do to a teammate's post, measured as the role (HS L2, 2026-10-30).
--   a worker may REPORT any teammate's post, an announcement included (the menu offers it to every worker; the
--   announcement guard used to refuse the report's flag as if the worker were posting one);
--   a worker still may NOT make their own post an announcement;
--   a supervisor moderates (pin) another member's post but cannot rewrite its words - they would go out under the
--   member's name - and still edits their own.
-- Every write is rolled back. Population printed (non-vacuity).
-- expect: announcements \| [1-9][0-9]*
-- expect: worker_reports_announcement \| t
-- expect: worker_makes_announcement \| refused
-- expect: supervisor_rewrite_kept_words \| t
-- expect: supervisor_pin_took \| t
-- expect: supervisor_own_edit_took \| t
\set H '30303030-3030-4030-8030-303030303030'
SELECT 'announcements | ' || count(*) FROM community_posts
 WHERE hive_id = :'H' AND category = 'announcement' AND deleted_at IS NULL;

BEGIN;
CREATE TEMP TABLE _r (k text, v text) ON COMMIT DROP;
GRANT ALL ON _r TO authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT auth_uid FROM hive_members
  WHERE worker_name = 'Joel Cruz' AND hive_id = :'H')::text, 'role', 'authenticated')::text, true);
SET LOCAL ROLE authenticated;
-- one not already under review: the HS walk's fixture keeps two reported posts in this hive, and reporting a post a
-- second time is a different question
SELECT 'worker_reports_announcement | ' || public.report_community_post((SELECT id FROM community_posts
  WHERE hive_id = :'H' AND category = 'announcement' AND deleted_at IS NULL AND NOT flagged
    AND author_name <> 'Joel Cruz' LIMIT 1));
DO $$
BEGIN
  UPDATE community_posts SET category = 'announcement'
   WHERE id = (SELECT id FROM community_posts WHERE author_name = 'Joel Cruz'
                AND hive_id = '30303030-3030-4030-8030-303030303030' AND deleted_at IS NULL
                AND category <> 'announcement' LIMIT 1);
  INSERT INTO _r VALUES ('make', 'allowed');
EXCEPTION WHEN insufficient_privilege THEN
  INSERT INTO _r VALUES ('make', 'refused');
END $$;
SELECT 'worker_makes_announcement | ' || v FROM _r WHERE k = 'make';
ROLLBACK;

BEGIN;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT auth_uid FROM hive_members
  WHERE worker_name = 'Ernesto Villareal' AND hive_id = :'H')::text, 'role', 'authenticated')::text, true);
SET LOCAL ROLE authenticated;
CREATE TEMP TABLE _o ON COMMIT DROP AS
  SELECT id, content, pinned FROM community_posts
   WHERE author_name <> 'Ernesto Villareal' AND hive_id = :'H' AND deleted_at IS NULL LIMIT 1;
CREATE TEMP TABLE _u ON COMMIT DROP AS
  WITH u AS (UPDATE community_posts c SET content = 'rewritten by a supervisor', pinned = NOT c.pinned
              FROM _o WHERE c.id = _o.id RETURNING c.content, c.pinned)
  SELECT * FROM u;
SELECT 'supervisor_rewrite_kept_words | ' || ((SELECT content FROM _u) = (SELECT content FROM _o));
SELECT 'supervisor_pin_took | ' || ((SELECT pinned FROM _u) IS DISTINCT FROM (SELECT pinned FROM _o));
WITH mine AS (SELECT id FROM community_posts WHERE author_name = 'Ernesto Villareal' AND hive_id = :'H'
               AND deleted_at IS NULL LIMIT 1),
     u AS (UPDATE community_posts c SET content = c.content || ' [own edit]' FROM mine WHERE c.id = mine.id
           RETURNING c.content LIKE '%[own edit]' AS took)
SELECT 'supervisor_own_edit_took | ' || bool_and(took) FROM u;
ROLLBACK;
