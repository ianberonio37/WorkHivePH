-- best_answer_single: a post can hold at most ONE accepted answer — set_community_best_answer
-- clears any prior holder before setting the new one, atomically. Full-path teeth inside
-- BEGIN/ROLLBACK: seed a post + two replies, call the REAL RPC under the post author's claims
-- (auth.uid() via request.jwt.claims — the RPC authorises through hive_members), accept #1 then #2,
-- and the accepted count must stay 1 while the holder switches. Rollback restores the table.
-- expect: accepted_after_first \| 1
-- expect: single_after_second \| 1
-- expect: holder_switched \| t
-- expect: replies_restored \| t
CREATE TEMP TABLE _ba AS
SELECT hm.hive_id, hm.worker_name, hm.auth_uid,
       gen_random_uuid() AS post_id, gen_random_uuid() AS r1, gen_random_uuid() AS r2,
       (SELECT count(*) FROM community_replies) AS n0
FROM hive_members hm
WHERE hm.status = 'active' AND hm.auth_uid IS NOT NULL
LIMIT 1;

BEGIN;

INSERT INTO community_posts (id, hive_id, author_name, content, auth_uid)
SELECT post_id, hive_id, worker_name, 'BA-PROBE question', auth_uid FROM _ba;
INSERT INTO community_replies (id, post_id, hive_id, author_name, content)
SELECT r1, post_id, hive_id, 'Probe Replier A', 'answer one' FROM _ba;
INSERT INTO community_replies (id, post_id, hive_id, author_name, content)
SELECT r2, post_id, hive_id, 'Probe Replier B', 'answer two' FROM _ba;

SELECT set_config('request.jwt.claims',
                  json_build_object('sub', (SELECT auth_uid FROM _ba)::text, 'role', 'authenticated')::text,
                  true);

SELECT set_community_best_answer((SELECT r1 FROM _ba), true);
SELECT 'accepted_after_first | ' || count(*) FROM community_replies
WHERE post_id = (SELECT post_id FROM _ba) AND is_accepted;

SELECT set_community_best_answer((SELECT r2 FROM _ba), true);
SELECT 'single_after_second | ' || count(*) FROM community_replies
WHERE post_id = (SELECT post_id FROM _ba) AND is_accepted;
SELECT 'holder_switched | ' || (
  (SELECT id FROM community_replies WHERE post_id = (SELECT post_id FROM _ba) AND is_accepted)
  = (SELECT r2 FROM _ba));
ROLLBACK;

-- _ba survives the rollback (created BEFORE the txn) so n0 is a real baseline, not a tautology —
-- the first version compared count(*) to itself, a green that cannot fail.
SELECT 'replies_restored | ' || ((SELECT count(*) FROM community_replies) = (SELECT n0 FROM _ba));
DROP TABLE _ba;
