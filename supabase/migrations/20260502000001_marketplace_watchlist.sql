-- Buyer Watchlist (saved listings)
-- Each row links a worker_name to a listing_id. UNIQUE constraint
-- prevents the same buyer from saving the same listing twice.
-- ON DELETE CASCADE means watchlist rows auto-clean when a listing is deleted.

CREATE TABLE IF NOT EXISTS public.marketplace_watchlist (
  id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  worker_name text        NOT NULL,
  listing_id  uuid        NOT NULL REFERENCES public.marketplace_listings(id) ON DELETE CASCADE,
  created_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (worker_name, listing_id)
);

CREATE INDEX IF NOT EXISTS idx_mkt_watchlist_worker
  ON public.marketplace_watchlist (worker_name);

CREATE INDEX IF NOT EXISTS idx_mkt_watchlist_listing
  ON public.marketplace_watchlist (listing_id);

GRANT SELECT, INSERT, DELETE ON public.marketplace_watchlist TO anon, authenticated;
