-- Buyer Review Support
-- Adds reviewed_at to marketplace_orders (prevents duplicate reviews)
-- and a trigger to keep marketplace_sellers.rating_avg current

-- =============================================
-- 1. reviewed_at on marketplace_orders
-- =============================================
ALTER TABLE public.marketplace_orders
  ADD COLUMN IF NOT EXISTS reviewed_at timestamptz;

-- =============================================
-- 2. Trigger: update seller rating on new review
-- =============================================
CREATE OR REPLACE FUNCTION public.update_seller_rating()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  v_seller_name text;
  v_new_avg     numeric(3,2);
  v_new_count   integer;
BEGIN
  -- Find the seller from the reviewed listing
  SELECT seller_name INTO v_seller_name
  FROM public.marketplace_listings
  WHERE id = NEW.listing_id;

  IF v_seller_name IS NULL THEN
    RETURN NEW;
  END IF;

  -- Compute new average and count across all this seller's listings
  SELECT
    ROUND(AVG(r.rating::numeric), 2),
    COUNT(*)::integer
  INTO v_new_avg, v_new_count
  FROM public.marketplace_reviews r
  JOIN public.marketplace_listings l ON r.listing_id = l.id
  WHERE l.seller_name = v_seller_name;

  -- Upsert seller profile (creates row if first review)
  INSERT INTO public.marketplace_sellers (worker_name, rating_avg, rating_count, updated_at)
  VALUES (v_seller_name, v_new_avg, v_new_count, now())
  ON CONFLICT (worker_name) DO UPDATE SET
    rating_avg   = v_new_avg,
    rating_count = v_new_count,
    updated_at   = now();

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_update_seller_rating ON public.marketplace_reviews;
CREATE TRIGGER trg_update_seller_rating
  AFTER INSERT ON public.marketplace_reviews
  FOR EACH ROW EXECUTE FUNCTION public.update_seller_rating();

-- =============================================
-- 3. Grant UPDATE on reviewed_at
-- =============================================
GRANT UPDATE (reviewed_at) ON public.marketplace_orders TO authenticated;
GRANT INSERT ON public.marketplace_reviews TO anon, authenticated;
