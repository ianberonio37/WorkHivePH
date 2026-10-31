-- a_departed_members_open_job: an open logbook entry whose author has left the hive can be closed, or assigned to an
-- active member, by an ACTIVE supervisor of the hive - and nothing else (mig 20261030000012). Before it, the only UPDATE
-- policy was the author's, so a departed member's open jobs stayed Open on every board for ever.
-- Each leg runs AS the person (authenticated + their claims) in its own BEGIN/ROLLBACK, so nothing it writes survives:
--   * the supervisor closes it (1 row) and assigns it to an active member (1 row);
--   * the supervisor may not rewrite what the entry says (42501), nor assign it to someone who is not an active member;
--   * a worker of the same hive cannot touch it (0 rows - RLS);
--   * an ACTIVE member's open entry stays the author's alone (the supervisor updates 0 rows).
-- Self-grounding: any hive holding a departed member's open entry, an active supervisor and an active worker.
-- expect: fixture_found \| t
-- expect: supervisor_closes \| 1
-- expect: take_over_pays_nobody \| 0
-- expect: supervisor_assigns \| 1
-- expect: A supervisor can close or assign a departed member's open job, not change it
-- expect: The job can be assigned only to an active member of this hive
-- expect: worker_cannot \| 0
-- expect: active_members_entry_untouched \| 0
-- expect: author_close_still_pays \| t
-- expect: state_restored \| t
CREATE TEMP TABLE _d AS
SELECT l.id AS entry_id, l.hive_id, l.status AS status0,
       (SELECT hm.auth_uid FROM hive_members hm WHERE hm.hive_id = l.hive_id AND hm.role = 'supervisor' AND hm.status = 'active' AND hm.auth_uid IS NOT NULL LIMIT 1) AS sup_uid,
       (SELECT hm.auth_uid FROM hive_members hm WHERE hm.hive_id = l.hive_id AND hm.role = 'worker' AND hm.status = 'active' AND hm.auth_uid IS NOT NULL LIMIT 1) AS wkr_uid,
       (SELECT hm.worker_name FROM hive_members hm WHERE hm.hive_id = l.hive_id AND hm.role = 'worker' AND hm.status = 'active' LIMIT 1) AS wkr_name,
       (SELECT hm.worker_name FROM hive_members hm WHERE hm.hive_id = l.hive_id AND hm.status <> 'active' LIMIT 1) AS gone_name,
       (SELECT a.id FROM logbook a JOIN hive_members am ON am.hive_id = a.hive_id AND am.auth_uid = a.auth_uid AND am.status = 'active'
         WHERE a.hive_id = l.hive_id AND a.status = 'Open' AND a.deleted_at IS NULL AND am.role = 'worker' LIMIT 1) AS active_entry
  FROM logbook l
 WHERE l.status = 'Open' AND l.deleted_at IS NULL AND l.auth_uid IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM hive_members hm WHERE hm.hive_id = l.hive_id AND hm.auth_uid = l.auth_uid AND hm.status = 'active')
   AND EXISTS (SELECT 1 FROM hive_members hm WHERE hm.hive_id = l.hive_id AND hm.role = 'supervisor' AND hm.status = 'active' AND hm.auth_uid IS NOT NULL)
 ORDER BY l.created_at DESC
 LIMIT 1;
GRANT SELECT ON _d TO authenticated;
SELECT 'fixture_found | ' || EXISTS (SELECT 1 FROM _d WHERE sup_uid IS NOT NULL AND wkr_uid IS NOT NULL AND active_entry IS NOT NULL);

BEGIN;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT sup_uid FROM _d)::text, 'role', 'authenticated')::text, true);
SET LOCAL ROLE authenticated;
WITH u AS (UPDATE logbook SET status = 'Closed', closed_at = now(), action = 'Closed by the supervisor - the member who raised it has left'
            WHERE id = (SELECT entry_id FROM _d) RETURNING 1)
SELECT 'supervisor_closes | ' || count(*) FROM u;
RESET ROLE;
-- the close award is the closer's own: a supervisor's take-over pays the departed author nothing (walked: it paid 50)
SELECT 'take_over_pays_nobody | ' || count(*) FROM achievement_xp_log
 WHERE source_id = (SELECT entry_id FROM _d)::text AND source_action IN ('logbook_close', 'breakdown_root_cause')
   AND earned_at >= now() - interval '1 second' AND reversed_at IS NULL;
ROLLBACK;

BEGIN;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT sup_uid FROM _d)::text, 'role', 'authenticated')::text, true);
SET LOCAL ROLE authenticated;
WITH u AS (UPDATE logbook SET wo_assigned_to = (SELECT wkr_name FROM _d), wo_state = 'assigned'
            WHERE id = (SELECT entry_id FROM _d) RETURNING 1)
SELECT 'supervisor_assigns | ' || count(*) FROM u;
ROLLBACK;

BEGIN;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT sup_uid FROM _d)::text, 'role', 'authenticated')::text, true);
SET LOCAL ROLE authenticated;
UPDATE logbook SET problem = 'rewritten by the supervisor' WHERE id = (SELECT entry_id FROM _d);
ROLLBACK;

BEGIN;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT sup_uid FROM _d)::text, 'role', 'authenticated')::text, true);
SET LOCAL ROLE authenticated;
UPDATE logbook SET wo_assigned_to = (SELECT gone_name FROM _d), wo_state = 'assigned' WHERE id = (SELECT entry_id FROM _d);
ROLLBACK;

BEGIN;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT wkr_uid FROM _d)::text, 'role', 'authenticated')::text, true);
SET LOCAL ROLE authenticated;
WITH u AS (UPDATE logbook SET status = 'Closed', closed_at = now() WHERE id = (SELECT entry_id FROM _d) RETURNING 1)
SELECT 'worker_cannot | ' || count(*) FROM u;
ROLLBACK;

BEGIN;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT sup_uid FROM _d)::text, 'role', 'authenticated')::text, true);
SET LOCAL ROLE authenticated;
WITH u AS (UPDATE logbook SET status = 'Closed', closed_at = now() WHERE id = (SELECT active_entry FROM _d) RETURNING 1)
SELECT 'active_members_entry_untouched | ' || count(*) FROM u;
ROLLBACK;

-- CONTROL: the author closing their OWN job is still paid - the take-over rule must not have stopped the award itself
BEGIN;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT a.auth_uid FROM logbook a WHERE a.id = (SELECT active_entry FROM _d))::text, 'role', 'authenticated')::text, true);
SET LOCAL ROLE authenticated;
UPDATE logbook SET status = 'Closed', closed_at = now() WHERE id = (SELECT active_entry FROM _d);
RESET ROLE;
SELECT 'author_close_still_pays | ' || (count(*) > 0) FROM achievement_xp_log
 WHERE source_id = (SELECT active_entry FROM _d)::text AND source_action = 'logbook_close' AND earned_at >= now() - interval '1 second';
ROLLBACK;

SELECT 'state_restored | ' || ((SELECT status FROM logbook WHERE id = (SELECT entry_id FROM _d)) = (SELECT status0 FROM _d));
DROP TABLE _d;
