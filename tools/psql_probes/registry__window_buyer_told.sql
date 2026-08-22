-- money-lifecycle completion window, DB half: (1) fanout_completion_push tells the CLIENT the
-- deadline AND the consequence and returns early when client_auth_uid is null (nobody to tell);
-- (2) the date the row shows CANNOT disagree with the sweep: v_service_request_truth.objection_deadline
-- matches service_objection_deadline(id), both derived from the completion_window_days knob. The
-- truth view is caller-scoped (auth.uid()), so it is asked AS THE BUYER over an in-txn completed
-- fixture - asked as postgres it returns 0 rows and the comparison would be vacuous. (The page half -
-- svcWindowNotice()'s wording - is carried by marketplace.html in depends_on.)
-- expect: fixture_found \| t
-- expect: push_tells_deadline_and_consequence \| t
-- expect: push_returns_early_when_nobody_to_tell \| t
-- expect: rows_checked \| [1-9][0-9]*
-- expect: deadline_present \| t
-- expect: deadline_disagreements \| 0
CREATE TEMP TABLE _wt AS
SELECT sr.id AS job_id, sr.client_auth_uid AS buyer_uid
FROM service_requests sr WHERE sr.client_auth_uid IS NOT NULL LIMIT 1;
GRANT SELECT ON _wt TO authenticated;
SELECT 'fixture_found | ' || (EXISTS (SELECT 1 FROM _wt));
SELECT 'push_tells_deadline_and_consequence | ' ||
       (prosrc ~* 'marked done' AND prosrc ~* 'raise a problem by' AND prosrc ~* 'settles automatically')
  FROM pg_proc WHERE proname = 'fanout_completion_push';
SELECT 'push_returns_early_when_nobody_to_tell | ' ||
       (prosrc ~* 'client_auth_uid[^;]*null' AND prosrc ~* 'return')
  FROM pg_proc WHERE proname = 'fanout_completion_push';
BEGIN;
UPDATE service_requests SET status = 'completed', completed_at = now() WHERE id = (SELECT job_id FROM _wt);
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT buyer_uid FROM _wt)::text, 'role', 'authenticated')::text, true);
SELECT 'rows_checked | ' || count(*) FROM v_service_request_truth;
SELECT 'deadline_present | ' || (objection_deadline IS NOT NULL)
  FROM v_service_request_truth WHERE id = (SELECT job_id FROM _wt);
SELECT 'deadline_disagreements | ' || count(*) FROM v_service_request_truth t
 WHERE t.objection_deadline IS DISTINCT FROM service_objection_deadline(t.id);
ROLLBACK;
DROP TABLE _wt;
