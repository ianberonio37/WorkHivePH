-- ============================================================================
-- Marketplace listing-image storage lockdown (Marketplace PDDA, I-axis)
-- ----------------------------------------------------------------------------
-- HOLE (confirmed 2026-07-11): the 'marketplace-listings' storage bucket had
--   "Anon delete marketplace-listings"  DELETE USING (bucket_id = 'marketplace-listings')
--   "Anon upload marketplace-listings"  INSERT WITH CHECK (bucket_id = 'marketplace-listings')
-- i.e. NO owner/identity restriction. Anyone (even logged-out) could DELETE ANY seller's
-- listing photo (vandalism/defacement) or upload arbitrary objects (storage flooding).
--
-- FIX: DELETE restricted to the object OWNER (the uploader's auth.uid()) or a platform admin.
-- INSERT restricted to authenticated users (the post flow always runs as an authed seller).
-- Public SELECT (read) stays — listing images are public, like the listings themselves.
-- ============================================================================

DROP POLICY IF EXISTS "Anon delete marketplace-listings" ON storage.objects;
CREATE POLICY "Owner or admin delete marketplace-listings"
  ON storage.objects FOR DELETE
  USING (
    bucket_id = 'marketplace-listings'
    AND (owner = auth.uid() OR public.is_marketplace_admin())
  );

DROP POLICY IF EXISTS "Anon upload marketplace-listings" ON storage.objects;
CREATE POLICY "Authed upload marketplace-listings"
  ON storage.objects FOR INSERT
  WITH CHECK (
    bucket_id = 'marketplace-listings'
    AND auth.uid() IS NOT NULL
  );
