-- Seller Dashboard Support
-- Adds seller_name + reply fields to marketplace_inquiries
-- so sellers can query their own inquiries without a JOIN

ALTER TABLE public.marketplace_inquiries
  ADD COLUMN IF NOT EXISTS seller_name  text,
  ADD COLUMN IF NOT EXISTS reply_text   text,
  ADD COLUMN IF NOT EXISTS replied_at   timestamptz;

-- Back-fill seller_name from the listing for any existing inquiries
UPDATE public.marketplace_inquiries inq
SET seller_name = ml.seller_name
FROM public.marketplace_listings ml
WHERE inq.listing_id = ml.id
  AND inq.seller_name IS NULL;

CREATE INDEX IF NOT EXISTS idx_mkt_inquiries_seller
  ON public.marketplace_inquiries (seller_name, status);

-- Grant UPDATE on new reply columns
GRANT UPDATE (reply_text, replied_at, status)
  ON public.marketplace_inquiries TO authenticated;
