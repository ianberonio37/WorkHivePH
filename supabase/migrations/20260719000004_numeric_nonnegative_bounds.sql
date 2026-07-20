-- Fix (per-page bughunt P4 input-validation, 2026-07-19): several money/quantity columns had NO
-- server-side bound, so the client's numeric validation was bypassable via a direct PostgREST call
-- (e.g. a seller could POST a listing with price = -9999, or an inventory row with qty_on_hand = -100).
-- Nonsensical negatives corrupt aggregates, trust displays, and stock math. Non-negativity is an
-- unambiguous business rule for every column below; NULLs still pass (a CHECK is not violated by NULL),
-- so optional fields (downtime_hours, price on a contact-for-price listing) are unaffected.
-- Verified 0 existing violations on the test DB. Added NOT VALID so the constraint enforces on all
-- NEW/updated rows immediately but does NOT re-scan existing rows on apply — a production-safe deploy
-- (a stray legacy negative can't fail the whole migration; clean it + VALIDATE CONSTRAINT separately).

ALTER TABLE public.inventory_items
  ADD CONSTRAINT inventory_items_qty_on_hand_nonneg CHECK (qty_on_hand >= 0) NOT VALID,
  ADD CONSTRAINT inventory_items_min_qty_nonneg      CHECK (min_qty     >= 0) NOT VALID;

ALTER TABLE public.marketplace_listings
  ADD CONSTRAINT marketplace_listings_price_nonneg CHECK (price >= 0) NOT VALID;

ALTER TABLE public.marketplace_orders
  ADD CONSTRAINT marketplace_orders_price_nonneg CHECK (price >= 0) NOT VALID;

ALTER TABLE public.logbook
  ADD CONSTRAINT logbook_downtime_hours_nonneg CHECK (downtime_hours >= 0) NOT VALID;
