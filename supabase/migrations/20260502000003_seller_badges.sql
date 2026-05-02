-- Multi-tier seller verification badges (Phase B4)
-- Existing kyb_verified column repurposed as the "Identity Verified" badge
-- (no schema change needed — only the user-facing label).
-- New columns track Certified badge (admin reviews seller-listed certs).
-- Quick Reply + Top Rated badges are computed client-side from existing
-- marketplace_inquiries (response time) and marketplace_reviews (rating) data.

ALTER TABLE public.marketplace_sellers
  ADD COLUMN IF NOT EXISTS certifications     text,         -- newline-separated cert names
  ADD COLUMN IF NOT EXISTS cert_verified      boolean       NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS cert_verified_at   timestamptz;

GRANT UPDATE (certifications, cert_verified, cert_verified_at, updated_at)
  ON public.marketplace_sellers TO authenticated;
