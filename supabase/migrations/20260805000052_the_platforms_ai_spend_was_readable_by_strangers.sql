-- ═══════════════════════════════════════════════════════════════════════════════════════════════
-- THE PLATFORM'S AI SPEND AND LOAD-SHEDDING WAS READABLE BY STRANGERS
--
-- Continuing the grant_matches_policy sweep that found the voice queue (mig 50). Fourteen tables in
-- public are readable with RLS disabled. Thirteen turned out to be genuine reference or aggregate
-- data once every column was read — a term dictionary, UI field templates, industry MTBF benchmarks
-- (sample_hives is a COUNT, not a list of hives), the assistant's knowledge corpus, and one empty
-- shell table carrying nothing but id and created_at.
--
-- ai_global_budget is not reference data. It is live operational metering:
--
--     minute_count · day_count · shed_count_today · deny_count_today
--     depth_samples_today · depth_sum_today · max_depth_today
--
-- That is how much AI the platform is burning right now, and how often it is shedding load or
-- denying requests. An anonymous visitor could read all of it. It leaks no user's data, so this is
-- not the voice queue — but it is the platform's operating posture published to anyone who asks,
-- and nothing needs it: the only reader in the entire codebase is supabase/functions/_shared/
-- rate-limit.ts, which runs under the service role and bypasses RLS anyway.
--
-- Verified before revoking: no page, no client script, no test reads this table.
-- ═══════════════════════════════════════════════════════════════════════════════════════════════

revoke select on public.ai_global_budget from anon;
revoke select on public.ai_global_budget from authenticated;

comment on table public.ai_global_budget is
  'Platform-wide AI rate/spend counters. Written and read ONLY by the service role (see '
  '_shared/rate-limit.ts). Not readable by anon or authenticated since mig 52 (2026-08-05) — it was '
  'world-readable before that, exposing shed/deny rates to anyone.';
