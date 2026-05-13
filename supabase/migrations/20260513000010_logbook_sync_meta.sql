-- Add logbook.sync_meta JSONB column.
--
-- Discovered during the 2026-05-13 walkthrough: compute_hive_readiness()
-- queries logbook.sync_meta to count offline-queued writes as part of the
-- infrastructure_resilience_score. The column was assumed to exist when
-- the Phase 0 RPC was authored but never actually shipped.
--
-- Add as JSONB with DEFAULT '{}' so existing rows get a sane value and the
-- RPC's `(sync_meta->>'offline_queued')::boolean` reads NULL/false cleanly.
-- Offline queue writers (logbook.html, offline-queue.js) can populate
-- {"offline_queued": true} when draining their queue post-brownout.

BEGIN;

ALTER TABLE public.logbook
  ADD COLUMN IF NOT EXISTS sync_meta jsonb NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN public.logbook.sync_meta IS
  'Phase 0/2 — write provenance metadata. Offline-queue drain writes {"offline_queued": true} so compute_hive_readiness can count infra-resilience evidence. Open shape so future fields (e.g. queued_at, retry_count) extend without migration.';

COMMIT;
