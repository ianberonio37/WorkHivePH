-- ─── v_marketplace_orders_truth canonical view ──────────────────────────────
-- Turn 4 of the canonical-drift flywheel. 5 raw reads at baseline.
-- Bridges to marketplace_listings for title + section, and derives status
-- flags (is_escrow / is_released / is_pending / is_disputed / is_refunded)
-- so consumers can drop the status-string scatter that all 5 consumers
-- currently reimplement.

DROP VIEW IF EXISTS public.v_marketplace_orders_truth;

CREATE VIEW public.v_marketplace_orders_truth AS
SELECT
  o.id,
  o.listing_id,
  o.hive_id,
  o.buyer_name,
  o.seller_name,
  o.price,
  o.currency,
  o.stripe_session_id,
  o.stripe_payment_id,
  o.stripe_transfer_id,
  o.status,
  o.escrow_release_at,
  o.buyer_confirmed_at,
  o.released_at,
  o.created_at,
  o.updated_at,
  -- Bridge to marketplace_listings
  l.title    AS listing_title,
  l.section  AS listing_section,
  l.image_url AS listing_image_url,
  -- Derived status flags
  (o.status = 'pending_payment') AS is_pending_payment,
  (o.status = 'escrow_hold')     AS is_escrow,
  (o.status = 'buyer_confirmed') AS is_buyer_confirmed,
  (o.status = 'released')        AS is_released,
  (o.status = 'refunded')        AS is_refunded,
  (o.status = 'disputed')        AS is_disputed,
  -- Derived: is the escrow window approaching release?
  CASE WHEN o.escrow_release_at IS NOT NULL
       THEN GREATEST(0, EXTRACT(EPOCH FROM (o.escrow_release_at - now()))/86400.0)::int
       ELSE NULL
  END AS days_until_escrow_release
FROM public.marketplace_orders o
LEFT JOIN public.marketplace_listings l ON l.id = o.listing_id;

GRANT SELECT ON public.v_marketplace_orders_truth TO anon, authenticated;

COMMENT ON VIEW public.v_marketplace_orders_truth IS
  'Canonical marketplace_orders reader. Listing bridge (title/section/image_url) + 6 derived status flags + days_until_escrow_release.';

INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES
  ('marketplace_orders_truth', 'view', 'v_marketplace_orders_truth', 'marketplace', 'realtime',
   'Canonical marketplace_orders reader. Per-order granularity with listing bridge and derived status flags + days_until_escrow_release.',
   jsonb_build_object(
     'key',             jsonb_build_array('id'),
     'hive_scoped',     true,
     'soft_delete',     false,
     'bridge_columns',  jsonb_build_array('listing_title','listing_section','listing_image_url'),
     'derived_columns', jsonb_build_array('is_pending_payment','is_escrow','is_buyer_confirmed','is_released','is_refunded','is_disputed','days_until_escrow_release')
   ),
   'Turn 4 of TIER C gap-table sweep (2026-05-20). 5 raw reads at baseline.')
ON CONFLICT (domain) DO UPDATE
  SET source_kind = EXCLUDED.source_kind, source_name = EXCLUDED.source_name,
      owner_skill = EXCLUDED.owner_skill, freshness = EXCLUDED.freshness,
      description = EXCLUDED.description, contract = EXCLUDED.contract,
      notes       = EXCLUDED.notes;
