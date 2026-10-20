-- BRH-R (2026-10-21): v_service_provider_leaderboard runs as the person reading it.
--
-- Supabase's advisor (security_definer_view, ERROR, emailed 2026-10-20) named five views that read their base tables with
-- their OWNER's rights, so the reader's own row policies never apply. Compared through the API, row by row, as a visitor,
-- a provider (Bryan Garcia) and a client (David Velasco): the leaderboard returns identical rows as invoker for every
-- signed-in reader (a visitor is refused either way), so it simply runs as its reader now.
--
-- The other four: v_marketplace_listings_public runs as its reader too, in 20261021000006, which must follow
-- 20261020000003 (that migration redefines the view, and would put its owner rights back); the sellers, job-tracking and
-- open-broadcast views keep their owner rights inside functions (20261015990000), each for a measured reason given there.

alter view public.v_service_provider_leaderboard set (security_invoker = true);
