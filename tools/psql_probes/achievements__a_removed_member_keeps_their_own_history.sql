-- a_removed_member_keeps_their_own_history: a member a supervisor removed still reads their OWN XP history - the log's read
-- policy and my_recent_xp() admit auth_own_history_names() (mig 20261105000008), which adds the names of the person's own
-- removed memberships to auth_worker_names(). Before it, a removed member's achievements page said "No XP this week" for
-- work they had just logged. Found by the group-journey walk GJ J14 hand-off 4. A member of another hive still reads none.
-- The legs run AS the removed member and AS an outsider (authenticated + claims) inside one BEGIN/ROLLBACK.
-- Self-grounding: a hive's active worker with an account, XP lines under their name, and nowhere else to be a member.
-- expect: fixture_found \| t
-- expect: removed_member_reads_own_xp \| t
-- expect: removed_member_recent_xp_lists_it \| t
-- expect: outsider_reads_none_of_it \| t
CREATE TEMP TABLE _p AS
SELECT m.id AS member_id, m.auth_uid AS w_uid, m.worker_name AS w_name,
       (SELECT o.auth_uid FROM hive_members o WHERE o.status = 'active' AND o.auth_uid IS NOT NULL
          AND o.hive_id <> m.hive_id AND o.auth_uid <> m.auth_uid ORDER BY o.worker_name LIMIT 1) AS outsider_uid
  FROM hive_members m
 WHERE m.status = 'active' AND m.role = 'worker' AND m.auth_uid IS NOT NULL
   AND EXISTS (SELECT 1 FROM achievement_xp_log x WHERE x.worker_name = m.worker_name)
   AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.id <> m.id)
   AND NOT EXISTS (SELECT 1 FROM marketplace_sellers s WHERE s.auth_uid = m.auth_uid)
 ORDER BY m.worker_name
 LIMIT 1;
CREATE TEMP TABLE _r (k text, v boolean);
GRANT SELECT ON _p TO authenticated;
GRANT ALL ON _r TO authenticated;
SELECT 'fixture_found | ' || EXISTS (SELECT 1 FROM _p WHERE outsider_uid IS NOT NULL);

BEGIN;
SET LOCAL session_replication_role = replica;
UPDATE hive_members SET status = 'kicked' WHERE id = (SELECT member_id FROM _p);
SET LOCAL session_replication_role = origin;

SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT w_uid FROM _p)::text, 'role', 'authenticated')::text, true) IS NULL;
SET LOCAL ROLE authenticated;
INSERT INTO _r SELECT 'removed_member_reads_own_xp', (SELECT count(*) FROM achievement_xp_log WHERE worker_name = (SELECT w_name FROM _p)) > 0;
INSERT INTO _r SELECT 'removed_member_recent_xp_lists_it', (SELECT count(*) FROM my_recent_xp(30)) > 0;
RESET ROLE;

SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT outsider_uid FROM _p)::text, 'role', 'authenticated')::text, true) IS NULL;
SET LOCAL ROLE authenticated;
INSERT INTO _r SELECT 'outsider_reads_none_of_it', (SELECT count(*) FROM achievement_xp_log WHERE worker_name = (SELECT w_name FROM _p)) = 0;
RESET ROLE;
SELECT k || ' | ' || v FROM _r ORDER BY k;
ROLLBACK;
