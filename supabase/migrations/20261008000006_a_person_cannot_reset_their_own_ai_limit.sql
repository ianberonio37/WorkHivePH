-- ★A LIMIT THE PERSON IT LIMITS COULD RESET (2026-10-08, found proving the hive-less limiter as `authenticated`).
-- A person with no hive is now limited on their own ai_user_rate_limits bucket (marketplace-listing-assist,
-- ai-orchestrator and analytics-orchestrator joined the solo functions there the same day). That bucket's policy,
-- ai_user_rate_limits_own (20260620000004), was written "a user may read their own rate-limit row; the edge writes via
-- service_role bypass" - but it was created FOR ALL, and anon/authenticated held INSERT/UPDATE/DELETE on the table.
-- So any signed-in person could PATCH /rest/v1/ai_user_rate_limits?user_id=eq.<self> {call_count:0, day_count:0}, or
-- DELETE the row, and start a fresh allowance whenever they liked: a per-person limit enforced on the person's honour.
--
-- The edge writes this table only as service_role (BYPASSRLS), so the person needs exactly what the comment said:
-- READ their own row. The policy becomes SELECT-only and the write privileges go (a policy is not consulted for a
-- privilege the role does not hold, and TRUNCATE never consults RLS at all - it was not granted and is revoked here
-- for the record). The three hive-keyed limiter tables already refuse every client write by policy (USING false /
-- WITH CHECK false) but still carried the same write GRANTs; they are revoked too, so no future policy edit can
-- reopen a door the grant left standing. SELECT stays where policies allow it (members read their hive's route
-- counters; grafana_reader reads all). Forward-only and idempotent.

drop policy if exists ai_user_rate_limits_own on public.ai_user_rate_limits;
create policy ai_user_rate_limits_own on public.ai_user_rate_limits
  for select
  using (auth.uid() is not null and user_id = auth.uid()::text);

revoke insert, update, delete, truncate on public.ai_user_rate_limits from anon, authenticated;
revoke insert, update, delete, truncate on public.ai_rate_limits      from anon, authenticated;
revoke insert, update, delete, truncate on public.hive_route_calls    from anon, authenticated;
revoke insert, update, delete, truncate on public.hive_route_quotas   from anon, authenticated;

comment on policy ai_user_rate_limits_own on public.ai_user_rate_limits is
  'A signed-in person may READ their own AI rate-limit bucket. Only the edge (service_role) writes it: a limit the '
  'person could update or delete would be no limit (2026-10-08).';
