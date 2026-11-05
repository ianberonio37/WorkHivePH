-- community__a_chosen_answer_earns_its_credit (GJ M9 J7, 2026-11-06, mig 20261106000004): an answer the asker chooses
-- as the best pays its author 30 XP in the achievement log the achievements page reads; un-choosing takes it back with a
-- negative line; choosing your own reply on your own question pays nothing. All inside a rolled-back transaction.
-- expect: fixture \| t
-- expect: chosen_pays \| 30
-- expect: unchosen_takes_back \| t
-- expect: own_reply_pays_nothing \| t
-- expect: restored \| t
CREATE TEMP TABLE _ba AS
SELECT (SELECT m.auth_uid FROM hive_members m WHERE m.hive_id = h.id AND m.role = 'worker' AND m.status = 'active' ORDER BY m.worker_name LIMIT 1) AS asker,
       (SELECT m.auth_uid FROM hive_members m WHERE m.hive_id = h.id AND m.role = 'worker' AND m.status = 'active' ORDER BY m.worker_name OFFSET 1 LIMIT 1) AS answerer,
       h.id AS hive, (SELECT count(*) FROM achievement_xp_log) AS n0
  FROM hives h WHERE h.name = 'Batangas Refinery Maintenance';
GRANT SELECT ON _ba TO authenticated;
BEGIN;
INSERT INTO community_posts (hive_id, author_name, auth_uid, content, category)
SELECT b.hive, (SELECT display_name FROM worker_profiles WHERE auth_uid = b.asker), b.asker, 'PROBE-BA how do you align a coupling without a laser?', 'technical' FROM _ba b;
INSERT INTO community_replies (post_id, hive_id, author_name, auth_uid, content)
SELECT p.id, b.hive, (SELECT display_name FROM worker_profiles WHERE auth_uid = b.answerer), b.answerer, 'PROBE-BA-R1 rim and face with two dials' FROM _ba b, community_posts p WHERE p.content LIKE 'PROBE-BA how%';
INSERT INTO community_replies (post_id, hive_id, author_name, auth_uid, content)
SELECT p.id, b.hive, (SELECT display_name FROM worker_profiles WHERE auth_uid = b.asker), b.asker, 'PROBE-BA-R2 answering my own question' FROM _ba b, community_posts p WHERE p.content LIKE 'PROBE-BA how%';
SELECT 'fixture | ' || ((SELECT count(*) FROM community_replies WHERE content LIKE 'PROBE-BA-R%') = 2);
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT asker FROM _ba)::text, 'role', 'authenticated')::text, true);
SELECT public.set_community_best_answer((SELECT id FROM community_replies WHERE content LIKE 'PROBE-BA-R1%'), true);
RESET ROLE;
SELECT 'chosen_pays | ' || coalesce((SELECT sum(xp_earned)::text FROM achievement_xp_log WHERE source_action = 'best_answer'
  AND source_id = (SELECT id::text FROM community_replies WHERE content LIKE 'PROBE-BA-R1%') AND reversed_at IS NULL), '0');
-- the asker moves the best answer to their own reply: R1's award is taken back, R2 pays nothing
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT asker FROM _ba)::text, 'role', 'authenticated')::text, true);
SELECT public.set_community_best_answer((SELECT id FROM community_replies WHERE content LIKE 'PROBE-BA-R2%'), true);
RESET ROLE;
SELECT 'unchosen_takes_back | ' || ((SELECT coalesce(sum(xp_earned), 0) FROM achievement_xp_log WHERE source_action = 'best_answer'
  AND source_id = (SELECT id::text FROM community_replies WHERE content LIKE 'PROBE-BA-R1%')) = 0);
SELECT 'own_reply_pays_nothing | ' || NOT EXISTS (SELECT 1 FROM achievement_xp_log WHERE source_action = 'best_answer'
  AND source_id = (SELECT id::text FROM community_replies WHERE content LIKE 'PROBE-BA-R2%'));
ROLLBACK;
SELECT 'restored | ' || ((SELECT count(*) FROM achievement_xp_log) = (SELECT n0 FROM _ba) AND NOT EXISTS (SELECT 1 FROM community_posts WHERE content LIKE 'PROBE-BA%'));
