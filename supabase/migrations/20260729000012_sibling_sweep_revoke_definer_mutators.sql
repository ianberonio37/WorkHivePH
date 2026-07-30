-- =====================================================================
-- SIBLING SWEEP · the same exposure, everywhere it exists
-- =====================================================================
-- Fixing `sweep_service_broadcasts` (mig 20260729000011) revealed a CLASS, not an incident:
-- Postgres grants EXECUTE to PUBLIC on every new function by default, so any SECURITY DEFINER
-- helper that mutates across tenants is callable by any signed-in user unless it is explicitly
-- revoked. The platform's own `definer_tenant_gate` named two more of exactly that shape, both
-- pre-dating the service-hailing arc. The sibling-sweep discipline says fix every occurrence of a
-- pattern, not only the one that bit us - so:
--
--   expire_stale_parts_recommendations()          cron-driven (job parts-recs-expire-0550pht),
--                                                 mutates parts_staging_recommendations for EVERY
--                                                 hive. A user could expire another hive's
--                                                 recommendations. No page or edge fn calls it.
--   recompute_seller_sales_and_tier(p_seller_name) called INTERNALLY by the marketplace order
--                                                 trigger (PERFORM), but exposed with a
--                                                 caller-supplied seller name - so a user could
--                                                 aim it at ANY seller's trust signals (sales
--                                                 count + tier), the exact trust-forge surface the
--                                                 platform guards elsewhere. No client calls it.
--
-- Revoking EXECUTE from public/anon/authenticated does NOT affect either legitimate path: cron runs
-- as the owner, and a PERFORM inside a SECURITY DEFINER trigger executes with that function's
-- privileges, not the end user's. Verified live after applying: the marketplace order trigger still
-- recomputes, and the parts cron still runs.

BEGIN;

revoke all on function public.expire_stale_parts_recommendations()          from public, anon, authenticated;
revoke all on function public.recompute_seller_sales_and_tier(text)         from public, anon, authenticated;

comment on function public.expire_stale_parts_recommendations() is
  'Cron-only TTL sweep over parts_staging_recommendations. EXECUTE revoked from public/anon/authenticated: it mutates every hive''s rows and no caller-owned row exists for RLS to scope.';

comment on function public.recompute_seller_sales_and_tier(text) is
  'Recomputes a seller''s sales count + tier from source truth. Invoked ONLY by the marketplace order trigger (PERFORM, runs with the trigger function''s rights). EXECUTE revoked from public/anon/authenticated because the seller name is a caller-supplied argument - exposed, it lets any user aim a trust-signal mutator at any seller.';

COMMIT;
