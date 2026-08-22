-- money-lifecycle objection window: the BUYER (the only party the function accepts) raises a problem
-- on a 'completed' job -> ok:true, the job moves to 'disputed' NOT 'settled', and the reason is
-- journalled to service_job_events. Teeth the other way (own txn): a NON-buyer gets the party
-- refusal by name - the party check has no admin bypass above it. Fixture flipped in-txn, rolled back.
-- expect: fixture_found \| t
-- expect: "ok": ?true
-- expect: status_after \| disputed
-- expect: event_journalled \| t
-- expect: Only the person who hailed this job can raise a problem
-- forbid: status_after \| settled
CREATE TEMP TABLE _oj AS
SELECT sr.id AS job_id, sr.client_auth_uid AS buyer_uid,
       (SELECT hm.auth_uid FROM hive_members hm
         WHERE hm.auth_uid IS NOT NULL AND hm.auth_uid <> sr.client_auth_uid LIMIT 1) AS other_uid
FROM service_requests sr
WHERE sr.client_auth_uid IS NOT NULL
LIMIT 1;
GRANT SELECT ON _oj TO authenticated;
SELECT 'fixture_found | ' || (EXISTS (SELECT 1 FROM _oj WHERE other_uid IS NOT NULL));
BEGIN;
UPDATE service_requests SET status = 'completed', completed_at = now() WHERE id = (SELECT job_id FROM _oj);
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT buyer_uid FROM _oj)::text, 'role', 'authenticated')::text, true);
SELECT raise_service_objection((SELECT job_id FROM _oj), 'probe: the finished work was not what was hailed');
RESET ROLE;
SELECT 'status_after | ' || status FROM service_requests WHERE id = (SELECT job_id FROM _oj);
SELECT 'event_journalled | ' || (EXISTS (SELECT 1 FROM service_job_events
 WHERE request_id = (SELECT job_id FROM _oj) AND to_state = 'disputed'
   AND note ~* 'buyer raised a problem inside the objection window'));
ROLLBACK;
BEGIN;
UPDATE service_requests SET status = 'completed', completed_at = now() WHERE id = (SELECT job_id FROM _oj);
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT other_uid FROM _oj)::text, 'role', 'authenticated')::text, true);
SELECT raise_service_objection((SELECT job_id FROM _oj), 'probe: a stranger tries to object');
ROLLBACK;
DROP TABLE _oj;
