-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- ★ THE REST OF THE MARKETPLACE BELONGS TO ACCOUNTS, NOT NAMES (2026-10-08 - completes 20261008000060/61)
-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- 20261008000060 moved listing ownership to the account and 20261008000061 moved inquiries. The same name test -
-- `<name column> IN (SELECT auth_worker_names())` - still decided who may read and change five more tables, and any
-- signed-in person can hold any name (20261008000031: found a hive, join it under that name). Measured on the local
-- seed: 6 orders, 0 disputes, 17 reviews, 1 saved search, 1 watchlist row - each readable, and all but reviews
-- changeable, by whoever holds the name on it.
--
--   orders     the BUYER is buyer_auth_uid (new), the SELLER is the listing's owner (listing_is_mine)
--   disputes   the OPENER is opened_by_auth_uid (new), the SELLER is the listing's owner; opening one still needs a
--              conversation or an order the opener is party to - now proven by account (helpers below)
--   reviews    the REVIEWER is reviewer_auth_uid (it existed, nothing stamped it); "you may not review your own
--              listing" and "you must have asked about it" are asked by account too
--   saved searches, watchlist   the OWNER is auth_uid (new) - a person's own private lists
-- Every key is stamped from auth.uid() on a signed-in insert (whatever was sent) and bound for existing rows only when
-- exactly ONE account holds the name (resolve_marketplace_party, 20261008000061) - NULL otherwise: FAIL CLOSED, the
-- row is then an admin's to bind. Where another person can see the row (orders, disputes, public reviews) the key is
-- hidden by column grants (a column revoke is inert under a table grant), so it is checked by RLS without being read.
BEGIN;

-- ── shared: is this order mine (as its buyer or its listing's seller)? asked without reading the hidden key ─────────
-- (defined after the column exists, below)

-- ═══ ORDERS ═══════════════════════════════════════════════════════════════════════════════════════
ALTER TABLE public.marketplace_orders ADD COLUMN IF NOT EXISTS buyer_auth_uid uuid REFERENCES auth.users(id) ON DELETE SET NULL;
ALTER TABLE public.marketplace_orders ALTER COLUMN buyer_auth_uid SET DEFAULT auth.uid();
CREATE INDEX IF NOT EXISTS idx_marketplace_orders_buyer_auth_uid ON public.marketplace_orders (buyer_auth_uid);
UPDATE public.marketplace_orders SET buyer_auth_uid = public.resolve_marketplace_party(buyer_name, hive_id) WHERE buyer_auth_uid IS NULL;

CREATE OR REPLACE FUNCTION public.order_is_mine(p_order uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path TO 'public' AS $fn$
  SELECT auth.uid() IS NOT NULL AND EXISTS (
    SELECT 1 FROM public.marketplace_orders o
     WHERE o.id = p_order AND (o.buyer_auth_uid = auth.uid() OR public.listing_is_mine(o.listing_id))
  );
$fn$;
REVOKE ALL ON FUNCTION public.order_is_mine(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.order_is_mine(uuid) TO anon, authenticated;   -- false for a stranger (see listing_is_mine)

DROP POLICY IF EXISTS mkt_orders_read ON public.marketplace_orders;
CREATE POLICY mkt_orders_read ON public.marketplace_orders FOR SELECT
  USING (buyer_auth_uid = auth.uid() OR public.listing_is_mine(listing_id) OR is_marketplace_admin());
DROP POLICY IF EXISTS mkt_orders_insert ON public.marketplace_orders;
CREATE POLICY mkt_orders_insert ON public.marketplace_orders FOR INSERT
  WITH CHECK (buyer_auth_uid = auth.uid() AND buyer_name IN (SELECT auth_worker_names()));
DROP POLICY IF EXISTS mkt_orders_update ON public.marketplace_orders;
CREATE POLICY mkt_orders_update ON public.marketplace_orders FOR UPDATE
  USING (buyer_auth_uid = auth.uid() OR public.listing_is_mine(listing_id) OR is_marketplace_admin())
  WITH CHECK (buyer_auth_uid = auth.uid() OR public.listing_is_mine(listing_id) OR is_marketplace_admin());

-- ═══ DISPUTES ═════════════════════════════════════════════════════════════════════════════════════
ALTER TABLE public.marketplace_disputes ADD COLUMN IF NOT EXISTS opened_by_auth_uid uuid REFERENCES auth.users(id) ON DELETE SET NULL;
ALTER TABLE public.marketplace_disputes ALTER COLUMN opened_by_auth_uid SET DEFAULT auth.uid();
CREATE INDEX IF NOT EXISTS idx_marketplace_disputes_opened_by_auth_uid ON public.marketplace_disputes (opened_by_auth_uid);
UPDATE public.marketplace_disputes SET opened_by_auth_uid = public.resolve_marketplace_party(opened_by, NULL) WHERE opened_by_auth_uid IS NULL;

DROP POLICY IF EXISTS mkt_disp_read ON public.marketplace_disputes;
CREATE POLICY mkt_disp_read ON public.marketplace_disputes FOR SELECT
  USING (opened_by_auth_uid = auth.uid() OR public.listing_is_mine(listing_id)
         OR (order_id IS NOT NULL AND public.order_is_mine(order_id)) OR is_marketplace_admin());
DROP POLICY IF EXISTS mkt_disp_update ON public.marketplace_disputes;
-- the seller is the listing's owner, reached directly or through the order (a dispute needs a party - an inquiry
-- about a listing, or an order - since 20260907000003, so one of the two always names the seller)
CREATE POLICY mkt_disp_update ON public.marketplace_disputes FOR UPDATE
  USING (opened_by_auth_uid = auth.uid() OR public.listing_is_mine(listing_id)
         OR (order_id IS NOT NULL AND public.order_is_mine(order_id)) OR is_marketplace_admin())
  WITH CHECK (opened_by_auth_uid = auth.uid() OR public.listing_is_mine(listing_id)
         OR (order_id IS NOT NULL AND public.order_is_mine(order_id)) OR is_marketplace_admin());
DROP POLICY IF EXISTS mkt_disp_insert ON public.marketplace_disputes;
CREATE POLICY mkt_disp_insert ON public.marketplace_disputes FOR INSERT TO authenticated
  WITH CHECK (opened_by_auth_uid = auth.uid() AND opened_by IN (SELECT auth_worker_names()) AND (
    EXISTS (SELECT 1 FROM public.marketplace_inquiries i
             WHERE i.listing_id = marketplace_disputes.listing_id AND public.inquiry_is_from_me(i.id))
    OR (order_id IS NOT NULL AND public.order_is_mine(order_id))));

-- ═══ REVIEWS ══════════════════════════════════════════════════════════════════════════════════════
ALTER TABLE public.marketplace_reviews ALTER COLUMN reviewer_auth_uid SET DEFAULT auth.uid();
CREATE INDEX IF NOT EXISTS idx_marketplace_reviews_reviewer_auth_uid ON public.marketplace_reviews (reviewer_auth_uid);
UPDATE public.marketplace_reviews SET reviewer_auth_uid = public.resolve_marketplace_party(reviewer_name, NULL) WHERE reviewer_auth_uid IS NULL;

DROP POLICY IF EXISTS mkt_reviews_insert ON public.marketplace_reviews;
CREATE POLICY mkt_reviews_insert ON public.marketplace_reviews FOR INSERT TO authenticated
  WITH CHECK (is_marketplace_admin() OR (
    reviewer_auth_uid = auth.uid() AND reviewer_name IN (SELECT auth_worker_names()) AND verified_purchase = false
    AND EXISTS (SELECT 1 FROM public.marketplace_inquiries i
                 WHERE i.listing_id = marketplace_reviews.listing_id AND public.inquiry_is_from_me(i.id))
    AND NOT public.listing_is_mine(listing_id)));
DROP POLICY IF EXISTS mkt_reviews_update ON public.marketplace_reviews;
CREATE POLICY mkt_reviews_update ON public.marketplace_reviews FOR UPDATE
  USING (reviewer_auth_uid = auth.uid() OR is_marketplace_admin())
  WITH CHECK (is_marketplace_admin() OR (reviewer_auth_uid = auth.uid() AND verified_purchase = false));
DROP POLICY IF EXISTS mkt_reviews_delete ON public.marketplace_reviews;
CREATE POLICY mkt_reviews_delete ON public.marketplace_reviews FOR DELETE
  USING (reviewer_auth_uid = auth.uid() OR is_marketplace_admin());

-- ═══ SAVED SEARCHES, WATCHLIST - a person's own lists ═════════════════════════════════════════════
ALTER TABLE public.marketplace_saved_searches ADD COLUMN IF NOT EXISTS auth_uid uuid REFERENCES auth.users(id) ON DELETE CASCADE;
ALTER TABLE public.marketplace_saved_searches ALTER COLUMN auth_uid SET DEFAULT auth.uid();
CREATE INDEX IF NOT EXISTS idx_marketplace_saved_searches_auth_uid ON public.marketplace_saved_searches (auth_uid);
UPDATE public.marketplace_saved_searches SET auth_uid = public.resolve_marketplace_party(worker_name, NULL) WHERE auth_uid IS NULL;
DROP POLICY IF EXISTS mkt_saved_searches_owner_rw ON public.marketplace_saved_searches;
CREATE POLICY mkt_saved_searches_owner_rw ON public.marketplace_saved_searches FOR ALL
  USING (auth_uid = auth.uid()) WITH CHECK (auth_uid = auth.uid() AND worker_name IN (SELECT auth_worker_names()));

ALTER TABLE public.marketplace_watchlist ADD COLUMN IF NOT EXISTS auth_uid uuid REFERENCES auth.users(id) ON DELETE CASCADE;
ALTER TABLE public.marketplace_watchlist ALTER COLUMN auth_uid SET DEFAULT auth.uid();
CREATE INDEX IF NOT EXISTS idx_marketplace_watchlist_auth_uid ON public.marketplace_watchlist (auth_uid);
UPDATE public.marketplace_watchlist SET auth_uid = public.resolve_marketplace_party(worker_name, NULL) WHERE auth_uid IS NULL;
DROP POLICY IF EXISTS mkt_watchlist_owner_rw ON public.marketplace_watchlist;
CREATE POLICY mkt_watchlist_owner_rw ON public.marketplace_watchlist FOR ALL
  USING (auth_uid = auth.uid()) WITH CHECK (auth_uid = auth.uid() AND worker_name IN (SELECT auth_worker_names()));

-- ── one bind trigger for every key: a signed-in person acts as themselves; the key never moves through the API ─────
CREATE OR REPLACE FUNCTION public.bind_marketplace_party()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path TO 'public' AS $fn$
DECLARE
  k text := TG_ARGV[0];   -- the key column
  n text := TG_ARGV[1];   -- the display-name column it is bound from
  newv uuid; oldv uuid; nm text; hv uuid;
BEGIN
  newv := (to_jsonb(NEW) ->> k)::uuid;
  IF TG_OP = 'INSERT' THEN
    IF auth.uid() IS NOT NULL THEN
      newv := auth.uid();
    ELSIF newv IS NULL THEN
      nm := to_jsonb(NEW) ->> n;
      hv := NULLIF(to_jsonb(NEW) ->> 'hive_id', '')::uuid;
      newv := public.resolve_marketplace_party(nm, hv);
    END IF;
  ELSE
    oldv := (to_jsonb(OLD) ->> k)::uuid;
    IF newv IS DISTINCT FROM oldv AND auth.uid() IS NOT NULL AND NOT public.is_marketplace_admin() THEN
      newv := oldv;   -- the column grant refuses this first where the key is hidden; the second fence everywhere
    END IF;
  END IF;
  NEW := jsonb_populate_record(NEW, jsonb_build_object(k, newv));
  RETURN NEW;
END $fn$;
REVOKE ALL ON FUNCTION public.bind_marketplace_party() FROM PUBLIC, anon, authenticated;
DROP TRIGGER IF EXISTS trg_bind_order_buyer ON public.marketplace_orders;
CREATE TRIGGER trg_bind_order_buyer BEFORE INSERT OR UPDATE OF buyer_auth_uid ON public.marketplace_orders
  FOR EACH ROW EXECUTE FUNCTION public.bind_marketplace_party('buyer_auth_uid', 'buyer_name');
DROP TRIGGER IF EXISTS trg_bind_dispute_opener ON public.marketplace_disputes;
CREATE TRIGGER trg_bind_dispute_opener BEFORE INSERT OR UPDATE OF opened_by_auth_uid ON public.marketplace_disputes
  FOR EACH ROW EXECUTE FUNCTION public.bind_marketplace_party('opened_by_auth_uid', 'opened_by');
DROP TRIGGER IF EXISTS trg_bind_review_author ON public.marketplace_reviews;
CREATE TRIGGER trg_bind_review_author BEFORE INSERT OR UPDATE OF reviewer_auth_uid ON public.marketplace_reviews
  FOR EACH ROW EXECUTE FUNCTION public.bind_marketplace_party('reviewer_auth_uid', 'reviewer_name');
DROP TRIGGER IF EXISTS trg_bind_saved_search_owner ON public.marketplace_saved_searches;
CREATE TRIGGER trg_bind_saved_search_owner BEFORE INSERT OR UPDATE OF auth_uid ON public.marketplace_saved_searches
  FOR EACH ROW EXECUTE FUNCTION public.bind_marketplace_party('auth_uid', 'worker_name');
DROP TRIGGER IF EXISTS trg_bind_watchlist_owner ON public.marketplace_watchlist;
CREATE TRIGGER trg_bind_watchlist_owner BEFORE INSERT OR UPDATE OF auth_uid ON public.marketplace_watchlist
  FOR EACH ROW EXECUTE FUNCTION public.bind_marketplace_party('auth_uid', 'worker_name');

-- ── where another person sees the row, the key is checked without being readable: an allowlist of every OTHER column
DO $g$ DECLARE t text; k text; r text; cols text; BEGIN
  FOR t, k IN VALUES ('marketplace_orders', 'buyer_auth_uid'), ('marketplace_disputes', 'opened_by_auth_uid'),
                     ('marketplace_reviews', 'reviewer_auth_uid') LOOP
    SELECT string_agg(quote_ident(column_name), ', ' ORDER BY ordinal_position) INTO cols
      FROM information_schema.columns WHERE table_schema = 'public' AND table_name = t AND column_name <> k;
    FOREACH r IN ARRAY ARRAY['anon', 'authenticated'] LOOP
      IF has_table_privilege(r, 'public.' || t, 'SELECT') THEN
        EXECUTE format('REVOKE SELECT ON public.%I FROM %I', t, r);
        EXECUTE format('GRANT SELECT (%s) ON public.%I TO %I', cols, t, r);
      END IF;
      IF has_table_privilege(r, 'public.' || t, 'UPDATE') THEN
        EXECUTE format('REVOKE UPDATE ON public.%I FROM %I', t, r);
        EXECUTE format('GRANT UPDATE (%s) ON public.%I TO %I', cols, t, r);
      END IF;
    END LOOP;
  END LOOP;
END $g$;

DO $$ DECLARE n1 int; n2 int; n3 int; n4 int; n5 int; BEGIN
  SELECT count(*) INTO n1 FROM public.marketplace_orders WHERE buyer_auth_uid IS NULL;
  SELECT count(*) INTO n2 FROM public.marketplace_disputes WHERE opened_by_auth_uid IS NULL;
  SELECT count(*) INTO n3 FROM public.marketplace_reviews WHERE reviewer_auth_uid IS NULL AND request_id IS NULL;
  SELECT count(*) INTO n4 FROM public.marketplace_saved_searches WHERE auth_uid IS NULL;
  SELECT count(*) INTO n5 FROM public.marketplace_watchlist WHERE auth_uid IS NULL;
  IF n1 + n2 + n3 + n4 + n5 > 0 THEN
    RAISE NOTICE 'unbound (fail closed until an account is bound): % orders, % disputes, % reviews, % saved searches, % watchlist rows', n1, n2, n3, n4, n5;
  END IF;
END $$;

COMMIT;
