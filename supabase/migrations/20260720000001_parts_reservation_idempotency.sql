-- Arc S (Resilience/DR) C-lens depth, 2026-07-20: idempotency for the parts-staging accept.
--
-- THE GAP: asset-hub.html `_onStagingAccept()` fires TWO writes in parallel (Promise.allSettled) —
-- (1) parts_staged_reservations.insert(reservations) and (2) parts_staging_recommendations.update(...).
-- The UPDATE is idempotency-guarded (`.is('acted_at', null)` — no double-act re-flip), but the INSERT is
-- NOT: parts_staged_reservations had only a pkey, so a double-accept (double-click racing the button-disable,
-- an offline-retry, a network-timeout re-send, or a second device) inserts DUPLICATE reservation rows while
-- the recommendation status correctly flips once. Client button-disable is a UI-only guard = bypassable
-- (see feedback_ui_only_approval_gate_is_bypassable); the robust idempotency guard is server-side.
--
-- THE FIX: one reservation per (recommendation, item) is the natural business key — you cannot stage the same
-- item from the same recommendation twice. A UNIQUE index makes the accept idempotent regardless of the client
-- path (the client insert becomes upsert(onConflict, ignoreDuplicates) → a re-fire is a no-op, not a duplicate).
-- Verified 0 existing duplicate (recommendation_id, item_id) pairs on the test DB. NULL recommendation_id rows
-- (manual reservations with no source recommendation) are unaffected — NULLs are distinct in a unique index.

CREATE UNIQUE INDEX IF NOT EXISTS parts_staged_reservations_rec_item_uidx
  ON public.parts_staged_reservations (recommendation_id, item_id);
