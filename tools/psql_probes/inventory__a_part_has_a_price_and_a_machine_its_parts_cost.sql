-- inventory__a_part_has_a_price_and_a_machine_its_parts_cost (GJ M9 J10, 2026-11-06, mig 20261106000010): a machine's
-- parts cost is each logged part's quantity x that part's unit cost, joined by the part's ID - a part logged by NAME only
-- is counted as unpriced, never guessed; who set a price is the server's stamp (a client-sent name is overwritten); and a
-- member of another hive reads none of it. A part, a machine's entry and its price are written inside a rolled-back
-- transaction; restoration is asserted.
-- expect: fixture \| t
-- expect: price_stamp_is_the_callers_own \| t
-- expect: cost_is_qty_times_unit_cost \| 2400.00
-- expect: name_only_line_is_unpriced \| 1
-- expect: the_logger_is_named \| t
-- expect: another_hive_reads_nothing \| 0
-- expect: restored \| t
BEGIN;
SELECT hm.hive_id AS hid, hm.auth_uid AS suid, hm.worker_name AS sname,
       coalesce((SELECT display_name FROM worker_profiles w WHERE w.auth_uid = hm.auth_uid LIMIT 1), hm.worker_name) AS sdisplay
  FROM hive_members hm WHERE hm.role = 'supervisor' AND hm.status = 'active' AND hm.auth_uid IS NOT NULL
 ORDER BY hm.hive_id LIMIT 1 \gset
SELECT hm.auth_uid AS fuid FROM hive_members hm WHERE hm.status = 'active' AND hm.auth_uid IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM hive_members h2 WHERE h2.auth_uid = hm.auth_uid AND h2.hive_id = :'hid')
 ORDER BY hm.auth_uid LIMIT 1 \gset
SELECT id AS node FROM asset_nodes WHERE hive_id = :'hid' AND deleted_at IS NULL ORDER BY created_at LIMIT 1 \gset
INSERT INTO inventory_items (id, hive_id, worker_name, part_number, part_name, unit, qty_on_hand, min_qty, status, auth_uid)
VALUES ('probe-part-cost', :'hid', :'sname', 'PRB-COST-1', 'probe brake pad set', 'pcs', 5, 0, 'approved', :'suid');
SELECT 'fixture | ' || (:'node' <> '' AND :'fuid' <> '');
-- the supervisor prices the part, and tries to name someone else as the one who did
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', :'suid', 'role', 'authenticated')::text, true) IS NOT NULL AS c1 \gset
UPDATE inventory_items SET unit_cost = 1200, unit_cost_set_by = 'Somebody Else' WHERE id = 'probe-part-cost';
RESET ROLE;
SELECT 'price_stamp_is_the_callers_own | ' || ((SELECT unit_cost_set_by = :'sdisplay' AND unit_cost_set_at IS NOT NULL FROM inventory_items WHERE id = 'probe-part-cost'));
-- a closed job on the machine: 2 of the priced part by its ID, and 1 line by name only
SET LOCAL session_replication_role = replica;
INSERT INTO logbook (id, hive_id, worker_name, machine, problem, status, asset_node_id, parts_used, created_at, date)
VALUES ('probe-cost-entry', :'hid', 'Probe Driver', 'probe machine', 'probe brakes grinding', 'Closed', :'node',
        '[{"partId":"probe-part-cost","partName":"probe brake pad set","qty":2},{"partName":"some grease","qty":1}]'::jsonb, now(), now());
SET LOCAL session_replication_role = origin;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', :'suid', 'role', 'authenticated')::text, true) IS NOT NULL AS c2 \gset
SELECT 'cost_is_qty_times_unit_cost | ' || (SELECT parts_cost FROM parts_cost_by_asset(:'hid', 30) WHERE asset_node_id = :'node');
SELECT 'name_only_line_is_unpriced | ' || (SELECT unpriced_lines FROM parts_cost_by_asset(:'hid', 30) WHERE asset_node_id = :'node');
SELECT 'the_logger_is_named | ' || ((SELECT last_logged_by FROM parts_cost_by_asset(:'hid', 30) WHERE asset_node_id = :'node') = 'Probe Driver');
SELECT set_config('request.jwt.claims', json_build_object('sub', :'fuid', 'role', 'authenticated')::text, true) IS NOT NULL AS c3 \gset
SELECT 'another_hive_reads_nothing | ' || (SELECT count(*) FROM parts_cost_by_asset(:'hid', 30));
ROLLBACK;
SELECT 'restored | ' || (NOT EXISTS (SELECT 1 FROM inventory_items WHERE id = 'probe-part-cost') AND NOT EXISTS (SELECT 1 FROM logbook WHERE id = 'probe-cost-entry'));
