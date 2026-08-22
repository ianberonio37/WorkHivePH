-- best_answer_names_chooser: an accepted answer records WHO chose it and WHEN (mig ...062:
-- accepted_by/accepted_at), and the name recorded is the membership-VERIFIED worker_name (the RPC
-- reads it from the same hive_members row that authorises the caller — never caller-supplied).
-- Teeth: run the real RPC under claims and read the chooser back.
-- expect: columns_present \| t
-- expect: rpc_records_verified_actor \| t
-- expect: chooser_recorded \| t
-- expect: replies_restored \| t
SELECT 'columns_present | ' || (count(*) = 2) FROM information_schema.columns
WHERE table_name='community_replies' AND column_name IN ('accepted_by','accepted_at');
SELECT 'rpc_records_verified_actor | ' ||
  (prosrc ILIKE '%hm.worker_name%' AND prosrc ILIKE '%accepted_by%')
FROM pg_proc WHERE proname='set_community_best_answer';

CREATE TEMP TABLE _bc AS
SELECT hm.hive_id, hm.worker_name, hm.auth_uid,
       gen_random_uuid() AS post_id, gen_random_uuid() AS r1,
       (SELECT count(*) FROM community_replies) AS n0
FROM hive_members hm
WHERE hm.status = 'active' AND hm.auth_uid IS NOT NULL
LIMIT 1;

BEGIN;
INSERT INTO community_posts (id, hive_id, author_name, content, auth_uid)
SELECT post_id, hive_id, worker_name, 'BC-PROBE question', auth_uid FROM _bc;
INSERT INTO community_replies (id, post_id, hive_id, author_name, content)
SELECT r1, post_id, hive_id, 'Probe Replier', 'the answer' FROM _bc;
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT auth_uid FROM _bc)::text, 'role', 'authenticated')::text, true);
SELECT set_community_best_answer((SELECT r1 FROM _bc), true);
SELECT 'chooser_recorded | ' || (
  SELECT accepted_by = (SELECT worker_name FROM _bc) AND accepted_at IS NOT NULL
  FROM community_replies WHERE id = (SELECT r1 FROM _bc));
ROLLBACK;

SELECT 'replies_restored | ' || ((SELECT count(*) FROM community_replies) = (SELECT n0 FROM _bc));
DROP TABLE _bc;
