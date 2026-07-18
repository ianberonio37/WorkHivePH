-- ============================================================================
-- Backfill marketplace_inquiries.seller_name from the joined listing (F-axis)
-- ----------------------------------------------------------------------------
-- BUG THIS HEALS (Marketplace PDDA, found via LIVE deepwalk 2026-07-11):
-- The primary buyer path — the "Contact Seller" inquiry form in marketplace.html —
-- inserted a marketplace_inquiries row WITHOUT seller_name (only the RFQ/bulk-quote
-- path set it). But the seller dashboard (marketplace-seller.html) surfaces inquiries
-- by querying v_marketplace_inquiries_truth ... .eq('seller_name', WORKER_NAME).
-- The view selects i.seller_name (the base column), NOT the joined l.seller_name — so
-- a NULL seller_name inquiry NEVER matched the seller's filter. The buyer saw
-- "Inquiry sent! Seller responds within 48 hours" but the inquiry was a BLACK-HOLE the
-- seller could never see.
--
-- FIX: marketplace.html now always writes seller_name (stashed from the listing at
-- openInquirySheet, read at submit). This migration heals any historical rows whose
-- seller_name is NULL by copying it from the joined listing.
--
-- Idempotent: only touches rows where seller_name IS NULL and the listing still exists.
-- ============================================================================

UPDATE public.marketplace_inquiries i
SET    seller_name = l.seller_name
FROM   public.marketplace_listings l
WHERE  i.listing_id = l.id
  AND  i.seller_name IS NULL
  AND  l.seller_name IS NOT NULL;
