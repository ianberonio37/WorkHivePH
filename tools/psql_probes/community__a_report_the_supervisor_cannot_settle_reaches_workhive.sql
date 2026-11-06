-- community__a_report_the_supervisor_cannot_settle_reaches_workhive (GJ M10 G-ESC, 2026-11-06, mig 20261106000015):
-- only a supervisor of the post's hive sends a REPORTED post on to WorkHive, with words; a second send points at the
-- first; the item is bound to the supervisor's account, linked to the post, carries the reports' reasons and never a
-- reporter's name, and can never be published (the founder included). WorkHive's answer pushes the supervisor AND every
-- reporter, never the author; each reads it back - the supervisor under "Your reports", the reporter there and in the
-- moderation news, where it replaces "waiting for a supervisor". All inside a rolled-back transaction; restoration asserted.
-- expect: fixture \| t
-- expect: a_worker_cannot_send_it_on \| refused
-- expect: words_are_required \| error 22023
-- expect: supervisor_sends_it_on \| t
-- expect: bound_to_the_supervisor_and_the_post \| t
-- expect: carries_the_reason_not_the_reporter \| t
-- expect: a_second_send_points_at_the_first \| t
-- expect: never_published_even_by_the_founder \| error 23514
-- expect: supervisor_pushed_with_the_answer \| t
-- expect: reporter_pushed_with_the_answer \| t
-- expect: author_not_pushed \| t
-- expect: supervisor_reads_it_back \| t
-- expect: reporter_reads_it_back \| t
-- expect: reporter_news_says_what_workhive_decided \| t
-- expect: reporter_news_no_longer_says_waiting \| t
-- expect: author_reads_no_escalation \| t
-- expect: restored \| t
CREATE FUNCTION pg_temp.try_exec(sql text) RETURNS text LANGUAGE plpgsql AS $f$
BEGIN
  EXECUTE sql;
  RETURN 'ran';
EXCEPTION WHEN insufficient_privilege THEN RETURN 'refused';
  WHEN others THEN RETURN 'error ' || SQLSTATE;
END $f$;
BEGIN;
-- a hive with a supervisor and two workers: one writes the post, the other reports it
SELECT s.hive_id AS hid, s.auth_uid AS sup_uid, s.worker_name AS sup_name
  FROM hive_members s
 WHERE s.status = 'active' AND s.role = 'supervisor' AND s.auth_uid IS NOT NULL
   AND (SELECT count(DISTINCT w.auth_uid) FROM hive_members w WHERE w.hive_id = s.hive_id AND w.status = 'active'
         AND w.role = 'worker' AND w.auth_uid IS NOT NULL AND w.auth_uid <> s.auth_uid) >= 2
 ORDER BY s.hive_id, s.auth_uid LIMIT 1 \gset
SELECT w.auth_uid AS rep_uid, w.worker_name AS rep_name FROM hive_members w
 WHERE w.hive_id = :'hid' AND w.status = 'active' AND w.role = 'worker' AND w.auth_uid IS NOT NULL AND w.auth_uid <> :'sup_uid'
 ORDER BY w.auth_uid LIMIT 1 \gset
SELECT w.auth_uid AS auth_uid_a, w.worker_name AS author_name FROM hive_members w
 WHERE w.hive_id = :'hid' AND w.status = 'active' AND w.role = 'worker' AND w.auth_uid IS NOT NULL
   AND w.auth_uid NOT IN (:'sup_uid', :'rep_uid')
 ORDER BY w.auth_uid DESC LIMIT 1 \gset
SET LOCAL session_replication_role = replica;   -- the fixture post and its report are written past their intake guards
INSERT INTO community_posts (hive_id, author_name, auth_uid, content, category, flagged)
VALUES (:'hid', :'author_name', :'auth_uid_a', 'probe escalation post - selling spare bearings', 'general', true)
RETURNING id AS pid \gset
INSERT INTO hive_audit_log (hive_id, actor, action, target_type, target_id, target_name, meta)
VALUES (:'hid', :'rep_name', 'report_post', 'community_posts', :'pid', 'probe',
        jsonb_build_object('target_id', :'pid', 'page', 'community', 'reason', 'spam', 'details', 'probe details',
                           'actor_auth_uid', :'rep_uid'));
SET LOCAL session_replication_role = origin;
SELECT 'fixture | ' || (:'pid' <> '' AND :'rep_uid' <> '' AND :'auth_uid_a' <> '');
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', :'rep_uid', 'role', 'authenticated')::text, true) IS NOT NULL AS c1 \gset
SELECT 'a_worker_cannot_send_it_on | ' || pg_temp.try_exec(format('SELECT escalate_reported_post(%L, %L)', :'pid', 'probe forged escalation'));
SELECT set_config('request.jwt.claims', json_build_object('sub', :'sup_uid', 'role', 'authenticated')::text, true) IS NOT NULL AS c2 \gset
SELECT 'words_are_required | ' || pg_temp.try_exec(format('SELECT escalate_reported_post(%L, %L)', :'pid', '   '));
SELECT escalate_reported_post(:'pid', 'probe words - a member is selling in the plant feed') AS r1 \gset
SELECT 'supervisor_sends_it_on | ' || ((:'r1')::jsonb ->> 'escalated')::boolean;
SELECT 'a_second_send_points_at_the_first | ' || (((escalate_reported_post(:'pid', 'probe again')) ->> 'id') = ((:'r1')::jsonb ->> 'id')
   AND ((escalate_reported_post(:'pid', 'probe again')) ->> 'reason') = 'already_with_workhive');
RESET ROLE;
SELECT ((:'r1')::jsonb ->> 'id') AS fid \gset
SELECT 'bound_to_the_supervisor_and_the_post | ' || ((SELECT auth_uid = :'sup_uid' AND ref_post_id = :'pid' AND NOT is_public
   AND 'escalation' = ANY (labels) AND body LIKE 'probe words%' FROM platform_feedback WHERE id = :'fid'));
SELECT 'carries_the_reason_not_the_reporter | ' || ((SELECT body LIKE '%spam%' AND body NOT LIKE '%' || :'rep_name' || '%'
   FROM platform_feedback WHERE id = :'fid'));
SELECT 'never_published_even_by_the_founder | ' || pg_temp.try_exec(format('UPDATE platform_feedback SET is_public = true WHERE id = %L', :'fid'));
-- WorkHive answers
UPDATE platform_feedback SET status = 'resolved', sender_reply = 'probe answer - personal sales are not allowed; the post is removed'
 WHERE id = :'fid';
SELECT 'supervisor_pushed_with_the_answer | ' || EXISTS (SELECT 1 FROM service_outbox WHERE payload->'auth_uids' ? :'sup_uid' AND payload->>'url' = '/feedback/?reports=1'
   AND payload->>'title' = 'WorkHive answered your report' AND payload->>'body' LIKE '%probe answer%');
SELECT 'reporter_pushed_with_the_answer | ' || EXISTS (SELECT 1 FROM service_outbox WHERE payload->'auth_uids' ? :'rep_uid' AND payload->>'url' = '/feedback/?reports=1'
   AND payload->>'title' = 'WorkHive reviewed the post you reported' AND payload->>'body' LIKE '%probe answer%');
SELECT 'author_not_pushed | ' || NOT EXISTS (SELECT 1 FROM service_outbox WHERE payload->'auth_uids' ? :'auth_uid_a'
   AND payload::text LIKE '%probe answer%');
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', :'sup_uid', 'role', 'authenticated')::text, true) IS NOT NULL AS c3 \gset
SELECT 'supervisor_reads_it_back | ' || EXISTS (SELECT 1 FROM my_feedback_outcomes() o WHERE o.id = :'fid'
   AND o.subject LIKE 'Reported post:%' AND o.status = 'resolved' AND o.sender_reply LIKE 'probe answer%');
SELECT set_config('request.jwt.claims', json_build_object('sub', :'rep_uid', 'role', 'authenticated')::text, true) IS NOT NULL AS c4 \gset
SELECT 'reporter_reads_it_back | ' || EXISTS (SELECT 1 FROM my_feedback_outcomes() o WHERE o.id = :'fid'
   AND o.subject LIKE 'A post you reported:%' AND o.sender_reply LIKE 'probe answer%');
SELECT 'reporter_news_says_what_workhive_decided | ' || EXISTS (SELECT 1 FROM my_moderation_news() n WHERE n.kind = 'escalation'
   AND n.post_id = :'pid' AND n.outcome = 'resolved' AND n.note LIKE 'probe answer%' AND n.moderated_by = :'sup_name');
SELECT 'reporter_news_no_longer_says_waiting | ' || NOT EXISTS (SELECT 1 FROM my_moderation_news() n WHERE n.kind = 'your_report'
   AND n.post_id = :'pid');
SELECT set_config('request.jwt.claims', json_build_object('sub', :'auth_uid_a', 'role', 'authenticated')::text, true) IS NOT NULL AS c5 \gset
SELECT 'author_reads_no_escalation | ' || (NOT EXISTS (SELECT 1 FROM my_feedback_outcomes() o WHERE o.id = :'fid')
   AND NOT EXISTS (SELECT 1 FROM my_moderation_news() n WHERE n.kind = 'escalation' AND n.post_id = :'pid'));
RESET ROLE;
ROLLBACK;
SELECT 'restored | ' || (NOT EXISTS (SELECT 1 FROM community_posts WHERE content = 'probe escalation post - selling spare bearings')
   AND NOT EXISTS (SELECT 1 FROM platform_feedback WHERE body LIKE 'probe words%'));
