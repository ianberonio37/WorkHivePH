-- WorkHive Marketplace — Scaling Layer
-- Phase 1: indexes, full-text search, seller profiles, orders, disputes

-- =============================================
-- 1. INDEXES on marketplace_listings
-- =============================================
CREATE INDEX IF NOT EXISTS idx_mkt_listings_section_status
  ON public.marketplace_listings (section, status);

CREATE INDEX IF NOT EXISTS idx_mkt_listings_hive_section
  ON public.marketplace_listings (hive_id, section, status);

CREATE INDEX IF NOT EXISTS idx_mkt_listings_seller
  ON public.marketplace_listings (seller_name, status);

CREATE INDEX IF NOT EXISTS idx_mkt_listings_created
  ON public.marketplace_listings (created_at DESC);

-- =============================================
-- 2. FULL-TEXT SEARCH column on marketplace_listings
-- =============================================
ALTER TABLE public.marketplace_listings
  ADD COLUMN IF NOT EXISTS search_vector tsvector
  GENERATED ALWAYS AS (
    to_tsvector('english',
      coalesce(title,       '') || ' ' ||
      coalesce(description, '') || ' ' ||
      coalesce(category,    '') || ' ' ||
      coalesce(location,    '') || ' ' ||
      coalesce(seller_name, '')
    )
  ) STORED;

CREATE INDEX IF NOT EXISTS idx_mkt_listings_fts
  ON public.marketplace_listings USING GIN (search_vector);

-- =============================================
-- 3. INDEXES on marketplace_inquiries + reviews
-- =============================================
CREATE INDEX IF NOT EXISTS idx_mkt_inquiries_listing
  ON public.marketplace_inquiries (listing_id, status);

CREATE INDEX IF NOT EXISTS idx_mkt_inquiries_created
  ON public.marketplace_inquiries (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_mkt_reviews_listing
  ON public.marketplace_reviews (listing_id);

-- =============================================
-- 4. marketplace_sellers — seller profiles
-- =============================================
CREATE TABLE IF NOT EXISTS public.marketplace_sellers (
  id                 uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  worker_name        text        NOT NULL UNIQUE,
  auth_uid           uuid,
  hive_id            uuid        REFERENCES public.hives(id) ON DELETE SET NULL,
  tier               text        NOT NULL DEFAULT 'bronze'
                                 CHECK (tier IN ('bronze','silver','gold')),
  kyb_verified       boolean     NOT NULL DEFAULT false,
  kyb_verified_at    timestamptz,
  total_sales        integer     NOT NULL DEFAULT 0,
  rating_avg         numeric(3,2),
  rating_count       integer     NOT NULL DEFAULT 0,
  response_rate      numeric(5,2),
  response_time_h    numeric(6,1),
  stripe_account_id  text,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_mkt_sellers_worker
  ON public.marketplace_sellers (worker_name);

CREATE INDEX IF NOT EXISTS idx_mkt_sellers_tier
  ON public.marketplace_sellers (tier, kyb_verified);

-- =============================================
-- 5. marketplace_orders — purchase records (escrow)
-- =============================================
CREATE TABLE IF NOT EXISTS public.marketplace_orders (
  id                   uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  listing_id           uuid        REFERENCES public.marketplace_listings(id) ON DELETE SET NULL,
  hive_id              uuid        REFERENCES public.hives(id) ON DELETE SET NULL,
  buyer_name           text        NOT NULL,
  seller_name          text        NOT NULL,
  price                numeric(14,2) NOT NULL,
  currency             text        NOT NULL DEFAULT 'PHP',
  stripe_session_id    text        UNIQUE,
  stripe_payment_id    text,
  stripe_transfer_id   text,
  status               text        NOT NULL DEFAULT 'pending_payment'
                                   CHECK (status IN (
                                     'pending_payment',
                                     'escrow_hold',
                                     'buyer_confirmed',
                                     'released',
                                     'refunded',
                                     'disputed'
                                   )),
  escrow_release_at    timestamptz,
  buyer_confirmed_at   timestamptz,
  released_at          timestamptz,
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_mkt_orders_listing
  ON public.marketplace_orders (listing_id);

CREATE INDEX IF NOT EXISTS idx_mkt_orders_buyer
  ON public.marketplace_orders (buyer_name, status);

CREATE INDEX IF NOT EXISTS idx_mkt_orders_seller
  ON public.marketplace_orders (seller_name, status);

CREATE INDEX IF NOT EXISTS idx_mkt_orders_stripe_session
  ON public.marketplace_orders (stripe_session_id);

-- =============================================
-- 6. marketplace_disputes — structured escalation
-- =============================================
CREATE TABLE IF NOT EXISTS public.marketplace_disputes (
  id                 uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id           uuid        REFERENCES public.marketplace_orders(id) ON DELETE CASCADE,
  listing_id         uuid        REFERENCES public.marketplace_listings(id) ON DELETE SET NULL,
  opened_by          text        NOT NULL,
  seller_name        text        NOT NULL,
  reason             text        NOT NULL,
  evidence_urls      text[],
  status             text        NOT NULL DEFAULT 'open'
                                 CHECK (status IN (
                                   'open',
                                   'seller_responded',
                                   'admin_review',
                                   'resolved_refund',
                                   'resolved_release'
                                 )),
  seller_reply       text,
  seller_replied_at  timestamptz,
  admin_decision     text,
  admin_decided_at   timestamptz,
  resolved_at        timestamptz,
  created_at         timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_mkt_disputes_order
  ON public.marketplace_disputes (order_id);

CREATE INDEX IF NOT EXISTS idx_mkt_disputes_status
  ON public.marketplace_disputes (status, created_at);

-- =============================================
-- 7. Seller tier auto-update trigger
--    Fires after an order moves to 'released'
-- =============================================
CREATE OR REPLACE FUNCTION public.update_seller_tier()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.status = 'released' AND OLD.status <> 'released' THEN
    INSERT INTO public.marketplace_sellers (worker_name, total_sales, tier)
    VALUES (NEW.seller_name, 1, 'bronze')
    ON CONFLICT (worker_name) DO UPDATE SET
      total_sales = marketplace_sellers.total_sales + 1,
      tier = CASE
        WHEN marketplace_sellers.total_sales + 1 >= 51 THEN 'gold'
        WHEN marketplace_sellers.total_sales + 1 >= 11 THEN 'silver'
        ELSE 'bronze'
      END,
      updated_at = now();
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_seller_tier ON public.marketplace_orders;
CREATE TRIGGER trg_seller_tier
  AFTER UPDATE OF status ON public.marketplace_orders
  FOR EACH ROW EXECUTE FUNCTION public.update_seller_tier();

-- =============================================
-- 8. pg_cron: auto-escalate disputes with no
--    seller reply after 48 hours (daily at 09:00 UTC)
-- =============================================
-- Requires pg_cron extension (enabled by default on Supabase Pro)
-- Uncomment when on Pro tier:
-- SELECT cron.schedule(
--   'dispute-escalate-48h',
--   '0 9 * * *',
--   $$
--     UPDATE public.marketplace_disputes
--     SET status = 'admin_review'
--     WHERE status = 'open'
--       AND seller_replied_at IS NULL
--       AND created_at < NOW() - INTERVAL '48 hours';
--   $$
-- );

-- =============================================
-- 9. Velocity guard: max 20 new listings per hive per day
-- =============================================
CREATE OR REPLACE FUNCTION public.check_listing_rate()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE daily_count integer;
BEGIN
  IF NEW.hive_id IS NULL THEN RETURN NEW; END IF;
  SELECT COUNT(*) INTO daily_count
    FROM public.marketplace_listings
    WHERE hive_id = NEW.hive_id
      AND created_at > NOW() - INTERVAL '24 hours';
  IF daily_count >= 20 THEN
    RAISE EXCEPTION 'Daily listing limit of 20 reached for this hive';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_listing_rate ON public.marketplace_listings;
CREATE TRIGGER trg_listing_rate
  BEFORE INSERT ON public.marketplace_listings
  FOR EACH ROW EXECUTE FUNCTION public.check_listing_rate();

-- =============================================
-- 10. Grants
-- =============================================
GRANT SELECT, INSERT ON public.marketplace_sellers TO anon, authenticated;
GRANT UPDATE (tier, kyb_verified, kyb_verified_at, total_sales, rating_avg,
              rating_count, response_rate, response_time_h, updated_at)
  ON public.marketplace_sellers TO authenticated;

GRANT SELECT, INSERT ON public.marketplace_orders TO anon, authenticated;
GRANT UPDATE (status, buyer_confirmed_at, released_at, updated_at)
  ON public.marketplace_orders TO authenticated;

GRANT SELECT, INSERT ON public.marketplace_disputes TO anon, authenticated;
GRANT UPDATE (seller_reply, seller_replied_at, status)
  ON public.marketplace_disputes TO authenticated;
