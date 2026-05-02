-- Listing view counter (Phase B3 — Seller Analytics)
-- Tracks total views per listing so sellers can see which listings perform.
-- RPC ensures atomic increment under concurrent reads (avoids the SELECT-UPDATE
-- race that drops counts when two buyers open the same listing simultaneously).

ALTER TABLE public.marketplace_listings
  ADD COLUMN IF NOT EXISTS view_count integer NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_mkt_listings_view_count
  ON public.marketplace_listings (view_count DESC);

-- Atomic increment via RPC (callable from anon role for view tracking)
CREATE OR REPLACE FUNCTION public.increment_listing_view(p_listing_id uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  UPDATE public.marketplace_listings
  SET view_count = view_count + 1
  WHERE id = p_listing_id
    AND status = 'published';   -- only count views on live listings
END;
$$;

GRANT EXECUTE ON FUNCTION public.increment_listing_view(uuid) TO anon, authenticated;
