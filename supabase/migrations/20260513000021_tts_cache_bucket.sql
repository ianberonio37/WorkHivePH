-- TTS Cache Bucket (Phase 7 of the Persona Contract)
--
-- Stores MP3 files keyed by SHA-256 hash of (text + voice_id) so repeat
-- queries for the same narration are served from cache for $0 — no extra
-- Azure Speech free-tier characters consumed.
--
-- Bucket policy:
--   - PUBLIC read (signed URLs work without auth, audio plays from <audio> tag)
--   - service-role write (only tts-speak edge fn writes; client can't pollute the cache)
--
-- See: WORKHIVE_PERSONA_CONTRACT.md

BEGIN;

-- Create the bucket if it doesn't exist
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES ('tts-cache', 'tts-cache', true, 524288, ARRAY['audio/mpeg', 'audio/mp3'])
ON CONFLICT (id) DO NOTHING;

-- Read access for anonymous (public bucket so signed URLs aren't needed)
DROP POLICY IF EXISTS tts_cache_public_read ON storage.objects;
CREATE POLICY tts_cache_public_read
  ON storage.objects FOR SELECT
  USING (bucket_id = 'tts-cache');

-- Only service-role (= the tts-speak edge fn) may write
DROP POLICY IF EXISTS tts_cache_service_role_write ON storage.objects;
CREATE POLICY tts_cache_service_role_write
  ON storage.objects FOR INSERT
  WITH CHECK (bucket_id = 'tts-cache' AND auth.role() = 'service_role');

COMMIT;
