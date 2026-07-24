-- 20260723000002_asset_node_rejection_reason.sql
-- ============================================================================
-- A REJECTION MUST SAY WHY (§12 flywheel loop 12, approval-chain journey walk).
--
-- FOUND: asset-hub's rejectAssetNode() sets status='rejected' + approved_by +
-- approved_at and writes an audit row - but captures NO REASON. The submitting
-- worker sees their asset flip to "rejected" with no explanation, so they cannot
-- fix and resubmit; they can only guess or go ask in person. That is a classic
-- dead-end state (rubric class X1) sitting in the middle of a multi-actor async
-- journey, which is exactly the kind of break a single-page scan never sees.
--
-- WHY THIS IS NOT SCOPE-CREEP: the capture UI already exists - `window.whPrompt`
-- (utils.js) is the shared confirm-with-text-input, sibling of whConfirm. So this
-- is one nullable column plus a whConfirm -> whPrompt swap at the call site. It
-- encodes the universal "tell the user why", not a business-policy choice.
--
-- Nullable by design: every historical rejection predates this and must stay
-- valid; the UI treats a NULL reason as "no reason recorded".
-- ============================================================================

ALTER TABLE public.asset_nodes
  ADD COLUMN IF NOT EXISTS rejection_reason text;

-- Keep it a short human note, not a dumping ground (mirrors the platform's
-- server-side text-cap discipline on user-entered fields).
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'asset_nodes_rejection_reason_len'
  ) THEN
    ALTER TABLE public.asset_nodes
      ADD CONSTRAINT asset_nodes_rejection_reason_len
      CHECK (rejection_reason IS NULL OR char_length(rejection_reason) <= 500);
  END IF;
END $$;

COMMENT ON COLUMN public.asset_nodes.rejection_reason IS
  'Supervisor note captured at reject time (whPrompt) so the submitting worker learns WHY and can fix + resubmit. NULL = rejected before this column existed, or no reason given.';
