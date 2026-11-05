-- a_reply_stays_its_authors_words: community_replies' UPDATE policy lets the author AND a supervisor update a reply, and
-- until mig 20261105000007 nothing kept a supervisor from rewriting a member's answer or an author from marking their own
-- reply the accepted answer. The guard (tg_community_replies_authorship_fields) is the posts' rule for replies: nobody
-- else's words go out under an author's name, and the best answer is chosen only through set_community_best_answer.
-- Found reading J7's premise (GJ M9). The legs run AS a supervisor and AS the author inside one BEGIN/ROLLBACK.
-- Self-grounding: a post in a hive with an active worker and an active supervisor, both with accounts.
-- expect: fixture_found \| t
-- expect: supervisor_cannot_rewrite_a_members_reply \| t
-- expect: author_cannot_accept_their_own_reply \| t
-- expect: author_can_edit_their_own_words \| t
CREATE TEMP TABLE _p AS
SELECT p.id AS post_id, p.hive_id, w.auth_uid AS w_uid, wp.display_name AS w_name, s.auth_uid AS s_uid
  FROM community_posts p
  JOIN hive_members w ON w.hive_id = p.hive_id AND w.role = 'worker' AND w.status = 'active' AND w.auth_uid IS NOT NULL
  JOIN worker_profiles wp ON wp.auth_uid = w.auth_uid
  JOIN hive_members s ON s.hive_id = p.hive_id AND s.role = 'supervisor' AND s.status = 'active' AND s.auth_uid IS NOT NULL
 WHERE p.deleted_at IS NULL
 ORDER BY p.created_at DESC
 LIMIT 1;
CREATE TEMP TABLE _r (k text, v boolean);
GRANT SELECT ON _p TO authenticated;
GRANT ALL ON _r TO authenticated;
SELECT 'fixture_found | ' || EXISTS (SELECT 1 FROM _p);

BEGIN;
SET LOCAL session_replication_role = replica;
INSERT INTO community_replies (id, post_id, hive_id, auth_uid, author_name, content)
SELECT '00000000-0000-4000-8000-0000000e9719', post_id, hive_id, w_uid, w_name, 'probe: my own words' FROM _p;
SET LOCAL session_replication_role = origin;

SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT s_uid FROM _p)::text, 'role', 'authenticated')::text, true) IS NULL;
SET LOCAL ROLE authenticated;
UPDATE community_replies SET content = 'probe: words the member never wrote' WHERE id = '00000000-0000-4000-8000-0000000e9719';
RESET ROLE;
INSERT INTO _r SELECT 'supervisor_cannot_rewrite_a_members_reply', EXISTS (SELECT 1 FROM community_replies
  WHERE id = '00000000-0000-4000-8000-0000000e9719' AND content = 'probe: my own words');

SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT w_uid FROM _p)::text, 'role', 'authenticated')::text, true) IS NULL;
SET LOCAL ROLE authenticated;
UPDATE community_replies SET is_accepted = true, content = 'probe: my own words, edited' WHERE id = '00000000-0000-4000-8000-0000000e9719';
RESET ROLE;
INSERT INTO _r SELECT 'author_cannot_accept_their_own_reply', EXISTS (SELECT 1 FROM community_replies
  WHERE id = '00000000-0000-4000-8000-0000000e9719' AND is_accepted IS NOT TRUE);
INSERT INTO _r SELECT 'author_can_edit_their_own_words', EXISTS (SELECT 1 FROM community_replies
  WHERE id = '00000000-0000-4000-8000-0000000e9719' AND content = 'probe: my own words, edited');
SELECT k || ' | ' || v FROM _r ORDER BY k;
ROLLBACK;
