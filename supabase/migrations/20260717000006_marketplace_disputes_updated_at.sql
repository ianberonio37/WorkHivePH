-- Sibling of 20260717000005 (bug-hunt roadmap P6, 2026-07-17), caught by validate_oc_updated_at_backed.py.
-- marketplace_disputes had NO `updated_at` column, yet marketplace-admin.html writes it when an admin
-- resolves/updates a dispute:
--   const update = { updated_at: nowIso };  ...  db.from('marketplace_disputes').update(disputeUpdate)...
-- A phantom-column write on a money/trust-adjacent admin flow (dispute resolution) — the field is
-- rejected/dropped and there is no updated_at to hang optimistic concurrency on. Same canonical fix.
ALTER TABLE public.marketplace_disputes ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

DROP TRIGGER IF EXISTS tg_marketplace_disputes_touch_updated ON public.marketplace_disputes;
CREATE TRIGGER tg_marketplace_disputes_touch_updated
  BEFORE UPDATE ON public.marketplace_disputes
  FOR EACH ROW EXECUTE FUNCTION public.touch_updated_at();
