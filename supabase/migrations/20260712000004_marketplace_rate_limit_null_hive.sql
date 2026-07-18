-- ============================================================================
-- Close the listing rate-limit NULL-hive bypass (Marketplace PDDA, I-axis)
-- ----------------------------------------------------------------------------
-- HOLE (confirmed 2026-07-11): check_listing_rate() early-returns when NEW.hive_id IS NULL,
-- so the 20-listings-per-24h anti-spam limit was bypassed entirely for any NULL-hive listing.
-- The marketplace_listings INSERT policy only checks seller_name (not hive_id), so an authed
-- user could POST with hive_id=null via a direct API call and flood unlimited listings.
--
-- FIX: when hive_id IS NULL (legit solo/no-hive sellers exist), rate-limit by the RLS-enforced
-- seller_name instead of bypassing. Real solo sellers stay capped; the bypass is closed.
-- ============================================================================

CREATE OR REPLACE FUNCTION public.check_listing_rate()
 RETURNS trigger LANGUAGE plpgsql AS $function$
DECLARE daily_count integer;
BEGIN
  IF NEW.hive_id IS NOT NULL THEN
    SELECT COUNT(*) INTO daily_count
      FROM public.marketplace_listings
      WHERE hive_id = NEW.hive_id
        AND created_at > NOW() - INTERVAL '24 hours';
  ELSE
    -- solo/no-hive seller: cap by the (INSERT-RLS-enforced) seller identity so a NULL hive_id
    -- cannot bypass the anti-spam limit.
    SELECT COUNT(*) INTO daily_count
      FROM public.marketplace_listings
      WHERE seller_name = NEW.seller_name
        AND created_at > NOW() - INTERVAL '24 hours';
  END IF;
  IF daily_count >= 20 THEN
    RAISE EXCEPTION 'Daily listing limit of 20 reached';
  END IF;
  RETURN NEW;
END;
$function$;
