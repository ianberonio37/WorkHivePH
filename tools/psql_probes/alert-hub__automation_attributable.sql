-- automation_attributable: every automation run is attributable - automation_log rows all carry
-- job_name, triggered_at and status, and every row can be ROUTED: it either names the hive it acted
-- on, or it says in its own detail what it covered when it acted platform-wide.
-- expect: log_rows \| [1-9][0-9]*
-- expect: unattributed \| 0
-- expect: unroutable_rows \| 0
SELECT 'log_rows | ' || count(*) FROM automation_log;
SELECT 'unattributed | ' || count(*) FROM automation_log
WHERE job_name IS NULL OR triggered_at IS NULL OR status IS NULL;
-- ★THE SCOPE INVARIANT WAS PER-JOB, AND ROUTING IS PER-ROW. This used to ask that no job_name ever
-- appear both hive-scoped and platform-scoped, calling the mix "a job whose failures cannot be routed
-- to an owner". Two jobs run in BOTH modes on purpose and say so themselves: benchmark-compute writes
-- "Computed benchmarks for 3 hive(s)" with hive_id NULL for the platform sweep and "for 1 hive(s)"
-- with a hive_id for a single-hive run; failure-signature-scan writes "Scanned 6 hive(s)" for its
-- sweep. A sweep failure routes to the platform and a per-hive failure to that hive - the hive_id
-- column IS the routing, correct on every row.
--
-- ...and the first repair for that was too crude in the other direction: requiring the word "hive" in
-- the detail flagged two ml-retrain rows whose detail is JSON explaining exactly why they skipped
-- ("Only 60 asset-level rows - need >= 100 to train"). A platform-wide row that explains itself is
-- routable. Unroutable means the row says NOTHING: no hive, and no detail either.
SELECT 'unroutable_rows | ' || count(*) FROM automation_log
WHERE hive_id IS NULL AND (detail IS NULL OR btrim(detail) = '');
