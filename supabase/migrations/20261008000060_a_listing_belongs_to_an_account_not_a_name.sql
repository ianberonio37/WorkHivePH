-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- ★ A LISTING BELONGS TO AN ACCOUNT, NOT A NAME (marketplace, 2026-10-08 - decided in UFAI §LM.11)
-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- Every marketplace_listings policy asked whether seller_name was among auth_worker_names() - the names the caller
-- holds. A name is not an identity on this platform: names are not unique across hives, and (20261008000031) any
-- signed-in person can found a hive and join it under ANY name. Proven at the database's own role level, as
-- `authenticated` with the person's jwt claims, inside a transaction that was ROLLED BACK: a second account whose
-- only tie to Bryan Garcia was a hive membership under the name "Bryan Garcia" updated Bryan's listing (1 row), and
-- through v_marketplace_listings_public - a definer view with the same name test - could read Bryan's drafts.
--
-- THE OWNER KEY IS THE ACCOUNT:
--   * marketplace_listings.auth_uid, bound once from the name only when exactly ONE account holds it - the listing's
--     own hive roster first (joining a SPECIFIC hive needs its invite), else, for a hive-less listing, exactly one
--     seller row - and NULL otherwise. A NULL owner is FAIL CLOSED: no one but a marketplace admin may edit it until
--     an account is bound (the same rule 20261008000031 applies to admin grants). The NOTICE below counts them.
--   * a signed-in person always lists AS THEMSELVES: the bind trigger stamps auth.uid() on insert, whatever was sent,
--     and the insert policy refuses any other value; a service/seed insert is resolved from the name.
--   * read (drafts), update and delete are keyed on auth_uid = auth.uid(); seller_name stays the DISPLAY name.
--   * the key is checked by RLS without being readable by other members: `authenticated` loses its table-wide
--     SELECT/UPDATE (a column revoke is inert under a table grant) and is re-granted every column EXCEPT auth_uid -
--     an allowlist, so a column added later is not auto-handed out. Nobody can rewrite the key through the API.
--   * "is this mine?" is answered without exposing the key: is_mine on both listing views (the truth view asks a
--     SECURITY DEFINER helper, because a security_invoker view naming auth_uid would need the very grant revoked).
-- Measured on the local seed before writing this: 28 of 28 listings resolve to exactly one account.
BEGIN;

-- 1. the owner key
ALTER TABLE public.marketplace_listings ADD COLUMN IF NOT EXISTS auth_uid uuid REFERENCES auth.users(id) ON DELETE SET NULL;
ALTER TABLE public.marketplace_listings ALTER COLUMN auth_uid SET DEFAULT auth.uid();
CREATE INDEX IF NOT EXISTS idx_marketplace_listings_auth_uid ON public.marketplace_listings (auth_uid);

-- 2. exactly one account, or none
CREATE OR REPLACE FUNCTION public.resolve_listing_owner(p_seller_name text, p_hive_id uuid)
RETURNS uuid LANGUAGE sql STABLE SECURITY DEFINER SET search_path TO 'public' AS $fn$
  WITH h AS (
    SELECT DISTINCT auth_uid FROM public.hive_members
     WHERE p_hive_id IS NOT NULL AND hive_id = p_hive_id AND worker_name = p_seller_name AND auth_uid IS NOT NULL
  ), s AS (
    SELECT DISTINCT auth_uid FROM public.marketplace_sellers
     WHERE worker_name = p_seller_name AND auth_uid IS NOT NULL
  )
  SELECT CASE
    WHEN p_hive_id IS NOT NULL THEN CASE WHEN (SELECT count(*) FROM h) = 1 THEN (SELECT auth_uid FROM h) END
    WHEN (SELECT count(*) FROM s) = 1 THEN (SELECT auth_uid FROM s)
  END;
$fn$;
REVOKE ALL ON FUNCTION public.resolve_listing_owner(text, uuid) FROM PUBLIC, anon, authenticated;

-- 3. bind every existing listing
UPDATE public.marketplace_listings SET auth_uid = public.resolve_listing_owner(seller_name, hive_id) WHERE auth_uid IS NULL;
DO $$ DECLARE n int; BEGIN
  SELECT count(*) INTO n FROM public.marketplace_listings WHERE auth_uid IS NULL;
  IF n > 0 THEN
    RAISE NOTICE 'marketplace_listings: % listing(s) resolve to no single account and are editable only by a marketplace admin until one is bound (fail closed)', n;
  END IF;
END $$;

-- 4. a signed-in person lists as themselves; the key never moves through the API
CREATE OR REPLACE FUNCTION public.bind_listing_owner()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path TO 'public' AS $fn$
BEGIN
  IF TG_OP = 'INSERT' THEN
    IF auth.uid() IS NOT NULL THEN
      NEW.auth_uid := auth.uid();
    ELSIF NEW.auth_uid IS NULL THEN
      NEW.auth_uid := public.resolve_listing_owner(NEW.seller_name, NEW.hive_id);
    END IF;
  ELSIF NEW.auth_uid IS DISTINCT FROM OLD.auth_uid AND auth.uid() IS NOT NULL AND NOT public.is_marketplace_admin() THEN
    NEW.auth_uid := OLD.auth_uid;   -- the column grant refuses this first; the second fence
  END IF;
  RETURN NEW;
END $fn$;
REVOKE ALL ON FUNCTION public.bind_listing_owner() FROM PUBLIC, anon, authenticated;
DROP TRIGGER IF EXISTS trg_bind_listing_owner ON public.marketplace_listings;
CREATE TRIGGER trg_bind_listing_owner BEFORE INSERT OR UPDATE OF auth_uid ON public.marketplace_listings
  FOR EACH ROW EXECUTE FUNCTION public.bind_listing_owner();

-- 5. ownership on the account (a NULL owner matches no one: fail closed)
DROP POLICY IF EXISTS mkt_listings_read ON public.marketplace_listings;
CREATE POLICY mkt_listings_read ON public.marketplace_listings FOR SELECT
  USING (status = 'published' OR auth_uid = auth.uid() OR is_marketplace_admin());
DROP POLICY IF EXISTS mkt_listings_insert ON public.marketplace_listings;
CREATE POLICY mkt_listings_insert ON public.marketplace_listings FOR INSERT
  WITH CHECK (auth_uid = auth.uid() AND seller_name IN (SELECT auth_worker_names()));
DROP POLICY IF EXISTS mkt_listings_update ON public.marketplace_listings;
CREATE POLICY mkt_listings_update ON public.marketplace_listings FOR UPDATE
  USING (auth_uid = auth.uid() OR is_marketplace_admin())
  WITH CHECK (auth_uid = auth.uid() OR is_marketplace_admin());
DROP POLICY IF EXISTS mkt_listings_delete ON public.marketplace_listings;
CREATE POLICY mkt_listings_delete ON public.marketplace_listings FOR DELETE
  USING (auth_uid = auth.uid() OR is_marketplace_admin());

-- 6. the key is not readable or writable by members: an allowlist of every OTHER column
REVOKE SELECT, UPDATE ON public.marketplace_listings FROM authenticated;
DO $g$ DECLARE cols text; BEGIN
  SELECT string_agg(quote_ident(column_name), ', ' ORDER BY ordinal_position) INTO cols
    FROM information_schema.columns
   WHERE table_schema = 'public' AND table_name = 'marketplace_listings' AND column_name <> 'auth_uid';
  EXECUTE 'GRANT SELECT (' || cols || ') ON public.marketplace_listings TO authenticated';
  -- UPDATE keeps every column the table grant gave except the key (a probe's no-op `SET id = id` must still reach RLS,
  -- which is what refuses a foreign row; refusing it at the grant layer would hide whether RLS still holds)
  SELECT string_agg(quote_ident(column_name), ', ' ORDER BY ordinal_position) INTO cols
    FROM information_schema.columns
   WHERE table_schema = 'public' AND table_name = 'marketplace_listings' AND column_name <> 'auth_uid';
  EXECUTE 'GRANT UPDATE (' || cols || ') ON public.marketplace_listings TO authenticated';
END $g$;

-- 7. "is this mine?" without the key
CREATE OR REPLACE FUNCTION public.listing_is_mine(p_listing uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path TO 'public' AS $fn$
  SELECT auth.uid() IS NOT NULL AND EXISTS (
    SELECT 1 FROM public.marketplace_listings WHERE id = p_listing AND auth_uid = auth.uid()
  );
$fn$;
REVOKE ALL ON FUNCTION public.listing_is_mine(uuid) FROM PUBLIC;
-- anon too: a policy predicate runs with the CALLER's privileges, and inquiry/order/dispute policies ask this. A
-- stranger must get "not mine" (false - auth.uid() is null), not a permission error that fails their whole read
-- (measured: a psql step-down to anon segfaulted the local server on the refused call; over PostgREST it is a 42501).
GRANT EXECUTE ON FUNCTION public.listing_is_mine(uuid) TO anon, authenticated;

CREATE OR REPLACE VIEW public.v_marketplace_listings_truth WITH (security_invoker = on) AS
SELECT l.id,
    l.hive_id,
    l.seller_name,
    l.seller_contact,
    COALESCE(ms.kyb_verified, false) OR COALESCE(ms.cert_verified, false) AS seller_verified,
    COALESCE(ms.total_sales, 0) AS completed_sales,
    ms.rating_avg,
    l.section,
    l.category,
    l.title,
    l.description,
    l.price,
    l.condition,
    l.location,
    l.image_url,
    l.status,
    l.view_count,
    l.created_at,
    l.updated_at,
    ms.tier AS seller_tier,
    ms.kyb_verified AS seller_kyb_verified,
    ms.total_sales AS seller_total_sales,
    ms.rating_avg AS seller_rating_avg_live,
    ms.rating_count AS seller_rating_count,
    ms.response_rate AS seller_response_rate,
    ms.response_time_h AS seller_response_time_h,
    l.status = 'published'::text AS is_published,
    l.status = 'sold'::text AS is_sold,
    l.status = 'draft'::text AS is_draft,
    l.part_number,
    l.moderation_reason,
    l.moderated_at,
    l.moderated_by,
    public.listing_is_mine(l.id) AS is_mine
   FROM marketplace_listings l
     LEFT JOIN marketplace_sellers ms ON ms.worker_name = l.seller_name;

-- the definer view's own filter asked the name too: a holder of the name read the owner's drafts through it
CREATE OR REPLACE VIEW public.v_marketplace_listings_public AS
SELECT l.id,
    l.hive_id,
    l.seller_name,
    COALESCE(ms.kyb_verified, false) OR COALESCE(ms.cert_verified, false) AS seller_verified,
    COALESCE(ms.total_sales, 0) AS completed_sales,
    ms.rating_avg,
    l.section,
    l.category,
    l.title,
    l.description,
    l.price,
    l.condition,
    l.location,
    l.image_url,
    l.status,
    l.view_count,
    l.created_at,
    l.updated_at,
    ms.tier AS seller_tier,
    ms.kyb_verified AS seller_kyb_verified,
    ms.total_sales AS seller_total_sales,
    ms.rating_avg AS seller_rating_avg_live,
    ms.rating_count AS seller_rating_count,
    ms.response_rate AS seller_response_rate,
    ms.response_time_h AS seller_response_time_h,
    l.status = 'published'::text AS is_published,
    l.status = 'sold'::text AS is_sold,
    l.status = 'draft'::text AS is_draft,
    l.part_number,
    COALESCE(l.auth_uid = auth.uid(), false) AS is_mine
   FROM marketplace_listings l
     LEFT JOIN marketplace_sellers ms ON ms.worker_name = l.seller_name
  WHERE l.status = 'published'::text OR l.auth_uid = auth.uid();

COMMIT;
