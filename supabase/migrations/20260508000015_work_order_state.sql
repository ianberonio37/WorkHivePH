-- Phase E.4: Work Order State Machine on logbook entries.
--
-- Industrial maintenance practice (ISO 14224, Philippine plant convention) tracks
-- work orders through more states than just Open/Closed. This migration adds two
-- ADDITIVE columns to the existing `logbook` table so the new workflow is opt-in
-- per entry: existing rows stay NULL and behave exactly as before, new entries
-- can flow through the formal states below.
--
--   (null = legacy)
--      |
--      v
--   requested  --(supervisor approves)--->  approved
--      |                                       |
--      |                                       v
--      |                                    assigned  -->  in_progress  -->  completed
--      |                                       |               |                 |
--      |                                       v               v                 v
--      +---(supervisor rejects)----------->  rejected     (worker)           verified  -->  (status='Closed')
--                                              ^
--                                              |
--                                            re-open
--                                              |
--                                          requested
--
-- Skills consulted before writing:
--   architect (ADD COLUMN nullable + CHECK, no FK to keep it simple, no breaking
--   changes to existing rows), data-engineer (composite indexes on hive_id +
--   wo_state for board-style queries), security (CHECK constraint server-side
--   even though primary enforcement is client-side at this stage; RLS deferred
--   per RLS decision memory).

BEGIN;

-- 1. Add the two new columns. Both nullable, no default, no FK — keeps the
--    migration safe on a populated table and zero coupling to other schemas.

ALTER TABLE public.logbook
  ADD COLUMN IF NOT EXISTS wo_state text;

ALTER TABLE public.logbook
  ADD COLUMN IF NOT EXISTS wo_assigned_to text;

-- 2. Enforce the valid set at the database level. NULL is accepted (legacy rows).
--    DROP first so re-runs of this migration don't 42710-conflict.

ALTER TABLE public.logbook
  DROP CONSTRAINT IF EXISTS logbook_wo_state_check;

ALTER TABLE public.logbook
  ADD CONSTRAINT logbook_wo_state_check
  CHECK (
    wo_state IS NULL OR wo_state IN (
      'requested', 'approved', 'assigned', 'in_progress',
      'completed', 'verified', 'rejected'
    )
  );

-- 3. Indexes for the future Kanban board view (Phase E.4.b) plus per-worker
--    "what's assigned to me" queries from the operational home dashboard.

CREATE INDEX IF NOT EXISTS idx_logbook_hive_wo_state
  ON public.logbook (hive_id, wo_state)
  WHERE wo_state IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_logbook_wo_assigned_to
  ON public.logbook (hive_id, wo_assigned_to)
  WHERE wo_assigned_to IS NOT NULL;

COMMENT ON COLUMN public.logbook.wo_state IS
  'Work-order workflow state. NULL = legacy entry (uses status field only).';

COMMENT ON COLUMN public.logbook.wo_assigned_to IS
  'worker_name of the assignee for this work order. NULL when unassigned or legacy.';

COMMIT;
