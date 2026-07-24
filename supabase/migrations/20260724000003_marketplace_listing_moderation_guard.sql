-- ============================================================================
-- Marketplace MODERATION INTEGRITY — close the listing SELF-PUBLISH hole
-- (Marketplace PDDA I-axis; found + live-exploited via deepwalk 2026-07-24)
-- ----------------------------------------------------------------------------
-- HOLE — the marketplace_listings UPDATE policy lets a seller edit their OWN
--   listing (correct, for title / price / description), but has NO column-level
--   restriction, so a non-admin seller could PATCH status='published' directly and
--   SELF-PUBLISH an unmoderated listing straight to the live marketplace — bypassing
--   the admin review the UI promises ("submitted for review -> goes live once
--   approved"). Same shape as the seller-trust HOLE #2 in 20260712000001: RLS
--   WITH CHECK cannot express "may edit the row but not THIS column", so the fix is
--   a SECURITY DEFINER BEFORE trigger, not a policy.
--   VERIFIED live 2026-07-24: non-admin worker inserted a draft then set
--   status='published'; v_marketplace_listings_truth then returned it as published
--   (i.e. live + visible to every buyer). Trust columns were already safe (the
--   truth view derives them from canonical, 20260713000009) — only `status` was open.
-- ============================================================================

CREATE OR REPLACE FUNCTION public.guard_marketplace_listing_status()
 RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $function$
BEGIN
  -- service-role / backend writes (no JWT: seeders, edge fns, any system trigger) are
  -- already vetted -- allow. (Parity with guard_marketplace_seller_trust_columns.)
  IF auth.uid() IS NULL THEN RETURN NEW; END IF;
  -- platform admins publish / moderate.
  IF public.is_marketplace_admin() THEN RETURN NEW; END IF;
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

DROP TRIGGER IF EXISTS trg_guard_listing_status ON public.marketplace_listings;
CREATE TRIGGER trg_guard_listing_status
  BEFORE INSERT OR UPDATE ON public.marketplace_listings
  FOR EACH ROW EXECUTE FUNCTION public.guard_marketplace_listing_status();

COMMENT ON FUNCTION public.guard_marketplace_listing_status() IS
  'Moderation backstop: a non-admin seller may edit / withdraw / mark-sold their OWN listing but may NOT transition it INTO status=published (self-publish). Only a platform admin (is_marketplace_admin) or a service-role/system write may publish. Closes the deepwalk-2026-07-24 self-publish hole; parity with guard_marketplace_seller_trust_columns (Marketplace PDDA I-axis).';
