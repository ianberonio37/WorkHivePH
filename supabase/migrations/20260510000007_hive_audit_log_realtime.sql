-- ─── hive_audit_log realtime publication ────────────────────────────────────
--
-- audit-log.html (supervisor viewer, 2026-05-10) subscribes to INSERT events
-- on hive_audit_log so new approve/reject/kick/join entries surface live in
-- the supervisor's feed without a manual refresh.
--
-- Without this ALTER, the .channel('postgres_changes') subscription opens
-- silently and never fires — the page would still work via the 60s reload,
-- but supervisors lose the "live" feel and the validate_realtime_publication
-- gate FAILs (subscribed table not in publication).
--
-- The hive_audit_log table is hive-scoped via its hive_id column; the
-- audit-log.html subscription includes filter='hive_id=eq.<HIVE_ID>' so
-- one hive's supervisors never see another hive's events even though the
-- publication is unfiltered at the DB level.
--
-- Re-running this migration is safe — the DO block checks pg_publication_tables
-- before issuing ALTER PUBLICATION (idempotent).

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime'
      AND schemaname = 'public'
      AND tablename = 'hive_audit_log'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.hive_audit_log;
  END IF;
END $$;
