-- feedback__the_public_board_reads_the_words_not_the_sender (GJ M10, 2026-11-06, mig 20261106000014): a published
-- feedback item reaches a visitor as its words, kind, status, status date and votes - never the sender's email, account,
-- name, hive or browser, nor the founder's internal note. Anon cannot read the table at all and a signed-in member reads
-- no row of it; the board's definer read carries only the public columns; a status change dates itself and a vote does
-- not; the feedback button can still post without an account. All inside a rolled-back transaction; restoration asserted.
-- expect: fixture \| t
-- expect: anon_cannot_read_the_email \| refused
-- expect: anon_cannot_read_the_table \| refused
-- expect: board_shows_the_item \| t
-- expect: board_carries_no_sender_column \| t
-- expect: member_reads_no_row_directly \| t
-- expect: status_change_is_dated \| t
-- expect: a_vote_is_not_a_status_change \| t
-- expect: anon_can_still_send \| ran
-- expect: anon_cannot_list_voter_tokens \| refused
-- expect: a_visitor_reads_their_own_votes \| t
-- expect: a_visitor_reads_no_one_elses_votes \| t
-- expect: restored \| t
CREATE FUNCTION pg_temp.try_exec(sql text) RETURNS text LANGUAGE plpgsql AS $f$
BEGIN
  EXECUTE sql;
  RETURN 'ran';
EXCEPTION WHEN insufficient_privilege THEN RETURN 'refused';
  WHEN others THEN RETURN 'error ' || SQLSTATE;
END $f$;
BEGIN;
SELECT hm.auth_uid AS sender_uid, hm.worker_name AS sender_name, hm.hive_id AS sender_hive
  FROM hive_members hm WHERE hm.status = 'active' AND hm.auth_uid IS NOT NULL ORDER BY hm.auth_uid LIMIT 1 \gset
SELECT hm.auth_uid AS member_uid
  FROM hive_members hm WHERE hm.status = 'active' AND hm.auth_uid IS NOT NULL AND hm.auth_uid <> :'sender_uid'
   AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = hm.auth_uid)
 ORDER BY hm.auth_uid DESC LIMIT 1 \gset
INSERT INTO platform_feedback (auth_uid, worker_name, hive_id, contact_email, kind, subject, body, status, is_public,
                               admin_note, user_agent, created_at)
VALUES (:'sender_uid', :'sender_name', :'sender_hive', 'probe-sender@local.invalid', 'idea', 'probe public item',
        'probe public body', 'triaged', true, 'PROBE-INTERNAL-NOTE', 'probe-agent', now() - interval '2 days')
RETURNING id AS fid \gset
SELECT 'fixture | ' || (:'fid' <> '' AND :'member_uid' <> '');
SET LOCAL ROLE anon;
SELECT 'anon_cannot_read_the_email | ' || pg_temp.try_exec(format('SELECT contact_email FROM platform_feedback WHERE id = %L', :'fid'));
SELECT 'anon_cannot_read_the_table | ' || pg_temp.try_exec(format('SELECT id FROM platform_feedback WHERE id = %L', :'fid'));
SELECT 'board_shows_the_item | ' || EXISTS (SELECT 1 FROM public_feedback_board() b WHERE b.id = :'fid' AND b.subject = 'probe public item');
SELECT 'board_carries_no_sender_column | ' || NOT EXISTS (
  SELECT 1 FROM public_feedback_board() b, jsonb_object_keys(to_jsonb(b)) k
   WHERE b.id = :'fid' AND k IN ('contact_email', 'auth_uid', 'worker_name', 'hive_id', 'user_agent', 'admin_note', 'sender_reply'));
RESET ROLE;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', :'member_uid', 'role', 'authenticated')::text, true) IS NOT NULL AS c1 \gset
SELECT 'member_reads_no_row_directly | ' || ((SELECT count(*) FROM platform_feedback WHERE id = :'fid') = 0);
RESET ROLE;
UPDATE platform_feedback SET status = 'resolved' WHERE id = :'fid';
SELECT 'status_change_is_dated | ' || ((SELECT status_at > now() - interval '1 minute' FROM platform_feedback WHERE id = :'fid'));
-- status_at is pinned against direct writes (only a status change moves it), so the fixture backdates it with triggers off
SET LOCAL session_replication_role = replica;
UPDATE platform_feedback SET status_at = now() - interval '1 day' WHERE id = :'fid';
SET LOCAL session_replication_role = origin;
UPDATE platform_feedback SET upvotes = upvotes + 1 WHERE id = :'fid';
SELECT 'a_vote_is_not_a_status_change | ' || ((SELECT status_at < now() - interval '23 hours' FROM platform_feedback WHERE id = :'fid'));
SET LOCAL ROLE anon;
SELECT 'anon_can_still_send | ' || pg_temp.try_exec(
  'INSERT INTO platform_feedback (kind, subject, body, contact_email) VALUES (''bug'', ''probe anon send'', ''probe anon body'', ''probe-anon@local.invalid'')');
RESET ROLE;
INSERT INTO platform_feedback_votes (feedback_id, voter_token) VALUES (:'fid', 'v_probe-voter-token-0001');
SET LOCAL ROLE anon;
SELECT 'anon_cannot_list_voter_tokens | ' || pg_temp.try_exec('SELECT voter_token FROM platform_feedback_votes');
SELECT 'a_visitor_reads_their_own_votes | ' || EXISTS (SELECT 1 FROM my_feedback_votes('v_probe-voter-token-0001') v WHERE v.feedback_id = :'fid');
SELECT 'a_visitor_reads_no_one_elses_votes | ' || NOT EXISTS (SELECT 1 FROM my_feedback_votes('v_probe-other-token-0002') v WHERE v.feedback_id = :'fid');
RESET ROLE;
ROLLBACK;
SELECT 'restored | ' || (NOT EXISTS (SELECT 1 FROM platform_feedback WHERE subject IN ('probe public item', 'probe anon send')));
