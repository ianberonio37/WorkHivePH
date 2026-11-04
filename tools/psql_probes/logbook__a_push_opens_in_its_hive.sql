-- a_push_opens_in_its_hive: the "Work order assigned to you" push links the logbook WITH its hive (&hive=<id>), so a
-- person who belongs to two hives opens it in the hive the job is in (mig 20261105000003; the page start-up whStartupHive
-- seats a linked hive only for an active member of it). Found by the group-journey walk GJ G-MULTI hand-off 3: the push
-- sent /logbook.html?status=Open and a contractor last standing in their other hive opened a logbook without the job.
-- The leg runs AS a supervisor (authenticated + their claims) in its own BEGIN/ROLLBACK; the entry and push go too.
-- Self-grounding: a hive with an active supervisor and an active worker, both with accounts.
-- expect: fixture_found \| t
-- expect: push_names_its_hive \| t
CREATE TEMP TABLE _p AS
SELECT s.hive_id, s.auth_uid AS sup_uid, s.worker_name AS sup_name, w.auth_uid AS w_uid, w.worker_name AS w_name
  FROM hive_members s
  JOIN hive_members w ON w.hive_id = s.hive_id AND w.role = 'worker' AND w.status = 'active' AND w.auth_uid IS NOT NULL
 WHERE s.role = 'supervisor' AND s.status = 'active' AND s.auth_uid IS NOT NULL
 ORDER BY s.hive_id, w.worker_name
 LIMIT 1;
GRANT SELECT ON _p TO authenticated;
SELECT 'fixture_found | ' || EXISTS (SELECT 1 FROM _p);

BEGIN;
INSERT INTO logbook (id, hive_id, worker_name, auth_uid, machine, problem, status, wo_state, wo_assigned_to, date)
SELECT 'probe-push-hive-1', hive_id, sup_name, sup_uid, 'Probe machine', 'probe: a push opens in its hive', 'Open', 'assigned', w_name, now()
  FROM _p;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT sup_uid FROM _p)::text, 'role', 'authenticated')::text, true) IS NULL;
SET LOCAL ROLE authenticated;
SELECT notify_wo_assigned('probe-push-hive-1');
RESET ROLE;
SELECT 'push_names_its_hive | ' || EXISTS (SELECT 1 FROM service_outbox o WHERE o.consumer = 'notify-push' AND o.created_at >= now() - interval '1 minute'
  AND o.payload->'auth_uids' ? (SELECT w_uid FROM _p)::text
  AND o.payload->>'url' = '/logbook.html?status=Open&hive=' || (SELECT hive_id FROM _p)::text);
ROLLBACK;
