-- ============================================================================
-- Marketplace TRUST INTEGRITY — close two live-exploited trust-poisoning holes
-- (Marketplace PDDA, I-axis; both LIVE-EXPLOITED 2026-07-11 before fixing)
-- ----------------------------------------------------------------------------
-- HOLE #1 — marketplace_reviews had RLS DISABLED + anon/authenticated INSERT+SELECT
--   grants. Anyone (even logged-out) could INSERT a review with any rating and
--   verified_purchase=true; the trg_update_seller_rating trigger then recomputes the
--   seller's rating_avg/rating_count from it → a competitor spams 1-stars, or a seller
--   fabricates 5-star "verified" reviews. Trust/rating system fully poisonable.
--
-- HOLE #2 — marketplace_sellers UPDATE policy checked only (auth_uid = auth.uid()) with
--   NO column-level restriction. A seller self-UPDATE could set kyb_verified, cert_verified,
--   tier, rating_avg, rating_count, total_sales, response_* → fabricate EVERY trust signal.
--   (Verified live: set kyb_verified=true, tier='gold', rating_avg=5, total_sales=999.)
--   RLS WITH CHECK cannot express "may edit the row but not THESE columns" nor a
--   pending→verified transition — same shape as the supervisor-approval backstop, so the
--   fix is a SECURITY DEFINER BEFORE trigger, not a policy.
-- ============================================================================

-- ── HOLE #1: lock marketplace_reviews ───────────────────────────────────────
ALTER TABLE public.marketplace_reviews ENABLE ROW LEVEL SECURITY;

-- Reviews are PUBLIC trust signals (shown on the public listing detail) — anyone may read.
DROP POLICY IF EXISTS mkt_reviews_read ON public.marketplace_reviews;
CREATE POLICY mkt_reviews_read ON public.marketplace_reviews FOR SELECT USING (true);

-- Only an authenticated user may post a review, only under their OWN worker name, and may
-- NOT self-claim verified_purchase (a contact-only/free marketplace has no order to verify
-- against; only a trusted/admin path may mark a review verified). Admins may do anything.
DROP POLICY IF EXISTS mkt_reviews_insert ON public.marketplace_reviews;
CREATE POLICY mkt_reviews_insert ON public.marketplace_reviews FOR INSERT
  WITH CHECK (
    public.is_marketplace_admin()
    OR (reviewer_name IN (SELECT public.auth_worker_names()) AND verified_purchase = false)
  );

DROP POLICY IF EXISTS mkt_reviews_update ON public.marketplace_reviews;
CREATE POLICY mkt_reviews_update ON public.marketplace_reviews FOR UPDATE
  USING (reviewer_name IN (SELECT public.auth_worker_names()) OR public.is_marketplace_admin())
  WITH CHECK (
    public.is_marketplace_admin()
    OR (reviewer_name IN (SELECT public.auth_worker_names()) AND verified_purchase = false)
  );

DROP POLICY IF EXISTS mkt_reviews_delete ON public.marketplace_reviews;
CREATE POLICY mkt_reviews_delete ON public.marketplace_reviews FOR DELETE
  USING (reviewer_name IN (SELECT public.auth_worker_names()) OR public.is_marketplace_admin());

-- Grants: anon read-only (public trust signal); authenticated full, gated by the policies.
REVOKE ALL ON public.marketplace_reviews FROM anon;
GRANT SELECT ON public.marketplace_reviews TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.marketplace_reviews TO authenticated;

-- ── HOLE #2: column-level guard on marketplace_sellers trust signals ─────────
-- The rating/tier recompute triggers legitimately write rating_avg/rating_count/total_sales/
-- tier as SECURITY INVOKER (i.e. as the acting user). They announce themselves via a
-- transaction-local GUC so the guard lets THEM through while blocking direct self-grants.
CREATE OR REPLACE FUNCTION public.update_seller_rating()
 RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $function$
 -- DEFINER: a review by any authed user recomputes the SELLER's rating_avg/rating_count.
 -- That sellers-upsert must not be blocked by the sellers INSERT RLS (auth_uid=auth.uid()),
 -- since the reviewer is not the seller. DEFINER lets the system recompute run; the guard
 -- trigger still fires but is exempted via the workhive.seller_system_write GUC below.
DECLARE
  v_seller_name text;
  v_new_avg     numeric(3,2);
  v_new_count   integer;
BEGIN
  SELECT seller_name INTO v_seller_name FROM public.marketplace_listings WHERE id = NEW.listing_id;
  IF v_seller_name IS NULL THEN RETURN NEW; END IF;
  SELECT ROUND(AVG(r.rating::numeric), 2), COUNT(*)::integer
    INTO v_new_avg, v_new_count
    FROM public.marketplace_reviews r
    JOIN public.marketplace_listings l ON r.listing_id = l.id
   WHERE l.seller_name = v_seller_name;
  PERFORM set_config('workhive.seller_system_write', 'on', true);  -- announce system recompute to the guard
  INSERT INTO public.marketplace_sellers (worker_name, rating_avg, rating_count, updated_at)
  VALUES (v_seller_name, v_new_avg, v_new_count, now())
  ON CONFLICT (worker_name) DO UPDATE SET
    rating_avg = v_new_avg, rating_count = v_new_count, updated_at = now();
  RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION public.update_seller_tier()
 RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $function$
BEGIN
  IF NEW.status = 'released' AND OLD.status <> 'released' THEN
    PERFORM set_config('workhive.seller_system_write', 'on', true);  -- announce system recompute to the guard
    INSERT INTO public.marketplace_sellers (worker_name, total_sales, tier)
    VALUES (NEW.seller_name, 1, 'bronze')
    ON CONFLICT (worker_name) DO UPDATE SET
      total_sales = marketplace_sellers.total_sales + 1,
      tier = CASE
        WHEN marketplace_sellers.total_sales + 1 >= 51 THEN 'gold'
        WHEN marketplace_sellers.total_sales + 1 >= 11 THEN 'silver'
        ELSE 'bronze' END,
      updated_at = now();
  END IF;
  RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION public.guard_marketplace_seller_trust_columns()
 RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $function$
BEGIN
  -- service-role / backend writes (no JWT) are already vetted (seeders, edge fns) — allow.
  IF auth.uid() IS NULL THEN RETURN NEW; END IF;
  -- platform admins may set verification / tier / ratings.
  IF public.is_marketplace_admin() THEN RETURN NEW; END IF;
  -- the rating/tier recompute triggers announced themselves this transaction — allow.
  IF current_setting('workhive.seller_system_write', true) = 'on' THEN RETURN NEW; END IF;

  IF TG_OP = 'INSERT' THEN
    -- a seller may create their own profile row, but only with SAFE defaults for trust signals.
    IF COALESCE(NEW.kyb_verified,false) = true OR COALESCE(NEW.cert_verified,false) = true
       OR NEW.kyb_verified_at IS NOT NULL OR NEW.cert_verified_at IS NOT NULL
       OR COALESCE(NEW.tier,'bronze') <> 'bronze'
       OR COALESCE(NEW.rating_avg,0) <> 0 OR COALESCE(NEW.rating_count,0) <> 0
       OR COALESCE(NEW.total_sales,0) <> 0
       OR NEW.response_rate IS NOT NULL OR NEW.response_time_h IS NOT NULL THEN
      RAISE EXCEPTION 'Not allowed: KYB / certification / tier / rating / sales are set by WorkHive, not self-assigned'
        USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
  END IF;

  -- UPDATE: block SELF-UPGRADE of trust signals. A seller MAY downgrade their own
  -- verification (e.g. cert_verified=false when they edit their cert list — legitimate
  -- re-review trigger), so verification checks only fire when turning the flag ON.
  IF (COALESCE(NEW.kyb_verified,false)  = true AND COALESCE(NEW.kyb_verified,false)  IS DISTINCT FROM COALESCE(OLD.kyb_verified,false))
     OR (COALESCE(NEW.cert_verified,false) = true AND COALESCE(NEW.cert_verified,false) IS DISTINCT FROM COALESCE(OLD.cert_verified,false))
     OR (NEW.kyb_verified_at  IS NOT NULL AND NEW.kyb_verified_at  IS DISTINCT FROM OLD.kyb_verified_at)
     OR (NEW.cert_verified_at IS NOT NULL AND NEW.cert_verified_at IS DISTINCT FROM OLD.cert_verified_at)
     OR (NEW.tier            IS DISTINCT FROM OLD.tier)
     OR (NEW.rating_avg      IS DISTINCT FROM OLD.rating_avg)
     OR (NEW.rating_count    IS DISTINCT FROM OLD.rating_count)
     OR (NEW.total_sales     IS DISTINCT FROM OLD.total_sales)
     OR (NEW.response_rate   IS DISTINCT FROM OLD.response_rate)
     OR (NEW.response_time_h IS DISTINCT FROM OLD.response_time_h) THEN
    RAISE EXCEPTION 'Not allowed: KYB / certification / tier / rating / sales are set by WorkHive, not self-assigned'
      USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_guard_seller_trust ON public.marketplace_sellers;
CREATE TRIGGER trg_guard_seller_trust
  BEFORE INSERT OR UPDATE ON public.marketplace_sellers
  FOR EACH ROW EXECUTE FUNCTION public.guard_marketplace_seller_trust_columns();

COMMENT ON FUNCTION public.guard_marketplace_seller_trust_columns() IS
  'Column-level backstop: a non-admin seller may edit their own profile (messenger, certifications text, contact) but may NOT self-grant KYB/cert verification, tier, ratings, sales, or response metrics. Downgrades of own verification are allowed; the rating/tier recompute triggers are exempt via the workhive.seller_system_write GUC. (Marketplace PDDA I-axis; fixes a live-exploited self-grant.)';
