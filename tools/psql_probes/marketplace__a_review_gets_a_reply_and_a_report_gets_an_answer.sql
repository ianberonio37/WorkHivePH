-- marketplace__a_review_gets_a_reply_and_a_report_gets_an_answer (GJ M9 J27, 2026-11-06, mig 20261106000011): only a
-- listing's own seller answers its reviews (the reviewer can neither answer for them through the function nor write the
-- reply columns directly), the answer pushes the reviewer; a person reads back their own reports and nobody else's, a
-- status/answer change pushes them, and the founder console's INTERNAL note never reaches the sender. All inside a
-- rolled-back transaction; restoration is asserted.
-- expect: fixture \| t
-- expect: reviewer_cannot_answer_for_the_seller \| t
-- expect: reviewer_cannot_write_the_reply_column \| refused
-- expect: seller_answers \| t
-- expect: answer_stamped_with_the_sellers_name \| t
-- expect: reviewer_pushed \| t
-- expect: sender_reads_own_outcome \| t
-- expect: stranger_reads_no_outcome \| t
-- expect: sender_pushed_with_the_answer \| t
-- expect: internal_note_never_pushed \| t
-- expect: restored \| t
CREATE FUNCTION pg_temp.try_exec(sql text) RETURNS text LANGUAGE plpgsql AS $f$
BEGIN
  EXECUTE sql;
  RETURN 'ran';
EXCEPTION WHEN insufficient_privilege THEN RETURN 'refused';
  WHEN others THEN RETURN 'error ' || SQLSTATE;
END $f$;
BEGIN;
SELECT l.id AS lid, l.auth_uid AS seller_uid,
       coalesce((SELECT display_name FROM worker_profiles w WHERE w.auth_uid = l.auth_uid LIMIT 1), l.seller_name) AS seller_name
  FROM marketplace_listings l WHERE l.auth_uid IS NOT NULL AND l.status = 'published' ORDER BY l.created_at LIMIT 1 \gset
SELECT hm.auth_uid AS buyer_uid, hm.worker_name AS buyer_name
  FROM hive_members hm WHERE hm.status = 'active' AND hm.auth_uid IS NOT NULL AND hm.auth_uid <> :'seller_uid'
 ORDER BY hm.auth_uid LIMIT 1 \gset
SELECT hm.auth_uid AS stranger_uid
  FROM hive_members hm WHERE hm.status = 'active' AND hm.auth_uid IS NOT NULL AND hm.auth_uid NOT IN (:'seller_uid', :'buyer_uid')
 ORDER BY hm.auth_uid DESC LIMIT 1 \gset
SET LOCAL session_replication_role = replica;   -- the fixture review and report are written past their intake guards
INSERT INTO marketplace_reviews (listing_id, reviewer_name, reviewer_auth_uid, rating, comment, created_at)
VALUES (:'lid', :'buyer_name', :'buyer_uid', 2, 'probe review - two arrived cracked', now()) RETURNING id AS rid \gset
INSERT INTO platform_feedback (auth_uid, worker_name, kind, subject, body, status)
VALUES (:'buyer_uid', :'buyer_name', 'bug', 'probe report', 'probe report body', 'new') RETURNING id AS fid \gset
SET LOCAL session_replication_role = origin;
SELECT 'fixture | ' || (:'rid' <> '' AND :'fid' <> '' AND :'stranger_uid' <> '');
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', :'buyer_uid', 'role', 'authenticated')::text, true) IS NOT NULL AS c1 \gset
SELECT 'reviewer_cannot_answer_for_the_seller | ' || NOT ((reply_to_listing_review(:'rid', 'probe forged answer')) ->> 'ok')::boolean;
SELECT 'reviewer_cannot_write_the_reply_column | ' || pg_temp.try_exec(format('UPDATE marketplace_reviews SET seller_reply = %L WHERE id = %L', 'probe forged', :'rid'));
SELECT set_config('request.jwt.claims', json_build_object('sub', :'seller_uid', 'role', 'authenticated')::text, true) IS NOT NULL AS c2 \gset
SELECT 'seller_answers | ' || ((reply_to_listing_review(:'rid', 'probe answer - replacements ship today')) ->> 'ok')::boolean;
RESET ROLE;
SELECT 'answer_stamped_with_the_sellers_name | ' || ((SELECT seller_reply = 'probe answer - replacements ship today' AND seller_replied_by = :'seller_name' AND seller_replied_at IS NOT NULL
   FROM marketplace_reviews WHERE id = :'rid'));
SELECT 'reviewer_pushed | ' || EXISTS (SELECT 1 FROM service_outbox WHERE payload->'auth_uids' ? :'buyer_uid'
   AND payload->>'title' = 'The seller answered your review' AND created_at >= now() - interval '1 minute');
-- the platform answers the report: an internal note and an answer to the sender
UPDATE platform_feedback SET status = 'resolved', admin_note = 'PROBE-INTERNAL-ONLY', sender_reply = 'probe answer to the sender' WHERE id = :'fid';
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', :'buyer_uid', 'role', 'authenticated')::text, true) IS NOT NULL AS c3 \gset
SELECT 'sender_reads_own_outcome | ' || EXISTS (SELECT 1 FROM my_feedback_outcomes() o WHERE o.id = :'fid' AND o.status = 'resolved' AND o.sender_reply = 'probe answer to the sender');
SELECT set_config('request.jwt.claims', json_build_object('sub', :'stranger_uid', 'role', 'authenticated')::text, true) IS NOT NULL AS c4 \gset
SELECT 'stranger_reads_no_outcome | ' || NOT EXISTS (SELECT 1 FROM my_feedback_outcomes() o WHERE o.id = :'fid');
RESET ROLE;
SELECT 'sender_pushed_with_the_answer | ' || EXISTS (SELECT 1 FROM service_outbox WHERE payload->'auth_uids' ? :'buyer_uid'
   AND payload->>'title' = 'WorkHive answered your report' AND payload->>'body' LIKE '%probe answer to the sender%');
SELECT 'internal_note_never_pushed | ' || NOT EXISTS (SELECT 1 FROM service_outbox WHERE payload::text LIKE '%PROBE-INTERNAL-ONLY%');
ROLLBACK;
SELECT 'restored | ' || (NOT EXISTS (SELECT 1 FROM marketplace_reviews WHERE comment = 'probe review - two arrived cracked')
   AND NOT EXISTS (SELECT 1 FROM platform_feedback WHERE subject = 'probe report'));
