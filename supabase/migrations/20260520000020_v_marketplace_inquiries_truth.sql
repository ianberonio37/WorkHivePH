-- ─── v_marketplace_inquiries_truth canonical view ──────────────────────────
-- TIER C gap-table promotion #4: marketplace_inquiries had 5+ raw reads
-- across marketplace-seller, marketplace-seller-profile, marketplace-admin
-- consumers + multiple internal SELECTs on the seller dashboard.
--
-- Superset of every reader's column set + bridges listing title (so the
-- inline `marketplace_listings(title)` PostgREST relationship selects can
-- drop). Derived flags (is_pending, is_replied, is_closed) replace the
-- `.eq('status', 'pending')` scatter on 4 consumer pages.

DROP VIEW IF EXISTS public.v_marketplace_inquiries_truth;

CREATE VIEW public.v_marketplace_inquiries_truth AS
SELECT
  i.id,
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
  -- Bridge to marketplace_listings (canonical title for the inquiry row)
  l.title    AS listing_title,
  l.section  AS listing_section,
  l.price    AS listing_price,
  l.status   AS listing_status,
  -- Derived flags drop the .eq('status', 'X') scatter
  (i.status = 'pending') AS is_pending,
  (i.status = 'replied') AS is_replied,
  (i.status = 'closed')  AS is_closed
FROM public.marketplace_inquiries i
LEFT JOIN public.marketplace_listings l ON l.id = i.listing_id;

GRANT SELECT ON public.v_marketplace_inquiries_truth TO anon, authenticated;

COMMENT ON VIEW public.v_marketplace_inquiries_truth IS
  'Canonical marketplace_inquiries reader. Per-inquiry granularity + marketplace_listings bridge (title/section/price/status) + derived is_pending/is_replied/is_closed flags.';

INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES
  ('marketplace_inquiries_truth', 'view', 'v_marketplace_inquiries_truth', 'marketplace', 'realtime',
   'Canonical marketplace_inquiries reader. Per-inquiry granularity with listing bridge (title, section, price, status) and derived is_pending/is_replied/is_closed flags.',
   jsonb_build_object(
     'key',             jsonb_build_array('id'),
     'hive_scoped',     true,
     'soft_delete',     false,
     'bridge_columns',  jsonb_build_array('listing_title','listing_section','listing_price','listing_status'),
     'derived_columns', jsonb_build_array('is_pending','is_replied','is_closed')
   ),
   'Phase 3 of the TIER C gap-table sweep (2026-05-20). 5+ raw reads at baseline.')
ON CONFLICT (domain) DO UPDATE
  SET source_kind = EXCLUDED.source_kind,
      source_name = EXCLUDED.source_name,
      owner_skill = EXCLUDED.owner_skill,
      freshness   = EXCLUDED.freshness,
      description = EXCLUDED.description,
      contract    = EXCLUDED.contract,
      notes       = EXCLUDED.notes;
