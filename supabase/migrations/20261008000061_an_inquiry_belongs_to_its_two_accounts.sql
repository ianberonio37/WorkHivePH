-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- ★ AN INQUIRY BELONGS TO ITS TWO ACCOUNTS, NOT TO TWO NAMES (marketplace, 2026-10-08 - the class 20261008000060 opened)
-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- An inquiry is a private message between a buyer and a seller: what they want, how to reach them, the reply. Every
-- marketplace_inquiries policy asked whether buyer_name OR seller_name was among auth_worker_names(), and a name is
-- not an identity (20261008000031: any signed-in person can found a hive and join it under any name). So whoever held a
-- buyer's or a seller's NAME read - and could rewrite - that conversation. buyer_auth_uid existed and was filled on
-- 0 of 6 rows: nothing ever stamped it.
--
--   * the BUYER is the account that sent it: buyer_auth_uid, stamped from auth.uid() on every signed-in insert (the
--     insert policy refuses any other value) and bound for existing rows only when exactly one account holds the name
--     (the buyer's own hive roster first, then exactly one account anywhere) - NULL otherwise, FAIL CLOSED.
--   * the SELLER is the account that owns the listing asked about: listing_is_mine(listing_id), the owner key
--     20261008000060 put on marketplace_listings - one source of truth for "this is my listing", no second copy of it.
--   * the buyer's key is not readable by the seller or anyone else (column grants: a column revoke is inert under a
--     table grant); "is this from me / to me?" is answered on the view by two SECURITY DEFINER helpers.
BEGIN;

-- 1. one resolver for every marketplace party named by a display name (exactly one account, or none)
CREATE OR REPLACE FUNCTION public.resolve_marketplace_party(p_name text, p_hive_id uuid)
RETURNS uuid LANGUAGE sql STABLE SECURITY DEFINER SET search_path TO 'public' AS $fn$
  WITH h AS (
    SELECT DISTINCT auth_uid FROM public.hive_members
     WHERE p_hive_id IS NOT NULL AND hive_id = p_hive_id AND worker_name = p_name AND auth_uid IS NOT NULL
  ), a AS (
    SELECT auth_uid FROM public.hive_members WHERE worker_name = p_name AND auth_uid IS NOT NULL
    UNION SELECT auth_uid FROM public.marketplace_sellers WHERE worker_name = p_name AND auth_uid IS NOT NULL
    UNION SELECT auth_uid FROM public.worker_profiles WHERE display_name = p_name AND auth_uid IS NOT NULL
  )
  SELECT CASE
    WHEN (SELECT count(*) FROM h) = 1 THEN (SELECT auth_uid FROM h)
    WHEN (SELECT count(*) FROM h) = 0 AND (SELECT count(*) FROM a) = 1 THEN (SELECT auth_uid FROM a)
  END;
$fn$;
REVOKE ALL ON FUNCTION public.resolve_marketplace_party(text, uuid) FROM PUBLIC, anon, authenticated;

-- 2. bind the existing inquiries' buyers
UPDATE public.marketplace_inquiries SET buyer_auth_uid = public.resolve_marketplace_party(buyer_name, hive_id)
 WHERE buyer_auth_uid IS NULL;
DO $$ DECLARE n int; BEGIN
  SELECT count(*) INTO n FROM public.marketplace_inquiries WHERE buyer_auth_uid IS NULL;
  IF n > 0 THEN
    RAISE NOTICE 'marketplace_inquiries: % inquiry(ies) name a buyer no single account holds; only the seller and an admin can read them until one is bound (fail closed)', n;
  END IF;
END $$;

-- 3. a signed-in buyer always sends as themselves; the key never moves through the API
ALTER TABLE public.marketplace_inquiries ALTER COLUMN buyer_auth_uid SET DEFAULT auth.uid();
CREATE INDEX IF NOT EXISTS idx_marketplace_inquiries_buyer_auth_uid ON public.marketplace_inquiries (buyer_auth_uid);
CREATE OR REPLACE FUNCTION public.bind_inquiry_buyer()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path TO 'public' AS $fn$
BEGIN
  IF TG_OP = 'INSERT' THEN
    IF auth.uid() IS NOT NULL THEN
      NEW.buyer_auth_uid := auth.uid();
    ELSIF NEW.buyer_auth_uid IS NULL THEN
      NEW.buyer_auth_uid := public.resolve_marketplace_party(NEW.buyer_name, NEW.hive_id);
    END IF;
  ELSIF NEW.buyer_auth_uid IS DISTINCT FROM OLD.buyer_auth_uid AND auth.uid() IS NOT NULL AND NOT public.is_marketplace_admin() THEN
    NEW.buyer_auth_uid := OLD.buyer_auth_uid;   -- the column grant refuses this first; the second fence
  END IF;
  RETURN NEW;
END $fn$;
REVOKE ALL ON FUNCTION public.bind_inquiry_buyer() FROM PUBLIC, anon, authenticated;
DROP TRIGGER IF EXISTS trg_bind_inquiry_buyer ON public.marketplace_inquiries;
CREATE TRIGGER trg_bind_inquiry_buyer BEFORE INSERT OR UPDATE OF buyer_auth_uid ON public.marketplace_inquiries
  FOR EACH ROW EXECUTE FUNCTION public.bind_inquiry_buyer();

-- 4. the two parties, by account
DROP POLICY IF EXISTS mkt_inq_read ON public.marketplace_inquiries;
CREATE POLICY mkt_inq_read ON public.marketplace_inquiries FOR SELECT
  USING (buyer_auth_uid = auth.uid() OR public.listing_is_mine(listing_id) OR is_marketplace_admin());
DROP POLICY IF EXISTS mkt_inq_insert ON public.marketplace_inquiries;
CREATE POLICY mkt_inq_insert ON public.marketplace_inquiries FOR INSERT
  WITH CHECK (buyer_auth_uid = auth.uid() AND buyer_name IN (SELECT auth_worker_names()));
DROP POLICY IF EXISTS mkt_inq_update ON public.marketplace_inquiries;
CREATE POLICY mkt_inq_update ON public.marketplace_inquiries FOR UPDATE
  USING (buyer_auth_uid = auth.uid() OR public.listing_is_mine(listing_id) OR is_marketplace_admin())
  WITH CHECK (buyer_auth_uid = auth.uid() OR public.listing_is_mine(listing_id) OR is_marketplace_admin());

-- 5. the buyer's key is no one else's to read or write: an allowlist of every OTHER column
REVOKE SELECT, UPDATE ON public.marketplace_inquiries FROM authenticated;
DO $g$ DECLARE cols text; BEGIN
  SELECT string_agg(quote_ident(column_name), ', ' ORDER BY ordinal_position) INTO cols
    FROM information_schema.columns
   WHERE table_schema = 'public' AND table_name = 'marketplace_inquiries' AND column_name <> 'buyer_auth_uid';
  EXECUTE 'GRANT SELECT (' || cols || ') ON public.marketplace_inquiries TO authenticated';
  EXECUTE 'GRANT UPDATE (' || cols || ') ON public.marketplace_inquiries TO authenticated';
END $g$;

-- 6. "from me / to me" without the key
CREATE OR REPLACE FUNCTION public.inquiry_is_from_me(p_inquiry uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path TO 'public' AS $fn$
  SELECT auth.uid() IS NOT NULL AND EXISTS (
    SELECT 1 FROM public.marketplace_inquiries WHERE id = p_inquiry AND buyer_auth_uid = auth.uid()
  );
$fn$;
REVOKE ALL ON FUNCTION public.inquiry_is_from_me(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.inquiry_is_from_me(uuid) TO anon, authenticated;   -- false for a stranger (see listing_is_mine)

CREATE OR REPLACE VIEW public.v_marketplace_inquiries_truth WITH (security_invoker = true) AS
SELECT i.id,
    i.listing_id,
    i.hive_id,
    i.buyer_name,
    i.buyer_contact,
    i.seller_name,
    i.message,
    i.reply_text,
    i.replied_at,
    i.status,
    i.created_at,
    l.title AS listing_title,
    l.section AS listing_section,
    l.price AS listing_price,
    l.status AS listing_status,
    i.status = 'pending'::text AS is_pending,
    i.status = 'replied'::text AS is_replied,
    i.status = 'closed'::text AS is_closed,
    public.listing_is_mine(i.listing_id) AS to_me,
    public.inquiry_is_from_me(i.id) AS from_me
   FROM marketplace_inquiries i
     LEFT JOIN marketplace_listings l ON l.id = i.listing_id;

COMMIT;
