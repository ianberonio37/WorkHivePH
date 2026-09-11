-- ai_quality_escalation: one standing flag per worker per hive, not a pile of them.
--
-- WHY. voice-handler upserts this row when a worker leaves a third thumbs-down inside seven days, so the
-- ai-quality dashboard can prompt supervisor outreach. `upsert` with no conflict target is an INSERT:
-- PostgREST sends resolution=merge-duplicates, and with nothing unique to merge ON, every negative rating
-- after the threshold would have appended ANOTHER escalation row for the same person. A worker having one
-- bad week would read on the dashboard as a worker escalated five times.
--
-- Nothing has actually landed yet - the same write named `negative_count`, a column this table does not
-- have (it is `thumbs_down_7d`), so every row was refused for an unknown column inside an empty catch that
-- a resolved refusal never reaches. Both are fixed together: the client now writes the real column and
-- names this constraint as its conflict target.
--
-- Safe on a table with existing rows: the DELETE below keeps the most recent row per (worker_name,
-- hive_id) before the index is built, so the migration cannot fail on a duplicate it did not create.
-- Measured on this stack the table is empty, so it deletes nothing; the clause is there for a project
-- where it is not.

BEGIN;

DELETE FROM public.ai_quality_escalation a
 USING public.ai_quality_escalation b
 WHERE a.worker_name IS NOT DISTINCT FROM b.worker_name
   AND a.hive_id     IS NOT DISTINCT FROM b.hive_id
   AND a.created_at  <  b.created_at;

-- A partial-free plain unique index: both columns are nullable, and in Postgres NULLs do not collide, so
-- a row with a null hive_id stays unconstrained rather than blocking every other null. That is the right
-- behaviour here - a flag with no hive is not a flag anyone is looking at.
CREATE UNIQUE INDEX IF NOT EXISTS ux_ai_quality_escalation_worker_hive
  ON public.ai_quality_escalation (worker_name, hive_id);

COMMIT;
