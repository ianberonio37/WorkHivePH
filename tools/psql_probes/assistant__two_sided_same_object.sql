-- two_sided_same_object (assistant feedback): ONE row, THREE identities, one transaction — the
-- author reads their own feedback back, a SAME-HIVE supervisor reads the same row (granted by
-- membership, not role), and an ACTIVE FOREIGN-hive member with a valid uid reads ZERO (a refusal,
-- not an anon artifact). Seeded and rolled back.
-- expect: author_reads_own \| 1
-- expect: same_hive_supervisor_reads \| 1
-- expect: foreign_member_reads \| 0
-- expect: restored \| t
CREATE TEMP TABLE _ts AS
SELECT a.hive_id, a.auth_uid AS author,
       (SELECT s.auth_uid FROM hive_members s WHERE s.hive_id = a.hive_id
          AND s.role = 'supervisor' AND s.status = 'active'
          AND s.auth_uid IS NOT NULL AND s.auth_uid <> a.auth_uid LIMIT 1) AS supervisor,
       (SELECT f.auth_uid FROM hive_members f WHERE f.hive_id <> a.hive_id
          AND f.status = 'active' AND f.auth_uid IS NOT NULL
          AND f.auth_uid NOT IN (SELECT auth_uid FROM hive_members x
                                  WHERE x.hive_id = a.hive_id AND x.auth_uid IS NOT NULL)
          LIMIT 1) AS foreigner,
       gen_random_uuid() AS marker_id,
       (SELECT count(*) FROM ai_reply_feedback) AS n0
FROM hive_members a
WHERE a.status = 'active' AND a.auth_uid IS NOT NULL AND a.role <> 'supervisor'
  AND EXISTS (SELECT 1 FROM hive_members s WHERE s.hive_id = a.hive_id
               AND s.role = 'supervisor' AND s.status = 'active'
               AND s.auth_uid IS NOT NULL AND s.auth_uid <> a.auth_uid)
LIMIT 1;
GRANT SELECT ON _ts TO authenticated;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT author FROM _ts)::text, 'role', 'authenticated')::text, true);
INSERT INTO ai_reply_feedback (id, hive_id, auth_uid, source, rating, agent, question)
SELECT marker_id, hive_id, author, 'probe', 1, 'probe-agent', 'two-sided probe' FROM _ts;
SELECT 'author_reads_own | ' || count(*) FROM ai_reply_feedback
WHERE id = (SELECT marker_id FROM _ts);
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT supervisor FROM _ts)::text, 'role', 'authenticated')::text, true);
SELECT 'same_hive_supervisor_reads | ' || count(*) FROM ai_reply_feedback
WHERE id = (SELECT marker_id FROM _ts);
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT foreigner FROM _ts)::text, 'role', 'authenticated')::text, true);
SELECT 'foreign_member_reads | ' || count(*) FROM ai_reply_feedback
WHERE id = (SELECT marker_id FROM _ts);
ROLLBACK;
SELECT 'restored | ' || ((SELECT count(*) FROM ai_reply_feedback) = (SELECT n0 FROM _ts));
DROP TABLE _ts;
