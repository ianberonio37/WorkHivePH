-- Marketplace listing image storage
-- Public bucket so listing images are accessible from any browser without auth.
-- Anon writes are allowed because WorkHive uses string identity (no Supabase Auth yet).
-- See project_rls_decision memory: RLS deferred until Auth migration.
-- Spam control: 5 MB file size limit + allowed MIME types only + admin can delete.

-- =============================================
-- 1. Bucket
-- =============================================
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'marketplace-listings',
  'marketplace-listings',
  true,
  5242880,  -- 5 MB
  ARRAY['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
)
ON CONFLICT (id) DO UPDATE SET
  public             = EXCLUDED.public,
  file_size_limit    = EXCLUDED.file_size_limit,
  allowed_mime_types = EXCLUDED.allowed_mime_types;

-- =============================================
-- 2. RLS policies on storage.objects (scoped to this bucket)
-- =============================================

-- Public read so listing images render for everyone (signed-in or not)
DROP POLICY IF EXISTS "Public read marketplace-listings" ON storage.objects;
CREATE POLICY "Public read marketplace-listings"
  ON storage.objects FOR SELECT
  USING (bucket_id = 'marketplace-listings');

-- Anon insert (matches the rest of the WorkHive string-identity model)
DROP POLICY IF EXISTS "Anon upload marketplace-listings" ON storage.objects;
CREATE POLICY "Anon upload marketplace-listings"
  ON storage.objects FOR INSERT
  WITH CHECK (bucket_id = 'marketplace-listings');

-- Anon delete (sellers replacing images, admins cleaning up rejected listings)
-- Tighten to owner-only when Supabase Auth migration completes
DROP POLICY IF EXISTS "Anon delete marketplace-listings" ON storage.objects;
CREATE POLICY "Anon delete marketplace-listings"
  ON storage.objects FOR DELETE
  USING (bucket_id = 'marketplace-listings');
