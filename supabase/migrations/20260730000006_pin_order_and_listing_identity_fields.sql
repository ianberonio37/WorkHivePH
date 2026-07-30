-- 20260730000006_pin_order_and_listing_identity_fields.sql
--
-- TWO MORE LIVE EXPLOITS of the class mig 20260730000005 opened. Both were probed end to end in rolled-back
-- transactions BEFORE this migration was written, and both were ALLOWED:
--
--   ORDERS    update marketplace_orders set seller_name = '<me>', status = 'released' where id = <a
--             stranger's order>;   -> admin_total_sales=1, the real seller left at 0. update_seller_tier
--             bumps on NEW.seller_name; the party gate reads OLD. Sales and tier are the trust signals.
--
--   LISTINGS  update marketplace_listings set seller_name = '<me>', status = 'published' where id = <a
--             stranger's listing>;  -> final_seller = the admin, final_status = 'published'. A listing taken
--             over and published as the admin's own.
--
-- ONE ROOT: a guard's decision and the action it authorises read DIFFERENT VERSIONS of the same row. The
-- party check reads OLD so that party-ness cannot be edited away mid-statement; the consequence reads NEW so
-- the effect lands where the row now points. Each is right on its own. Together they let an admin who is a
-- party to NOTHING pass the gate on the old values and collect on the new ones.
--
-- `guard_service_request_status` was already immune - it already refuses changes to matched_provider_id and
-- client_auth_uid. That rule is what these two guards were missing, so this generalises it rather than
-- inventing anything.
--
-- Verified against the shipped surface first: orders are updated only as {status, updated_at}
-- (marketplace-admin.html:948) and listing moderation only patches status/moderation_* fields
-- (marketplace-admin.html:714) - a seller editing their own listing changes title/price/description and never
-- seller_name (marketplace-seller.html:918). So only identity/money fields are pinned and no working flow
-- changes.
--
-- Both definitions were EXTRACTED with pg_get_functiondef and one anchored block inserted each, the build
-- script asserting the anchor appears exactly once per function.

CREATE OR REPLACE FUNCTION public.guard_marketplace_order_status()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_is_party boolean;
BEGIN
  -- Buyer and seller are free-text worker names on this table, so party-ness is resolved the way the
  -- app resolves identity everywhere else: auth_worker_names() maps auth.uid() through
  -- hive_members / marketplace_sellers ([[feedback_free_text_identity_is_a_claim]] — the NAME is a
  -- claim, the mapping is the proof).
  v_is_party := (coalesce(OLD.buyer_name,  NEW.buyer_name)  IN (SELECT public.auth_worker_names()))
             OR (coalesce(OLD.seller_name, NEW.seller_name) IN (SELECT public.auth_worker_names()));

  -- service-role / backend writes (no JWT: seeders, escrow edge fns) are already vetted — allow.
  IF auth.uid() IS NULL THEN RETURN NEW; END IF;
  -- marketplace admins may drive any transition (dispute resolution, manual release/refund) — on an
  -- order they are NOT a party to. On their own order they are a buyer or a seller like anyone else,
  -- because 'released' fires the total_sales / tier bump and 'refunded' reverses a payment.
  -- ── IDENTITY AND MONEY FIELDS ARE IMMUTABLE (mig 20260730000006) ──────────────────────────────────
  -- update_seller_tier bumps marketplace_sellers on NEW.seller_name when an order reaches 'released', while the party gate above reads coalesce(OLD.seller_name, NEW.seller_name). One statement made them disagree and an admin claimed a stranger's SALE: probed live, ALLOWED, admin_total_sales=1 and the real seller left at 0. total_sales and tier ARE the marketplace's trust signals, so that is sales forgery.
  --
  -- Third and second instances of one class, found after mig 20260730000005 fixed the first on top-ups: a
  -- guard's decision and the action it authorises must agree on WHICH VERSION of the row they describe. The
  -- check reads OLD (correct - you must not escape party-ness by editing the row in flight) and the
  -- consequence reads NEW (also correct - the effect lands where the row now says). Both defensible, together
  -- a hole. `guard_service_request_status` was already immune because it already pins matched_provider_id and
  -- client_auth_uid; these two had no such rule.
  --
  -- The no-JWT backend path returned above, so seeders are unaffected. The announced system-write GUC is
  -- exempted explicitly because its own check sits AFTER the admin bypass below.
  IF TG_OP = 'UPDATE'
     AND coalesce(current_setting('workhive.order_system_write', true), '') <> 'on'
     AND (NEW.buyer_name IS DISTINCT FROM OLD.buyer_name
       OR NEW.seller_name IS DISTINCT FROM OLD.seller_name
       OR NEW.price IS DISTINCT FROM OLD.price
       OR NEW.currency IS DISTINCT FROM OLD.currency
       OR NEW.hive_id IS DISTINCT FROM OLD.hive_id) THEN
    RAISE EXCEPTION 'Not allowed: an order''s parties and price are immutable - releasing an order settles it, it does not re-write who traded or for how much'
      USING ERRCODE = 'check_violation';
  END IF;

  IF public.is_marketplace_admin() AND NOT v_is_party THEN RETURN NEW; END IF;
  -- a future release/refund RPC or edge fn announces itself for the duration of its transaction.
  IF current_setting('workhive.order_system_write', true) = 'on' THEN RETURN NEW; END IF;

  -- ---- from here: a raw authenticated (buyer/seller) client ----
  -- A client may NOT create an order already in a privileged/terminal state.
  IF TG_OP = 'INSERT' AND NEW.status <> 'pending_payment' THEN
    RAISE EXCEPTION 'Not allowed: a new order must start as pending_payment (status % is set by the escrow system)', NEW.status
      USING ERRCODE = 'check_violation';
  END IF;

  -- The trust-bearing terminal states are backend-only. 'released' fires the total_sales / tier bump;
  -- 'refunded' reverses a payment — neither may be self-assigned by a buyer or seller.
  IF TG_OP = 'UPDATE' AND NEW.status IN ('released', 'refunded') AND NEW.status IS DISTINCT FROM OLD.status THEN
    RAISE EXCEPTION 'Not allowed: order status % is set by the WorkHive escrow system, not by a buyer or seller', NEW.status
      USING ERRCODE = 'check_violation';
  END IF;

  RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION public.guard_marketplace_listing_status()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_is_party boolean;
BEGIN
  v_is_party := coalesce(OLD.seller_name, NEW.seller_name) IN (SELECT public.auth_worker_names());

  -- service-role / backend writes (no JWT: seeders, edge fns, any system trigger) are
  -- already vetted -- allow. (Parity with guard_marketplace_seller_trust_columns.)
  IF auth.uid() IS NULL THEN RETURN NEW; END IF;
  -- platform admins publish / moderate -- OTHER PEOPLE's listings. Reviewing your own is not review,
  -- and 'a listing goes live only after WorkHive review' is exactly the sentence the old bypass broke.
  -- ── IDENTITY AND MONEY FIELDS ARE IMMUTABLE (mig 20260730000006) ──────────────────────────────────
  -- The party gate reads coalesce(OLD.seller_name, NEW.seller_name), so an admin who is a party to nothing takes the bypass - and the same statement can rewrite seller_name. Probed live: ALLOWED, final_seller became the admin and final_status 'published'. A stranger's listing, taken over and published as the admin's own. Only the identity fields are pinned: a seller legitimately edits title/price/description on their own listing (marketplace-seller.html:918).
  --
  -- Third and second instances of one class, found after mig 20260730000005 fixed the first on top-ups: a
  -- guard's decision and the action it authorises must agree on WHICH VERSION of the row they describe. The
  -- check reads OLD (correct - you must not escape party-ness by editing the row in flight) and the
  -- consequence reads NEW (also correct - the effect lands where the row now says). Both defensible, together
  -- a hole. `guard_service_request_status` was already immune because it already pins matched_provider_id and
  -- client_auth_uid; these two had no such rule.
  --
  -- The no-JWT backend path returned above, so seeders are unaffected. The announced system-write GUC is
  -- exempted explicitly because its own check sits AFTER the admin bypass below.
  IF TG_OP = 'UPDATE'
     AND coalesce(current_setting('workhive.listing_system_write', true), '') <> 'on'
     AND (NEW.seller_name IS DISTINCT FROM OLD.seller_name
       OR NEW.hive_id IS DISTINCT FROM OLD.hive_id) THEN
    RAISE EXCEPTION 'Not allowed: a listing''s owner and hive are immutable - review publishes a listing, it does not transfer it'
      USING ERRCODE = 'check_violation';
  END IF;

  IF public.is_marketplace_admin() AND NOT v_is_party THEN RETURN NEW; END IF;
  -- a system write announced itself this transaction (future auto-approve path) -- allow.
  IF current_setting('workhive.listing_system_write', true) = 'on' THEN RETURN NEW; END IF;

  -- Block a NON-ADMIN from transitioning a listing INTO 'published' (self-approval).
  -- A seller MAY keep editing (status stays 'draft'), withdraw ('removed'), or mark
  -- 'sold' on their OWN listing (RLS already scopes to owner) -- but going LIVE is an
  -- admin/review-gated transition, never self-served. On INSERT there is no OLD row,
  -- so any non-admin insert that arrives already-published is blocked outright.
  IF NEW.status = 'published'
     AND (TG_OP = 'INSERT' OR OLD.status IS DISTINCT FROM 'published') THEN
    RAISE EXCEPTION 'Not allowed: a listing goes live only after WorkHive review, not by self-publishing'
      USING ERRCODE = '42501';
  END IF;

  RETURN NEW;
END;
$function$;
