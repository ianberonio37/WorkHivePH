-- a_supervisor_moves_a_work_order: an ACTIVE supervisor of an entry's hive can approve, assign, verify or reject the work
-- order on a teammate's open entry through set_logbook_wo (mig 20261104000001) - and nobody else can, and nothing else
-- moves. Found by the group-journey walk (GJ J2 hand-off 2): the form promised "supervisors approve, assign, and verify"
-- while logbook's UPDATE policy is the author's alone, so the seven-state workflow could not be driven by a supervisor.
-- Each leg runs AS the person (authenticated + their claims) in its own BEGIN/ROLLBACK, so nothing it writes survives:
--   * the supervisor assigns the worker's entry to another active member: the state, the assignee, the push to them;
--   * only wo_state / wo_assigned_to move - the worker's own account (problem) is untouched;
--   * the entry's author (a worker), and a supervisor of ANOTHER hive, are refused (42501);
--   * an assignee who is not an active member of the hive is refused;
--   * a direct UPDATE by the supervisor still changes 0 rows (the owner-only policy is not widened).
-- Self-grounding: any hive with an active worker's open entry, an active supervisor and a second active member.
-- expect: fixture_found \| t
-- expect: supervisor_assigns \| assigned
-- expect: assignee_is_the_member \| t
-- expect: push_to_the_assignee \| t
-- expect: account_untouched \| t
-- expect: only an active supervisor of the entry's hive may move its work order
-- expect: is not an active member of this hive
-- expect: direct_update_still_refused \| 0
-- expect: state_restored \| t
CREATE TEMP TABLE _w AS
SELECT l.id AS entry_id, l.hive_id, l.wo_state AS state0, l.problem AS problem0, l.auth_uid AS author_uid,
       (SELECT hm.auth_uid FROM hive_members hm WHERE hm.hive_id = l.hive_id AND hm.role = 'supervisor' AND hm.status = 'active'
          AND hm.auth_uid IS NOT NULL ORDER BY hm.worker_name LIMIT 1) AS sup_uid,
       (SELECT hm.worker_name FROM hive_members hm WHERE hm.hive_id = l.hive_id AND hm.status = 'active' AND hm.auth_uid IS NOT NULL
          AND hm.auth_uid <> l.auth_uid ORDER BY hm.worker_name LIMIT 1) AS to_name,
       (SELECT hm.auth_uid FROM hive_members hm WHERE hm.hive_id = l.hive_id AND hm.status = 'active' AND hm.auth_uid IS NOT NULL
          AND hm.auth_uid <> l.auth_uid ORDER BY hm.worker_name LIMIT 1) AS to_uid,
       (SELECT hm.auth_uid FROM hive_members hm WHERE hm.hive_id <> l.hive_id AND hm.role = 'supervisor' AND hm.status = 'active'
          AND hm.auth_uid IS NOT NULL AND NOT EXISTS (SELECT 1 FROM hive_members x WHERE x.hive_id = l.hive_id AND x.auth_uid = hm.auth_uid)
          ORDER BY hm.worker_name LIMIT 1) AS foreign_sup
  FROM logbook l
  JOIN hive_members am ON am.hive_id = l.hive_id AND am.auth_uid = l.auth_uid AND am.status = 'active' AND am.role = 'worker'
 WHERE l.status = 'Open' AND l.deleted_at IS NULL
 ORDER BY l.created_at DESC
 LIMIT 1;
GRANT SELECT ON _w TO authenticated;
SELECT 'fixture_found | ' || EXISTS (SELECT 1 FROM _w WHERE sup_uid IS NOT NULL AND to_uid IS NOT NULL AND foreign_sup IS NOT NULL);

-- the supervisor assigns it, and the assignee is pushed
BEGIN;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT sup_uid FROM _w)::text, 'role', 'authenticated')::text, true) IS NULL;
SET LOCAL ROLE authenticated;
SELECT 'supervisor_assigns | ' || (set_logbook_wo((SELECT entry_id FROM _w), 'assigned', (SELECT to_name FROM _w)) ->> 'wo_state');
RESET ROLE;
SELECT 'assignee_is_the_member | ' || ((SELECT wo_assigned_to FROM logbook WHERE id = (SELECT entry_id FROM _w)) = (SELECT to_name FROM _w));
SELECT 'push_to_the_assignee | ' || EXISTS (SELECT 1 FROM service_outbox o WHERE o.consumer = 'notify-push'
  AND o.created_at >= now() - interval '1 minute' AND o.payload->'auth_uids' ? (SELECT to_uid FROM _w)::text
  AND o.payload->>'title' = 'Work order assigned to you');
SELECT 'account_untouched | ' || ((SELECT problem FROM logbook WHERE id = (SELECT entry_id FROM _w)) IS NOT DISTINCT FROM (SELECT problem0 FROM _w));
ROLLBACK;

-- the entry's own author (a worker) is refused
BEGIN;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT author_uid FROM _w)::text, 'role', 'authenticated')::text, true) IS NULL;
SET LOCAL ROLE authenticated;
SELECT set_logbook_wo((SELECT entry_id FROM _w), 'approved');
ROLLBACK;

-- a supervisor of ANOTHER hive is refused
BEGIN;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT foreign_sup FROM _w)::text, 'role', 'authenticated')::text, true) IS NULL;
SET LOCAL ROLE authenticated;
SELECT set_logbook_wo((SELECT entry_id FROM _w), 'assigned', (SELECT to_name FROM _w));
ROLLBACK;

-- an assignee who is not an active member is refused
BEGIN;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT sup_uid FROM _w)::text, 'role', 'authenticated')::text, true) IS NULL;
SET LOCAL ROLE authenticated;
SELECT set_logbook_wo((SELECT entry_id FROM _w), 'assigned', 'Nobody Of This Hive');
ROLLBACK;

-- the owner-only policy is not widened: a direct UPDATE by the supervisor changes nothing
BEGIN;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT sup_uid FROM _w)::text, 'role', 'authenticated')::text, true) IS NULL;
SET LOCAL ROLE authenticated;
WITH u AS (UPDATE logbook SET wo_state = 'assigned' WHERE id = (SELECT entry_id FROM _w) RETURNING 1)
SELECT 'direct_update_still_refused | ' || count(*) FROM u;
ROLLBACK;

SELECT 'state_restored | ' || ((SELECT wo_state FROM logbook WHERE id = (SELECT entry_id FROM _w)) IS NOT DISTINCT FROM (SELECT state0 FROM _w));
