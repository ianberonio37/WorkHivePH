-- a_removed_member_is_told_who_and_when: a supervisor's Remove (hive_members.status -> 'kicked') stamps the removed
-- member's OWN row with who removed them and when (mig 20261105000004, trg_hive_members_stamp_removal) - the one row a
-- removed person can still read - so the Hive Board can tell them "removed by <name> on <date>" instead of "by a
-- supervisor", undated. Found by the group-journey walk GJ J14 / G-LEAVE hand-off 1. A re-approval clears the stamp;
-- an update that does not change the status cannot write one; a new membership is born without one.
-- The leg runs AS a supervisor (authenticated + their claims) in its own BEGIN/ROLLBACK.
-- Self-grounding: a hive with an active supervisor and an active worker, both with accounts.
-- expect: fixture_found \| t
-- expect: removal_stamped_with_who_and_when \| t
-- expect: removed_member_reads_which_hive_who_and_when \| t
-- expect: unrelated_update_cannot_write_a_stamp \| t
-- expect: reapproval_clears_the_stamp \| t
CREATE TEMP TABLE _p AS
SELECT s.hive_id, s.auth_uid AS sup_uid, w.id AS member_id, w.auth_uid AS w_uid,
       (SELECT wp.display_name FROM worker_profiles wp WHERE wp.auth_uid = s.auth_uid) AS sup_display
  FROM hive_members s
  JOIN hive_members w ON w.hive_id = s.hive_id AND w.role = 'worker' AND w.status = 'active' AND w.auth_uid IS NOT NULL
 WHERE s.role = 'supervisor' AND s.status = 'active' AND s.auth_uid IS NOT NULL
 ORDER BY s.hive_id, w.worker_name
 LIMIT 1;
GRANT SELECT ON _p TO authenticated;
SELECT 'fixture_found | ' || EXISTS (SELECT 1 FROM _p WHERE sup_display IS NOT NULL);

BEGIN;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT sup_uid FROM _p)::text, 'role', 'authenticated')::text, true) IS NULL;
SET LOCAL ROLE authenticated;
UPDATE hive_members SET status = 'kicked' WHERE id = (SELECT member_id FROM _p);
RESET ROLE;
SELECT 'removal_stamped_with_who_and_when | ' || EXISTS (SELECT 1 FROM hive_members m, _p
  WHERE m.id = _p.member_id AND m.status = 'kicked' AND m.removed_by = _p.sup_display
    AND m.removed_at >= now() - interval '1 minute');
-- the removed member, on their next visit, is told which hive, who and when (my_recent_removal - they can no longer read
-- the hive's own row)
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT w_uid FROM _p)::text, 'role', 'authenticated')::text, true) IS NULL;
SET LOCAL ROLE authenticated;
CREATE TEMP TABLE IF NOT EXISTS _seen AS SELECT * FROM my_recent_removal();
RESET ROLE;
SELECT 'removed_member_reads_which_hive_who_and_when | ' || EXISTS (SELECT 1 FROM _seen s, _p, hives h
  WHERE h.id = _p.hive_id AND s.hive_name = h.name AND s.removed_by = _p.sup_display AND s.removed_at IS NOT NULL);
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT sup_uid FROM _p)::text, 'role', 'authenticated')::text, true) IS NULL;
SET LOCAL ROLE authenticated;
-- a write that does not change the status cannot replace the stamp with another name
UPDATE hive_members SET removed_by = 'Somebody Else', removed_at = '2020-01-01' WHERE id = (SELECT member_id FROM _p);
RESET ROLE;
SELECT 'unrelated_update_cannot_write_a_stamp | ' || EXISTS (SELECT 1 FROM hive_members m, _p
  WHERE m.id = _p.member_id AND m.removed_by = _p.sup_display AND m.removed_at > '2020-01-02');
SET LOCAL ROLE authenticated;
UPDATE hive_members SET status = 'active' WHERE id = (SELECT member_id FROM _p);
RESET ROLE;
SELECT 'reapproval_clears_the_stamp | ' || EXISTS (SELECT 1 FROM hive_members m, _p
  WHERE m.id = _p.member_id AND m.status = 'active' AND m.removed_by IS NULL AND m.removed_at IS NULL);
ROLLBACK;
