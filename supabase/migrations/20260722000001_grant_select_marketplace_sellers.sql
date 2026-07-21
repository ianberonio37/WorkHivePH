-- 20260722000001_grant_select_marketplace_sellers.sql
-- ============================================================================
-- FIX: a seller cannot save their OWN messenger handle / certifications.
-- Found 2026-07-22 by the Arc-K MS3 live journey: marketplace-seller.html's
--   db.from('marketplace_sellers').upsert({...}, { onConflict: 'worker_name' })
-- returned 42501 "permission denied for table marketplace_sellers".
--
-- ROOT CAUSE: the `authenticated` role held INSERT/UPDATE/DELETE on
-- public.marketplace_sellers but NOT SELECT. An upsert (INSERT … ON CONFLICT
-- DO UPDATE) must READ the conflict target, and PostgREST adds `RETURNING`, so
-- the write needs table SELECT — without it Postgres raises 42501 at the GRANT
-- layer, BEFORE RLS is even consulted. This was masked because the page READS
-- the seller via the `v_marketplace_sellers_truth` view, so the missing base
-- SELECT never surfaced on the read path. The RLS policy `mkt_sellers_read`
-- (USING auth.uid() IS NOT NULL) already exists and is DEAD without this grant —
-- proof SELECT was intended. Sibling tables (marketplace_listings) grant SELECT.
--
-- FIX: grant the SELECT the read policy was written for. RLS still scopes rows;
-- this only restores the table-level privilege the RLS layer sits on top of.
-- ============================================================================

GRANT SELECT ON public.marketplace_sellers TO authenticated;

-- (anon already reads public seller profiles via the truth view / RLS; grant
--  parity is intentionally NOT extended here — only the authenticated write path
--  was broken. If anon base-table reads are ever needed, add them explicitly.)
