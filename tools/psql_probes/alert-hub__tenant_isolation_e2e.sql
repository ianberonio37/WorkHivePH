-- tenant_isolation_e2e (alert-hub): the alert surfaces are hive-scoped end to end — as postgres
-- (control) foreign rows demonstrably exist in v_alert_truth and amc_briefings, and under an active
-- member's ROLE + claims the same reads return ONLY their hive's rows, zero foreign.
-- expect: control_sees_foreign \| t
-- expect: member_alerts_own_only \| t
-- expect: member_briefs_own_only \| t
CREATE TEMP TABLE _te AS
SELECT hm.hive_id, hm.auth_uid,
       (SELECT count(*) FROM v_alert_truth WHERE hive_id <> hm.hive_id) AS foreign_alerts,
       (SELECT count(*) FROM amc_briefings WHERE hive_id <> hm.hive_id) AS foreign_briefs
FROM hive_members hm WHERE hm.status='active' AND hm.auth_uid IS NOT NULL LIMIT 1;
GRANT SELECT ON _te TO authenticated;
SELECT 'control_sees_foreign | ' ||
  (((SELECT foreign_alerts FROM _te) > 0) AND ((SELECT foreign_briefs FROM _te) > 0));
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT auth_uid FROM _te)::text, 'role', 'authenticated')::text, true);
SELECT 'member_alerts_own_only | ' ||
  ((SELECT count(*) FROM v_alert_truth WHERE hive_id <> (SELECT hive_id FROM _te)) = 0);
SELECT 'member_briefs_own_only | ' ||
  ((SELECT count(*) FROM amc_briefings WHERE hive_id <> (SELECT hive_id FROM _te)) = 0);
ROLLBACK;
DROP TABLE _te;
