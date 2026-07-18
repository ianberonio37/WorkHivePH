-- ============================================================================
-- Enable RLS + owner-scoped read on achievement_xp_log (deep-walk dim-2/3, found 2026-07-07).
--
-- The table was RLS-OFF: a policy `ach_log_read USING(true)` existed but ROW LEVEL SECURITY was
-- never ENABLED, so it was inert -> any authed/anon key holder could read EVERY worker's XP
-- history AND write/tamper XP (which feeds worker_achievements + the leaderboard). Found via a
-- sweep for worker_name-scoped tables with RLS off (the same blind spot that hid
-- marketplace_watchlist / marketplace_saved_searches).
--
-- Access model: the client only ever reads its OWN log (achievements.html:985 filters
-- .eq('worker_name', WORKER_NAME)); XP is AWARDED server-side (no client insert/RPC exists in
-- *.html/*.js), which runs as service_role and bypasses RLS. So: enable RLS, scope read to the
-- owner (auth_worker_names() maps auth.uid() -> the caller's worker_name(s)), and add NO client
-- write policy -> client XP writes stay blocked (no tampering), server-role awarding is unaffected.
-- ============================================================================

ALTER TABLE public.achievement_xp_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ach_log_read ON public.achievement_xp_log;
DROP POLICY IF EXISTS ach_log_owner_read ON public.achievement_xp_log;
CREATE POLICY ach_log_owner_read ON public.achievement_xp_log
  FOR SELECT
  USING (worker_name IN (SELECT public.auth_worker_names()));
