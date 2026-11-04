-- a_decision_says_who_and_where: when a supervisor approves or rejects a submission, the submitter's push names the
-- supervisor and sends them where the decision can be read - a machine to Asset Hub on that machine, a part to Inventory
-- (mig 20261104000003; each link names its hive since mig 20261105000003, so a person in two hives lands in this one). Found by the group-journey walk GJ J9 hand-off 5: the push named nobody, an approved machine
-- landed on the logbook, and a rejected machine was told to "open Inventory to see why".
-- Each leg runs AS the supervisor (authenticated + their claims) in its own BEGIN/ROLLBACK; the pushes it queues go too.
-- Self-grounding: a machine and a part submitted by a worker of a hive that has an active supervisor.
-- expect: fixture_found \| t
-- expect: machine_approved_names_who \| t
-- expect: machine_approved_lands_on_machine \| t
-- expect: machine_rejected_points_to_asset_hub \| t
-- expect: part_rejected_points_to_inventory \| t
CREATE TEMP TABLE _s AS
SELECT n.id::text AS node_id, n.hive_id,
       (SELECT hm.auth_uid FROM hive_members hm WHERE hm.hive_id = n.hive_id AND hm.role = 'supervisor' AND hm.status = 'active'
          AND hm.auth_uid IS NOT NULL ORDER BY hm.worker_name LIMIT 1) AS sup_uid,
       (SELECT hm.worker_name FROM hive_members hm WHERE hm.hive_id = n.hive_id AND hm.role = 'supervisor' AND hm.status = 'active'
          AND hm.auth_uid IS NOT NULL ORDER BY hm.worker_name LIMIT 1) AS sup_name,
       (SELECT o.auth_uid FROM hive_members o WHERE o.hive_id = n.hive_id AND o.worker_name = n.worker_name AND o.auth_uid IS NOT NULL LIMIT 1) AS owner_uid,
       (SELECT i.id FROM inventory_items i JOIN hive_members im ON im.hive_id = i.hive_id AND im.worker_name = i.worker_name AND im.auth_uid IS NOT NULL
         WHERE i.hive_id = n.hive_id LIMIT 1) AS part_id
  FROM asset_nodes n
  JOIN hive_members m ON m.hive_id = n.hive_id AND m.worker_name = n.worker_name AND m.role = 'worker' AND m.status = 'active' AND m.auth_uid IS NOT NULL
 WHERE n.hive_id IS NOT NULL
 ORDER BY n.created_at DESC
 LIMIT 1;
GRANT SELECT ON _s TO authenticated;
SELECT 'fixture_found | ' || EXISTS (SELECT 1 FROM _s WHERE sup_uid IS NOT NULL AND owner_uid IS NOT NULL AND part_id IS NOT NULL);

BEGIN;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT sup_uid FROM _s)::text, 'role', 'authenticated')::text, true) IS NULL;
SET LOCAL ROLE authenticated;
SELECT notify_submission_decided('asset_nodes', (SELECT node_id FROM _s), 'approved');
RESET ROLE;
SELECT 'machine_approved_names_who | ' || EXISTS (SELECT 1 FROM service_outbox o WHERE o.consumer = 'notify-push' AND o.created_at >= now() - interval '1 minute'
  AND o.payload->'auth_uids' ? (SELECT owner_uid FROM _s)::text AND o.payload->>'body' LIKE '%approved by ' || (SELECT sup_name FROM _s) || '%');
SELECT 'machine_approved_lands_on_machine | ' || EXISTS (SELECT 1 FROM service_outbox o WHERE o.consumer = 'notify-push' AND o.created_at >= now() - interval '1 minute'
  AND o.payload->'auth_uids' ? (SELECT owner_uid FROM _s)::text AND o.payload->>'url' = '/asset-hub.html?node_id=' || (SELECT node_id FROM _s) || '&hive=' || (SELECT hive_id FROM _s)::text);
ROLLBACK;

BEGIN;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT sup_uid FROM _s)::text, 'role', 'authenticated')::text, true) IS NULL;
SET LOCAL ROLE authenticated;
SELECT notify_submission_decided('asset_nodes', (SELECT node_id FROM _s), 'rejected');
RESET ROLE;
SELECT 'machine_rejected_points_to_asset_hub | ' || EXISTS (SELECT 1 FROM service_outbox o WHERE o.consumer = 'notify-push' AND o.created_at >= now() - interval '1 minute'
  AND o.payload->'auth_uids' ? (SELECT owner_uid FROM _s)::text AND o.payload->>'body' LIKE '%rejected by % open Asset Hub to see why%');
ROLLBACK;

BEGIN;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT sup_uid FROM _s)::text, 'role', 'authenticated')::text, true) IS NULL;
SET LOCAL ROLE authenticated;
SELECT notify_submission_decided('inventory_items', (SELECT part_id FROM _s)::text, 'rejected');
RESET ROLE;
SELECT 'part_rejected_points_to_inventory | ' || EXISTS (SELECT 1 FROM service_outbox o WHERE o.consumer = 'notify-push' AND o.created_at >= now() - interval '1 minute'
  AND o.payload->>'url' = '/inventory.html?hive=' || (SELECT hive_id FROM _s)::text AND o.payload->>'body' LIKE '%open Inventory to see why%');
ROLLBACK;
