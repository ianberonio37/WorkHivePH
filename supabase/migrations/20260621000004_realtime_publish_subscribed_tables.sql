-- Arc J — fix silently-dead realtime feeds: tables SUBSCRIBED via postgres_changes that were
-- never actually in the supabase_realtime publication.
--
-- FINDING (2026-06-21): 8 tables are subscribed in HTML (hive.html, asset-hub.html, community.html,
-- inventory.html, pm-scheduler.html, marketplace.html) via `.on('postgres_changes', { table: ... })`
-- but were absent from the live publication → those live feeds received NO events (the page loads its
-- initial query, then never updates live). `validate_realtime_publication.py` missed it because it
-- checks a hardcoded EXPECTED_PUBLISHED_TABLES allowlist (which lists them) instead of the LIVE
-- publication — the allowlist's "Added to publication on <date>" comments were aspirational; no
-- migration ever performed the ADD (they were set via the dashboard in prod and lost on local reset).
--
-- This migration makes the publication membership MIGRATION-TRACKED (reproducible across resets) for the
-- 7 tables that are RLS-enabled + hive-scoped with no permissive bypass (verified safe: an anon read
-- returns 0; the realtime subscription-isolation gate keeps them locked). REPLICA IDENTITY FULL so a
-- DELETE event carries the full old row (incl. hive_id) — required for the client `filter=hive_id=eq.X`
-- to match on DELETE and for the DELETE handlers (payload.old) to work.
--
-- EXCLUDED: marketplace_listings — it is RLS-OFF (public storefront). Publishing an RLS-off table
-- streams every row to any anon subscriber; that may be acceptable-by-design for a public marketplace,
-- but it needs its own RLS decision first (publish + by-design exemption, OR enable RLS). Tracked, not
-- bundled into this safe migration.
--
-- Idempotent: ADD TABLE errors if the table is already a member, so guard each with a DO block.

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'automation_log', 'community_posts', 'community_reactions', 'community_replies',
    'inventory_items', 'logbook', 'pm_completions'
  ] LOOP
    IF NOT EXISTS (
      SELECT 1 FROM pg_publication_tables
      WHERE pubname = 'supabase_realtime' AND schemaname = 'public' AND tablename = t
    ) THEN
      EXECUTE format('ALTER PUBLICATION supabase_realtime ADD TABLE public.%I', t);
    END IF;
    EXECUTE format('ALTER TABLE public.%I REPLICA IDENTITY FULL', t);
  END LOOP;
END $$;
