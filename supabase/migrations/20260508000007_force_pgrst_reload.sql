-- Force PostgREST to fully reload schema cache by adding a trivial column
-- comment. NOTIFY alone wasn't enough — the Supabase API gateway holds the
-- old schema where worker_achievements + achievement_xp_log appear blocked
-- to anon despite RLS being disabled.

COMMENT ON TABLE worker_achievements IS 'Per-worker achievement progress. Public read via direct SELECT (no RLS). Writes via SECURITY DEFINER triggers only.';
COMMENT ON TABLE achievement_xp_log  IS 'Append-only XP audit log. Public read. Writes via SECURITY DEFINER triggers only.';

-- Re-grant explicitly (no-op if already granted but ensures clarity)
GRANT SELECT ON worker_achievements TO anon, authenticated;
GRANT SELECT ON achievement_xp_log  TO anon, authenticated;

-- Reload PostgREST
NOTIFY pgrst, 'reload schema';
NOTIFY pgrst, 'reload config';
