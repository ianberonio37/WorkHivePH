-- a_deleted_post_takes_its_achievement: a community post pays twice on insert - community_xp (its award ledger) and the
-- 'voice_of_hive' achievement (award_achievement_xp, logged in achievement_xp_log). Until 20261030000011 only the first
-- was taken back when the post was deleted, so post-a-safety-note, Delete, repeat paid 60 achievement XP a cycle with no
-- post left (measured as Joel through wh_trash: voice_of_hive 360 -> 420, community_xp 220 -> 220).
-- Walked through the product's OWN path, as a member: insert, wh_trash, wh_restore (community.html deletePost /
-- restorePost) - never a hard DELETE, which only moderation and reset take.
--   * the post pays its achievement;
--   * Delete takes it back, and the week's xp_earned for the post nets to zero (achievements.html sums the week without
--     reading reversed_at, so the take-back must be a row of its own);
--   * Restore pays it again, and a second delete + restore still holds exactly ONE live award - never two.
-- One BEGIN/ROLLBACK block, so nothing it writes survives; self-grounding: any active non-supervisor member.
-- expect: fixture_found \| t
-- expect: post_paid \| t
-- expect: delete_takes_it_back \| t
-- expect: week_nets_zero \| t
-- expect: restore_pays_once \| t
-- expect: second_cycle_holds_one_award \| t
BEGIN;
CREATE TEMP TABLE _m ON COMMIT DROP AS
SELECT hm.auth_uid AS uid, hm.worker_name AS who, hm.hive_id
  FROM hive_members hm
 WHERE hm.status = 'active' AND hm.role <> 'supervisor' AND hm.auth_uid IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM community_posts p WHERE p.author_name = hm.worker_name AND p.hive_id = hm.hive_id
                    AND p.created_at > now() - interval '1 day')
 LIMIT 1;
CREATE TEMP TABLE _v (k text, v bigint) ON COMMIT DROP;
GRANT SELECT ON _m TO authenticated;
SELECT 'fixture_found | ' || EXISTS (SELECT 1 FROM _m);
INSERT INTO _v SELECT 'a0', coalesce((SELECT xp_total FROM worker_achievements
  WHERE worker_name = (SELECT who FROM _m) AND achievement_id = 'voice_of_hive'), 0);

SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT uid FROM _m)::text, 'role', 'authenticated')::text, true);
SET LOCAL ROLE authenticated;
INSERT INTO community_posts (hive_id, author_name, auth_uid, content, category)
SELECT hive_id, who, uid, 'probe: guard rail loose at line 3 - a_deleted_post_takes_its_achievement', 'safety' FROM _m;
RESET ROLE;
CREATE TEMP TABLE _p ON COMMIT DROP AS
SELECT id FROM community_posts WHERE content = 'probe: guard rail loose at line 3 - a_deleted_post_takes_its_achievement';
GRANT SELECT ON _p TO authenticated;
INSERT INTO _v SELECT 'a1', (SELECT xp_total FROM worker_achievements WHERE worker_name = (SELECT who FROM _m) AND achievement_id = 'voice_of_hive');

SET LOCAL ROLE authenticated;
SELECT wh_trash('community_posts', (SELECT id::text FROM _p)) IS NOT NULL AS trashed;
RESET ROLE;
INSERT INTO _v SELECT 'a2', (SELECT xp_total FROM worker_achievements WHERE worker_name = (SELECT who FROM _m) AND achievement_id = 'voice_of_hive');
INSERT INTO _v SELECT 'week', (SELECT coalesce(sum(xp_earned), 0) FROM achievement_xp_log
  WHERE source_action = 'community_post' AND source_id = (SELECT id::text FROM _p));

SET LOCAL ROLE authenticated;
SELECT wh_restore('community_posts', (SELECT id::text FROM _p)) IS NOT NULL AS restored;
RESET ROLE;
INSERT INTO _v SELECT 'a3', (SELECT xp_total FROM worker_achievements WHERE worker_name = (SELECT who FROM _m) AND achievement_id = 'voice_of_hive');

SET LOCAL ROLE authenticated;
SELECT wh_trash('community_posts', (SELECT id::text FROM _p)) IS NOT NULL AS trashed_again;
SELECT wh_restore('community_posts', (SELECT id::text FROM _p)) IS NOT NULL AS restored_again;
RESET ROLE;
INSERT INTO _v SELECT 'a5', (SELECT xp_total FROM worker_achievements WHERE worker_name = (SELECT who FROM _m) AND achievement_id = 'voice_of_hive');
INSERT INTO _v SELECT 'live', (SELECT count(*) FROM achievement_xp_log
  WHERE source_action = 'community_post' AND source_id = (SELECT id::text FROM _p) AND xp_earned > 0 AND reversed_at IS NULL);

SELECT 'post_paid | ' || ((SELECT v FROM _v WHERE k = 'a1') = (SELECT v FROM _v WHERE k = 'a0') + 60);
SELECT 'delete_takes_it_back | ' || ((SELECT v FROM _v WHERE k = 'a2') = (SELECT v FROM _v WHERE k = 'a0'));
SELECT 'week_nets_zero | ' || ((SELECT v FROM _v WHERE k = 'week') = 0);
SELECT 'restore_pays_once | ' || ((SELECT v FROM _v WHERE k = 'a3') = (SELECT v FROM _v WHERE k = 'a0') + 60);
SELECT 'second_cycle_holds_one_award | ' || ((SELECT v FROM _v WHERE k = 'a5') = (SELECT v FROM _v WHERE k = 'a0') + 60
                                            AND (SELECT v FROM _v WHERE k = 'live') = 1);
ROLLBACK;
