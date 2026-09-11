-- benchmark_aggregate_only (hive): the page never shows another hive's identifiable row - the network
-- figure is aggregate-only, proven from the PAYLOAD rather than from the label. A number captioned
-- "network average" is not aggregate because of its caption.
--
-- TWO SEPARATE WAYS THIS CAN LEAK, and the second is the one a schema check alone would miss:
--
--   1. STRUCTURAL - the aggregate table carries a tenant key, so a row IS one hive's figure wearing a
--      network label. `network_benchmarks` has no `hive_id` column at all, which is the right shape:
--      equipment_category, industry, avg/p25/p75 mtbf, sample_hives, period_days. Asserted, so adding
--      a hive_id to it later fails here rather than shipping.
--
--   2. K-ANONYMITY - the table is shaped correctly and a row is computed over ONE hive. Then the
--      "network average" is that hive's private MTBF, exactly, published to everyone else on the
--      platform, and no column inspection can see it: the leak is in the CARDINALITY, not the schema.
--      `sample_hives` is the field that decides it, and every row must be over at least two.
--
-- Measured today: 5 rows, all at sample_hives = 3. The threshold below is 2 - the weakest bound that
-- still makes "network" mean more than one - so the lock cannot be satisfied by a single hive and does
-- not fail the board over a legitimate 2-hive category.
-- expect: rows_present \| [1-9][0-9]*
-- expect: no_tenant_key_on_the_aggregate \| t
-- expect: min_sample_hives \| [2-9][0-9]*
-- expect: every_row_is_over_two_or_more_hives \| t
-- expect: detector_sees_a_single_hive_row \| t
-- expect: rows_restored_after_rollback \| t
SELECT 'rows_present | ' || (SELECT count(*) FROM network_benchmarks);

SELECT 'no_tenant_key_on_the_aggregate | ' || NOT EXISTS (
  SELECT 1 FROM information_schema.columns
   WHERE table_schema = 'public' AND table_name = 'network_benchmarks'
     AND column_name IN ('hive_id', 'auth_uid', 'worker_name'));

SELECT 'min_sample_hives | ' || (SELECT min(sample_hives) FROM network_benchmarks);
SELECT 'every_row_is_over_two_or_more_hives | ' || (
  (SELECT count(*) FROM network_benchmarks WHERE sample_hives IS NULL OR sample_hives < 2) = 0);

CREATE TEMP TABLE _bfx AS SELECT count(*) AS n0 FROM network_benchmarks;

BEGIN;
-- TEETH: a row computed over a single hive is a private figure with a public caption. The check above
-- must see it - a k-anonymity lock that cannot detect k=1 is decoration.
UPDATE network_benchmarks SET sample_hives = 1
 WHERE id = (SELECT id FROM network_benchmarks LIMIT 1);
SELECT 'detector_sees_a_single_hive_row | ' || (
  (SELECT count(*) FROM network_benchmarks WHERE sample_hives IS NULL OR sample_hives < 2) > 0);
ROLLBACK;

-- ★A COUNT-BASED RESTORATION CHECK IS BROKEN BY ANY CONCURRENT WRITER (2026-09-10). Comparing
-- count-at-start with count-at-end reported `false` in a sibling recipe while its rollbacks had
-- worked perfectly - an archetype walk had written two real rows between the readings. A probe
-- that fails when the platform is BUSY teaches people to re-run reds until they go green. The
-- assertions below are about THIS probe's own residue, or about the invariant itself, so another
-- writer cannot move them.
SELECT 'rows_restored_after_rollback | ' || (
  (SELECT count(*) FROM network_benchmarks WHERE sample_hives IS NULL OR sample_hives < 2) = 0);
DROP TABLE _bfx;
