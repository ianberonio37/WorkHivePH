-- =====================================================================
-- SECURITY FIX · a cron sweep must not be callable by a signed-in user
-- =====================================================================
-- Found 2026-07-29 by the full-mode `definer_tenant_gate` (which --fast never runs), then PROVEN
-- exploitable: a freshly-minted authenticated user with NO relationship to any hail called
-- `public.sweep_service_broadcasts()` and it RAN, returning {"expired":0,"stamped":0,"widened":0}.
--
-- WHY THAT MATTERS. The sweep is SECURITY DEFINER and mutates `service_requests` for EVERY tenant:
-- it stamps shelf lives, doubles the broadcast radius, and expires un-accepted hails. Exposed to
-- `authenticated`, any signed-in account could fire it repeatedly to age other people's hails out
-- of their TTL window - forcing expiry of jobs they have nothing to do with. There is no row the
-- caller owns here, so no RLS predicate saves it; the ONLY correct control is that a user cannot
-- call it at all. Postgres grants EXECUTE to PUBLIC on every new function by default, so a cron
-- helper is exposed unless it is explicitly revoked - which is exactly what happened: the later
-- sweep (sweep_pm_auto_hail) carried its REVOKE, this earlier one did not.
--
-- The cron job runs as the table owner, so revoking from PUBLIC/anon/authenticated does not affect
-- the schedule.
--
-- The two TRIGGER functions are revoked for the same hygiene reason: they are only ever invoked by
-- the trigger machinery, never by a client, and a directly-callable trigger function is a needless
-- surface (it runs with owner rights and hand-crafted NEW records are a known abuse shape).

BEGIN;

revoke all on function public.sweep_service_broadcasts()      from public, anon, authenticated;
revoke all on function public.land_accepted_job_on_dayplan()  from public, anon, authenticated;
revoke all on function public.guard_service_review()          from public, anon, authenticated;

comment on function public.sweep_service_broadcasts() is
  'Per-minute TTL/radius sweep over service_requests. CRON ONLY - EXECUTE is revoked from public/anon/authenticated because it mutates every tenant''s hails and no caller-owned row exists for RLS to scope. Proven exploitable before this revoke: a random authenticated user could run it and age other people''s broadcasts out of their TTL window.';

COMMIT;
