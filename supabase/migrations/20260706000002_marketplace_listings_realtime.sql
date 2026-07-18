-- ============================================================================
-- Add marketplace_listings to the supabase_realtime publication.
--
-- Deep-walk dim-11 (2026-07-06): the marketplace feed subscribes to
-- postgres_changes on public.marketplace_listings to live-prepend a "New listing
-- just posted!" card. But the table was NEVER a member of the supabase_realtime
-- publication, so Postgres emitted no WAL events for it and the listener received
-- nothing — the live feed was dead at the source (independent of, and in addition
-- to, the malformed compound client filter fixed in marketplace.html:startRealtime).
--
-- Published listings are public-read (see 20260706000001_marketplace_rls.sql), so
-- broadcasting INSERTs of published rows to subscribers matches the RLS model.
-- Idempotent: only ADD if not already a member (safe to re-run / re-apply).
-- INSERT events carry the full new row under default REPLICA IDENTITY, so no
-- replica-identity change is needed for this INSERT-only listener.
-- ============================================================================
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime'
      AND schemaname = 'public'
      AND tablename = 'marketplace_listings'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.marketplace_listings;
  END IF;
END $$;
