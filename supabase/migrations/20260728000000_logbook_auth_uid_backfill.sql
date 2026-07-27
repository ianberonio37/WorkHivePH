-- ─────────────────────────────────────────────────────────────────────────────
-- Backfill logbook.auth_uid for legacy rows, so their owner can edit them again.
--
-- FOUND BY THE LB9 WALK (2026-07-28, LOGBOOK_DEEPWALK_EXPANSION_ROADMAP):
-- logbook's RLS is asymmetric on purpose — SELECT is hive-scoped (any active member reads the
-- hive's entries) while UPDATE and DELETE are owner-scoped (`auth_uid = auth.uid()`). That is the
-- right shape. But rows written before `trg_bind_submitter_logbook` started binding the submitter
-- carry auth_uid IS NULL, and `NULL = auth.uid()` is never true — so those rows are editable and
-- deletable by NOBODY, forever, while the UI still offers Edit and Delete on them.
--
-- Measured live before writing this: 72 of 3,771 rows (1.9%), all belonging to one worker, created
-- between April and July 2026. An update of one such row applied nothing and returned no error,
-- which is what made the page tell the user "Entry was modified by someone else" — a message that
-- is false and that no amount of reloading can resolve.
--
-- WHAT THIS INFERS, AND WHY IT IS SAFE:
-- The row already asserts its author in `worker_name`; this only links that author to their account,
-- which is exactly what the INSERT trigger does for every row written today. The join is applied
-- ONLY where the mapping is unambiguous — a worker_name resolving to exactly one auth_uid across
-- hive_members. A name shared by two accounts is skipped rather than guessed, because attribution in
-- a maintenance logbook is the DOLE/ISO audit trail and a wrong guess there is worse than a gap.
-- Idempotent and narrow: touches only rows where auth_uid IS NULL, so re-running is a no-op and no
-- existing attribution is ever overwritten.
-- ─────────────────────────────────────────────────────────────────────────────

WITH unambiguous AS (
    -- No MIN() for uuid in Postgres; the HAVING below guarantees the array holds exactly one value.
    SELECT worker_name, (array_agg(DISTINCT auth_uid))[1] AS auth_uid
    FROM hive_members
    WHERE auth_uid IS NOT NULL AND worker_name IS NOT NULL
    GROUP BY worker_name
    HAVING COUNT(DISTINCT auth_uid) = 1
)
UPDATE logbook l
SET    auth_uid = u.auth_uid
FROM   unambiguous u
WHERE  l.auth_uid IS NULL
  AND  l.worker_name = u.worker_name;
