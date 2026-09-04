-- codes_collision_free (project-manager): generate_project_code and generate_change_order_number are
-- collision-free under concurrency. The generators read the current maximum and increment, so under
-- true concurrency two callers CAN compute the same string - which is precisely why the guarantee must
-- not live in the generator. It lives in a UNIQUE INDEX, the only thing that holds when two
-- transactions run at once: the loser is REFUSED with 23505 instead of quietly minting a duplicate
-- code that two projects then answer to.
-- Both directions are proven: a colliding write is refused, and a distinct one is accepted - a
-- constraint that rejected everything would satisfy a refusal-only test while breaking the product.
-- expect: project_code_unique_index \| t
-- expect: co_number_unique_index \| t
-- expect: fixture_two_projects \| t
-- expect: duplicate key value violates unique constraint "projects_code_per_hive"
-- expect: distinct_code_accepted \| 1
-- expect: generators_present \| 2
-- expect: rows_restored_after_rollback \| t
SELECT 'project_code_unique_index | ' || EXISTS (
  SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='projects_code_per_hive'
    AND indexdef ILIKE '%UNIQUE%' AND indexdef ILIKE '%hive_id, project_code%');
SELECT 'co_number_unique_index | ' || EXISTS (
  SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='project_change_orders_co_number'
    AND indexdef ILIKE '%UNIQUE%' AND indexdef ILIKE '%project_id, co_number%');
SELECT 'generators_present | ' || count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
 WHERE n.nspname='public' AND p.proname IN ('generate_project_code','generate_change_order_number');

CREATE TEMP TABLE _pc AS
SELECT a.id AS mine, a.hive_id, b.project_code AS taken_code,
       (SELECT count(*) FROM projects) AS n0
FROM projects a JOIN projects b ON b.hive_id = a.hive_id AND b.id <> a.id
WHERE a.deleted_at IS NULL AND b.deleted_at IS NULL AND b.project_code IS NOT NULL
LIMIT 1;
SELECT 'fixture_two_projects | ' || EXISTS (SELECT 1 FROM _pc);

-- TEETH: take a sibling's code in the same hive. The partial unique index must refuse it.
BEGIN;
UPDATE projects SET project_code = (SELECT taken_code FROM _pc) WHERE id = (SELECT mine FROM _pc);
ROLLBACK;

-- CONTROL: a code nobody holds is accepted, so the refusal above was about the COLLISION
BEGIN;
WITH u AS (UPDATE projects SET project_code = 'WH-PROBE-UNIQUE-0001'
            WHERE id = (SELECT mine FROM _pc) RETURNING 1)
SELECT 'distinct_code_accepted | ' || count(*) FROM u;
ROLLBACK;

SELECT 'rows_restored_after_rollback | ' || ((SELECT count(*) FROM projects) = (SELECT n0 FROM _pc));
DROP TABLE _pc;
