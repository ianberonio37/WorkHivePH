-- the_assignee_moves_their_job_forward: the active member an open job is ASSIGNED to (not its author) can start it and
-- finish it through advance_assigned_wo (mig 20261104000002) - and nobody else can, and nothing else moves. Found preparing
-- the group-journey walk GJ J9: a job a supervisor raised and handed on could not be moved by the person it was handed to,
-- because logbook's UPDATE policy is the author's alone.
-- Each leg runs AS the person (authenticated + their claims) in its own BEGIN/ROLLBACK, so nothing it writes survives:
--   * the assignee moves it to in_progress, then completed; the entry's account (problem) and status are untouched;
--   * the assignee may not set a supervisor state (approved) - refused;
--   * another member of the same hive, not the assignee, is refused;
--   * a direct UPDATE by the assignee still changes 0 rows (the owner-only policy is not widened).
-- Self-grounding: an open entry in a hive with two other active members (one becomes the assignee inside the leg).
-- expect: fixture_found \| t
-- expect: assignee_starts \| in_progress
-- expect: assignee_finishes \| completed
-- expect: account_untouched \| t
-- expect: a job is assigned to moves it to in progress or completed
-- expect: that job is not assigned to you
-- expect: direct_update_still_refused \| 0
-- expect: state_restored \| t
CREATE TEMP TABLE _a AS
SELECT l.id AS entry_id, l.hive_id, l.wo_state AS state0, l.wo_assigned_to AS to0, l.problem AS problem0, l.status AS status0,
       (SELECT hm.worker_name FROM hive_members hm WHERE hm.hive_id = l.hive_id AND hm.status = 'active' AND hm.auth_uid IS NOT NULL
          AND hm.auth_uid IS DISTINCT FROM l.auth_uid ORDER BY hm.worker_name LIMIT 1) AS asg_name,
       (SELECT hm.auth_uid FROM hive_members hm WHERE hm.hive_id = l.hive_id AND hm.status = 'active' AND hm.auth_uid IS NOT NULL
          AND hm.auth_uid IS DISTINCT FROM l.auth_uid ORDER BY hm.worker_name LIMIT 1) AS asg_uid,
       (SELECT hm.auth_uid FROM hive_members hm WHERE hm.hive_id = l.hive_id AND hm.status = 'active' AND hm.auth_uid IS NOT NULL
          AND hm.auth_uid IS DISTINCT FROM l.auth_uid ORDER BY hm.worker_name OFFSET 1 LIMIT 1) AS other_uid
  FROM logbook l
 WHERE l.status = 'Open' AND l.deleted_at IS NULL AND l.auth_uid IS NOT NULL
 ORDER BY l.created_at DESC
 LIMIT 1;
GRANT SELECT ON _a TO authenticated;
SELECT 'fixture_found | ' || EXISTS (SELECT 1 FROM _a WHERE asg_uid IS NOT NULL AND other_uid IS NOT NULL);

-- the assignee starts it and finishes it
BEGIN;
UPDATE logbook SET wo_assigned_to = (SELECT asg_name FROM _a), wo_state = 'assigned' WHERE id = (SELECT entry_id FROM _a);
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT asg_uid FROM _a)::text, 'role', 'authenticated')::text, true) IS NULL;
SET LOCAL ROLE authenticated;
SELECT 'assignee_starts | ' || (advance_assigned_wo((SELECT entry_id FROM _a), 'in_progress') ->> 'wo_state');
SELECT 'assignee_finishes | ' || (advance_assigned_wo((SELECT entry_id FROM _a), 'completed') ->> 'wo_state');
RESET ROLE;
SELECT 'account_untouched | ' || ((SELECT problem FROM logbook WHERE id = (SELECT entry_id FROM _a)) IS NOT DISTINCT FROM (SELECT problem0 FROM _a)
  AND (SELECT status FROM logbook WHERE id = (SELECT entry_id FROM _a)) IS NOT DISTINCT FROM (SELECT status0 FROM _a));
ROLLBACK;

-- the assignee may not take a supervisor's state
BEGIN;
UPDATE logbook SET wo_assigned_to = (SELECT asg_name FROM _a) WHERE id = (SELECT entry_id FROM _a);
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT asg_uid FROM _a)::text, 'role', 'authenticated')::text, true) IS NULL;
SET LOCAL ROLE authenticated;
SELECT advance_assigned_wo((SELECT entry_id FROM _a), 'approved');
ROLLBACK;

-- another member, not the assignee, is refused
BEGIN;
UPDATE logbook SET wo_assigned_to = (SELECT asg_name FROM _a) WHERE id = (SELECT entry_id FROM _a);
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT other_uid FROM _a)::text, 'role', 'authenticated')::text, true) IS NULL;
SET LOCAL ROLE authenticated;
SELECT advance_assigned_wo((SELECT entry_id FROM _a), 'in_progress');
ROLLBACK;

-- the owner-only policy is not widened: the assignee's direct UPDATE changes nothing
BEGIN;
UPDATE logbook SET wo_assigned_to = (SELECT asg_name FROM _a) WHERE id = (SELECT entry_id FROM _a);
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT asg_uid FROM _a)::text, 'role', 'authenticated')::text, true) IS NULL;
SET LOCAL ROLE authenticated;
WITH u AS (UPDATE logbook SET wo_state = 'completed' WHERE id = (SELECT entry_id FROM _a) RETURNING 1)
SELECT 'direct_update_still_refused | ' || count(*) FROM u;
ROLLBACK;

SELECT 'state_restored | ' || ((SELECT wo_state FROM logbook WHERE id = (SELECT entry_id FROM _a)) IS NOT DISTINCT FROM (SELECT state0 FROM _a)
  AND (SELECT wo_assigned_to FROM logbook WHERE id = (SELECT entry_id FROM _a)) IS NOT DISTINCT FROM (SELECT to0 FROM _a));
