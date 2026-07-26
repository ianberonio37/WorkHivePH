-- ============================================================================
-- Marketplace MODERATION FEEDBACK — tell the seller WHY a listing was rejected
-- (Marketplace Deepwalk EXPANSION arc, J10/MK2 "moderation-state honesty", 2026-07-24)
-- ----------------------------------------------------------------------------
-- THE DEFECT: the post flow promises "submitted for review -> goes live once approved", and the
--   admin console's Reject action sets status='removed'. But NOTHING captured a reason: the only
--   record was a hive_audit_log row the SELLER cannot read. On the seller dashboard the listing
--   simply became a bare red "Removed" chip. So the moderation pipeline had a one-way mirror --
--   the platform tells you it is reviewing, then silently kills the listing with no feedback and
--   no path to fix it. That is the MK2 half the 2026-07-24 walk left open (the self-publish half
--   was closed by 20260724000003).
--
-- THE FIX: three additive columns + expose them on the truth view.
--   Privacy is already correct by construction: `mkt_listings_read` is
--   (status='published' OR seller_name IN auth_worker_names() OR is_marketplace_admin()), so a
--   'removed' row -- and therefore its moderation_reason -- is readable ONLY by its own seller or
--   a platform admin. No buyer/anon exposure.
-- ============================================================================

ALTER TABLE public.marketplace_listings
  ADD COLUMN IF NOT EXISTS moderation_reason text,
  ADD COLUMN IF NOT EXISTS moderated_at      timestamptz,
  ADD COLUMN IF NOT EXISTS moderated_by      text;

COMMENT ON COLUMN public.marketplace_listings.moderation_reason IS
  'Why a platform admin rejected/unpublished this listing, shown back to the SELLER on their dashboard so the moderation pipeline is not a one-way mirror. Readable only by the owning seller or an admin (mkt_listings_read). MK2 moderation-state honesty, 2026-07-24.';

-- Expose the moderation feedback on the canonical read path. CREATE OR REPLACE VIEW permits
-- APPENDING columns (existing column list + order preserved), so every existing consumer is
-- unaffected. security_invoker=on is restated explicitly so the base-table RLS keeps applying.
CREATE OR REPLACE VIEW public.v_marketplace_listings_truth
WITH (security_invoker = on) AS
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
     -- appended (MK2):
     l.moderation_reason,
     l.moderated_at,
     l.moderated_by
    FROM marketplace_listings l
      LEFT JOIN marketplace_sellers ms ON ms.worker_name = l.seller_name;
