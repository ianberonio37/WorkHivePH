-- sharing_is_the_supervisors: a post reaches the Global feed only by a supervisor's decision (HS L2, 2026-10-30).
-- community.html offers "Make post public" and the "Share with all WorkHive teams" box to supervisors only; the server
-- holds the same line in tg_community_posts_moderation_fields. Teeth in BOTH directions, every write rolled back:
--   a worker cannot share their own post (update or insert), and their edit of a post a supervisor shared keeps it
--   shared (the edit's wording is kept); a supervisor CAN share another member's post; and a definer function acting
--   for the platform (publish_service_showcase's path) can still publish on a member's behalf.
-- The subjects are the full hive's worker and supervisor (seeders/full_hive.py); population printed (non-vacuity).
-- expect: subjects \| 2
-- expect: worker_update_shares \| f
-- expect: worker_insert_shares \| f
-- expect: worker_edit_keeps_shared \| t
-- expect: worker_edit_kept_wording \| t
-- expect: supervisor_shares \| t
-- expect: definer_path_shares \| t
\set H '30303030-3030-4030-8030-303030303030'
SELECT 'subjects | ' || count(*) FROM hive_members
 WHERE hive_id = :'H' AND status = 'active' AND auth_uid IS NOT NULL
   AND worker_name IN ('Joel Cruz', 'Ernesto Villareal');

BEGIN;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT auth_uid FROM hive_members
  WHERE worker_name = 'Joel Cruz' AND hive_id = :'H')::text, 'role', 'authenticated')::text, true);
SET LOCAL ROLE authenticated;
WITH mine AS (SELECT id FROM community_posts WHERE author_name = 'Joel Cruz' AND hive_id = :'H'
               AND deleted_at IS NULL AND NOT public LIMIT 1),
     u AS (UPDATE community_posts c SET public = true FROM mine WHERE c.id = mine.id RETURNING c.public)
SELECT 'worker_update_shares | ' || coalesce(bool_or(public), true) FROM u;
WITH u AS (INSERT INTO community_posts (hive_id, author_name, content, category, public, auth_uid)
           VALUES (:'H', 'Joel Cruz', 'probe - rolled back', 'general', true, (SELECT auth.uid())) RETURNING public)
SELECT 'worker_insert_shares | ' || bool_or(public) FROM u;
ROLLBACK;

BEGIN;
UPDATE community_posts SET public = true
 WHERE id = (SELECT id FROM community_posts WHERE author_name = 'Joel Cruz' AND hive_id = :'H'
              AND deleted_at IS NULL AND NOT public LIMIT 1);
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT auth_uid FROM hive_members
  WHERE worker_name = 'Joel Cruz' AND hive_id = :'H')::text, 'role', 'authenticated')::text, true);
SET LOCAL ROLE authenticated;
CREATE TEMP TABLE _e ON COMMIT DROP AS
WITH u AS (UPDATE community_posts c SET public = false, content = c.content || ' [probe edit]'
            WHERE c.author_name = 'Joel Cruz' AND c.hive_id = :'H' AND c.public AND c.deleted_at IS NULL
            RETURNING c.public, c.content LIKE '%[probe edit]' AS kept)
SELECT * FROM u;
SELECT 'worker_edit_keeps_shared | ' || (count(*) > 0 AND bool_and(public)) FROM _e;
SELECT 'worker_edit_kept_wording | ' || (count(*) > 0 AND bool_and(kept)) FROM _e;
ROLLBACK;

BEGIN;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT auth_uid FROM hive_members
  WHERE worker_name = 'Ernesto Villareal' AND hive_id = :'H')::text, 'role', 'authenticated')::text, true);
SET LOCAL ROLE authenticated;
WITH other AS (SELECT id FROM community_posts WHERE author_name <> 'Ernesto Villareal' AND hive_id = :'H'
                AND deleted_at IS NULL AND NOT public LIMIT 1),
     u AS (UPDATE community_posts c SET public = true FROM other WHERE c.id = other.id RETURNING c.public)
SELECT 'supervisor_shares | ' || coalesce(bool_and(public), false) FROM u;
ROLLBACK;

BEGIN;
CREATE FUNCTION public._probe_definer_publish(p uuid) RETURNS boolean LANGUAGE sql SECURITY DEFINER
  SET search_path = public AS $f$ UPDATE public.community_posts SET public = true WHERE id = p RETURNING public $f$;
GRANT EXECUTE ON FUNCTION public._probe_definer_publish(uuid) TO authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT auth_uid FROM hive_members
  WHERE worker_name = 'Joel Cruz' AND hive_id = :'H')::text, 'role', 'authenticated')::text, true);
SET LOCAL ROLE authenticated;
SELECT 'definer_path_shares | ' || public._probe_definer_publish((SELECT id FROM community_posts
  WHERE author_name = 'Joel Cruz' AND hive_id = :'H' AND deleted_at IS NULL AND NOT public LIMIT 1));
ROLLBACK;
