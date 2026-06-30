-- ============================================================================
-- Arc S (Resilience / DR) — C-lens: dedup constraints (exactly-once on retries)
-- ============================================================================
-- Two write paths can create duplicate rows on a double-submit / network retry
-- because the dedup is only attempted client-side (button-disable, which has a
-- race window) with NO database-level UNIQUE guard:
--
--   * pm_completions   — a worker double-taps "Complete" (or SAP/Maximo re-sends
--     a completion on timeout) -> two identical completion rows for the same
--     (scope_item, worker, day). validate_idempotency flagged this WARN; Arc S
--     promotes it to a hard DB constraint (C floor = 100).
--   * project_links    — double-click "Link" -> two identical (project, type, id)
--     link rows. UI shows duplicates; no constraint existed.
--
-- The fix is a partial UNIQUE index (the DB-level exactly-once guarantee). A
-- second insert then fails with 23505 unique_violation, which the client catches
-- and treats as benign ("already recorded") instead of creating a phantom row.
--
-- pm_completions has pre-existing duplicates in dev/test DBs (test-seeder + live
-- MCP test writes). We clean-then-constrain: keep the earliest row (min ctid) per
-- (scope_item_id, worker_name, UTC-day) group, then add the index. The DELETE is
-- conservative — it only removes EXACT triple-duplicates, which are by definition
-- accidental double-submits.
--
-- Index expression note: date(timestamptz) is STABLE (depends on the session
-- TimeZone) so it cannot live in an index. `(completed_at AT TIME ZONE 'UTC')::date`
-- uses a literal zone and IS immutable, so it is index-safe and deterministic.
--
-- Forward-only. Idempotent (IF NOT EXISTS). No schema change beyond the indexes.
-- ============================================================================

-- ── pm_completions: clean-then-constrain ────────────────────────────────────
DELETE FROM public.pm_completions a
USING public.pm_completions b
WHERE a.scope_item_id IS NOT NULL
  AND a.scope_item_id = b.scope_item_id
  AND a.worker_name   = b.worker_name
  AND (a.completed_at AT TIME ZONE 'UTC')::date = (b.completed_at AT TIME ZONE 'UTC')::date
  AND a.ctid > b.ctid;   -- keep the earliest physical row per dup group

CREATE UNIQUE INDEX IF NOT EXISTS pm_completions_dedup_uidx
  ON public.pm_completions (scope_item_id, worker_name, ((completed_at AT TIME ZONE 'UTC')::date))
  WHERE scope_item_id IS NOT NULL;

-- ── project_links: constrain (already clean) ────────────────────────────────
CREATE UNIQUE INDEX IF NOT EXISTS project_links_target_uidx
  ON public.project_links (project_id, link_type, link_id)
  WHERE link_id IS NOT NULL;
