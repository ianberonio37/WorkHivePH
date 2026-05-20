-- ─── v_marketplace_listings_truth canonical view ────────────────────────────
-- TIER C gap-table promotion: marketplace_listings had 10 raw reads across
-- 7 consumers (asset-hub, marketplace, marketplace-admin, marketplace-seller,
-- marketplace-seller-profile, marketplace-checkout, project-manager) at
-- baseline. validate_user_facing_kpi_canonical.py L0 ratchet flagged it as
-- the #1 gap-table candidate on 2026-05-20.
--
-- The view supersets every reading site's column set AND bridges to
-- marketplace_sellers (already canonical via v_marketplace_sellers_truth) for
-- richer seller signals: tier, kyb_verified, total_sales, rating_avg,
-- rating_count, response_rate. Consumers that previously needed a second
-- query to enrich a listing with seller-trust info collapse to a single read.
--
-- Two derived flags (is_published, is_sold) so consumers can drop the
-- `status === 'published'` / `status === 'sold'` filter scatter.
--
-- RLS: views inherit RLS from underlying tables. marketplace_listings + the
-- bridged marketplace_sellers both have RLS enabled with public-published
-- SELECT policies, so the view inherits the same coverage. No extra policy.

DROP VIEW IF EXISTS public.v_marketplace_listings_truth;

CREATE VIEW public.v_marketplace_listings_truth AS
SELECT
  l.id,
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
  -- Bridge to marketplace_sellers (canonical seller record). The listing
  -- row carries a denormalised snapshot (seller_verified, completed_sales,
  -- rating_avg) but the seller table is the live source of truth. Consumers
  -- can read either; the bridged fields are prefixed so the rename is safe.
  ms.tier            AS seller_tier,
  ms.kyb_verified    AS seller_kyb_verified,
  ms.total_sales     AS seller_total_sales,
  ms.rating_avg      AS seller_rating_avg_live,
  ms.rating_count    AS seller_rating_count,
  ms.response_rate   AS seller_response_rate,
  ms.response_time_h AS seller_response_time_h,
  -- Derived flags for status-based UI logic (drops the `.status === 'X'`
  -- scatter from 6 consumer pages).
  (l.status = 'published') AS is_published,
  (l.status = 'sold')      AS is_sold,
  (l.status = 'draft')     AS is_draft
FROM public.marketplace_listings l
LEFT JOIN public.marketplace_sellers ms ON ms.worker_name = l.seller_name;

GRANT SELECT ON public.v_marketplace_listings_truth TO anon, authenticated;

COMMENT ON VIEW public.v_marketplace_listings_truth IS
  'Canonical marketplace_listings reader. Supersets every consumer column + bridges to marketplace_sellers (tier, kyb_verified, total_sales, response_rate). Derived is_published/is_sold/is_draft flags drop status-string scatter.';

-- ─── Register in canonical_sources ───────────────────────────────────────────

INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES
  ('marketplace_listings_truth', 'view', 'v_marketplace_listings_truth', 'marketplace', 'realtime',
   'Canonical marketplace_listings reader. Per-listing granularity with seller-row bridge (tier, kyb_verified, total_sales, rating_avg_live, rating_count, response_rate, response_time_h) and derived is_published/is_sold/is_draft status flags.',
   jsonb_build_object(
     'key',             jsonb_build_array('id'),
     'hive_scoped',     true,
     'soft_delete',     false,
     'bridge_columns',  jsonb_build_array('seller_tier','seller_kyb_verified','seller_total_sales','seller_rating_avg_live','seller_rating_count','seller_response_rate','seller_response_time_h'),
     'derived_columns', jsonb_build_array('is_published','is_sold','is_draft')
   ),
   'Phase 2 of the TIER C gap-table sweep (2026-05-20). 10 raw reads across 7 consumers at baseline. Wrapper enables consumer migration in follow-up commits.')
ON CONFLICT (domain) DO UPDATE
  SET source_kind  = EXCLUDED.source_kind,
      source_name  = EXCLUDED.source_name,
      owner_skill  = EXCLUDED.owner_skill,
      freshness    = EXCLUDED.freshness,
      description  = EXCLUDED.description,
      contract     = EXCLUDED.contract,
      notes        = EXCLUDED.notes;
