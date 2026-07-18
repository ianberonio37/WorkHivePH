-- ============================================================================
-- Enable RLS + owner-scoped policies on marketplace_watchlist + marketplace_saved_searches
-- (deep-walk dim-2/dim-3, found 2026-07-07).
--
-- Both tables were RLS-OFF: the C8 marketplace RLS migration (20260706000001) enabled RLS on
-- the other 6 marketplace tables but MISSED these two. With RLS off, any holder of the public
-- publishable key (visible in page source) could, even unauthenticated, SELECT every user's
-- watchlist and saved searches -- and marketplace_saved_searches stores an `email` column, so
-- this leaked PII platform-wide, plus allowed insert/overwrite of anyone's rows.
--
-- Model: both are PRIVATE per-owner. Owner = worker_name; auth_worker_names() (defined in the
-- C8 migration) maps auth.uid() -> the caller's worker_name(s). No public read, no cross-user,
-- no admin (personal preference data, not moderation surface). Notification digests read
-- saved_searches as service_role, which bypasses RLS. Anon (auth.uid() null) sees 0 rows.
-- ============================================================================

ALTER TABLE public.marketplace_watchlist ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS mkt_watchlist_owner_rw ON public.marketplace_watchlist;
CREATE POLICY mkt_watchlist_owner_rw ON public.marketplace_watchlist
  FOR ALL
  USING      (worker_name IN (SELECT public.auth_worker_names()))
  WITH CHECK (worker_name IN (SELECT public.auth_worker_names()));

ALTER TABLE public.marketplace_saved_searches ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS mkt_saved_searches_owner_rw ON public.marketplace_saved_searches;
CREATE POLICY mkt_saved_searches_owner_rw ON public.marketplace_saved_searches
  FOR ALL
  USING      (worker_name IN (SELECT public.auth_worker_names()))
  WITH CHECK (worker_name IN (SELECT public.auth_worker_names()));
