-- ============================================================================
-- Marketplace "Certified" BADGE — a verification badge requires something that was verified
-- (Marketplace Deepwalk EXPANSION arc, J11/J16/MK1, 2026-07-24)
-- ----------------------------------------------------------------------------
-- THE DEFECT (measured): 3 sellers rendered a violet "Certified" badge while their certifications
--   column was NULL and cert_verified_at was NULL too. So the badge asserted that an admin had
--   verified trade certifications when there were none to verify and no record of a verification
--   ever happening. A buyer choosing a contractor on the strength of "Certified" was reading nothing.
--   Third instance of the same class as the unbacked rating (20260724000007) and the unearned tier
--   (20260724000008): a trust signal displayed without the evidence that defines it.
--
-- WHY THE WRITE PATH WAS INNOCENT: both moderation surfaces already only offer "Verify certs" when
--   `!cert_verified && certifications` (platform-actions.html, founder-console.html), and
--   marketplace-seller.html resets cert_verified/cert_verified_at whenever the seller edits the list,
--   so a verification cannot survive a change to what it covered. No admin action could have produced
--   this state: it was seeded. The gap was that the BADGE render trusted the flag alone, so the bad
--   state had a way to reach a buyer's eye. This migration fixes the data; the three render sites are
--   fixed alongside it so a future bad state cannot display an empty claim either.
--
-- A NOTE ON THE CHECK CONSTRAINT WE ARE *NOT* ADDING: a table-level CHECK (cert_verified implies
--   certifications IS NOT NULL) would be tempting, but it would make an ordinary seller edit fail at
--   the database instead of invalidating the badge, which is the friendlier and already-implemented
--   behaviour. The invariant is held by the write path plus the validate_marketplace_fraud_signals
--   detector, which reports any recurrence at zero tolerance.
-- ============================================================================

DO $fix$
DECLARE
  v_fixed integer := 0;
BEGIN
  PERFORM set_config('workhive.seller_system_write', 'on', true);  -- announce to the trust guard

  UPDATE public.marketplace_sellers
     SET cert_verified    = false,
         cert_verified_at = NULL,
         updated_at       = now()
   WHERE cert_verified
     AND COALESCE(btrim(certifications), '') = '';

  GET DIAGNOSTICS v_fixed = ROW_COUNT;
  RAISE NOTICE 'marketplace cert badge: cleared % unbacked Certified badge(s) (no certifications on file)', v_fixed;
END
$fix$;

COMMENT ON COLUMN public.marketplace_sellers.cert_verified IS
  'True only when an admin has reviewed a NON-EMPTY certifications list. Reset to false by marketplace-seller.html whenever the seller edits that list, so a verification never outlives what it covered. Backfilled 2026-07-24 after 3 sellers were found showing a Certified badge with no certifications and no verification date. Renders require BOTH this flag and a non-empty list.';
