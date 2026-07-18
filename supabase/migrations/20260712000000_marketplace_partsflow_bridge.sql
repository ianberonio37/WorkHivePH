-- ============================================================================
-- KEYSTONE — Inventory ↔ Marketplace parts-flow fabric (Marketplace PDDA, X-axis)
-- ----------------------------------------------------------------------------
-- THE DISCONNECT (Ian's keystone insight, X-baseline = 0, LIVE-confirmed 2026-07-11):
--   `inventory_items` (what a plant HAS: qty_on_hand, min_qty, part_number) and
--   `marketplace_listings` (what's FOR SALE) were unlinked islands. marketplace_listings
--   had NO part_number and NO provenance back to the inventory item it came from, so the
--   marketplace could not be a plant's surplus outlet nor a below-reorder sourcing channel.
--
-- THIS MIGRATION (X 0→1, the schema foundation):
--   1. part_number            — the STRONG part-identity join key (inventory & listing
--      taxonomies DIVERGE: inventory=material classes, listings=equipment classes; only
--      bearings/filters/instrumentation categories overlap — so category equality is NOT a
--      reliable join, part_number is). PUBLIC (exposed on the truth view) so buyers can
--      search by part number and a below-reorder item can "Find on Marketplace".
--   2. source_inventory_item_id — provenance FK to the inventory item a "Sell surplus"
--      listing came from. inventory_items.id is TEXT (e.g. 'inv-6a30a255a735') — so this is
--      TEXT, not uuid. ON DELETE SET NULL: deleting the private inventory item must not
--      break the public listing. Kept BASE-TABLE-ONLY (NOT on the public truth view) — it
--      is the seller's own provenance; there is no reason to expose an inventory id to anon
--      cross-hive readers. Isolation: RLS on inventory_items still blocks any cross-hive
--      read of the row itself; the FK only asserts existence (checked as system, no leak).
--
-- FREE + contact-only (no Stripe/payments — removed 2026-06-30). No new tables → no new
-- GRANT block needed (ALTER inherits marketplace_listings' existing grants + RLS).
-- ============================================================================

ALTER TABLE public.marketplace_listings
  ADD COLUMN IF NOT EXISTS part_number              text,
  ADD COLUMN IF NOT EXISTS source_inventory_item_id text
       REFERENCES public.inventory_items(id) ON DELETE SET NULL;

-- Index every column that enters a filter/join (data-engineer skill):
--   part_number → buyer .eq/.ilike search + reorder match; source_item → provenance join + integrity gate.
CREATE INDEX IF NOT EXISTS idx_mkt_listings_part_number ON public.marketplace_listings (part_number);
CREATE INDEX IF NOT EXISTS idx_mkt_listings_source_item ON public.marketplace_listings (source_inventory_item_id);

COMMENT ON COLUMN public.marketplace_listings.part_number IS
  'Part-identity join key to inventory_items.part_number. Public (on truth view) — powers buyer part# search + below-reorder "Find on Marketplace". (Marketplace PDDA X-keystone)';
COMMENT ON COLUMN public.marketplace_listings.source_inventory_item_id IS
  'Provenance: the inventory item a "Sell surplus" listing was created from (TEXT id). Base-table only, NOT on the public truth view. ON DELETE SET NULL. (Marketplace PDDA X-keystone)';

-- Recreate the truth view to project part_number at the end (CREATE OR REPLACE allows
-- appending columns only). source_inventory_item_id is deliberately NOT projected.
CREATE OR REPLACE VIEW public.v_marketplace_listings_truth AS
 SELECT l.id,
    l.hive_id,
    l.seller_name,
    l.seller_contact,
    l.seller_verified,
    l.completed_sales,
    l.rating_avg,
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
    ms.tier            AS seller_tier,
    ms.kyb_verified    AS seller_kyb_verified,
    ms.total_sales     AS seller_total_sales,
    ms.rating_avg      AS seller_rating_avg_live,
    ms.rating_count    AS seller_rating_count,
    ms.response_rate   AS seller_response_rate,
    ms.response_time_h AS seller_response_time_h,
    l.status = 'published'::text AS is_published,
    l.status = 'sold'::text      AS is_sold,
    l.status = 'draft'::text     AS is_draft,
    l.part_number
   FROM marketplace_listings l
     LEFT JOIN marketplace_sellers ms ON ms.worker_name = l.seller_name;
