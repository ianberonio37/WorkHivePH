-- ─────────────────────────────────────────────────────────────────────────────
-- Close the cross-hive compliance-poisoning hole the asset check left open.
--
-- FOUND BY THE PM13 WALK (2026-07-28, PM_DEEPWALK_EXPANSION_ROADMAP):
-- `pm_completions_write`'s WITH CHECK already required that the row's `asset_id` belong to the same
-- hive as its `hive_id` (migration 20260712000012, PM Scheduler PDDA arc). It said NOTHING about
-- `scope_item_id`. So a member of hive A could insert a completion with:
--
--     hive_id       = their OWN hive      (passes the membership test)
--     asset_id      = their OWN asset     (passes the existing parent check)
--     scope_item_id = a scope item in hive B
--
-- ...and it was ACCEPTED. Every consumer joins completions to scope items by `scope_item_id`, NOT by
-- the completion's own `hive_id`:
--   * `get_pm_compliance_smrp` counts completions per scope item -> hive B's compliance rises.
--     Probed live: the foreign hive's credited completions went 502 -> 503 from one inserted row.
--   * `get_pm_ontime_delivery` counts the same intervals -> hive B's on-time figure moves.
--   * `v_pm_scope_items_truth.last_completed_at` takes the newest completion for the item, which
--     drives `next_due_date` -> an OVERDUE PM in hive B silently reads as done. That is the sharpest
--     consequence: it is not just a number, it removes work from another plant's overdue list.
--
-- The PDDA arc's `xcomp` test does not catch this because it sets `hive_id` to the FOREIGN hive
-- (correctly blocked). Pointing `hive_id` at your OWN hive while aiming `scope_item_id` at theirs
-- slips through the gap between the two columns — a child/ledger-table WITH-CHECK that validates one
-- parent and not the other.
--
-- THE RULE ADDED: a completion's scope item must belong to the SAME ASSET the completion names.
-- Since the existing check already ties that asset to the row's hive, one condition closes both the
-- tenancy hole and the nonsense pairing (completing scope item X "on" an asset it does not belong
-- to). Verified safe before applying: of 1,591 existing completions, ZERO have a scope item in
-- another hive, on another asset, or a NULL scope_item_id — so this rejects nothing that exists.
--
-- NULL scope_item_id stays permitted for a future ad-hoc completion with no scope item; the
-- condition is written so NULL passes rather than being silently refused.
-- ─────────────────────────────────────────────────────────────────────────────

DROP POLICY IF EXISTS pm_completions_scope_parent_guard ON public.pm_completions;
CREATE POLICY pm_completions_scope_parent_guard
  ON public.pm_completions
  AS RESTRICTIVE
  FOR ALL
  USING (true)          -- reads are governed by the existing permissive policy; this guards writes
  WITH CHECK (
    scope_item_id IS NULL
    OR EXISTS (
      SELECT 1 FROM public.pm_scope_items s
       WHERE s.id       = pm_completions.scope_item_id
         AND s.asset_id = pm_completions.asset_id
    )
  );
