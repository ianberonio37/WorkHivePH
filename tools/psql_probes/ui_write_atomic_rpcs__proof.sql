-- expect: PASS inventory_adjust moves the balance AND writes the adjustment row
-- expect: PASS inventory_adjust refuses a stale expected count
-- expect: PASS accept_parts_staging reserves
-- expect: PASS a second accept says already_acted
-- expect: PASS create_pm_asset_with_tasks writes the asset with both tasks
-- expect: PASS a task that cannot be written leaves no asset behind
-- expect: PASS a non-member cannot adjust another hive
-- expect: PASS nothing persisted after the rollback
-- forbid: FAIL 
-- ui_write_atomic_rpcs__proof.sql (2026-10-08) - the three one-transaction RPCs that replaced two-write UI paths,
-- proven AS A SIGNED-IN MEMBER (role authenticated + JWT claims) inside ONE transaction that is rolled back.
--   accept_parts_staging       (asset-hub: reservations + recommendation status, migration 20261008000011)
--   inventory_adjust           (inventory: ledger row + balance, migration 20261008000012)
--   create_pm_asset_with_tasks (pm-scheduler: asset + scope items, migration 20261008000013)
-- Each check prints PASS/FAIL; nothing persists (ROLLBACK at the end; the row counts are re-read afterwards).
-- Cast: Christine Dizon (supervisor, hive 084c113b...) as the member; Bryan Garcia (member of 084c113b only) as the
-- non-member of hive b4f7fe63.
\set ON_ERROR_STOP on
BEGIN;

-- fixtures, as the owner connection (inside the rolled-back transaction)
CREATE TEMP TABLE _fx AS
SELECT (SELECT id FROM public.inventory_items WHERE hive_id = '084c113b-99c0-45c6-a8e8-b4b8349da46d' AND status = 'approved'
         ORDER BY id LIMIT 1) AS item_own,
       (SELECT id FROM public.inventory_items WHERE hive_id = 'b4f7fe63-92e1-4f8d-b96e-625c3f85ba61' AND status = 'approved'
         ORDER BY id LIMIT 1) AS item_foreign;
INSERT INTO public.parts_staging_recommendations (id, hive_id, asset_name, risk_score, failure_mode, parts, rationale,
                                                  confidence, status, generated_at, expires_at)
SELECT 'aaaaaaaa-0000-4000-8000-000000000001', '084c113b-99c0-45c6-a8e8-b4b8349da46d', 'PROOF pump', 0.9, 'wear',
       jsonb_build_array(jsonb_build_object('item_id', item_own, 'qty_avg', 2, 'part_name', 'proof part')),
       'proof', 0.8, 'pending', now(), now() + interval '1 day'
  FROM _fx;
GRANT SELECT ON _fx TO authenticated;

SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', '{"sub":"b2916047-d5b6-4707-bb12-5a569acc1d74","role":"authenticated"}', true);

-- 1. inventory_adjust: a changed count writes ONE adjustment row and moves the balance together
CREATE TEMP TABLE _r1 AS
SELECT i.qty_on_hand AS before_qty,
       public.inventory_adjust(f.item_own, i.qty_on_hand, i.qty_on_hand + 3, 'proof') AS res
  FROM _fx f JOIN public.inventory_items i ON i.id = f.item_own;
SELECT CASE WHEN (res->>'ok')::boolean AND (res->>'qty_on_hand')::numeric = before_qty + 3
             AND (SELECT qty_on_hand FROM public.inventory_items WHERE id = (SELECT item_own FROM _fx)) = before_qty + 3
             AND EXISTS (SELECT 1 FROM public.inventory_transactions t WHERE t.item_id = (SELECT item_own FROM _fx)
                          AND t.type = 'adjustment' AND t.qty_after = before_qty + 3 AND t.note = 'proof')
            THEN 'PASS' ELSE 'FAIL' END || ' inventory_adjust moves the balance AND writes the adjustment row' FROM _r1;
-- 1b. a count that moved since the form opened is refused, nothing written
SELECT CASE WHEN (public.inventory_adjust(f.item_own, -12345, 7, 'stale')->>'reason') = 'changed'
             AND NOT EXISTS (SELECT 1 FROM public.inventory_transactions WHERE note = 'stale')
            THEN 'PASS' ELSE 'FAIL' END || ' inventory_adjust refuses a stale expected count' FROM _fx f;

-- 2. accept_parts_staging: one call writes the reservation AND marks the recommendation, once
CREATE TEMP TABLE _r2 AS
SELECT public.accept_parts_staging('aaaaaaaa-0000-4000-8000-000000000001', ARRAY[(SELECT item_own FROM _fx)]) AS res;
SELECT CASE WHEN (res->>'ok')::boolean AND (res->>'staged')::int = 1
             AND (SELECT status FROM public.parts_staging_recommendations WHERE id = 'aaaaaaaa-0000-4000-8000-000000000001') = 'accepted'
             AND (SELECT qty_reserved FROM public.parts_staged_reservations
                   WHERE recommendation_id = 'aaaaaaaa-0000-4000-8000-000000000001') = 2
            THEN 'PASS' ELSE 'FAIL' END || ' accept_parts_staging reserves (qty from the recommendation) and marks it accepted' FROM _r2;
SELECT CASE WHEN (public.accept_parts_staging('aaaaaaaa-0000-4000-8000-000000000001', ARRAY[(SELECT item_own FROM _fx)])->>'reason') = 'already_acted'
            THEN 'PASS' ELSE 'FAIL' END || ' a second accept says already_acted and stages nothing';

-- 3. create_pm_asset_with_tasks: the asset and every task, or nothing
CREATE TEMP TABLE _r3 AS
SELECT public.create_pm_asset_with_tasks(
  jsonb_build_object('hive_id', '084c113b-99c0-45c6-a8e8-b4b8349da46d', 'worker_name', 'Christine Dizon',
                     'asset_name', 'PROOF compressor', 'category', 'Mechanical', 'criticality', 'Major'),
  jsonb_build_array(jsonb_build_object('item_text', 'Check belt tension', 'frequency', 'Monthly'),
                    jsonb_build_object('item_text', 'Change oil', 'frequency', 'Quarterly'))) AS res;
SELECT CASE WHEN (res->>'ok')::boolean AND (res->>'tasks')::int = 2
             AND (SELECT count(*) FROM public.pm_scope_items WHERE asset_id = (res->'asset'->>'id')::uuid) = 2
            THEN 'PASS' ELSE 'FAIL' END || ' create_pm_asset_with_tasks writes the asset with both tasks' FROM _r3;
SAVEPOINT bad_task;
DO $$ BEGIN
  PERFORM public.create_pm_asset_with_tasks(
    jsonb_build_object('hive_id', '084c113b-99c0-45c6-a8e8-b4b8349da46d', 'worker_name', 'Christine Dizon',
                       'asset_name', 'PROOF atomic', 'category', 'Mechanical'),
    jsonb_build_array(jsonb_build_object('item_text', NULL, 'frequency', 'Monthly')));
  RAISE NOTICE 'NO-ERROR';
EXCEPTION WHEN OTHERS THEN RAISE NOTICE 'refused: %', SQLSTATE;
END $$;
ROLLBACK TO SAVEPOINT bad_task;
SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM public.pm_assets WHERE asset_name = 'PROOF atomic')
            THEN 'PASS' ELSE 'FAIL' END || ' a task that cannot be written leaves no asset behind';

-- 4. a non-member: Bryan Garcia on a part in a hive he does not belong to
SELECT set_config('request.jwt.claims', '{"sub":"91e0d1eb-cd96-43ee-af5f-0ff2714b3923","role":"authenticated"}', true);
SELECT CASE WHEN (public.inventory_adjust(f.item_foreign, NULL, 1, 'foreign')->>'reason') = 'not_found'
            THEN 'PASS' ELSE 'FAIL' END || ' a non-member cannot adjust another hive''s part (not_found)' FROM _fx f;

RESET ROLE;
ROLLBACK;
-- after the rollback nothing persisted
SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM public.inventory_transactions WHERE note IN ('proof', 'stale', 'foreign'))
             AND NOT EXISTS (SELECT 1 FROM public.parts_staging_recommendations WHERE id = 'aaaaaaaa-0000-4000-8000-000000000001')
             AND NOT EXISTS (SELECT 1 FROM public.pm_assets WHERE asset_name LIKE 'PROOF %')
            THEN 'PASS' ELSE 'FAIL' END || ' nothing persisted after the rollback';
