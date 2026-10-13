-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- v_marketplace_sellers_truth exposes the identity its base table binds (BRP class B, the last one)
-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- Third and final class-B view in the wave that began with Ian's 2026-10-04 report. The pattern: a truth
-- VIEW exposes `worker_name` and NOT the `auth_uid` its base table carries, so no consumer can ask "is this
-- row mine?" correctly - the question is not merely answered wrongly, it is inexpressible.
-- 20261004000001 did v_logbook_truth and v_inventory_items_truth; this does the sellers view, which
-- marketplace-seller.html reads to decide whether the signed-in person IS the seller.
--
-- `marketplace_sellers` carries auth_uid (18 columns); the view exposes 23 and not that one. Appended last,
-- which is what CREATE OR REPLACE VIEW permits: every existing column keeps its name, type and position, so
-- no current reader is affected.
--
-- ★security_invoker IS RESTATED. CREATE OR REPLACE VIEW resets reloptions, and losing it would turn a
-- per-caller view into one that reads as its OWNER and bypasses RLS - the mistake that once opened `anon`
-- to 437 rows here. The view carries `security_invoker=on` today; it is re-declared below and the
-- verification block FAILS the migration if it comes back without it.
--
-- ON EXPOSURE: unlike the logbook and inventory views, `marketplace_sellers` grants anon and authenticated
-- INSERT/UPDATE/DELETE but NOT SELECT - a write-without-read grant shape that is wrong on its own terms and
-- is recorded as its own finding. Because those roles cannot select the base table at all, a
-- security_invoker view over it returns nothing to them regardless of which columns it lists, so adding
-- auth_uid here widens nothing for them. The grant shape itself is left alone: fixing it is a separate
-- change with a separate blast radius, and quietly adjusting privileges inside a column migration is how a
-- permission change escapes review.

BEGIN;

CREATE OR REPLACE VIEW public.v_marketplace_sellers_truth
WITH (security_invoker = on) AS
 SELECT s.id,
    s.worker_name,
    s.hive_id,
    s.tier,
    s.kyb_verified,
    s.kyb_verified_at,
    s.cert_verified,
    s.cert_verified_at,
    s.total_sales,
    s.rating_avg,
    s.rating_count,
    s.response_rate,
    s.response_time_h,
    s.messenger_username,
    s.certifications,
    s.created_at,
    s.updated_at,
    COALESCE(active_listings.n, 0::bigint) AS active_listings_count,
    COALESCE(total_orders.n, 0::bigint) AS total_orders_count,
    active_listings.last_at AS last_listed_at,
    total_orders.last_at AS last_order_at,
    s.kyb_verified AND s.cert_verified AS is_verified_public,
    s.messenger_username IS NOT NULL AND s.certifications IS NOT NULL AS profile_complete,
    s.auth_uid                      -- APPENDED (BRP-B, 2026-10-04): the identity the row is bound to
   FROM marketplace_sellers s
     LEFT JOIN LATERAL ( SELECT count(*) AS n,
            max(l.created_at) AS last_at
           FROM marketplace_listings l
          WHERE l.seller_name = s.worker_name AND l.status = 'published'::text) active_listings ON true
     LEFT JOIN LATERAL ( SELECT count(*) AS n,
            max(o.created_at) AS last_at
           FROM marketplace_orders o
          WHERE o.seller_name = s.worker_name) total_orders ON true;

DO $$
DECLARE opts text[]; n_cols int;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                  WHERE table_schema='public' AND table_name='v_marketplace_sellers_truth'
                    AND column_name='auth_uid') THEN
    RAISE EXCEPTION 'v_marketplace_sellers_truth did not gain auth_uid';
  END IF;

  SELECT c.reloptions INTO opts FROM pg_class c JOIN pg_namespace ns ON ns.oid = c.relnamespace
   WHERE ns.nspname='public' AND c.relname='v_marketplace_sellers_truth';
  IF opts IS NULL OR NOT ('security_invoker=on' = ANY(opts) OR 'security_invoker=true' = ANY(opts)) THEN
    RAISE EXCEPTION 'v_marketplace_sellers_truth lost security_invoker (reloptions=%) - an owner-rights '
                    'view here would bypass RLS for every caller', opts;
  END IF;

  SELECT count(*) INTO n_cols FROM information_schema.columns
   WHERE table_schema='public' AND table_name='v_marketplace_sellers_truth';
  IF n_cols <> 24 THEN
    RAISE EXCEPTION 'v_marketplace_sellers_truth has % columns, expected 24 (23 + auth_uid)', n_cols;
  END IF;

  RAISE NOTICE 'BRP-B: v_marketplace_sellers_truth exposes auth_uid; security_invoker intact; 24 columns';
END $$;

COMMIT;
